## 适配 3.0 rc.1：会话域全异步化 + 模型域语义 + skills/mcp 入口（v1.2.1）

### 问题（rc.1 实测三域破坏，多为静默）
1. **会话域全灭**：`session_inventory`（`get_session_info()` rc.1 已删）→ 列举返回空并触发 `_known()` 空集
   连锁误判「session not found」；`session_cap` 的 `info/memory_count/title/caps/memory_clear/delete`
   全用已删的同步 API；`delete_session` 未 await（丢 coroutine，**没删却报 deleted=true**）；
   `ctx.get_session_capabilities` 未 await。
2. **模型域**：`models` 列表只显示内部 ID（rc.1 起 key 是 uuid）——运维面板读不出模型；
   `add_model` 的 `found` 核对拿用户传的展示名去比内部 ID 键 → 注册成功却报 `registered=false`。
3. **skills/mcp 域**：`getattr(message_processor, "skills_manager"/"mcp_manager")` 在 rc.1 是 None
   （rc.1 规范入口在 `PluginContext.skills_mgr`/`mcp_mgr`）→ 两域静默失效 + 删会话后的范围清理静默跳过。

### 修法（特征识别，不绑版本号）
- 会话域：`session_inventory` 与 `session_cap` 的读写处理器全面异步化（分派器本就容忍 awaitable，零改框架侧）；
  新增 `_sm_get/_sm_count/_sm_update_info/_sm_clear/_sm_caps/_sm_caps_update/_sm_effective` 双世代助手
  （`hasattr` + `__await__` 鸭子探测）。**memory_clear 两代都只清对话内容、保留会话标题与能力设置**。
- 模型域：`models` 显示「可读名 [内部ID]」（同名只显示一次）；`add_model` 用 `register_model` 的
  返回值（rc.1 返回内部 ID）回填核对，2.x 回退原名核对。
- skills/mcp 域：优先 `ctx.skills_mgr`/`ctx.mcp_mgr`，旧 `message_processor.*` 路径兜底；
  删会话后的范围清理同此探测。
- `ChatMemory` 的 `_exists` 畸形键修复语义保留（2.x raw 直查；3.0 DB 约束下走 `get_session(ensure_session=False)`）。

### 测试桩同步双世代化（tests/）
- `PluginContext` 构造：新增 `_ctx_extra()` 懒探测（rc.1 的 7 个必填新字段 None 填充 + `sticker_mgr` 改名适配）
- `plugin_registry`/`plugin_handlers` 导入候选链；`data/skills` 目录初始化
- 假传输接线改**实例级遮蔽**（`ctx.send_message_chain = fake`），两代都能截获发送；
  rc.1 下给 `owner` 补 `_FakeDelivery`（复刻真委托的路由逻辑）
- `test_panel_contract` 的 `_panel_payload` 调用改 `asyncio.run`（产品侧因会话枚举异步化）

### 验证（两代真框架各跑一遍）
| 套件 | 2.x (v2.34.8) | 3.0 rc.1 |
| --- | --- | --- |
| test_kira_ops / races / gaps / dm_confirm / adversarial / panel_contract | 全 OK | 全 OK |
- 双世代静态检查全绿

### 变更面
`main.py` / `caps/session_cap.py`（重写两个处理器）/ `caps/provider_cap.py` / `caps/skill_cap.py` /
`caps/mcp_cap.py` + `tests/` 五文件双世代化 + `manifest.json`（1.2.0→1.2.1）+ `README.md`
