# TODO: distinguish workspace status access failures from service outages

**状态：待实现。** 本文记录错误场景盘点、最小修复范围及验收条件；不改变当前运行行为。

## 问题和责任边界

逐 Goal 加载时，Dashboard 服务可以正常响应目录请求，但生成 Goal 状态所需的
文件或运行时目录不可访问。后端把异常转换为 HTTP 500，前端显示
“本地服务暂时不可用，请重试继续加载”。这会把文件访问权限问题误报为服务不可用，
也会让用户反复重试一个需要先修复权限的问题。

现有链路：`GET /status.json?goal_id=...` → `ChatStatusRequestMixin._status`
→ `collect_status` → 状态依赖读取或 Effect runtime → HTTP 500 → `service` 提示。

归属是现有 Dashboard 状态读取和错误展示边界。涉及的文件是
[chat_status_api.py](../../../loopx/chat_status_api.py)、
[workspace-progressive-status.ts](../../../apps/presentation/dashboard/src/data/workspace-progressive-status.ts)
和 [i18n.tsx](../../../apps/presentation/dashboard/src/features/personal-workspace/i18n.tsx)。
复用 [Effect runtime](../../../loopx/control_plane/effect_runtime.py) 的异常类型与错误码；
无需新增 capability、provider、扩展或通用错误框架。

## 目前有多少场景被归为服务不可用

严格说，当前没有封闭的场景清单：前端把**所有 HTTP 5xx** 都归为 `service`，
不读取错误响应体；后端 `_status` 用 `except Exception` 捕获投影异常。
下面是沿现有路径归纳的 **6 类具体故障来源，加 1 类未知异常兜底**，不是互斥的
运行时枚举，也不是每一项都做过实机复现。只有异常未被内部处理并最终形成
逐 Goal 请求的 5xx 时，才进入这条提示。

| 故障来源 | 现有代码证据或例子 | 用户实际需要区分的原因 |
| --- | --- | --- |
| 1. 文件访问失败 | 注册文件读取、运行时目录创建、启动锁 `os.open` 等抛出 `PermissionError` 或其他 `OSError`；可能包装为 `runtime_request_failed` | 权限拒绝需要检查运行账户及访问权限；其他 I/O 错误不能一律当作权限不足 |
| 2. 注册数据解析失败 | `registry.read_json` 的 JSON 解码失败，或根节点不是对象时抛出 `ValueError` | 数据格式错误，需要检查配置；并不证明服务未启动 |
| 3. 运行时依赖或包异常 | `node_unavailable`、`packaged_runtime_source_unstable` 等 | 检查受支持的 Node 环境或安装完整性 |
| 4. 运行时启动失败 | `startup_lock_timeout`、`runtime_launch_failed`、`runtime_exited_before_ready`、`runtime_startup_timeout` | 运行时启动或就绪失败；其中启动权限拒绝应优先识别为第 1 类 |
| 5. 运行时通信或协议异常 | 请求超时、连接错误、响应过大、JSON 或响应结构异常；可能包装为 `runtime_request_failed` | 区分状态依赖通信失败与浏览器连接 Dashboard 失败 |
| 6. 运行时返回的结构化错误 | `EffectRuntimeRemoteError` 子类：请求拒绝、冲突、临时或永久 I/O、锁超时、内部失败 | 已有 `error_kind` / `diagnostic_code` 的语义不能被“服务不可用”全部覆盖；永久 I/O 也不等于权限拒绝 |
| 兜底：其他投影异常或上游 5xx | `_status` 内未预料的投影、序列化异常；所选状态来源返回的其他 5xx | 未知原因应保持中性说明，不推断权限、网络或依赖故障 |

数据解析依据见 [registry.py](../../../loopx/registry.py)；投影装配依据见
[collection.py](../../../loopx/control_plane/status/collection.py)。

前端目前共有 **6 个加载错误类别**，和上表的故障来源不是同一套分类：

| 前端类别 | 当前触发条件 |
| --- | --- |
| `timeout` | 单次逐 Goal 请求超过 30 秒，被前端取消 |
| `network` | 捕获到 `TypeError`，通常为浏览器 fetch 连接错误 |
| `service` | HTTP 状态码 >= 500 |
| `revision` | HTTP 409，或目录修订号不一致 |
| `scope` | 其他非成功 HTTP 响应，或返回的 Goal 集合与请求不一致 |
| `invalid` | 其余解析或校验异常 |

`timeout`、`network`、`service` 当前最多尝试 3 次。目录请求失败还可能进入旧版完整
状态读取的兼容路径，不能把它和逐 Goal 错误等同。HTTP 200 中的状态健康诊断也不
等于这里的 HTTP 5xx。

邻接入口 [chat.ts](../../../apps/presentation/dashboard/src/data/chat.ts) 也有“Chat 服务暂时不可用”
的 5xx 兜底文案，但会优先使用 `payload.error`；本 TODO 不扩展到 Chat 操作或
“需要宿主确认”的权限审批提示。

## 最小修复 TODO

- [ ] 在状态 API 边界识别直接及包装后的文件权限拒绝，返回稳定、可公开的错误码。
  优先使用异常类型、明确的 errno 或现有结构化错误码，不匹配异常文本中的关键词。
  检查有界的异常因果链，覆盖 `EffectRuntimeStartupError` 包装 `PermissionError`
  的路径；不能把所有启动错误、`OSError` 或 `io_permanent` 都归为权限不足。
- [ ] 前端读取受支持的结构化错误码，将权限拒绝显示为“无法访问 Goal 状态所需的
  本地文件或运行时目录。请检查服务运行账户的访问权限，修复后重试。”，并提供对应
  英文文案。区分真正的 HTTP 401/403 授权失败，不把文件 I/O 问题当作网页授权。
- [ ] 未知或旧版 5xx 保持兼容，并使用“Goal 状态读取失败”一类中性兜底，避免断言
  服务未启动或临时不可用；远程状态来源也不能被无依据地称为“本地服务”。
- [ ] 对已确定的权限拒绝停止自动重试，保留修复后的手动重试；其他类别保留原有
  有界重试行为。变更说明中明确这一处重试行为差异。
- [ ] 保留局部加载隔离：单个 Goal 失败不清空已加载 Goal，不影响其他 Goal 的加载。
  不修改权限、目录所有权、Goal 注册信息，不自动提权或重启服务。
- [ ] 保持错误披露边界：响应和页面不直接输出 `str(exc)`、异常堆栈、完整绝对路径、
  账户名或运行时令牌。用安全的资源类别和建议说明问题；需要精确路径时仅使用已有
  明确授权的本地诊断渠道，本次不新增诊断数据存储。

前瞻整理仅限现有错误分类边界：优先复用 Effect runtime 的结构化错误，避免再造一套
运行时状态规则。上表其他故障先保留为后续分类依据，不要求本轮全部新增 UI 类别。

## 验收 TODO

- [ ] 直接 `PermissionError` 与启动异常包装的 `PermissionError` 都得到权限专用提示；
  负例覆盖 Node 不可用、启动超时、非权限永久 I/O、未知异常和未知错误码。
- [ ] 旧版或非 JSON 的 5xx 可安全兜底；现有超时、网络、修订、范围和响应校验类别
  保持兼容，不因错误体解析失败误变为 `invalid`。
- [ ] 验证权限错误不自动重复请求，普通 5xx 仍有原有重试次数，手动重试可恢复；
  同时加载两个合成 Goal，证明另一个成功 Goal 保留可用。
- [ ] 通过真实 Dashboard HTTP 入口验证错误码、脱敏和恢复流程。仅在可丢弃的临时
  工作区与合成 Goal 上模拟文件访问拒绝；Windows 用受控 ACL，其他平台使用真正
  无访问权限的非特权进程。不得修改活动 Goal 或共享运行目录来制造失败。
- [ ] 覆盖中英文展示，并验证响应体、页面和公开测试材料均不包含敏感诊断内容。

完成实现后，将本记录改为已解决并链接修复 PR；本次文档提交不代表上述验收已经通过。
