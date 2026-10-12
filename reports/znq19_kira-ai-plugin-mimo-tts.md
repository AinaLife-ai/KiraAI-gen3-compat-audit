# znq19_kira-ai-plugin-mimo-tts
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 7 py（小米 MiMo 语音合成）
- 命中裁决: D/E/F 命中（plugin_handlers/plugin_registry/MessageProcessor/send_xml_messages/emoji_dict/message_types）**全部在 tests/_harness.py 与 test_pipeline.py**（自带 2.x 形态测试桩）——生产 main.py 导入仅 core.plugin 包级 + MessageChain + message_elements + LLMResponse + get_data_path，rc1 全在。合成走小米官方 HTTP API，无框架耦合。
- 备注: 测试桩是 2.x 形态——在 3.0 框架 checkout 上跑自带测试会红，但生产运行不受影响。建议补 core_version 声明。
