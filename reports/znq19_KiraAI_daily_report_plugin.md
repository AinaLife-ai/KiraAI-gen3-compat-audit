# znq19_KiraAI_daily_report_plugin
- 总级: SAFE-NOTE
- 版本: core_version 未声明
- 规模: 4 py（群日报，main.py 2000+ 行）
- 命中裁决:
  - [F] main.py:518/1999/2003 `await adapter.send_group_message(...)` → rc1 BaseAdapter 通用层虽无此方法，但 **rc1 QQ 适配器类保留了委托方法**（qq.py:170-173 `return await self.im.send_group_message(...)`），本插件只作用于自动探测到的 QQ 适配器（main.py:270-352 实例名探测逻辑）→ 功能正常
  - [H] persona_mgr.get_persona/list_personas（:949-1026）rc1 在且插件已正确 await → SAFE
  - [A] 「清空」命中为自有配置迁移（适配器实例名失效原子写回）——误报；G 组为业务词「锐评」——误报
- 备注: 依赖「QQ 适配器有 send_group_message 委托」这一非契约事实——rc1 核实存在，但若未来框架删掉委托需迁 `adapter.get_capability(IMCapability).send_group_message`。建议补 core_version 声明。
