# znq19_KiraAI_accelerator_plugin
- 总级: NEEDS-FIX
- 版本: manifest version 1.0.81 / core_version `>=2.33.1`（无上界 → rc.1 通过 manager 的 SpecifierSet(prereleases=True) 校验，不会被挡）
- 规模: 66 个 .py（生产 12：main.py / auto_thinking.py / stream_engine.py / stream_first.py / early_sent.py / patches.py / breaker.py / core_compat.py / parallel_tools.py / request_compat.py / config_migrations.py / wallpapers_api.py；其余 54 个在 tests/）；入口 main.py（BasePlugin，事件 ON_LLM_REQUEST/RESPONSE、AFTER_XML_PARSE、ON_MESSAGE_SENT/ON_TOOL_RESULT；页面 + REST API）
- 特点: 本仓自带较完整的跨世代兼容层（core_compat.py 用 importlib 按新→旧候选解析模块；patches.py 的 install() 对缺失属性返回 None 并 warning）。所以大部分 2.x→rc.1 断点被优雅降级，但**核心功能在 rc.1 上静默失效**。

- 命中裁决:
  - [E] main.py:1698 `install(h, MessageProcessor, "send_xml_messages", factory)` → **真命中**。rc.1 `core/message_manager.py` 的 `MessageProcessor` **不存在** `send_xml_messages`（全 core 已 grep 无此符号，发送路径迁到 `MessageDeliveryService.send_message_chain` / `workflow/src/im/stages/execute.py`）。`install()` 取不到 attr → warning + 跳过 ⇒ **本插件的招牌功能「抢先发送 / 边写边发」在 rc.1 上完全不生效**（streaming 仍可，因挂在 get_model_client 上）。属功能破坏，非崩溃 → NEEDS-FIX。
  - [E] main.py:985 `await mp._parse_xml_msg(seg, ctx.tag_set)` → **真命中**。rc.1 `MessageProcessor` 无 `_parse_xml_msg`（迁为 `MessageDeliveryService.parse_xml` 静态方法；`_add_message_ids`→`add_message_ids`）。此处被 `try/except Exception` 包住 ⇒ AttributeError 被吞、静默 `return False`（整段交回框架）⇒ 又一次「抢发降级为不抢发」，且不报错。→ NEEDS-FIX。
  - [B] main.py:1864-1868 `api_providers`：`for mid in llm.keys(): {"value": f"{pid}:{mid}", "label": f"{mid} ({pname})"}` → **真命中**。rc.1 `ProviderManager.get_models()` 返回 `{type: {internal_id: {"model_name":..., "config":...}}}`，`internal_id = uuid.uuid4().hex`（已核 `core/provider/model_identity.py:generate_model_id` / `provider_manager.py:372`）。**label 只取 key（内部 uuid），未读 `entry["model_name"]`** ⇒ 面板下拉/状态文本在 rc.1 显示 32 位十六进制乱码（正是用户关注的「展示变 UUID」）。`value` 用 `provider_id:internal_id` 反而是 rc.1 正确引用格式，无需改。→ NEEDS-FIX。
  - [C] main.py:687-744 patch `ProviderManager.get_model_client`；main.py:640 patch `OpenAICompatibleLLMClient._build_client`；main.py:1208 patch `_build_request_kwargs(self, request, **overrides)` → **SAFE-with-compat**。逐项核 rc.1：`get_model_client(provider_id, model_id, model_type=None)` 签名一致（`provider_manager.py:135`）；`_build_client(self)->AsyncOpenAI` 存在（`openai_compatible.py:45`，读 `self.model.provider_config`，与插件缓存键 base_url/api_key/headers 一致）；`_build_request_kwargs` 存在且 rc.1 已按 `model=self.model.model_name` 发上游（`openai_compatible.py:66`）。类解析走 `core_compat.openai_compatible_client()`（候选 `core.provider.openai_compatible` 存在 / 回退 `core.utils.model_clients`）。注意 rc.1 provider 停用时 `get_model_client` **抛 ProviderAPIError**（:162），插件 wrapper 未捕获 → 与框架同行为、非新增破坏。
  - [A] 「会话 API」组全 68 命中 → **误报/无害**。生产代码**未调用任何会话读写 API**（无 session_mgr / get_session / update_memory / read_memory / fetch_memory / get_existing_memory_snapshot 调用），命中全在 docstring/README/tests。唯一真实代码触点是 main.py:1500 `install(h, SessionManager, "_save_memory", factory)`：rc.1 `SessionManager` **已无 `_save_memory`/`_load_memory`**（改用 DB + `_load_legacy_memory`，见 session_manager.py:39-47）⇒ attr=None ⇒ warning + 跳过；且该功能 `compact_memory_dump` **默认关**。→ 误报（功能本就可选，缺失时静默跳过，无崩溃、无重复发送）。
  - [D] core_compat.py / patches.py / tests 命中「plugin_registry / plugin_handlers」→ **误报**（注释与 importlib 候选表；rc.1 实际路径 `core.plugin.handlers` 已被列为**首选**候选，`event_handler_reg`+`EventType` 均在 `core/plugin/handlers.py:20,102`）。
  - [F] 仅 tests 中 `message_types=` 构造 → **误报**（测试桩，非生产 emit）。[H] 仅 tests 一处 `selfie` 字符串 → **误报**。[G] ON_LLM_REQUEST/ON_LLM_RESPONSE/AFTER_XML_PARSE/ON_MESSAGE_SENT/ON_TOOL_RESULT 均存在于 rc.1 `EventType`（handlers.py:20-35），`@on.llm_request/...` 均存在（decorators.py:168-192）→ **SAFE**。
  - [I] 直读/patch 框架文件 150 命中 → 生产侧 **误报**（关键字「覆盖」多为「override/覆盖」语义注释；无 open 框架 .py / shutil 覆盖）。真实行为是**猴补丁**：经 patches.install() 幂等/可还原/带熔断，目标符号除上列 E 两项外均在 rc.1 存在。tests 中 importlib 加载框架模块属测试手段。
  - 补充扫盲：`@register.api`/`@register.tool`/`@register.page`+`PageMenu`+`PluginPage.from_folder` 均在 rc.1（decorators.py:29/76/13, pages.py:69）；`from core.plugin import BasePlugin,logger,on,Priority,register,PluginPage,PageMenu` 全部存在；`core.provider.LLMRequest/LLMResponse`、`core.chat.message_utils.KiraMessageBatchEvent/KiraIMSentResult`、`core.tag.RootTagAction`、`core.chat.MessageChain`、`core.provider.src.deepseek.DeepSeekLLMClient`、`core.provider.src.anthropic.AnthropicCompatibleLLMClient`、`core.agent.func_tool_manager.FuncToolManager/tool_logger`、`core.utils.tool_utils.BaseTool`、`core.agent.tool.ToolResult`、`core.chat.message_elements.Text`、`core.provider.llm_model.LLMStreamChunk` 全部命中 rc.1。

- 修复方案(NEEDS-FIX):
  1) main.py:1698（`_install_early_sent_strip`）：rc.1 已无 `MessageProcessor.send_xml_messages`。最小修法——探测可补丁目标：
     `target = MessageProcessor if hasattr(MessageProcessor,"send_xml_messages") else (service.method if 可定位)`；
     更实际的 rc.1 落点是 patch `MessageDeliveryService.send_message_chain`（`core/workflow/src/im/message_delivery.py:59`），或在 `ctx.message_delivery` 上包一层；同时把 main.py:985 的 `mp._parse_xml_msg` 改为 `await self.ctx.message_delivery.parse_xml(seg, ctx.tag_set)`（rc.1 为静态方法）。参照手册 E 条迁移表（`parse_xml`/`add_message_ids`）。风险：`send_message_chain` 是每链调用，剥离台账需按「链」而非「段」重新对账。
  2) main.py:1866 label：
     ```python
     for mid, entry in llm.items():
         name = entry.get("model_name") if isinstance(entry, dict) else None
         out.append({"value": f"{pid}:{mid}",
                     "label": f"{name or mid} ({pname})",
                     "provider_id": pid, "provider_name": pname, "model_id": mid})
     ```
     （照抄手册 B 节 `_model_entry_name` 模式；2.x 分支 entry 非 dict 时回退 `mid`。）
  3) 非阻断项：main.py:1435-1436 `mp.min_message_delay` 在 rc.1 已迁到 `MessageDeliveryService`（getattr 默认 0.0 兜底 → 发送间隔不生效但不报错），如需保真改为读 `ctx.message_delivery.min_message_delay`。

- 备注: 兼容层质量较高（importlib 候选、缺失即 warning 跳过、猴补丁可还原+熔断），但**两条 rc.1 破坏点（E 的 send_xml_messages/_parse_xml_msg、B 的模型 label 用内部 uuid）让「边写边发」静默失效且面板显示 UUID 乱码**，需按上表最小修复。
