# Qixuan112_KiraAI_Group-Manager-Plugin
- 总级: SAFE-NOTE
- 版本: core_version 未声明
- 规模: 3 py（群管理：禁言/名片/撤回/成员查询）
- 命中裁决:
  - [F] adapter_mgr.get_adapter + get_client + send_action 全系（main.py:212-342,475,1072,1214）→ rc1 QQ 适配器 get_client/send_action 保留（qq.py:167, client.py:491）→ 安全
  - [F] main.py:1294 `message_types=adapter.message_types` → rc1 兼容 property（base.py:38）功能正常，仅 deprecated → 建议迁移 supported_elements
  - [G] "comment"命中为加群验证消息文案——误报
  - 导入 `from core.chat import KiraIMMessage, User, Group, Session, MessageChain` → rc1 core/chat/__init__.py 全导出 → 安全
- 备注: 群管动作全走 OneBot send_action，与框架会话/模型层零耦合。
