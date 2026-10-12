## 修复：3.0 兼容两点（导入路径 + 快速模型标识可读性）

### 问题
1. `main.py:266`（`execute_tool` 内）裸导入 `from core.plugin.plugin_handlers import event_handler_reg, EventType`。该模块在 v3.0.0-rc.1 已删除（拆分为 `core/plugin/handlers.py`），3.0 上一旦启用自定义工具超时（`_tool_timeout > 0`）即 ImportError，工具执行链路报错。
2. `_models_hint_text` 展示「webui 快速模型」时用内部标识（3.0 起是 uuid 形态的内部稳定 ID），用户读不懂。

### 修法（特征识别，不绑版本号）
1. 导入改候选链：优先 `core.plugin.handlers`（3.0+，符号已核实存在于 `handlers.py:20/102`），`ImportError` 回退旧路径（2.x）。符号两代同名同语义。
2. 拆分「粘贴值」与「展示名」：
   - `_fast_model_label()` 保持返回**可粘贴的配置值**（3.0 下必须填内部 ID，rc1 的 `resolve_model_entry` 只按内部 ID / legacy_ids 解析，展示名拼不进去）；
   - 新增 `_fast_model_display()` 用于给人看的场景：优先 `model_name`（3.0 的可读名），附可粘贴标识；2.x 无 `model_name` 属性自动回退，行为不变。
   - `_models_hint_text` 的可选模型提示改用展示版。

### 变更面
- `main.py`：+25/-2
- `manifest.json`：version 1.1.1 → 1.1.2
- `README.md`：补兼容性声明 + 3.0 下 `available_models` 填内部 ID 的指引

### 验证
- 双世代静态检查全绿（两代框架导入核实 / 无未守卫的已删符号 / 无版本号绑定）
- `python -m ast` 语法核验通过；2.x 行为路径零改动
