# znq19_KiraAI_history_plugin
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 7 py（跨会话消息历史工具）
- 命中裁决: 生产仅 adapter_mgr.get_adapter + get_client + send_action（get_group_msg/get_history 等 OneBot 动作，main.py:161-337）与少量 client.post——rc1 QQ 客户端接口保留。I 组命中为文案。不碰框架会话库（它走 OneBot 拉真实历史，与 SessionManager 无关）。
- 备注: 建议补 core_version 声明。
