# znq19_KiraAI-anti-harass-plugin
- 总级: SAFE
- 版本: core_version >=2.29.6（无上界）
- 规模: 3 py（骚扰检测屏蔽）
- 命中裁决: A组"清空"命中均为自有窗口计数注释（harass_detect.py），不涉框架会话 API；G组钩子两代一致；I组"覆盖"命中全是中文注释语义。导入 core.plugin 包级 + LLMRequest + message_elements，rc1 均在。
- 备注: 屏蔽名单为自有存储，与框架会话库无关。
