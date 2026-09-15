"""离线安装的 Codex agent。

上游 `harbor.agents.installed.codex.Codex.install()` 在容器内 `npm install -g
@openai/codex`（非 musl 环境还要先装 NVM + Node 22），这需要容器能出公网。
LHTB 有 22 个任务 `allow_internet=false`，装不上——这正是上一轮 codex-gpt5.5
只能跑 24 个任务的原因。

但 `@openai/codex` 的 npm 包里带的是一个 **static-pie musl 二进制**，不依赖
Node、不依赖任何动态库（已在断网容器里验证 `codex --version` 可跑）。所以把
安装改成"从宿主机拷二进制进去"，就不需要容器出网了。同一个包里还带了 ripgrep，
一并拷进去（上游 install 也会装 rg）。

除 install() 外一切沿用上游 Codex：同样的 `codex exec` 命令行、同样的
config.toml / auth.json 处理、同样的轨迹解析。所以这不是另一个 harness，
只是把"怎么把 codex 放进容器"换了个不需要网的做法。

用法（config.yaml）：
    agents:
      - import_path: codex_offline:CodexOffline
        model_name: openai/gpt-5.5
需要 PYTHONPATH 指到本文件所在目录，且 CODEX_OFFLINE_DIR 指向存放
codex / rg 两个二进制的目录（默认见下）。
"""

import os
import tempfile
from pathlib import Path

from harbor.agents.installed.base import CliFlag
from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment

# wen/ 版默认指向本工作区暂存的二进制（当前 0.151.0）。原值
# 原默认曾指向某台特定机器的绝对路径，此处改为工作区相对路径。
_DEFAULT_OFFLINE_DIR = str(Path(__file__).resolve().parent.parent / "codex")

# 先落到 /tmp 再 install 到 /usr/local/bin：upload_file 以 root 落盘且不保留
# 执行位，直接传到 /usr/local/bin 会得到一个不可执行的文件。
_STAGE_DIR = os.path.join(tempfile.gettempdir(), "codex-offline")

# 上游限流会把 agent 打死：2026-08-21 第一次跑 46 全量时，5 个跑完的 trial 里
# 有 3 个死于
#   "stream disconnected before completion: Requests have exceeded the throughput
#    limit on your Provisioned-Managed deployment"
# nbody 的 todo 只完成 1/5 项就被切断（0.676 vs Terminus 的 0.973）。
#
# 【第一次诊断错了，留着当教训】起初以为是"Terminus 配了 num_retries=4 会重试、
# codex 不重试"，于是把这三个键设成 4。查了才知道 codex 的默认值本来就是
# request_max_retries=4 / stream_max_retries=5——设成 4 等于没改，stream 那个
# 还从 5 降到了 4。网关日志也证实 codex 一直在重试：那轮 1721 次调用里 109 次
# 是 0-token 的失败调用，最惨的一个 session 连续重试 38 次仍然没救回来。
#
# 真正的原因是**请求速率**：codex 约 17 次/分（4 路并发），Terminus 只有 2~3 次/分。
# 同样 4 路并发，codex 的压强是 Terminus 的 5~8 倍，顶穿了 provisioned 部署的吞吐
# 上限。Terminus 撞不到不是因为它会重试，是因为它根本达不到那个速率。
#
# 所以主修法是**降并发**（见 config 里的 n_concurrent_trials），这里只是把重试
# 抬到默认值以上做兜底——短暂抖动能扛过去，持续超限还是得靠降速率。
_RETRY_FLAGS = (
    # codex 0.151.0 起 provider 必须有非空 name，否则起手就是
    #   Error loading config.toml: model_providers.harbor: provider name must not be empty
    # harbor 自己生成的 provider 段没写 name（0.147 之前不校验），于是 codex 直接
    # 退出、连 session 目录都不建，trial 记成 reward=0 —— 看着像模型没做出来，
    # 其实一个 token 都没花。这一条必须排在其他 harbor provider 覆盖之前。
    "-c model_providers.harbor.name=harbor"
    " -c model_providers.harbor.request_max_retries=8"
    " -c model_providers.harbor.stream_max_retries=8"
    " -c model_providers.harbor.stream_idle_timeout_ms=300000"
)


class CodexOffline(Codex):
    # goals 在 0.133.0 里是 stable 且**默认开启**的：模型可以调 create_goal /
    # get_goal / update_goal，运行时会自动续跑（"Continue working toward the active
    # thread goal."）直到目标达成或预算耗尽。默认开意味着基线轮不显式关掉的话，
    # 它自己就带了 goal 模式，三轮就不是三个条件了。
    # 所以这里做成必须显式声明：基线 goals="false"，goal 轮 goals="true"。
    CLI_FLAGS = Codex.CLI_FLAGS + [
        CliFlag(
            "goals",
            cli="-c",
            type="enum",
            choices=["true", "false"],
            format="-c features.goals={value}",
        ),
        # 模型服务端的 web_search 由**模型侧**执行，不经过容器——internal 网络、
        # 无默认路由、iptables 对它全部无效。基线轮实测：46 个任务里 6 个用过，
        # 其中 4 个是断网任务，而 allow_internet=false 是任务作者设的约束。
        # sokoban 搜关卡答案 22 次、apex-law433 顺着任务反查到 HuggingFace 上的
        # 源数据集 RUC-AIBOX/Evo-Bench 并试图在里面找答案原文。
        #
        # 【键名踩过坑】正确的是 `web_search`，不是 `web_search_mode`。
        # 后者连同 disabled_tools / tools.web_search / --disable web_search_request
        # 一共四种写法**codex 都接受但都不生效**——实测同一个必须联网才能答的
        # 问题，不加开关触发 86 次，四个候选仍触发 46/72/117/52 次。
        # `web_search="disabled"` 实测触发 0 次，且 agent 会明说
        # "this session does not have usable web access" 后退回 shell——
        # **它想用而用不了**，这比计数为 0 更能证明工具真的不在了。
        CliFlag(
            "web_search",
            cli="-c",
            type="enum",
            choices=["disabled", "cached", "live"],
            format='-c web_search="{value}"',
        ),
    ]

    @staticmethod
    def name() -> str:
        return "codex-offline"

    def version(self) -> str | None:
        return self._version or "offline"

    def get_version_command(self) -> str | None:
        # 上游那条命令会先 source nvm；离线安装没有 nvm，直接问二进制。
        return "/usr/local/bin/codex --version"

    def build_cli_flags(self) -> str:
        flags = super().build_cli_flags()
        # 默认关掉模型服务端的 web_search，**对全部 46 个任务一律关闭**。
        #
        # 理由是与 Terminus 的信息通道对齐：Terminus 结构上没有这个工具
        # （46 轮 × 每轮几十个 debug.json 里 `tools` 字段一次都没出现），
        # 所以留着它就等于给 codex 一条对方没有的信息通道。
        #
        # 代价要认：对 24 个 allow_internet=true 的任务，搜索本是正当能力，
        # 关掉等于让 codex 减配上场——实测 spice-ephemeris 因此从 0.939 掉到 0.030。
        # 所以这样测出来的是「**限定在 Terminus 同等信息通道下**的对比」，
        # 而不是「codex 开箱能力」的对比。报告里必须写明这一点。
        #
        # 键名是 `web_search` 不是 `web_search_mode`——后者连同 disabled_tools /
        # tools.web_search / --disable web_search_request 四种写法 codex 都接受
        # 但都不生效（实测触发 46/72/117/52 次）。只有 web_search="disabled"
        # 真正关掉：触发 0 次，且 agent 会明说没有可用的 web access 后退回 shell。
        if "web_search=" not in flags:
            flags = f'{flags} -c web_search="disabled"'.strip()
        return f"{flags} {_RETRY_FLAGS}" if flags else _RETRY_FLAGS

    async def install(self, environment: BaseEnvironment) -> None:
        offline_dir = Path(os.environ.get("CODEX_OFFLINE_DIR", _DEFAULT_OFFLINE_DIR))
        # wen/codex 顶层的 codex / rg / codex-code-mode-host 都是指向 bin/ 与
        # codex-path/ 的软链（见 stage_codex_offline.sh）。upload_file 不跟随软链，
        # 直传会得到 "install: cannot stat ... No such file or directory"，
        # 所以这里一律 resolve 成真实文件再传。
        codex_bin = (offline_dir / "codex").resolve()
        rg_bin = (offline_dir / "rg").resolve()
        # unified_exec 的 sidecar。**少了它容器里每一次工具调用都失败**，
        # 而且模型连"把 goal 标成 blocked"都做不到（那也是工具调用），
        # 结果是跑满预算、零产物、不报错。宿主机上实测空转 47 轮才发现。
        sidecar_bin = (offline_dir / "codex-code-mode-host").resolve()
        # 沙箱助手。缺了它 app-server 每次起都报
        #   "Codex could not find bubblewrap on PATH ... will use the bundled bubblewrap"
        # 并计入 error_event_count。和当初漏 code-mode sidecar 是同一类错：
        # vendor 树里有，但上传清单没带上。
        bwrap_bin = (offline_dir / "codex-resources" / "bwrap")
        if not codex_bin.is_file():
            raise FileNotFoundError(
                f"离线 codex 二进制不存在: {codex_bin}。"
                " 用 stage_codex_offline.sh 从宿主机的 @openai/codex 包里取出来。"
            )
        if not sidecar_bin.is_file():
            raise FileNotFoundError(
                f"codex-code-mode-host 不存在: {sidecar_bin}。"
                " 重跑 stage_codex_offline.sh —— 旧版脚本只抠 codex 和 rg，"
                " 缺 sidecar 会让容器里的工具面静默全废。"
            )

        await self.exec_as_root(environment, command=f"mkdir -p {_STAGE_DIR}")

        await environment.upload_file(codex_bin, f"{_STAGE_DIR}/codex")
        await environment.upload_file(sidecar_bin, f"{_STAGE_DIR}/codex-code-mode-host")
        if rg_bin.is_file():
            await environment.upload_file(rg_bin, f"{_STAGE_DIR}/rg")
        if bwrap_bin.is_file():
            await environment.upload_file(bwrap_bin, f"{_STAGE_DIR}/bwrap")

        # install 而不是 mv：一步搞定权限位，且目标已存在时直接覆盖。
        # 顺便把版本和二进制指纹落进 agent 产物目录：上游 codex.py:370 从事件流里
        # 读 cli_version，但 0.114.0 的 JSON 事件不吐这个字段，harbor 只能记
        # "unknown"，事后没法从产物反查跑的是哪个版本。
        await self.exec_as_root(
            environment,
            command=(
                "set -eu; "
                f"install -m 0755 {_STAGE_DIR}/codex /usr/local/bin/codex; "
                # sidecar 必须和 codex 同目录：codex 按相对自身的位置找它
                f"install -m 0755 {_STAGE_DIR}/codex-code-mode-host "
                "  /usr/local/bin/codex-code-mode-host; "
                f"if [ -f {_STAGE_DIR}/rg ]; then "
                f"  install -m 0755 {_STAGE_DIR}/rg /usr/local/bin/rg; "
                "fi; "
                f"if [ -f {_STAGE_DIR}/bwrap ]; then "
                f"  install -m 0755 {_STAGE_DIR}/bwrap /usr/local/bin/bwrap; "
                "fi; "
                f"rm -rf {_STAGE_DIR}; "
                "mkdir -p /logs/agent; "
                "{ /usr/local/bin/codex --version; "
                "  md5sum /usr/local/bin/codex /usr/local/bin/codex-code-mode-host; "
                "} > /logs/agent/codex_version.txt 2>&1; "
                "cat /logs/agent/codex_version.txt"
            ),
        )

        self.logger.info(f"codex 离线安装完成（来源 {offline_dir}，含 code-mode sidecar）")
