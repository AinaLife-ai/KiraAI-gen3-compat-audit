# znq19_KiraAI_payload_defense_plugin
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 1 py（LLM 注入清洗）
- 命中裁决: [G] on_im_message/on_llm_request 钩子两代一致（rc1 decorators.py:150）。导入 core.plugin 包级 + core.provider.LLMRequest + message_elements(Text/Image/Sticker/Record/File/Video) + prompt_manager.Prompt——逐一核实 rc1 全存在。
- 备注: 纯消息清洗，不碰会话/模型。
