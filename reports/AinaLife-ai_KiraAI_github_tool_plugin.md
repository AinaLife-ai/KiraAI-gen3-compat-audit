# AinaLife-ai_KiraAI_github_tool_plugin
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 1 py（GitHub REST 工具，curl 直调）
- 命中裁决: [D] main.py:10 注释显示作者已知 3.0 registry 重构（未依赖旧路径）；G组命中全是 GitHub API 的 comment 词——误报。导入 core.plugin 包级 + core.provider.llm_model.LLMRequest（rc1 llm_model.py:20 在）+ prompt_manager.Prompt——核实通过。
- 备注: 无框架敏感面。
