"""codex 原生 goal 模式的 harbor agent。

与基线 `CodexOffline` 的**唯一差别**是不用 `codex exec`，改用
app-server + `thread/goal/set`。其余一切沿用：同一个离线二进制安装、同样的
provider/auth 配置、同样的 harbor trial 流程、同样的 verifier 调用。

## 为什么必须做成 agent 类而不是脚本

打分要公平，就得走 harbor 原路：同样的 trial 目录结构、同样的
`continue_until_timeout` 语义、同样的中途/最终 verifier 调用、同样的
`result.json`。脚本跑出来的东西和基线不可比。

## 为什么不能用 environment.exec

app-server 要持久双向 stdio，而 harbor 的 exec 把 stdin 设成 DEVNULL
（`docker.py` 里 `stdin=asyncio.subprocess.DEVNULL`）。agent 类本身跑在宿主机，
所以自己 `docker exec -i` 拿管道，codex 仍然跑在容器内——文件系统语义才对。

## goal 臂相对基线恰好多出三样（不多不少）

  1. 每轮注入的 5338 字符 `<goal_context>`
  2. `update_goal` 工具
  3. codex 的自动续跑调度

用法（config.yaml）：
    agents:
      - import_path: codex_goal_agent:CodexGoalAgent
        model_name: openai/gpt-5.5
        override_timeout_sec: 5400
        kwargs:
          reasoning_effort: medium
"""

import asyncio
import json
import os
import time
import shlex
import subprocess
from pathlib import Path

from harbor.agents.installed.codex import EnvironmentPaths
from harbor.environments.base import BaseEnvironment

from codex_offline import CodexOffline

# 宿主侧直接用已安装的官方 toolkit，不再 vendored 复制一份（容器侧另从官方包路径
# 拷同一文件进容器，见 goal_codex.py，两处都对着官方 owner，避免协议漂移与重复代码）。
from loopx.capabilities.benchmark_toolkit.native_codex_goal import (
    NativeGoalConfig,
    NativeGoalProtocolError,
    StdioNativeGoalTransport,
    compact_native_goal_receipt,
    refresh_native_goal_status,
    start_native_goal_turn,
    wait_native_goal_turn,
)

# objective 用 LoopX 自己的写法（测试夹具与 CLI 测试路径都是这句）。
#
# 极简通用、不含任务内容，三条理由：
#   1. codex 对 objective 有 4000 字符硬上限，46 个任务里 28 个指令超限，
#      而且超限的恰好是长程硬任务。完整指令走 turn 输入（不受限），一字不删。
#   2. 逐任务撰写验收标准 = 给 goal 臂一条基线没有的信息通道，
#      测出来的会是"写标准的水平"而不是 goal 机制的价值。
#   3. objective 的内容正是 LoopX treatment 臂的变量，基线臂先占了就没得比。
_OBJECTIVE = "Finish the task."

# goal 的单次时限。harbor 的 agent 基类**没有** _timeout_sec，agent 拿不到自己
# 的预算，超时是 trial 从外面掐的。所以这里只能给一个略小于 override_timeout_sec
# (5400) 的值，让内部循环自己抛超时、走到 finally 落 receipt，而不是被外部
# cancel 掉丢证据。
#
# 可用 GOAL_TIMEOUT_SEC 覆盖——冒烟测试要在几分钟内触发超时路径（那条路径正是
# 之前丢掉 20/27 份 receipt 的地方），不能等 90 分钟。
#
# 注意 continue_until_timeout 会多次调 run()，后续阶段的剩余时间递减，这个常量
# 会大于剩余量——那时仍会被外部掐断，靠 CancelledError 分支兜住。
_GOAL_TIMEOUT_SEC = float(os.environ.get("GOAL_TIMEOUT_SEC") or 5340.0)

# app-server 读 config.toml，`-c` 那套是给 `codex exec` 的，所以基线用 CLI flag
# 传的东西这里必须写进文件。内容与基线逐字对应：
#   web_search="disabled"        基线 build_cli_flags() 里加的
#   retries 三件套               基线 _RETRY_FLAGS
# 注意**不写** features.goals——goal 臂就是要它开着。
#
# 【踩过的坑】不能像上游那样分两次 `cat >>` 追加。TOML 里 table 头之后的裸键
# 都归该 table，所以第二段开头的 `web_search = "disabled"` 会变成
# `model_providers.harbor.web_search`；而再写一次 `[model_providers.harbor]`
# 是重复声明，直接解析失败。表现是每个 trial 都秒挂在
# `app_server_request_failed:thread/start`。所以整份文件一次性写出，自己控制顺序。
_CONFIG_TOML = """\
web_search = "disabled"
# 关掉 codex 的**内层**沙箱。容器本身就是隔离边界，再套一层 bubblewrap 只会
# 在启动时报
#   Codex's Linux sandbox uses bubblewrap and needs access to create user namespaces.
# 并让 app-server 的 initialize 握手失败（app_server_request_failed:initialize）。
# 宿主机 kernel.unprivileged_userns_clone=1，是容器内的 seccomp/apparmor 挡住了
# user namespace —— 装上 bwrap 二进制并不等于它能用。
#
# 这与基线臂的 `codex exec --dangerously-bypass-approvals-and-sandbox` 等价：
# 两臂都把隔离交给容器，工具面一致。
sandbox_mode = "danger-full-access"
# 把任务目录标成受信项目，否则 app-server 启动就报
#   Project-local config, hooks, and exec policies are disabled ... /app/.codex
projects."/app" = { trust_level = "trusted" }
model_provider = "harbor"
[model_providers.harbor]
name = "harbor"
base_url = "${OPENAI_BASE_URL}"
wire_api = "%(wire_api)s"
env_key = "OPENAI_API_KEY"
request_max_retries = 8
stream_max_retries = 8
stream_idle_timeout_ms = 300000
"""


class CodexGoalAgent(CodexOffline):
    # 驱动中的 turn，异常路径也要能落进 receipt（见 _drive 的说明）
    _turn = None

    @staticmethod
    def name() -> str:
        return "codex-goal"

    # ── 容器定位 ──────────────────────────────────────────────────────────
    def _container_id(self, environment: BaseEnvironment) -> str:
        """拿到本 trial 的容器 ID。

        harbor 用 docker compose 起容器，project name 是 session_id 消毒后的值、
        服务名固定 `main`。按 compose 标签查比解析 compose 文件列表稳。
        """
        from harbor.environments.docker.docker import (
            _sanitize_docker_compose_project_name,
        )

        project = _sanitize_docker_compose_project_name(environment.session_id)
        out = subprocess.run(
            ["docker", "ps", "-q",
             "--filter", f"label=com.docker.compose.project={project}",
             "--filter", "label=com.docker.compose.service=main"],
            capture_output=True, text=True, timeout=60,
        ).stdout.split()
        if not out:
            raise RuntimeError(f"找不到 trial 容器（compose project={project}）")
        return out[0]

    def _container_cwd(self, cid: str) -> str:
        """任务的工作目录，从容器镜像的 WorkingDir 读。

        【踩过的坑】原来写死 `/app` 兜底。46 个任务镜像里 45 个确实是 /app，
        但 `tabular-data-feature-covshift` 是 **/workspace**——`docker exec -w /app`
        直接失败，而且 **docker 把这个错误写到 stdout**：

            OCI runtime exec failed: chdir to cwd ("/app") ... no such file or directory

        于是 stderr 空、stdout 冒出一行非 JSON，撞上 LoopX 的 fail-closed 检查
        抛 app_server_frame_invalid_json，整个 trial 作废且无从追查（tee 都没
        执行到，raw stdout 也没有）。基线不受影响，因为上游走 exec_as_agent，
        用的是容器自己的 WORKDIR。
        """
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.Config.WorkingDir}}", cid],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        return out or "/app"

    def _user_flag(self, environment: BaseEnvironment) -> list[str]:
        """任务要求非 root 时，给 `docker exec` 补上 `-u`。

        【公平性缺陷，必须修】上游走 `exec_as_agent`，harbor 会按 task.toml 的
        `user =` 降权；我这条 `docker exec` 路绕开了它，而 46 个镜像的
        `Config.User` 全是空 —— 于是**默认以 root 运行**。

        46 个任务里只有 `sudoku-recovery` 设了 `user = "agent"`，它的 task.toml
        写明这是反作弊基石：非 root 才读不到 /opt/sudoku/private 的 oracle 与
        密钥、改不了引擎的节奏下限、杀不掉 root daemon。不补这个 flag，
        goal / LoopX 臂就比基线和 Terminus 多一份权限——本轮审计确认没被利用
        （敏感路径命中 0），但敞口不能留着。
        """
        user = getattr(environment, "default_user", None)
        return ["-u", str(user)] if user else []

    # ── 环境准备 ──────────────────────────────────────────────────────────
    async def _prepare(self, environment: BaseEnvironment) -> dict[str, str]:
        """写 auth.json + config.toml，与上游 Codex.run() 的准备段等价。"""
        codex_home = self._REMOTE_CODEX_HOME.as_posix()
        secrets = self._REMOTE_CODEX_SECRETS_DIR.as_posix()
        auth_path = (self._REMOTE_CODEX_SECRETS_DIR / "auth.json").as_posix()
        env = {"CODEX_HOME": codex_home}

        await self.exec_as_agent(
            environment,
            command=(f'mkdir -p "$CODEX_HOME" {shlex.quote(secrets)} '
                     f"{shlex.quote(EnvironmentPaths.agent_dir.as_posix())}"),
            env=env,
        )

        setup = (
            f"cat >{shlex.quote(auth_path)} <<EOF\n"
            '{\n  "OPENAI_API_KEY": "${OPENAI_API_KEY}"\n}\nEOF\n'
            f'ln -sf {shlex.quote(auth_path)} "$CODEX_HOME/auth.json"\n'
        )
        env["OPENAI_API_KEY"] = self._get_env("OPENAI_API_KEY") or ""

        base_url = self._get_env("OPENAI_BASE_URL")
        if not base_url:
            raise RuntimeError("OPENAI_BASE_URL 没设，app-server 找不到网关")
        env["OPENAI_BASE_URL"] = base_url
        wire_api = self._get_env("CODEX_WIRE_API") or "responses"
        # `>` 而不是 `>>`：整份一次性写出，避免 table 作用域和重复声明问题
        setup += (
            '\ncat >"$CODEX_HOME/config.toml" <<TOML\n'
            + (_CONFIG_TOML % {"wire_api": wire_api})
            + "TOML"
        )
        await self.exec_as_agent(environment, command=setup, env=env)

        # 前置检查：web_search 没关就中止。信息通道是必须锁死的项，
        # 静默跑偏比跑失败糟糕得多。
        check = await self._exec(
            environment,
            command=f'grep -c \'^web_search = "disabled"\' "{codex_home}/config.toml"',
        )
        if "1" not in (getattr(check, "stdout", "") or ""):
            raise RuntimeError("config.toml 里 web_search 不是 disabled，中止")
        return env

    # ── 主流程 ────────────────────────────────────────────────────────────
    async def run(self, instruction, environment: BaseEnvironment, context) -> None:
        if not self.model_name:
            raise ValueError("Model name is required")
        model = self.model_name.split("/")[-1]

        await self._prepare(environment)
        cid = self._container_id(environment)

        # 凭证必须在宿主机环境里，才能被 docker exec -e 转发进容器。
        # 缺了不会报错，只会变成静默空转（见下面 command 里的注释），
        # 所以在这里硬失败——空转比失败难发现得多。
        for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            if not os.environ.get(key):
                raise RuntimeError(
                    f"{key} 不在 harbor 进程的环境里，app-server 拿不到凭证，"
                    "会静默空转。检查 run_codex.sh 是否 export 了它。"
                )

        cwd = str(self._resolve_flag_values().get("cwd") or self._container_cwd(cid))

        # treatment 臂（LoopX）在这里装 profile、渲染 goal body。
        # 基线 goal 臂是空实现，不产生任何行为差异。
        # instruction 挂到实例上供钩子取用（LoopX 的 --goal-doc 要它）。
        self._pending_instruction = instruction
        # 任务要求的运行用户（非 root 时 LoopX 需要把 profile 目录 chown 过去）。
        self._task_user = getattr(environment, "default_user", None)
        self._treatment_setup(cid, cwd)

        # app-server 的 stdout 经 tee 留证 + 过滤后才交给 transport。
        #
        # 【踩过的坑】LoopX 的 _read_stream 对非 JSON 行是 fail-closed 的：一行
        # 不合法就抛 app_server_frame_invalid_json，整个 90 分钟的 trial 直接作废
        # （tabular-data-feature-covshift 就这么丢的，且 stderr 为空、无从还原）。
        # 协议层严格是对的，但一行杂音不该毁掉一次评测。
        #
        # 所以：tee 一份原始 stdout 到容器里留证，再只把 `{` 开头的行喂给
        # transport。这样既不改 LoopX 的代码，下次出问题也能捞到那行到底是什么。
        inner = (
            "codex app-server --listen stdio:// "
            "--enable goals --enable unified_exec"
        )
        piped = (
            f"{inner} | tee /tmp/goal_raw_stdout.jsonl "
            "| grep --line-buffered '^{'"
        )
        command = [
            "docker", "exec", "-i",
            # 【踩过的坑】必须把凭证转发进去。config.toml 里 env_key =
            # "OPENAI_API_KEY"，基线是靠 exec_as_agent(env=...) 注入的，而
            # docker exec 这条路绕开了那个机制。漏掉的表现极隐蔽：轮次能起来、
            # goal_context 能注入，但模型请求根本不发，turn 立刻 complete，
            # codex 见目标仍 active 又排一轮 —— 每 0.7 秒一圈的死循环，
            # 1.5 小时空转 17945 轮、0 次 token_count、0 条 error 记录。
            #
            # 用裸变量名（不带 =value）让 docker 从宿主机环境转发，
            # 这样密钥不会出现在进程命令行里被 ps 看到。
            "-e", "OPENAI_API_KEY",
            "-e", "OPENAI_BASE_URL",
            "-e", f"CODEX_HOME={self._REMOTE_CODEX_HOME.as_posix()}",
        ]
        # 与基线 exec_as_agent 对齐的降权（详见 _user_flag）。
        command += self._user_flag(environment)
        for k, v in self._extra_exec_env().items():
            command += ["-e", f"{k}={v}"]
        command += [
            "-w", cwd,
            cid,
            "sh", "-c", piped,
        ]
        config = NativeGoalConfig(
            cwd=cwd,
            objective=self._objective(),
            required_skill_ids=self._required_skill_ids(),
            task_instruction=instruction,   # harbor 已渲染，与基线同一份
            model=model,
            effort=str(self._resolve_flag_values().get("reasoning_effort") or "medium"),
            approval_policy="never",
            # 基线是 --dangerously-bypass-approvals-and-sandbox，展开就是这个。
            # 不要用 LoopX 参考实现默认的 workspace-write——那会让 goal 臂弱于基线。
            sandbox="danger-full-access",
            token_budget=None,   # 基线没有预算概念，设了就多一个基线没有的机制
        )

        out_dir = self.logs_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        turn = None
        err_path = out_dir / "goal_app_server.stderr"

        # transport 提到线程外持有：harbor 的超时是从外面掐的（agent 基类没有
        # _timeout_sec，拿不到自己的预算），被 cancel 时 asyncio.to_thread 里的
        # 线程不会停，app-server 会一直挂着、receipt 也丢。持有引用才能在
        # CancelledError 里主动 close()，让线程抛错退出、走到 finally 落 receipt。
        err = open(err_path, "w")
        transport = StdioNativeGoalTransport.spawn(
            command, cwd="/tmp", response_timeout_sec=180, stderr=err
        )
        try:
            turn = await asyncio.to_thread(self._drive, transport, config)
        # 五臂的原生 Goal 状态机现在都对着同一个 owner
        # （loopx.capabilities.benchmark_toolkit.native_codex_goal），不再有 vendored 副本，
        # 因此同名异常类只有一份。仍按消息判定而非按类捕获：超时是长程任务的**正常预算耗尽**，
        # 五臂必须一视同仁按部分进度评分——goal 臂的超时应被吞掉照常交 verifier，
        # 而不能像早期"同名异常类双来源"时那样只对 goal 臂生效、把 LoopX 臂的超时误当基础设施故障。
        # NativeGoalProtocolError 继承 RuntimeError，消息不匹配的照样重抛。
        except RuntimeError as exc:
            if str(exc) != "goal_timeout_before_terminal":
                raise
            self.logger.warning("goal 超时终止（预期行为）：%s", exc)
        except asyncio.CancelledError:
            self.logger.warning("harbor 掐断了 agent 阶段，关闭 app-server")
            raise
        finally:
            try:
                transport.close()
            finally:
                err.close()
                self._save_sessions(cid)
                self._write_receipt(out_dir, self._turn or turn, config)
                self._assert_not_spinning(self._turn or turn)

    def _drive(self, transport, config):
        """自己驱动续跑循环，而不是调 run_native_goal_until_terminal。

        【为什么不用现成的】那个函数超时时**抛异常而不返回 turn**，turn 对象
        在函数内部就丢了。结果是最需要过程证据的场景（长程任务跑满时间）反而
        什么都留不下——27 个已完成 trial 里 20 个的 receipt 是空壳。
        这里把 turn 存到 self._turn，异常路径也能落到 receipt 里。

        循环体只有排事件和轮询状态，**不再调 turn/start**——续跑轮次由 codex
        自己排，这是续跑归属的全部依据，不能自己造轮次。
        """
        turn = start_native_goal_turn(transport, config)
        self._turn = turn
        deadline = time.monotonic() + _GOAL_TIMEOUT_SEC
        completed_before = turn.turn_completed_count
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NativeGoalProtocolError("goal_timeout_before_terminal")
            try:
                wait_native_goal_turn(
                    transport, turn, timeout_sec=remaining,
                    completed_before=completed_before,
                )
            except NativeGoalProtocolError as exc:
                if str(exc) == "goal_turn_timeout":
                    raise NativeGoalProtocolError(
                        "goal_timeout_before_terminal") from exc
                raise
            completed_before = turn.turn_completed_count
            if refresh_native_goal_status(transport, turn) != "active":
                return turn

    def _save_sessions(self, cid: str) -> None:
        """把 codex 的 session rollout / goals 库 / 原始 stdout 拷进 /logs/agent。

        上游 Codex.run() 的 finally 里做了拷 sessions 这件事，我覆盖了整个 run()
        却没带上，导致 46 轮里 27 个已完成 trial 的轨迹**完全没有保存**，
        而容器随即被删除、永久丢失。

        **故意用同步 subprocess 而不是 await exec_as_agent**：harbor 从外面掐断
        agent 阶段时（continue_until_timeout 的后续阶段剩余时间 < _GOAL_TIMEOUT_SEC
        就会发生），finally 里的 await 会在 CancelledError 传播中立刻再次抛出，
        拷贝根本执行不到——而那恰恰是长程任务最需要留证的场景。
        同步调用不碰事件循环，取消中照样能跑完。
        """
        agent_dir = EnvironmentPaths.agent_dir.as_posix()
        home = self._REMOTE_CODEX_HOME.as_posix()
        script = (
            f'mkdir -p {agent_dir}; '
            f'if [ -d "{home}/sessions" ]; then '
            f'  rm -rf {agent_dir}/sessions; cp -R "{home}/sessions" {agent_dir}/sessions; '
            f'fi; '
            f'cp "{home}"/goals_1.sqlite* {agent_dir}/ 2>/dev/null; '
            f'cp /tmp/goal_raw_stdout.jsonl {agent_dir}/ 2>/dev/null; true'
        )
        try:
            subprocess.run(["docker", "exec", cid, "sh", "-c", script],
                           capture_output=True, timeout=180)
        except Exception as exc:
            self.logger.warning("保存 goal 轨迹失败: %s", exc)

    @staticmethod
    def _assert_not_spinning(turn) -> None:
        """空转检测：起了很多轮却一个 item 都没产生，说明模型压根没被调到。

        2026-08-23 第二次开跑就栽在这：漏传 OPENAI_API_KEY，轮次能起、
        goal_context 能注入，但请求不发、turn 立刻 complete、codex 见目标仍
        active 又排一轮，每 0.7 秒一圈。1.5 小时空转 17945 轮，
        **没有任何错误记录**，只有会话文件涨到 116MB 才看得出不对。

        与其让它安静地烧满 90 分钟再拿 0 分，不如让这个 trial 明确失败。
        """
        if turn is None:
            return
        turns = getattr(turn, "turn_started_count", 0) or 0
        items = getattr(turn, "item_event_count", 0) or 0
        if turns >= 20 and items == 0:
            raise RuntimeError(
                f"goal 空转：起了 {turns} 轮但 item_event_count=0，"
                "模型未被真正调用（多半是凭证没进到 app-server）"
            )

    def _write_receipt(self, out_dir: Path, turn, config) -> None:
        payload = {"objective_source": _OBJECTIVE,
                   "cwd": config.cwd, "model": config.model,
                   "effort": config.effort, "sandbox": config.sandbox,
                   "goal_timeout_sec": _GOAL_TIMEOUT_SEC}
        if turn is not None:
            payload.update(compact_native_goal_receipt(turn))
            # LoopX 臂的解锁次数存在 self._unblock_count 上，compact_native_goal_receipt
            # 只认 turn 对象、带不出来。不记进 receipt 的话，报分时无法回答
            # "这个分数用了几次 harness 干预"——那是必须披露的。
            if getattr(self, "_unblock_count", None) is not None:
                payload["_unblock_count"] = self._unblock_count
        else:
            payload["execution_mode"] = "goal_failed_before_receipt"

        # continue_until_timeout 会多次调 run()，每个阶段一份 receipt。
        # 只写固定文件名的话后面的阶段会把前面的覆盖掉——实测
        # langchain-version-migration 跑了 4 个阶段（每阶段模型都宣布 complete，
        # 前 3 次被中途 verifier 驳回），最后只剩阶段 4 的数据。
        # 所以逐阶段追加进 jsonl，同时保留 goal_receipt.json 指向最后一个阶段。
        payload["phase"] = self._phase = getattr(self, "_phase", 0) + 1
        with (out_dir / "goal_receipts.jsonl").open("a") as fh:
            fh.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
        (out_dir / "goal_receipt.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        )

    # ── treatment 钩子（基线臂全为空实现，子类覆盖）──────────────────────
    #
    # 这四个钩子是 LoopX treatment 臂唯一的接入点。基线 goal 臂走默认实现时
    # 行为与加钩子之前**逐字节相同**，所以两臂仍然只差 LoopX 那三样东西。

    def _treatment_setup(self, cid: str, cwd: str) -> None:
        """装 treatment 需要的东西（LoopX profile 等）。基线臂无操作。"""
        return None

    def _objective(self) -> str:
        """goal 的 objective。基线臂用 LoopX 夹具的那句极简写法。"""
        return _OBJECTIVE

    def _required_skill_ids(self) -> tuple:
        """交给 native_codex_goal 的 skills/list 保真度门禁。基线臂不需要。"""
        return ()

    def _extra_exec_env(self) -> dict:
        """追加给 app-server 的环境变量（LoopX 要改 HOME/PATH）。"""
        return {}
