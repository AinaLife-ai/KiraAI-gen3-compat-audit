# znq19_KiraAI_output_word_replacer_plugin
- 总级: SAFE
- 版本: manifest 1.0.0 / core_version 未声明
- 规模: 1 py（输出词汇替换钩子）
- 命中裁决: 预扫描 CLEAN。导入 core.plugin 包级；走 on_llm_response 类钩子改文本，不碰会话/模型 API。
- 备注: 建议补 core_version 声明。
