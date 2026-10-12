# AinaLife-ai_KiraAI_hotnews_plugin
- 总级: SAFE-NOTE
- 版本: core_version 未声明
- 规模: 2 py（热搜推送）
- 命中裁决:
  - [F] main.py:116 `message_types=ada.message_types` → rc1 BaseAdapter.message_types 是 @deprecated property 仍可用（base.py:38-39）；KiraMessageEvent 旧 kwarg 有 _accept_legacy_message_types 兼容 → 功能正常，仅 DeprecationWarning
  - adapter_mgr.get_adapter rc1 在
- 备注: 建议择机把 message_types= 迁到 supported_elements=（非阻塞）。
