"""codex + LoopX treatment 臂的 harbor agent。

继承 `CodexGoalAgent`（codex 原生 goal），在其之上加 LoopX 的三样东西——这正是
LoopX 自己 `benchmark/deepswe/README.md` 定义的 treatment 与 baseline 的差别：

  1. **skills**：LoopX 的 6 个 skill 装进 app-server 用的 `CODEX_HOME`
  2. **CLI**：`loopx` 可执行文件进 `PATH`，goal body 里指名的就是它
  3. **goal body**：objective 从 `"Finish the task."` 换成
     `loopx heartbeat-prompt --thin` 渲染出的 thin dispatcher

保真度靠 `required_skill_ids` 把关——`native_codex_goal.py` 会在 `thread/start`
之前发 `skills/list`，codex 没真的发现那些 skill 就直接失败，**一个 token 都不花**。
README 原话：*"A filesystem check alone is not treatment-fidelity evidence."*

## 为什么 LoopX 要装在容器里

codex 跑在容器内，goal body 让 agent 每轮调 `loopx` CLI 查状态——那个 CLI 必须
在容器里可执行。所以整个 profile（含 skills、CLI、registry）都装进容器。

## 离线安装怎么做到的

- LoopX `dependencies = []`，零第三方依赖，`install-local.sh` 只拷文件+生成 wrapper，
  全脚本没有一处网络访问。
- 但它要求 Python ≥3.11，而 46 个任务镜像里有 5 个是 3.10。所以**统一挂载一份
  可移植 python**（uv 的 python-build-standalone），46 个容器一视同仁，
  避免 41/5 两套环境。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from harbor.environments.base import BaseEnvironment

from codex_goal_agent import CodexGoalAgent, _GOAL_TIMEOUT_SEC
from loopx.capabilities.benchmark_toolkit.native_codex_goal import (
    NativeGoalProtocolError,
)

# 容器内的路径。profile 布局照抄 benchmark_toolkit 的 `_profile_paths()`，
# 这样 LoopX 自己的 inspect/doctor 逻辑对得上。
_SRC = "/opt/loopx-src"          # LoopX 源码（docker cp 进去）
_PY = "/opt/loopx-py"            # 可移植 python
_NODE = "/opt/loopx-node"        # 可移植 node（doctor 的 TS 运行时必需检查要它）
_ROOT = "/opt/lxprofile"
_HOME = f"{_ROOT}/home"
_CODEX_HOME = f"{_ROOT}/codex-home"
_BIN = f"{_ROOT}/bin"
_CLI = f"{_BIN}/loopx"
_REGISTRY = f"{_ROOT}/registry.json"
_RUNTIME = f"{_ROOT}/runtime"

_AGENT_ID = "lhtb-agent"

# ── 两个变体开关（env 驱动，同时写进 receipt 以便事后追溯用的是哪一版）────
#
# LOOPX_GOAL_DOC=1
#   bootstrap 时带 --goal-doc <任务原文>。LoopX 文档规定的接入方式是
#   「--objective 一句话 + --goal-doc 全文」，全文会被登记为 primary
#   authority source。第一版漏了这个参数，状态文件里明写
#   "No explicit goal document was provided during bootstrap"，
#   导致 LoopX 的 Next Action 一直钉在自带的 onboarding 项上、
#   Progress Ledger 只有 bootstrap 一条，任务进展没沉淀进持久状态。
#
#   注意 46 个镜像里只有 6 个自带 /app/instruction.md，所以统一由 agent
#   把 harbor 传来的 instruction 写进容器，不依赖镜像。
#
# LOOPX_GOAL_ID_MODE=task
#   goal_id 用任务名而不是固定的 lhtb-goal。LoopX 文档只要求 "stable goal id"，
#   benchmark 相关文档（deepswe README / RFC / 单元测试）**都没有规定**
#   benchmark 场景该怎么取，所以两种都不违反约定。
#   固定值的好处是 46 份 goal body 只差 goal-doc 一项；任务名的好处是更贴合
#   LoopX「一个项目一个持久目标」的语义。
_GOAL_DOC = bool(os.environ.get("LOOPX_GOAL_DOC"))
_GOAL_ID_MODE = os.environ.get("LOOPX_GOAL_ID_MODE", "fixed")
# LOOPX_UNGATED=1 —— 第三版：把前两版自己关掉/卡死的三处打开。
#
# 前两版的实测问题（见 LOOPX-DOC-46-RESULTS.md §二之二、§quota 分析）：
#
#   ① 待办规划被关掉。bootstrap 带了 `--no-onboarding-scan`，它的 help 原文是
#      "Skip the fast first-connect repository scan and **todo candidate proposal**"。
#      于是 LoopX 自己一条候选 todo 都没提，状态文件里那些任务专属 todo 全是模型
#      运行时自己建的。`terminal_no_followup`（待办队列空）因此成为最大拦截源之一。
#
#   ② 人工门禁在无人场景下永不放行。`--codex-app-heartbeat ask` 不预授权；
#      `coordination.write_scope` 是空的，agent 没有声明过的写权限；实测
#      `quota should-run` 真实返回里出现 state=operator_gate。
#
#   ③ 死锁。goal body 写明第三次相同阻塞轮就 `update_goal status=blocked`，
#      而「Only user `/goal resume` reactivates it」——benchmark 里没有 user。
#      v2 有 21/45 个任务、113/417 个阶段（27%）以 blocked 收尾。
#
# 修复①和②的参数已随上游删除首连 onboarding 门禁而失效：现在无论哪一版，
# bootstrap 都只登记 goal，不再写 onboarding todo，也不再要求
# connection validation / heartbeat 选择。LOOPX_UNGATED 目前只剩写权限声明
# 这一处差异，仍不碰 LoopX 渲染出的 goal body，保真度门禁照旧。
_UNGATED = bool(os.environ.get("LOOPX_UNGATED"))

# ── 三个模式 ────────────────────────────────────────────────────────────────
# WEN_MODE 选 LoopX README 里 Codex 的哪一行 host（README.md:289-291）。
# 定义在 wen/modes/profiles.py，这里只取参数，不复制一份枚举。
import sys as _sys  # noqa: E402
# modes/ 可能在同级（wen 布局）或 runtime/ 子目录（发布布局）下；探测哪个含
# modes/profiles.py 再加进 path，`from modes.profiles` 在两种布局都能解析。
_here = Path(__file__).resolve().parent
for _cand in (_here.parent, _here.parent / "runtime", _here.parent.parent):
    if (_cand / "modes" / "profiles.py").exists():
        _sys.path.insert(0, str(_cand))
        break
from modes.profiles import profile_args as _profile_args, resolve as _resolve_mode  # noqa: E402

_MODE = _resolve_mode(
    os.environ.get("WEN_MODE", "ssh-goal"),
    claim_codex_app=bool(os.environ.get("WEN_CLAIM_CODEX_APP")),
)
#: 渲染时传给 loopx 的 profile 参数（具名 profile 或 -H/-O/-M 三元组）
_PROFILE_ARGS = " ".join(_profile_args(_MODE))

_GOAL_DOC_PATH = f"{_ROOT}/goal-doc.md"
_FIXED_GOAL_ID = "lhtb-goal"
# 与 benchmark_toolkit 的 NATIVE_CODEX_PROFILE_REQUIRED_SKILL_IDS 对应。
# 实测 install-local.sh 物化出这 6 个。
# 技能门禁向上游常量看齐，不写死。
# 写死过一次 6 个，而 loopx 0.5.3 物化 7 个（多 loopx-benchmark）；
# 门禁只查那 6 个，于是容器里少装一个技能完全不会被发现。
# 从 LOOPX_SRC_DIR 读常量，读不到就退回历史的 6 个并在日志里说明。
def _load_required_skills() -> tuple[str, ...]:
    src = os.environ.get("LOOPX_SRC_DIR", "")
    if src and os.path.isdir(src):
        import sys as _s
        if src not in _s.path:
            _s.path.insert(0, src)
        try:
            from loopx.capabilities.benchmark_toolkit.native_codex_profile import (
                NATIVE_CODEX_PROFILE_REQUIRED_SKILL_IDS as _R,
            )
            return tuple(_R)
        except Exception:
            pass
    return (
        "loopx", "loopx-doc-registry", "loopx-pr-program",
        "loopx-pr-review", "loopx-project", "loopx-self-repair",
    )


_REQUIRED_SKILLS = _load_required_skills()

# `render_native_codex_goal_prompt` 里的同名常量：渲染出的 body 带这个占位符，
# 必须替换成真实 registry 路径，替换后还要验证占位符确实消失。
_GLOBAL_REGISTRY_TOKEN = "$HOME/.codex/loopx/registry.global.json"


class CodexLoopxAgent(CodexGoalAgent):
    _loopx_ready = False

    def _bootstrap_gates(self, cwd: str) -> str:
        """bootstrap 末尾那串门禁/规划相关的参数。

        历史记录（v1/v2 用 `--no-onboarding-scan --codex-app-heartbeat ask`，
        v3 用 `--accept-onboarding-agent-todos --begin-autonomous-advance
        --codex-app-heartbeat yes`）描述的是 LoopX 当时的首连门禁参数。这些参数
        已在上游删除：bootstrap 不再写入任何首连 onboarding todo，也不再有
        connection validation / heartbeat 选择项。现在两版只剩写权限声明不同，
        objective、adapter、goal-doc、goal-id 仍逐字不变。
        """
        if not _UNGATED:
            return ""
        # 声明写权限（原来 coordination.write_scope 是空的）
        return f"--write-scope {cwd}"

    def _goal_id(self) -> str:
        """本 trial 的 goal id。

        `LOOPX_GOAL_ID_MODE=task` 时取任务名。trial 目录名形如
        `<task>__<trialid>`，logs_dir 是 `.../<task>__<trialid>/agent`。
        LoopX 会把 goal_id 当路径段用，所以只保留安全字符、并保证首字符
        是字母或数字（`2048` 这类纯数字任务名也合法）。
        """
        if _GOAL_ID_MODE != "task":
            return _FIXED_GOAL_ID
        raw = self.logs_dir.parent.name.rsplit("__", 1)[0]
        safe = re.sub(r"[^A-Za-z0-9._-]", "-", raw).strip("-._")
        return f"{safe}-goal" if safe and safe[0].isalnum() else _FIXED_GOAL_ID

    @staticmethod
    def name() -> str:
        return "codex-loopx"

    # ── app-server 要跑在 LoopX profile 的环境里 ──────────────────────────
    # 覆盖父类的常量，让 config.toml / auth.json 写进 profile 的 CODEX_HOME，
    # 否则 codex 找不到 skills。
    @property
    def _REMOTE_CODEX_HOME(self):  # noqa: N802  (与上游同名)
        from pathlib import PurePosixPath
        return PurePosixPath(_CODEX_HOME)

    def _sh(self, cid: str, script: str, env: dict[str, str] | None = None,
            timeout: int = 600, as_root: bool = False) -> subprocess.CompletedProcess:
        cmd = ["docker", "exec"]
        # 默认以任务用户跑，这样 LoopX 写出的 registry / runtime / 状态文件归属
        # 正确，降权运行的 codex 后续才改得动。只有需要写 /opt 的目录创建和
        # 权限移交走 as_root=True。
        if not as_root and getattr(self, "_task_user", None):
            cmd += ["-u", str(self._task_user)]
        for k, v in (env or {}).items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [cid, "sh", "-c", script]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    async def _prepare(self, environment: BaseEnvironment):
        """先用 root 建好 profile 根目录并移交给任务用户，再走父类准备段。

        【踩过的坑】父类 `_prepare()` 第一件事就是
        `exec_as_agent('mkdir -p "$CODEX_HOME" ...')`，而我把 CODEX_HOME 挪到了
        `/opt/lxprofile/codex-home`（codex 必须从 `$CODEX_HOME/skills` 发现那 6 个
        skill，不放一起过不了保真度门禁）。`/opt` 归 root，于是在
        `sudoku-recovery`——46 个任务里唯一设 `user = "agent"` 的——直接：

            mkdir: cannot create directory '/opt/lxprofile': Permission denied

        trial 在 setup 阶段就死，一个 token 没花，却被记成 0.000，等于把基础设施
        失败当成了任务失败（同任务基线 0.429、goal 0.571/0.707）。v1 v2 共用
        本文件，两轮报错一字不差。

        为什么不把 `_ROOT` 换成 `/tmp`：那会让这一个任务的环境和另外 45 个不同，
        修公平性的补丁反而制造新的不公平。这里保持路径完全一致，只补权限。
        """
        # _drive 破自锁时要用容器 id，但它没有 environment 形参，这里存一份。
        # 之前直接写 self._environment 导致 'CodexLoopxAgent' object has no
        # attribute '_environment'，三个 LoopX 臂全挂。
        self._env_ref = environment
        self._task_user = getattr(environment, "default_user", None)
        if self._task_user:
            cid = self._container_id(environment)
            r = self._sh(
                cid,
                f"mkdir -p {_ROOT} {_SRC} {_PY} {_NODE} && "
                f"chown -R {self._task_user} {_ROOT} {_SRC} {_PY} {_NODE}",
                as_root=True, timeout=180,
            )
            if r.returncode:
                raise RuntimeError(
                    f"以 root 准备 LoopX profile 目录失败: {(r.stderr or r.stdout)[:200]}"
                )
            self.logger.info("非 root 任务（user=%s），profile 目录已移交",
                             self._task_user)
        return await super()._prepare(environment)

    def _install_env(self) -> dict[str, str]:
        """照抄 benchmark_toolkit `_formal_install_environment()` 的每一项。

        少一项就可能装成 canary（未验证源码不自动提升为默认），实测过：
        不设 LOOPX_PROMOTE_DEFAULT=1 就只有 loopx-canary、skills 也不装。
        """
        return {
            "HOME": _HOME, "SHELL": "/bin/sh", "CODEX_HOME": _CODEX_HOME,
            # node 必须在 PATH 上，doctor 用 shutil.which("node") 找它
            "PATH": f"{_NODE}/bin:{_BIN}:/usr/local/bin:/usr/bin:/bin",
            "LOOPX_PYTHON": f"{_PY}/bin/python3",
            "LOOPX_PROMOTE_DEFAULT": "1",
            "LOOPX_INSTALL_CANARY": "0",
            "LOOPX_BIN_DIR": _BIN,
            "LOOPX_RELEASES_DIR": f"{_ROOT}/releases",
            "LOOPX_RELEASE_ID": "native-goal-profile",
            "LOOPX_MAN_ROOT": f"{_ROOT}/man",
            "LOOPX_MAN_DIR": f"{_ROOT}/man/man1",
            "LOOPX_SHELL_PROFILE": f"{_HOME}/.profile",
            "LOOPX_SKILLS_DIR": f"{_CODEX_HOME}/skills",
            "LOOPX_INSTALL_SLASH_COMMANDS": "0",
            "LOOPX_INSTALL_OPENCODE": "0",
            "LOOPX_INSTALL_CLAUDE": "0",
            "LOOPX_SKILL_DEDUPE_OTHER_ROOT": "0",
        }

    def _cli_env(self) -> dict[str, str]:
        return {"HOME": _HOME, "CODEX_HOME": _CODEX_HOME,
                "PATH": f"{_NODE}/bin:{_BIN}:/usr/local/bin:/usr/bin:/bin"}

    # ── 安装 LoopX profile ────────────────────────────────────────────────
    def _install_loopx(self, cid: str) -> None:
        # wen/ 版默认落在本机布局上（原默认曾是某台特定机器的绝对路径）。
        # env.sh 会显式导出这两个变量，这里的 fallback 只是脱离 env.sh 时的兜底。
        _wen = Path(__file__).resolve().parent.parent
        src = os.environ.get("LOOPX_SRC_DIR", str(_wen.parent / "loopx"))
        py = os.environ.get(
            "LOOPX_PORTABLE_PYTHON",
            os.path.expanduser(
                "~/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu"
            ),
        )
        node = os.environ.get("LOOPX_NODE_DIR", "")
        if not node or not os.path.isdir(node):
            raise RuntimeError(
                "LOOPX_NODE_DIR 没指到可用的 node（>=22.6.0）。0.5.3 的 "
                "install-local.sh 会跑 doctor --deep，其中 "
                "typescript_effect_runtime_ready 是必需项，没有 node 就 missing，"
                "整个 LoopX 安装会中止。"
            )
        for host_path, dest in ((src, _SRC), (py, _PY), (node, _NODE)):
            if not os.path.isdir(host_path):
                raise RuntimeError(f"LoopX 依赖缺失: {host_path}")
            r = subprocess.run(["docker", "cp", f"{host_path}/.", f"{cid}:{dest}"],
                               capture_output=True, text=True, timeout=900)
            if r.returncode:
                raise RuntimeError(f"拷贝 {host_path} 失败: {r.stderr[:200]}")

        # `docker cp` 总是以 root 身份写入，非 root 任务上拷完必须再移交一次，
        # 否则 install-local.sh（降权运行）读不到源码、也写不进 releases。
        if getattr(self, "_task_user", None):
            self._sh(cid, f"chown -R {self._task_user} {_SRC} {_PY} {_NODE} {_ROOT}",
                     as_root=True, timeout=180)

        self._sh(cid, f"mkdir -p {_HOME} {_CODEX_HOME}/skills {_BIN} "
                      f"{_ROOT}/releases {_ROOT}/man {_RUNTIME}")
        # 拷进来的源码里可能带着宿主机 pip 留下的 *.egg-info / *.dist-info。
        # 那是致命污染：0.5.3 的 install-local.sh 会跑一道 RC doctor 深检，
        # importlib.metadata.distribution("loopx") 会解析到这份树内元数据，
        # 而 editable/in-tree 构建的 egg-info **不记录 console script**，于是
        #   distribution_command: {"ok": false, "error": "console_script_not_recorded"}
        #   loopx installer error: release candidate doctor validation failed
        # 整个 LoopX 臂装不进去。宿主机上删了 pip 还会再生成，所以在容器侧清，
        # 不依赖宿主状态。
        self._sh(cid,
                 f"find {_SRC} -maxdepth 2 -name '*.egg-info' -o -maxdepth 2 -name '*.dist-info' "
                 f"| xargs -r rm -rf",
                 timeout=120)

        r = self._sh(cid, f"bash {_SRC}/scripts/install-local.sh",
                     env=self._install_env(), timeout=900)
        if r.returncode:
            raise RuntimeError(f"LoopX 安装失败: {(r.stderr or r.stdout)[-400:]}")

        # fail-closed：CLI 与 6 个 skill 必须都在，doctor 必须 ok
        chk = self._sh(cid, f"test -x {_CLI} && ls {_CODEX_HOME}/skills",
                       env=self._cli_env())
        missing = [s for s in _REQUIRED_SKILLS if s not in (chk.stdout or "")]
        if chk.returncode or missing:
            raise RuntimeError(f"LoopX profile 不完整，缺 skill: {missing}")
        doc = self._sh(cid, f"{_CLI} --format json doctor --agent-type codex-app-ssh",
                       env=self._cli_env())
        try:
            if not json.loads(doc.stdout).get("ok"):
                raise ValueError
        except Exception:
            raise RuntimeError(f"loopx doctor 未通过: {(doc.stdout or doc.stderr)[:300]}")
        self.logger.info(f"LoopX profile 就绪（{len(_REQUIRED_SKILLS)} skills + CLI + doctor ok）")

    # ── 注册目标并渲染 goal body ──────────────────────────────────────────
    def _render_goal_body(self, cid: str, cwd: str, instruction: str = "") -> str:
        g = (f"{_CLI} --registry {_REGISTRY} --runtime-root {_RUNTIME}")
        env = self._cli_env()
        gid = self._goal_id()

        # bootstrap 幂等：registry 已有该目标就跳过。
        # harbor 的 continue_until_timeout 每阶段都会调 run()，重复 bootstrap
        # 会被 LoopX 拒绝（它禁止在已有状态上强制 bootstrap）。
        has = self._sh(cid, f"test -f {_REGISTRY} && grep -q {gid} {_REGISTRY}", env=env)
        if has.returncode:
            doc_flag = ""
            if _GOAL_DOC:
                # 46 个镜像里只有 6 个自带 instruction.md，所以统一由我们写进去，
                # 放在 profile 目录而不是任务工作区，避免多给 verifier 一个文件。
                if not instruction.strip():
                    raise RuntimeError("LOOPX_GOAL_DOC=1 但 instruction 为空")
                w = subprocess.run(
                    ["docker", "exec", "-i", cid, "sh", "-c",
                     f"cat > {_GOAL_DOC_PATH}"],
                    input=instruction, text=True, capture_output=True, timeout=120)
                if w.returncode:
                    raise RuntimeError(f"写 goal-doc 失败: {w.stderr[:200]}")
                doc_flag = f" --goal-doc {_GOAL_DOC_PATH}"
            r = self._sh(cid,
                         f"cd {cwd} && {g} bootstrap --project . --goal-id {gid} "
                         f"--objective 'Finish the task.'{doc_flag} "
                         f"--adapter-kind read_only_project_map_v0 "
                         f"--adapter-status connected-read-only "
                         f"{self._bootstrap_gates(cwd)}",
                         env=env, timeout=300)
            if r.returncode:
                raise RuntimeError(f"loopx bootstrap 失败: {(r.stderr or r.stdout)[-300:]}")
            r = self._sh(cid, f"cd {cwd} && {g} register-agent --goal-id {gid} "
                              f"--agent-id {_AGENT_ID} --require-new --execute",
                         env=env, timeout=300)
            if r.returncode:
                raise RuntimeError(f"loopx register-agent 失败: {(r.stderr or r.stdout)[-300:]}")

        # ── 每阶段解锁（破死锁）────────────────────────────────────────────
        # goal body 原文里写着：
        #   Third identical blocked turn with no progress: call update_goal with
        #   status=blocked ... **Only user `/goal resume` reactivates it**
        # benchmark 里没有 user，所以这是个单向阀门。实测 v2 有 21/45 个任务、
        # 27% 的阶段以 blocked 收尾。这里由 harness 扮演「每阶段来解锁的 operator」，
        # 用官方 CLI 清掉 waiting_on 并把 agent 置回 active，不碰 goal body。
        if _UNGATED:
            self._sh(cid,
                     f"cd {cwd} && {g} configure-goal --goal-id {gid} "
                     f"--clear-waiting-on --agent-work-mode {_AGENT_ID}=active --execute",
                     env=env, timeout=180)

        r = self._sh(cid,
                     f"cd {cwd} && {g} --format json heartbeat-prompt --thin "
                     f"--goal-id {gid} --agent-id {_AGENT_ID} "
                     f"{_PROFILE_ARGS} --cli-bin {_CLI} "
                     f"--available-capability shell --available-capability filesystem_write",
                     env=env, timeout=300)
        # 下面每一条校验都照抄 render_native_codex_goal_prompt()，
        # 失败码沿用它的命名，方便和 LoopX 自己的实现对照。
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise RuntimeError("goal_prompt_cli_invalid_json")
        if payload.get("ok") is not True:
            raise RuntimeError(f"goal_prompt_cli_not_ready: {str(payload.get('error'))[:200]}")
        if _MODE.runtime_profile and payload.get("runtime_profile") != _MODE.runtime_profile:
            raise RuntimeError(
                f"goal_prompt_runtime_profile_mismatch: "
                f"want={_MODE.runtime_profile} got={payload.get('runtime_profile')}"
            )
        budget = payload.get("interface_budget") or {}
        if budget.get("within_budget") is not True:
            raise RuntimeError("goal_prompt_interface_budget_invalid")
        body = payload.get("task_body")
        if not isinstance(body, str) or not body.strip():
            raise RuntimeError("goal_prompt_task_body_missing")
        if _CLI not in body:
            raise RuntimeError("goal_prompt_installed_cli_not_bound")
        if _GLOBAL_REGISTRY_TOKEN in body:
            body = body.replace(_GLOBAL_REGISTRY_TOKEN, _REGISTRY)
            if _GLOBAL_REGISTRY_TOKEN in body or _REGISTRY not in body:
                raise RuntimeError("goal_prompt_runtime_registry_not_bound")
        # codex 的 objective 硬上限 4000；LoopX 的 interface_budget 也按 4000 设计
        if len(body) > 4000:
            raise RuntimeError(f"goal body {len(body)} 字符，超过 codex 的 4000 上限")
        self._goal_body = body
        self._loopx_variant = {"goal_doc": _GOAL_DOC, "goal_id_mode": _GOAL_ID_MODE,
                               "goal_id": gid, "ungated": _UNGATED}
        self.logger.info(
            "LoopX goal body 已渲染（%d 字符，goal_id=%s，goal_doc=%s，ungated=%s）",
            len(body), gid, _GOAL_DOC, _UNGATED)
        return body

    # ── 覆盖父类的四个 treatment 钩子 ─────────────────────────────────────
    def _treatment_setup(self, cid: str, cwd: str) -> None:
        # profile 装一次即可；harbor 的 continue_until_timeout 每阶段都会调
        # run()，但容器不变，所以用实例标志 + 容器内探测双重保险。
        if not self._loopx_ready:
            probe = self._sh(cid, f"test -x {_CLI}")
            if probe.returncode:
                self._install_loopx(cid)
            self._loopx_ready = True
        self._render_goal_body(cid, cwd, self._pending_instruction)

    def _objective(self) -> str:
        body = getattr(self, "_goal_body", "")
        if not body:
            raise RuntimeError("LoopX goal body 未渲染，treatment 未生效")
        return body

    def _required_skill_ids(self) -> tuple:
        # 交给 native_codex_goal 的 skills/list 门禁：codex 没真的发现这些
        # skill 就在 thread/start 之前失败，不花 token。
        return _REQUIRED_SKILLS

    def _extra_exec_env(self) -> dict:
        # app-server 必须跑在 profile 的环境里，否则 codex 看不到 skills、
        # goal body 里指名的 loopx 也不在 PATH 上。
        return {"HOME": _HOME, "PATH": f"{_BIN}:/usr/local/bin:/usr/bin:/bin"}


    # ── 破自锁：blocked 不等于终态 ──────────────────────────────────────────
    def _restart_turn_same_thread(self, transport, config, turn):
        """在**已有 thread** 上再起一轮，只发 `turn/start`。

        【为什么不能用 start_native_goal_turn】它内部第一步是 attach_native_goal，
        而那会重发 `initialize`。同一条 transport 二次 initialize 是协议违规，
        app-server 直接拒绝：

            Trial ... failed: app_server_request_failed:initialize

        实测代价：kubernetes-rust-rewrite/codex-cli 三次尝试全挂在这里，$0.82 白花。
        更隐蔽的是**这条路径直到那一刻才第一次被执行到** —— 在此之前 goal 从没
        真的进过 blocked，receipt 里的解锁数一直是 0，我据此一轮轮报告"自锁未触发、
        兜底备而未用"。兜底其实是坏的，只是没被叫到。

        turn_params 逐字照抄上游 start_native_goal_turn，只去掉 attach 那一步，
        保证除"不重新握手"之外语义完全一致。
        """
        from loopx.capabilities.benchmark_toolkit.native_codex_goal import (  # noqa: E402
            NativeGoalProtocolError as _E, _nested,
        )
        turn_params = {
            "threadId": turn.thread_id,
            "input": [{"type": "text", "text": config.task_instruction}],
            "cwd": config.cwd,
            "approvalPolicy": config.approval_policy,
        }
        if config.model:
            turn_params["model"] = config.model
        if config.effort:
            turn_params["effort"] = config.effort
        if config.sandbox_policy is not None:
            turn_params["sandboxPolicy"] = dict(config.sandbox_policy)
        turn_result = transport.request("turn/start", turn_params)
        turn.methods.append("turn/start")
        rt = _nested(turn_result, "turn")
        rid = str(rt.get("id") or turn_result.get("turnId") or "")
        if not rid:
            raise _E("turn_start_id_missing")
        turn.turn_id = rid
        turn.response_turn_id = rid
        turn.turn_status = str(rt.get("status") or "accepted")
        return turn

    def _drive(self, transport, config):
        """在父类续跑循环之上，把 `blocked` 当成可恢复而不是终态。

        父类（codex_goal_agent._drive）的判据是 `status != "active"` 就返回——
        `blocked` 也满足。而 LoopX 的 goal body 明写：连续三轮相同阻塞就
        `update_goal status=blocked`，且**只有 user 的 `/goal resume` 能复活它**。
        benchmark 里没有 user，于是模型一 block，驱动立刻收工。

        实测后果：find-network-alignments/codex-cli 只跑了 7 步、131 个输出 token
        就以 post_goal_status=blocked、continuation_turn_completed_count=0 结束，
        而这个 benchmark 单次平均 27.2M token。测到的是自锁，不是 harness 能力。

        LOOPX_UNGATED=1 时由 harness 扮演那个不存在的 operator：清掉 waiting_on、
        把 agent 置回 active、再起一轮，直到真正终态或预算耗尽。
        每次解锁都计数并写进 receipt，报分时要能看出用了几次。
        """
        from loopx.capabilities.benchmark_toolkit.native_codex_goal import (  # noqa: E402
            refresh_native_goal_status, start_native_goal_turn, wait_native_goal_turn,
        )
        import time as _t

        if not _UNGATED:
            return super()._drive(transport, config)

        cid = self._container_id(self._env_ref)
        gid = self._goal_id()
        env = self._cli_env()
        cwd = getattr(self, "_workdir", None) or "/app"
        deadline = _t.monotonic() + _GOAL_TIMEOUT_SEC
        unblocks = 0
        max_unblocks = int(os.environ.get("LOOPX_MAX_UNBLOCKS", "8"))

        turn = start_native_goal_turn(transport, config)
        self._turn = turn
        completed_before = turn.turn_completed_count
        while True:
            remaining = deadline - _t.monotonic()
            if remaining <= 0:
                self._unblock_count = unblocks
                raise NativeGoalProtocolError("goal_timeout_before_terminal")
            try:
                wait_native_goal_turn(transport, turn, timeout_sec=remaining,
                                      completed_before=completed_before)
            except NativeGoalProtocolError as exc:
                if str(exc) == "goal_turn_timeout":
                    self._unblock_count = unblocks
                    raise NativeGoalProtocolError("goal_timeout_before_terminal") from exc
                # 【踩过的坑】这条裸 raise 原来不赋值 _unblock_count，于是 receipt 里
                # 该字段是 None 而不是数字。偏偏这是**最需要证据的**出口：非超时的
                # 协议错误（实测是 8 次流层重试被 TPM 限流耗尽后抛出的），trial 会
                # 提前几十分钟死掉。mastodon-clone/ssh-goal 就这么丢了解锁计数，
                # 排查时只能靠"别的臂都是 0、就它是 -"这个差异反推。
                # 每条出口都要留下计数，否则出问题的那次恰好没有证据。
                self._unblock_count = unblocks
                raise
            completed_before = turn.turn_completed_count
            status = refresh_native_goal_status(transport, turn)
            if status == "active":
                continue
            if status != "blocked" or unblocks >= max_unblocks:
                # 【实测教训】只在循环内判 blocked 是不够的：Goal 常常在 wait 返回、
                # codex 停止续跑之后才落到 blocked，那时已经走到这个 return。
                # 实测 ssh-goal cont=3 / codex-cli cont=2 都以 blocked 收尾而
                # 解锁一次未触发。这里在返回前再兜一次。
                if status == "blocked" and unblocks < max_unblocks:
                    unblocks += 1
                    self.logger.info("收尾时仍 blocked，第 %d 次解锁后重试", unblocks)
                    self._sh(cid,
                             f"cd {cwd} && {_CLI} configure-goal --goal-id {gid} "
                             f"--clear-waiting-on --agent-work-mode {_AGENT_ID}=active "
                             f"--execute", env=env, timeout=180)
                    turn = self._restart_turn_same_thread(transport, config, turn)
                    self._turn = turn
                    completed_before = turn.turn_completed_count
                    continue
                self._unblock_count = unblocks
                return turn
            # 扮演 operator：清阻塞、置回 active、再起一轮
            unblocks += 1
            self.logger.info("goal 进入 blocked，第 %d 次解锁", unblocks)
            self._sh(cid,
                     f"cd {cwd} && {_CLI} configure-goal --goal-id {gid} "
                     f"--clear-waiting-on --agent-work-mode {_AGENT_ID}=active --execute",
                     env=env, timeout=180)
            turn = self._restart_turn_same_thread(transport, config, turn)
            self._turn = turn
            completed_before = turn.turn_completed_count
