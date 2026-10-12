# znq19_KiraAI_group_member_viewer_plugin
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 1 py（群成员查询）
- 命中裁决: [F] main.py:91 adapter_mgr.get_adapter → get_client() → client.send_action("get_group_member_list")（main.py:115 一带）→ rc1 QQ get_client/send_action 均在（qq.py:167, client.py:491）。try/except 包裹，非 QQ 平台返回 None 优雅降级。
- 备注: 无。
