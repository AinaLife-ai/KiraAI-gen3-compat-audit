## 修复：3.0 下 ON_MESSAGE_SENT 补广播静默失效（导入路径双形态化）

### 问题
`main.py` 的 `_broadcast_sent` 里局部导入 `from core.plugin.plugin_handlers import event_handler_reg, EventType`。该模块在 v3.0.0-rc.1 已删除（拆分为 `core/plugin/handlers.py`），导入落入兜底 except → 补广播永远静默跳过——手动转发的合并卡片发出去了，但订阅 `ON_MESSAGE_SENT` 的下游插件（sustained / memory / token-stats 等）完全感知不到。2.x 不受影响。

### 修法（3 行）
- 优先 `core.plugin.handlers`（3.0+，已核实 `EventType`/`event_handler_reg` 在 `handlers.py:20/102`），`ImportError` 回退旧路径（2.x）。
- 特征识别（try-import 候选链），**不绑版本号**；符号两代同名同语义（`EventHandlerRegistry.get_handlers`），行为零变化。

### 变更面
- `main.py`：导入双形态化（+5/-1）
- `manifest.json`：version 1.0.2 → 1.0.3
- `README.md`：安装节补兼容性声明（2.33.1+ 与 3.0 全系列）

### 验证
- 仓内 `tests/test_no_duplicate.py`：12/12 通过（幂等与降级语义不变）
- 双世代静态检查：两代框架（v2.34.8 / v3.0.0-rc.1 `8a0b812`）导入核实、无已删符号直用、无版本号绑定——全绿
