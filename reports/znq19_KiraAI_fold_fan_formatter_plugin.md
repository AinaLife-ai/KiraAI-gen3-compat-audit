# znq19_KiraAI_fold_fan_formatter_plugin
- 总级: NEEDS-FIX
- 版本: core_version >=2.33.1
- 规模: 2 py（合并转发折叠卡片）
- 命中裁决:
  - [D] main.py:39 `from core.plugin.plugin_handlers import event_handler_reg, EventType` → **真命中**：rc1 的 plugin_handlers.py 模块已删除（见 kira30/core/plugin/ 目录，无此文件）；等效物在 rc1 `core/plugin/handlers.py:20(EventType),102(event_handler_reg)`。2.x 在 plugin_handlers.py:101。→ rc1 上 ImportError，插件无法加载
  - 其余 adapter_mgr/get_adapter 用法安全
- 修复方案: main.py:39 改双形态导入：
  ```python
  try:
      from core.plugin.handlers import event_handler_reg, EventType      # 3.0+
  except ImportError:
      from core.plugin.plugin_handlers import event_handler_reg, EventType  # 2.x
  ```
  符号两代同名同语义（EventHandlerRegistry.get_handlers），行为无变化，风险极低。
- 备注: 单点导入路径破坏，修复成本极小——**适合本会话直接修**。
