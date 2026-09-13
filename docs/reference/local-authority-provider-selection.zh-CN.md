# Local Authority Provider 选择

LoopX 现在为所有 provider-first coordination command 提供一个 typed 的
local-provider 边界。Goal 没有 selector 时，边界解析为 `file` profile
（`source_authority=file_v0`）。这使 File/SQLite provider 语义成为默认的
local contract，同时不会静默晋升已有的 Markdown Goal，也不会改变其 writer
fence。

## 选择 contract

`openLocalAuthorityStoreHandle(runtime_root, goal_id)` 返回一个 handle：

| 字段 | 含义 |
| --- | --- |
| `store` | 与 provider 无关的 `AuthorityStore` 实现 |
| `provider` | `file`、`sqlite` 或 `postgresql` |
| `sourceAuthority` | provider 证据标签（`*_v0`） |

没有 selector 时使用显式的默认 File profile。SQLite selector 继续使用已有
的 `loopx_local_authority_provider_v0` marker 及其 database incarnation。
PostgreSQL selector 使用同一 marker schema，并额外绑定 `tenant_id` 与
`postgresql:<32 位小写十六进制>` store identity。

PostgreSQL marker 不包含 URL、凭据或 database client。打开它必须提供由
service 持有的 `openPostgresqlStore` factory。factory 只接收经过校验的公开
binding facts，并且必须返回带 PostgreSQL 标签、且 identity 与 selector 一致
的 `AuthorityStore`。这是中期可切换 PostgreSQL profile 的 runtime seam；它
不包含 authenticated service，也不会向 Agent 授予数据库访问权。

## 失败与兼容规则

- 已选择的 provider 在 selector、数据库、factory、identity 或 metadata 不可用
  时，绝不回退到 File。
- `source_authority` 即使在打开失败时也标识被选择的 provider；选择未解析或
  格式错误时返回 `null`。
- 选择/打开失败时 `decision_read_from_provider` 为 false，
  `legacy_fallback_used` 始终为 false。
- 旧的 `openLocalAuthorityStore` 函数仍只返回 store，已有 caller 保持源码兼容。
  runtime entrypoint 统一使用一个 opening seam，不再重复构造 provider。
- provider identity 只是可观测 metadata，不负责决定 Todo eligibility、claim、
  lease、receipt 或 promotion。

默认 profile 是路由决策，不是迁移。已有 Markdown state、writer fence、
qualification gate 以及 File/SQLite 显式 promotion hold 均保持不变。在 shared-
authority RFC 的 D2 证据和 owner approval 完成前，SQLite 仍是 opt-in 的
qualified candidate；PostgreSQL 仍是独立的 service-provider qualification 路径。

## 验证

provider selection matrix 使用 production-scale synthetic coordination fixture
验证。测试覆盖默认 File handle、SQLite 持久化、selected provider 失败时不回退、
PostgreSQL factory identity fencing，以及 factory 返回其他 provider 时的拒绝。
File、SQLite 和 PostgreSQL 继续共享 provider-neutral transaction conformance
contract；PostgreSQL 的真实服务器 qualification 仍是独立 gate。
