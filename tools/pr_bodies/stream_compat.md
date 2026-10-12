## 修复：3.0 上插件加载即 ModuleNotFoundError（v1.1.1）

### 问题
`main.py` 顶部**裸导入** `from core.utils.model_clients import OpenAICompatibleLLMClient / TTSClient`。
该模块在 v3.0.0-rc.1 已删除（公共客户端迁至 `core.provider.openai_compatible`，三类客户端核实存在于该文件）——
插件在 3.0 上**导入期直接崩溃，无法加载**。2.x 不受影响。

### 修法（候选链探测，不绑版本号）
- 主导入改三代候选链：先试 `core.provider.openai_compatible`（3.0+），`ImportError` 回退 `core.utils.model_clients`（2.x）。
- STT 客户端的可选降级语义在两代各自保留（旧有 `try/except` 设计原样搬入两个分支）。
- 删除一处会"回盖"的旧 STT 导入块（不修会在 3.0 上把新分支解析到的 STT 客户端覆盖回 None）。
- 覆写兼容性已核实：子类 `chat/chat_stream/__init__` 签名与 rc1 基类一致；Provider 注册直写的
  `_registry/_manifests/_manifest_dirs/_schemas` 四个类属性两代同构（rc1 `register_provider_type` 写的也是这四个）。

### 变更面
- `main.py`：导入区重构（+14/-6）
- `manifest.json`：version 1.1.0 → 1.1.1
- `README.md`：版本兼容注补 3.0 全系列说明

### 验证
- 两代导入路径模拟执行均解析成功（3.0 走新模块、2.x 走旧模块、STT 降级语义各自保持）
- 双世代静态检查全绿（含"已删模块不得裸导入"项）
