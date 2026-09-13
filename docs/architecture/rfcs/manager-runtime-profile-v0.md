# Manager runtime profile v0 / 管家运行模式 v0

Status: M1 implementation candidate under capable-manager-semantic-handoff-v0 / 强能力管家 RFC 下的 M1 实现候选

## 中文

### 问题

LoopX 管家最初只有受限的规划会话：它可以读取 LoopX 提供的结构化 Goal
上下文，却不能使用安装宿主已有的文件、Shell、Git、Web 或已配置连接器。这适合
默认安装，但会把已经由 Owner 授权的常规工程工作再次退化为转交、等待或人工搬运。

单纯删除提示词限制不够。宿主 sandbox、提示词、工作区说明、持久配置和会话回读
必须表达同一个有效模式，否则 UI 显示“已开放”时，旧会话仍可能运行在只读线程中。

### 契约

`manager_runtime_profile_v0` 是机器级、显式且持久的授权选择：

- `restricted` 是默认值。管家保留作用域化的 LoopX 读取，Codex sandbox 为
  `read-only`。
- `trusted_owner` 允许 Codex 管家使用宿主正常提供的文件、Shell、Git、Web 和已配置
  连接器，Codex sandbox 为 `danger-full-access`。
- `trusted_owner` 不是通用提权。用户请求与既有 standing grant 仍限定工作范围；
  merge、release、deploy、delete、payment 等受保护操作继续走各自的 typed contract；
  外部 provider 权限、受众边界和 LoopX durable state owner 不被改写。
- 当前只有 Codex endpoint 能执行 `trusted_owner`。选择其他 endpoint 时必须返回可恢复的
  typed error，不能把受限执行伪装成已开放。
- `trusted_owner` 当前只对私有 Owner 管家会话生效。外部 audience（包括 Lark 群）是独立
  信任边界；在既有的 audience/resource grant 能被核验前，同一机器配置在那里仍解析为
  `restricted`，不能仅凭“同一管家”继承宿主资源权限。

机器配置沿用现有 capability workbench 的 `preview -> apply -> readback` 流程，不建立第二份
配置源。配置缺失时安全回退 `restricted`；配置损坏时也回退，并在能力投影中显示
`configuration_invalid` 与修复入口。

### 会话一致性

每个 manager Session 保存实际启动时的 profile、sandbox、standing grant、tool classes、
配置 revision 和状态。有效 manager namespace 发生变化时，LoopX 关闭旧上游线程，并用
可见历史启动新线程，避免旧 sandbox 或旧提示词继续生效。其他机器能力的修改不会旋转
健康的管家会话。旧版、默认受限的健康会话只补齐 readback，不做无意义重启。

Dashboard 同时显示机器配置和当前会话 readback。CLI/managed Turn、Dashboard 与 Lark
继续调用同一个 manager runtime controller；Lark 是同源会话的入口和投影，不拥有独立
profile 或权限状态，但当前外部 audience 会明确降级为 `restricted`。后续若开放 Lark
宿主工具，必须复用已有的 audience/resource authority，不在这里新增管家 ACL。

本切片只实现 [capable-manager-semantic-handoff-v0](capable-manager-semantic-handoff-v0.zh-CN.md)
的 M1 私有 Owner 旅程，目标验收为 A1–A3/A12。它不实现 M2 collaboration request、M3
outbox，也不把管家 session 字段当成工作、请求或送达权威。

### 验收

1. 默认安装启动 `restricted`，没有隐式授权。
2. 机器配置 preview/apply/readback 可把 profile 持久设置为 `trusted_owner`。
3. 新 Codex manager thread 的 app-server 请求携带 `danger-full-access`，Turn 提示词和托管
   `AGENTS.md` 不再包含只读限制。
4. profile 改变会旋转上游 thread，但保留 LoopX Session 和可见历史。
5. 不相关机器配置变化不会旋转 thread。
6. 非 Codex endpoint 对 `trusted_owner` fail closed，并给出切换 endpoint 或恢复
   `restricted` 的动作提示。
7. 桌面和移动 Dashboard 显示有效 profile；配置损坏时显示回退状态。
8. 外部 audience 在没有既有 scoped grant 时继续 `read-only`，并显示真实降级状态。

## English

### Problem

The original LoopX manager was a restricted planning conversation. It could read scoped,
structured Goal context but could not use the host's filesystem, shell, Git, web access, or
configured connectors. That is a safe installation default, but it also turns ordinary work
already authorized by the owner into delegation, waiting, or manual context transfer.

Removing a prompt sentence is insufficient. The host sandbox, prompt, managed workspace
instructions, persistent configuration, and Session readback must describe the same effective
mode; otherwise the UI can claim an enabled profile while an old upstream thread remains
read-only.

### Contract

`manager_runtime_profile_v0` is an explicit, persistent machine-level grant:

- `restricted` is the default. The manager keeps scoped LoopX reads and the Codex sandbox is
  `read-only`.
- `trusted_owner` lets the Codex manager use normal host filesystem, shell, Git, web, and
  configured-connector tools. Its Codex sandbox is `danger-full-access`.
- `trusted_owner` is not ambient authority. The current request and existing standing grants
  still bound the work. Protected merge, release, deploy, delete, and payment operations retain
  their typed contracts. Provider permission, audience, and durable LoopX state ownership do
  not change.
- Codex is currently the only endpoint that enforces `trusted_owner`. Other endpoints fail with
  an actionable typed error instead of pretending to provide the selected profile.
- `trusted_owner` currently applies only to the private owner-manager conversation. An external
  audience, including a Lark group, is a separate trust boundary and resolves the same machine
  choice to `restricted` until an existing audience/resource grant can be verified.

Configuration reuses the existing capability workbench and its
`preview -> apply -> readback` transaction. There is no second configuration source. Missing
configuration defaults to `restricted`; invalid configuration also falls back safely and
projects `configuration_invalid` plus a repair action.

### Session consistency

Each manager Session records the profile, sandbox, standing grant, tool classes, configuration
revision, and status used to start its upstream thread. A change to the effective manager
namespace closes the old upstream thread and starts a new one with visible history, preventing
stale sandbox or prompt state. Changes to unrelated machine capabilities do not rotate a healthy
manager. A healthy legacy Session already equivalent to the restricted default is backfilled
without an unnecessary restart.

Dashboard shows both machine configuration and current Session readback. CLI/managed Turn,
Dashboard, and Lark all use the same manager runtime controller. Lark remains an entry point and
projection of that Session; it does not own a separate profile or permission state, but an external
audience currently degrades visibly to `restricted`. Future Lark host-tool access must reuse an
existing audience/resource authority instead of adding a manager-specific ACL here.

This slice implements only the private-owner M1 journey in
[capable-manager-semantic-handoff-v0](capable-manager-semantic-handoff-v0.md), targeting A1–A3/A12.
It does not implement the M2 collaboration request, the M3 outbox, or treat manager Session fields
as work, request, or delivery authority.

### Acceptance

1. A default installation starts `restricted` with no implicit grant.
2. Machine configuration preview/apply/readback persists `trusted_owner`.
3. A new Codex manager thread sends `danger-full-access` to app-server, and its Turn prompt and
   managed `AGENTS.md` no longer contain the read-only restriction.
4. A profile change rotates the upstream thread while preserving the LoopX Session and visible
   history.
5. An unrelated machine-configuration change does not rotate the thread.
6. A non-Codex endpoint fails closed for `trusted_owner` and recommends selecting Codex or
   restoring `restricted`.
7. Desktop and mobile Dashboard show the effective profile; invalid configuration shows its
   fallback state.
8. An external audience without an existing scoped grant remains `read-only` and exposes the
   effective downgrade accurately.
