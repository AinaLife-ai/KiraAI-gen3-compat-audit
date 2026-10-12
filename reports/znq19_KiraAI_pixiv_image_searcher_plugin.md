# znq19_KiraAI_pixiv_image_searcher_plugin
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 2 py（Pixiv 搜图发送）
- 命中裁决: [F] adapter_mgr.get_adapter + get_client + `callable(getattr(client,'send_action',None))` 探测（main.py:647-664），rc1 QQ 客户端接口保留；官方机器人平台有显式回退路径（单条直发）。导入 core.plugin 包级 + path_utils.get_data_path（rc1 在）。
- 备注: 无。
