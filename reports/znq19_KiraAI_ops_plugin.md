# znq19_KiraAI_ops_plugin
- 总级: NEEDS-FIX
- 版本: manifest version `1.2.0` / core_version `>=2.34.6`（仅下界，无上界，**不会**挡 3.0）
- 规模: 34 个 py；入口 `main.py`（KiraOpsPlugin），域能力在 `caps/*.py`，工具面 ops_status/ops_read/ops_config/ops_action/ops_store
- 导入层: 全部 SAFE。`core.plugin{BasePlugin,PageMenu,PluginPage,Priority,logger,on,register}`、`core.chat.Session`、
  `core.chat.message_elements.Text`、`core.chat.message_utils{KiraMessageBatchEvent,MessageChain}`、`core.provider.LLMRequest`、
  `core.prompt_manager.Prompt`、`core.utils.path_utils{get_config_path,get_data_path,get_root_path}`、
  `core.logging_manager.log_cache_manager` 在 rc.1 均存在（逐一 grep 核实）。插件在 rc.1 **能加载**，破坏全在运行期会话/模型域。

## 命中裁决
### [A] 会话 API（会话域 = 会话API高危，实测全灭）
- `main.py:287 session_inventory()` → `sm.get_session_info()`；rc.1 SessionManager **已删**该符号
  （`kira30/core/chat/session_manager.py` 仅 `get_sessions/get_session`）→ 抛 AttributeError，被 except 吞掉后走
  `getattr(sm,"chat_memory",None)`（`main.py:290`）→ rc.1 **无此属性** → 返回 `([], [])`。
  → **连带** `session_cap.py:40/68` 的 `_known()` 得到**空集合**（非 None）→ rc.1 上任何合法 sid 的 `info/memory_count`
  都返回 `session not found`，`list` 永远空。→ **NEEDS-FIX**
- `caps/session_cap.py:105 sm.get_session_info(sid)`、`:154 update_session_info`、`:164 write_memory`、
  `:77/:132/:163 get_memory_count` → rc.1 全部**已删** → AttributeError（读路径被 except 转成 "not found"，写路径由
  `main.py:1030` 的 except 转成报错）。→ **NEEDS-FIX**
- `caps/session_cap.py:48 getattr(sm,"chat_memory",None)`（`_exists`）→ rc.1 无 → 退化为枚举，仍失效。→ **NEEDS-FIX**
- `caps/session_cap.py:114/:161 sm.get_effective_capabilities(...)`、`:160 update_session_capabilities(...)`、
  `:170 delete_session(...)`、`:108 ctx.get_session_capabilities(sid)` → 2.x 同步 / rc.1 **变异步**，插件**未 await**：
  `:170 delete_session` 丢 coroutine → **会话根本没删**却回 `deleted=True`；`:108` 在同步 `handle_read` 里拿到 coroutine
  → `.items()` AttributeError。→ **NEEDS-FIX**
- 清空上下文写法：`session_cap.py:163-164` 用 `get_memory_count`+`write_memory(sid,[])`（2.x 整体替换式）。
  rc.1 正确姿势应优先 `await update_session(sid, content=[])`（保留 title/data/capabilities），而非 delete+重建。→ **建议升级**
- 备注：`get_memory_count`/`write_memory`/`get_session_info`/`update_session_info` 在 rc.1 均无 compat shim；插件**无任何**
  hasattr/iscoroutine 探测。CHANGELOG/README/*.md 中的同名出现（预扫描 A 组大部分）为文档 → **误报**。

### [B] 模型身份分离（模型展示高危 — 会显示 uuid）
- `caps/provider_cap.py:164 found = mid in ((pm.get_models(pid) or {}).get(mtype) or {})`：rc.1 `get_models` 返回
  `{kind:{internal_id:{...}}}`（`provider_manager.py:372`），键是**内部 uuid ID**；用户传的 `model_id` 与其不等 →
  `add_model` 成功却回 `registered=False`。→ **NEEDS-FIX**
- `caps/provider_cap.py:145-150`（models 动作）返回 `{str(k): sorted(v or {}) for k,v in models.items()}` = **仅内部 uuid 键**，
  从不取 `entry["model_name"]` → 面板/命令展示**全是乱码 ID**（用户关切点命中）。→ **NEEDS-FIX**
- `caps/provider_cap.py:161 pm.register_model(pid,mtype,mid,cfg)`：rc.1 第 3 参语义变为 **model_name**，返回生成内部 ID
  （`provider_manager.py:352`）；插件仍当它是 model_id 用。→ **NEEDS-FIX**
- `:175 update_model`/`:187 delete_model`：rc.1 第 3 参须为**内部 ID**；插件 schema/文档以展示名/自造 id 引导 → 易失配。
- `schema.json:196`、`main.py:137/1306` 的 model_id/model_name 仅是 write_allow 字段名清单 → **误报**。
- 前端 `web/app.js` 无模型面板（不渲染模型）→ 展示问题仅在 provider_cap 输出。

### [D]/[E] 插件路径与内部字段（无崩溃，静默退化）
- `main.py:880 await self.ctx.flush_session_messages(sid)` → rc.1 存在（`plugin_context.py:110`，async，**已 await**）→ SAFE。
- `caps/skill_cap.py:33-34 getattr(message_processor,"skills_manager")`、`caps/mcp_cap.py:24-25 ..."mcp_manager"`、
  `session_cap.py:172/178`、`main.py:494/1116/1124/1527/1528`：rc.1 `MessageProcessor.__init__(im_workflow)` **无**这俩属性，
  它们在 workflow/lifecycle，且 ctx 规范名是 `skills_mgr`/`mcp_mgr` → getattr 默认 None → **技能域/MCP 域整体报 "manager unavailable"、
  会话删除后 skills/mcp scope 清理静默跳过**。→ **SAFE-NOTE（建议改用 ctx.skills_mgr/ctx.mcp_mgr）**
- 旧符号 `core.plugin.plugin_registry`/`plugin_handlers`、`core.utils.model_clients`、`workflow_registry`、`SessionBuffer`、
  `message_types`、`IMAdapter` 等**只出现在 tests/**（测试桩）→ 生产代码 **误报**。

### 其余组
- [C] Provider：`getattr(ctx,"provider_mgr")` 存在；`register_model/update_model/delete_model/sync_models/fetch_remote_models/
  health_check/set_provider` 在 rc.1 均在，且插件已用 `hasattr(res,"__await__")` 兼容返回 awaitable；`register_model` 返回 None 时
  `update_model` 的 bool(res) 语义亦可用 → **SAFE-with-compat**（除 B 的语义错配）。
- [F] 适配器/能力：生产代码**零命中**，全在 tests → **误报**。
- [G] 事件/钩子：`@on.llm_request/@on.im_message/@on.custom_event` + `Priority.LOW` + `@register.tool/.page/.api/.api`、
  `PluginPage.from_folder` 在 rc.1 均在，未用 SYS_* → SAFE。
- [H] 人设：`persona_cap.py` 全异步调用 `persona_mgr.list_personas/get_active_persona/get_persona/set_active_persona/
  create_persona/update_persona/delete_persona`，与 rc.1 `core/persona/persona_manager.py` **完全一致** → SAFE。
- [I] 直读/patch 框架：无 open(框架.py)/importlib(框架)/猴子补丁；`core/backup.py`、`store/installer.py` 的 shutil 仅备份
  config 与自更新自身插件目录，用 `plugin_mgr.plugin_dir/prepare_plugin_reload/load_plugin_from_dir`（rc.1 均在）→ SAFE。
- [plugin_mgr] `plugin_cap.py`/`agent_cap.py` 用的 `get_plugin_info/list_plugins/is_plugin_enabled/get_plugin_config/
  update_plugin_config/has_plugin/set_plugin_enabled/reload/get_plugin_schema/get_plugin_inst` + `info.uninstallable`
  在 rc.1 `core/plugin/manager.py`+`metadata.py` 均在 → SAFE。
- manifest：`core_version >=2.34.6` 无上界 → 双世代可安装。CHANGELOG/README/设计方案.md 命中 → **误报**。

## 修复方案（NEEDS-FIX）
1. **会话域（caps/session_cap.py + main.py.session_inventory）**：加 rc.1 探测分支 ——
   `sm=ctx.session_mgr`；枚举用 `await sm.get_sessions(include_content=False)`（列表元素取 `s.sid`/`s.session_title`），
   存在性用 `await sm.get_session(sid)`（None=不存在）；`info` 用返回的 Session 对象（`session_title/session_description/content`）；
   `memory_count` 用 `len(session.content)` 或 `await sm.get_session_message_counts()`；
   `title` → `await sm.update_session(sid, title=..., description=...)`；`memory_clear` → `await sm.update_session(sid, content=[])`；
   `caps` → `await sm.update_session_capabilities(sid, caps)`；`delete` → `await sm.delete_session(sid)`。
   兼容写法参考手册 A 节：`if hasattr(sm,"update_session") and inspect.iscoroutinefunction(...): ... elif hasattr(sm,"write_memory"): ...(2.x)`。
   `_known()` 的返回值语义需区分「空枚举」与「枚举失败」（rc.1 下现在恒为空集合 → 误判 not found）。
2. **ctx.get_session_capabilities**：`session_cap.py:108` 改 `merged = await self.ctx.get_session_capabilities(sid)`（handle_read 需变 async，或整体 await 化）。
3. **模型域（caps/provider_cap.py）**：`add_model` 把入参按 rc.1 语义传 `register_model(pid,mtype,model_name,cfg)` 并用**返回的内部 ID**回填；
   `models` 展示改为 `_model_entry_name(mid,entry)`（entry 含 `model_name` 时显示之，否则回退 mid）；`found` 判断改用返回 ID；
   `update_model/delete_model` 明确要求内部 ID（文档与 schema 同步说明）。参照手册 B 节 Z 插件模式。
4. **skills/mcp（skill_cap.py:33、mcp_cap.py:24）**：`_mgr()` 改为优先 `getattr(self.ctx,"skills_mgr"/"mcp_mgr")`，回退旧 `message_processor.*`。
- 风险点：rc.1 `content` 结构为 `list[list[dict]]`、角色仅 system/user/assistant/tool，`update_session(content=[])` 是**整体替换**；`get_effective_capabilities/update_session_capabilities/delete_session` 均须 await；会话事件在持久化后发布。

## 备注
- 单行：导入层双世代安全，但**会话域**(get_session_info/update_session_info/write_memory/get_memory_count/chat_memory 全删 + 4 个 API 变异步未 await) 与**模型域**(展示内部 uuid、register_model 语义变更) 双高危确认破坏，另有技能/MCP 域因 `message_processor.skills_manager|mcp_manager` 在 rc.1 为 None 而静默失效。
