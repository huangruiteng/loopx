# 创建 standalone Extension

本章从 LoopX 官方 scaffold 创建 `loopx-text-stats`。官方 scaffold 提供完整可运行基线；本章
给出需要收窄的 manifest、request/response 合同、核心函数与验证步骤，不依赖配套练习仓库。

## 成功标准

完成后，你应该能观察到：

- scaffold 是独立 Python package；
- manifest 使用 `loopx_extension_manifest_v0`；
- request 与 response 都有 versioned JSON Schema；
- provider 只从 stdin 读取一个 JSON object，并向 stdout 写一个 JSON object；
- doctor 无 side effect；
- 不合法 request 在工作开始前 fail closed；
- manifest 与 runtime 都声明零权限。

## 1. 生成官方 scaffold

从一个准备存放示例的工作目录运行：

```bash
loopx extension init loopx-text-stats \
  --destination standalone-extension \
  --execute \
  --format json
```

`extension init` 默认只预览；必须显式加 `--execute` 才写文件。目标目录必须不存在，即使空目录也会
被拒绝。命令不会自动 build、install、register 或 enable。

生成结构：

```text
standalone-extension/
├── extension.toml
├── pyproject.toml
├── README.md
├── examples/
│   └── request.json
├── schemas/
│   ├── request.schema.json
│   └── response.schema.json
└── src/
    └── loopx_text_stats/
        ├── __init__.py
        └── cli.py
```

这是 complete standalone path，不会猜测 `[[provides]]` 或 `[[implements]]` 所需的
Capability authority。

## 2. 读取 manifest

scaffold 生成并经本章收窄后的 manifest：

```toml
schema_version = "loopx_extension_manifest_v0"
id = "loopx-text-stats"
version = "0.1.0"
requires_loopx_api = ">=1,<2"
permissions = []

[runtime]
protocol = "loopx_text_stats_extension_v0"
entrypoint = "loopx-text-stats"
doctor_args = ["--doctor"]
required_permissions = []
timeout_seconds = 30
```

关键约束：

- `id` 是 lifecycle identity；
- `version` 参与 revision 与升级；
- `requires_loopx_api` 明确兼容窗口；
- `protocol` 是 provider wire contract；
- `entrypoint` 必须存在于 LoopX 所在 Python environment 的 `PATH`；
- `doctor_args` 指向只读 readiness probe；
- `permissions` 与 `required_permissions` 都为空；
- timeout 由 managed runtime 固定，调用者不能任意覆盖。

## 3. 定义 request contract

示例 request：

```json
{
  "schema_version": "loopx_text_stats_request_v0",
  "text": "LoopX keeps project state explicit.\nExtensions keep delivery lifecycle explicit."
}
```

request schema 要求：

- payload 必须是 object；
- `schema_version` 必须精确匹配；
- `text` 必须是包含非空白字符的 string；
- `additionalProperties` 为 false。

拒绝额外字段很重要。假如 caller 传入：

```json
{
  "schema_version": "loopx_text_stats_request_v0",
  "text": "hello",
  "path": "/tmp/input.txt"
}
```

provider 必须拒绝，而不是擅自把 `path` 理解为文件读取授权。schema 是 bounded request 的一部分。

## 4. 实现纯计算

示例的核心函数：

```python
def analyze_text(text: str) -> dict[str, int]:
    return {
        "characters": len(text),
        "non_whitespace_characters": sum(
            1 for character in text if not character.isspace()
        ),
        "words": len(re.findall(r"\S+", text)),
        "lines": len(text.splitlines()) or 1,
    }
```

它具有适合作为首个 standalone Extension 的性质：

- 同一输入得到同一输出；
- 不访问环境变量；
- 不读取文件；
- 不访问网络；
- 不写外部系统；
- 不依赖 LoopX project state。

provider 在计算前完成结构验证，错误也通过 versioned response object 返回：

```json
{
  "ok": false,
  "schema_version": "loopx_text_stats_response_v0",
  "extension_id": "loopx-text-stats",
  "error": "extension input has unsupported fields ['path']"
}
```

不要把 traceback、环境变量或本机路径直接输出到 public receipt。

## 5. 定义 response contract

成功 response 的稳定 domain 部分：

```json
{
  "ok": true,
  "schema_version": "loopx_text_stats_response_v0",
  "extension_id": "loopx-text-stats",
  "request_schema_version": "loopx_text_stats_request_v0",
  "result": {
    "characters": 80,
    "non_whitespace_characters": 71,
    "words": 10,
    "lines": 2
  }
}
```

response schema 使用 `oneOf` 区分成功与失败。测试应断言 domain contract，而不是绑定 LoopX CLI
外层展示的每个字段，否则 minor release 的 receipt 扩展会导致无意义失败。

## 6. 保持 doctor 无副作用

starter 的 doctor：

```python
if args.doctor:
    return 0
```

对于这个纯计算 provider，readiness 只需要证明 entrypoint 可启动和参数可解析。doctor 不应：

- 创建文件；
- 连接网络；
- 写入凭据；
- 修改 extension state；
- 产生业务 effect；
- 输出未经约束的大量日志。

真实 Provider 可以做必要的只读依赖检查，但 readiness probe 仍应有界、可重复、无 effect。

## 7. 安装 package 并运行 tests

在同一个 Python environment 中：

```bash
cd standalone-extension
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e '.[test]'
python3 -m pytest
```

同环境要求不是偶然限制。LoopX lifecycle 根据已安装 console entrypoint 验证 provider；如果 package
装在另一个 venv，正确结果是 `entrypoint_missing`，而不是静默寻找任意源码路径。

## 常见错误

### 手写一个比 scaffold 更小的目录

容易漏掉 schema、doctor、manifest compatibility 或 package entrypoint。先生成完整官方路径，再删改
不需要的领域字段。

### 让 provider 接受任意 kwargs

这会破坏 bounded request，并可能意外扩大权限。request schema 和 provider validation 应同时
fail closed。

### 用 doctor 执行业务请求

doctor 证明 readiness，不证明某个 effect 已获授权。业务调用必须通过 managed runtime 或
Capability/domain command。

### 为演示擅自增加 permission

一旦有 permission，`extension run` 会拒绝直接调用。先确定真实 Capability 和 authority，再设计
effectful provider，不要为了展示 manifest 字段制造假的权限合同。
