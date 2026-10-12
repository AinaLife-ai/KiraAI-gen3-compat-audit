# znq19_KiraAI_deepwiki_plugin
- 总级: SAFE
- 版本: core_version 未声明
- 规模: 1 py（DeepWiki MCP 查询，约 1700 行）
- 命中裁决: A组 15 命中全为**自有**「/dw clear 清除候选上下文」命令语义（自有候选存储，非框架会话 API）——误报；I组命中均为中文注释。导入 core.plugin 包级 + message_elements(Text/At) + MessageChain，rc1 均在。
- 备注: 其"clear"只清自有候选列表，不碰 SessionManager，无 rc1 会话破坏面。
