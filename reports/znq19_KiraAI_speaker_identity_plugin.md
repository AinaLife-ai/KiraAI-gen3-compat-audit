# znq19_KiraAI_speaker_identity_plugin
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 1 py（声纹识别注入）
- 命中裁决: [E] message_format_to_text 命中是注释；机制 on_llm_request 改 req（两代稳定）。导入包级 + Record 元素 + Prompt + LLMRequest，rc1 全在。声纹走外部 HTTP 接口。
- 备注: 无。
