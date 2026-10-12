# znq19_KiraAI_token_stats_plugin
- 总级: SAFE
- 版本: core_version >=2.29.7
- 规模: 2 py（main.py 6405 行 + html_render）
- 命中裁决:
  - [B] **已正确双世代适配**（main.py:1106-1130,4069-4071 注释自述）：`getattr(mi,'model_name',None) or getattr(mi,'model_id',None)` —— 正是手册 B 节推荐模式，面板下拉与统计表都不会显 UUID
  - [G] 统计读 `resp.input_tokens/output_tokens/cached_tokens` → 两代 llm_model.py:139-144 完全一致 → SAFE
  - [A] 4 命中全为 README/注释/自有缓存清空——误报；[C] provider_mgr(:4055) 仅列模型用
- 备注: rc1 兼容已完成，文档中可标注 ✓
