# 生命周期与 managed runtime

package 安装与 LoopX activation 是两个独立阶段。LoopX 不负责下载任意 package，也不允许 caller
传入任意 executable；它管理一个经过 doctor、绑定 revision 的 provider lifecycle。

## 本章目标

读完后，你应该能：

- 区分 Python package install 与 LoopX extension install；
- 完成 install、doctor、run、disable、enable、upgrade 与 rollback；
- 解释 preview 与 `--execute` 的关系；
- 判断什么时候 generic standalone runner 必须拒绝请求。

## 1. 安装 Python package

从包含 `standalone-extension/` 的工作目录创建环境：

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e './standalone-extension[test]'
```

这一步使 `loopx-text-stats` console entrypoint 出现在当前 environment。它不改变 LoopX extension
activation state。

检查 provider 自身：

```bash
loopx-text-stats --doctor
loopx-text-stats < standalone-extension/examples/request.json
```

直接执行 entrypoint 只适合开发调试。面向用户的支持路径是 `loopx extension`。

## 2. 预览并安装 Extension

先预览：

```bash
loopx extension install \
  --manifest standalone-extension/extension.toml \
  --format json
```

再执行：

```bash
loopx extension install \
  --manifest standalone-extension/extension.toml \
  --execute \
  --format json
```

install 会：

1. 读取 declarative manifest；
2. 检查 API compatibility 与 permissions；
3. 解析已安装 entrypoint；
4. 运行只读 doctor；
5. 记录 validated manifest snapshot 与 revision；
6. 激活该 revision。

它不会：

- 从网络下载 package；
- 运行任意 caller executable；
- 授予新权限；
- 把 provider output 存进 activation state；
- 读取你的项目 Goal。

## 3. 查看与复查 readiness

```bash
loopx extension list --format json
loopx extension doctor loopx-text-stats --execute --format json
```

`doctor --execute` 会真实运行 probe。readiness 绑定 active manifest revision 与 resolved runtime
identity；如果 executable 被替换或环境变化，旧 doctor proof 不再可信。

失败的 doctor 不应自动切换 revision。它会清除 stale readiness，等待环境修复和新的 probe。

## 4. 通过 managed runtime 调用

先预览：

```bash
loopx extension run loopx-text-stats \
  --input-json standalone-extension/examples/request.json \
  --format json
```

执行：

```bash
loopx extension run loopx-text-stats \
  --input-json standalone-extension/examples/request.json \
  --execute \
  --format json
```

managed runtime 固定：

- extension id 与 active revision；
- entrypoint 与 args；
- stdin/stdout JSON protocol；
- timeout；
- permissions；
- request input limit；
- stdout/stderr limit。

caller 不能附加 shell args 或替换 executable。超时和输出超限会终止 provider process group，
避免子进程在 LoopX 报告停止后继续运行。

`run` 只支持：

- enabled；
- doctor-ready；
- 有 runtime；
- 没有 `[[provides]]` / `[[implements]]`；
- manifest 与 runtime permissions 都为空；
- request 满足 bounded protocol；
- caller 显式 `--execute`。

任何不满足条件的 Extension 都应 fail closed。

## 5. Disable 与 enable

```bash
loopx extension disable loopx-text-stats --execute --format json
```

disabled Extension 仍可在 lifecycle state 中观察，但不是 dispatch candidate。此时 `extension run`
应失败。

重新启用：

```bash
loopx extension enable loopx-text-stats --execute --format json
```

enable 不会信任旧 readiness；它会重新运行 doctor，成功后才设置 enabled bit。

## 6. Upgrade 与 rollback

升级前先修改 package 与 manifest version，并把新 package 安装到同一 environment。然后预览：

```bash
loopx extension upgrade \
  --manifest standalone-extension/extension.toml \
  --format json
```

执行：

```bash
loopx extension upgrade \
  --manifest standalone-extension/extension.toml \
  --execute \
  --format json
```

upgrade 在切换 active revision 前验证并 probe 新 manifest。失败 probe 保持当前 revision，不应出现
“升级失败但旧版本也不可用”的半状态。

回滚：

```bash
loopx extension rollback loopx-text-stats --execute --format json
```

rollback 同样先 probe previous revision，再切换。它不是任意 Git checkout 回退，而是 activation
state 中已验证 revision 的生命周期转换。

## 7. 隔离示例状态

在 CI 或教程中，可以使用 `--state-file` 指向临时文件，避免污染用户的默认 runtime state：

```bash
state_file="$(mktemp)"
rm -f "$state_file"

loopx extension install \
  --state-file "$state_file" \
  --manifest standalone-extension/extension.toml \
  --execute \
  --format json
```

临时文件可能包含本机 runtime identity，不应提交到任何公开仓库。

## 何时不能使用 standalone `run`

以下需求必须进入 Capability 或 domain command：

- 读写文件；
- 访问需要授权的 API；
- 发送消息；
- 发布内容；
- 管理外部资源；
- 修改项目状态；
- 需要 action/scope authority 的任何 effect。

effectful dispatch 由 Capability 在 domain policy 检查后创建 request-bound execution envelope，绑定：

- exact action；
- structured effect scope；
- extension id 与 active revision；
- provider request digest。

envelope 不是 service credential，也不替代外部系统自己的 authorization。caller 自带 envelope、
scope 变宽、request 改变或 revision 不匹配都必须 fail closed。

## 故障定位

| 症状 | 优先检查 |
| --- | --- |
| `entrypoint_missing` | package 是否安装在运行 `loopx` 的同一 environment |
| install preview 成功但 list 没变化 | 是否遗漏 `--execute` |
| doctor stale | executable、interpreter 或 module source 是否变化 |
| run 报 disabled | 运行 `enable --execute` 并查看 doctor |
| run 拒绝 permissions | 该 Provider 是否应进入 Capability/domain command |
| upgrade 未切换 | 新 revision doctor 是否失败 |
| rollback 不可用 | 是否存在 validated previous revision |

生命周期失败时修复 contract 或环境，不要绕过 managed runtime 直接把 provider 当作已激活。
