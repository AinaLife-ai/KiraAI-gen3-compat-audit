---
name: kiraai-plugin-dev
description: Complete KiraAI robot framework plugin development skill. Use for any KiraAI plugin work: create/design/modify/debug plugins under data/plugins, BasePlugin, @register.tool/@on.* hooks, schema.json, manifest, PluginContext APIs, tag creation, adapter operations, KiraAI WebUI pages, KiraAI integration patterns, or when the user mentions "kira plugin / kiraai 插件 / kira 机器人插件 / KiraAI Plugin".
---

# KiraAI Plugin Development

Production-grade guide for building KiraAI plugins that integrate cleanly with the framework (hooks, tool calls, message delivery, WebUI).

**CRITICAL — 开发 / 修改 / 测试 / 排查插件前，必须先读本文件 + 对应 reference，并把关键约束应用到代码里；禁止凭记忆写 KiraAI 代码。**

## Repository Layout

| Path | Purpose |
|------|---------|
| `data/plugins/{id}/main.py` | Plugin entry |
| `data/plugins/{id}/manifest.json` | Metadata (`plugin_version`, `core_version`) |
| `data/plugins/{id}/schema.json` | Config schema (auto WebUI form) |
| `data/plugins/{id}/README.md` | Human docs |
| `plugins/{id}/` | **Built-in official plugins** (different path from data/plugins) |

## The Rules (ALWAYS obey)

1. **面向 3.0 正式版开发**——本 skill 对齐 **`v3.0.0`+**；需要兼容 2.x 最新版时按 `02-patterns.md` 附录 A 的特征识别写法，**绝不写版本字符串判断**。
2. **`manifest.core_version` 用 `>=x.y.z` 无上界**（框架 `prereleases=True`，对 rc/alpha 放行）；**绝不写上界**（`>=2.24.3,<3.0.0` 会在 3.0 直接被拒载）。
3. **优先 hook 注入，少修改主流程**——能用 `@on.*` / `@register.tool` 就别接管 `on_im_message`。
4. **适配器差异必须考虑**——通用用 `@register.tag` / `IMCapability` 能力接口；需 `get_adapter(...)` 直发时能力探测 + `adapter_name` 白名单。
5. **会话 API 全异步**（3.0）：`get_session / update_session / get_sessions / get_effective_capabilities / delete_session / flatten_content` 必须 await——**不得 sync 调用异步接口（静默拿到 coroutine 是全生态第一翻车点）**。
6. **模型身份已分离**：`model_id`=内部稳定 ID（uuid 形态，存配置/传参用它），`model_name`=可读名（**展示用它**）；面板/日志显示 uuid 形态一律视为 bug。
7. **别吃错**——工具/命令必须明确错误信息（LLM/用户可读），不允许静默 except。

## Decision Tree

```
User wants to add plugin behavior
├─ "reply when / listen to messages" → @on.im_message (read-only) or @on.message_received
├─ "LLM can call X"                 → @register.tool + ToolSet
├─ "send rich message"              → @register.tag (preferred) or adapter API
├─ "config panel"                   → schema.json (auto UI)
├─ "web page"                       → @register.page / @register.api / @register.static
├─ "persist data"                   → self.ctx.get_plugin_data_dir() (JSON/SQLite)
├─ "schedule / cron"                → asyncio.create_task (self-managed)
├─ "react to comments"              → @on.comment (KiraCommentEvent)
└─ "inter-plugin comms"             → KiraCustomEvent / plugin_registry
```

## Quick Start (2 min)

1. Read `references/01-api.md` → hook signatures, ctx methods, message types
2. Read `references/02-patterns.md` → 5 proven templates + 3.0/2.x 陷阱清单
3. Copy nearest pattern, adapt, keep it under ~200 lines for simple plugins
4. **Hot reload dev loop**: 修改插件代码 → WebUI 插件管理里手动"重载"，或重启框架。插件的 `manifest.json` / `schema.json` 改动**需要重启框架**才会生效

## Manifest Template (REQUIRED)

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "description": "What it does",
  "author": "you",
  "plugin_version": "1.0.0",
  "core_version": ">=3.0.0rc1",
  "configs": {},
  "dependencies": {},
  "python_dependencies": []
}
```

**`core_version` 陷阱**：`>=3.0.0` **不会**匹配 rc 版（PEP440 语义）——要覆盖仍在 rc 的环境写 `>=3.0.0rc1`；要双世代通吃写 `>=2.24.3`（推荐）。

## Key APIs (memorize)

| Need | Code |
|------|------|
| Listen IM messages | `@on.im_message(priority=50)` (post-decision; read-only) |
| Hook before send | `@on.im_message_sent(priority=50)` |
| Pre-LLM edit | `@on.llm_request(priority=50)` |
| Tool for LLM | `@register.tool(name="x", description="...")` + `async def x(self, **kw) -> ToolResult` |
| Custom XML tag | `@register.tag("mytag")` + `def handle(self, content, **attrs) -> MessageChain` |
| Config value | `self.config.get("key")` (from schema.json) |
| Plugin data dir | `self.ctx.get_plugin_data_dir()` (auto-created) |
| Send message | `await self.ctx.send_message_chain(adapter, type, id, chain, is_group=)` |
| Logger | `self.logger.info(...)` (auto-prefixed) |
| Async task | `self.task = asyncio.create_task(self._loop())` in `on_load` |
| LLM text call | `await llm_client.chat(request).get_openai_response()` → `resp.content` |
| Session read | `await self.ctx.session_mgr.get_session(sid)` → `.flatten_content()` |
| Session caps | `await self.ctx.session_mgr.get_effective_capabilities(sid)` |
| Capability check | `im = adapter.get_capability(IMCapability)`（无则跳过） |

## Common Failures & Fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Plugin not loading | manifest `core_version` 不满足 / `id` 含大写或空格 | 无上界声明；`[a-z0-9_]+` |
| Hook never fires | Wrong event name / not awaited in async / 会话是异步接口没 await | Check `01-api.md` Hooks table；async 接口全 await |
| 拿到 coroutine 当数据用 | **没 await 会话/能力接口**（3.0 全异步） | 返回值先 `inspect.isawaitable` 检查，或老老实实 await |
| Tool not visible to LLM | `description` too vague / missing ToolResult | Clear desc; always return `ToolResult` |
| Tag not parsing | `@register.tag` name mismatch / 在 `if self.ctx:` 之外注册 | Exact match in `<mytag>` |
| 面板显示一串 uuid | 把内部 `model_id` 当名字展示 | 用 `model_name`（或 `provider_id:model_id` 反查 entry） |
| Config not saving | schema.json `type` mismatch | Check 01-api Config table |
| "MessageChain object has no attribute X" | Treating MessageChain as str | Use `chain.message_list` / iterate |
| 插件改了不生效 | 修改了 manifest/schema 但没重启框架 | 重启框架；纯代码改动可手动重载 |

## Reference Files (read as needed)

| File | When to read |
|------|-------------|
| `references/01-api.md` | Hooks, PluginContext, MessageChain, Adapter ops, schema field types |
| `references/02-patterns.md` | Copy-paste patterns, XML tag DSL, **3.0/2.x 陷阱清单**, 测试规范, 2.x 双世代兼容附录 |

## Anti-Patterns (NEVER do these)

```python
# ❌ 接管/包装框架方法时把签名写死（3.0 给发送落点加过 bot= ⇒ 写死签名的包装当场全灭）
async def send_message_chain(d_self, session, chain, *, memory_message=None, self_id=None):
    return await original(d_self, session, chain, memory_message=memory_message, self_id=self_id)
# ✅ 只取自己要的，其余原样透传（绝不 try/except 重试：发送有副作用，重试=重发）
async def send_message_chain(d_self, session=None, chain=None, *args, **kwargs):
    return await original(d_self, session, chain, *args, **kwargs)

# ❌ 给发送 API 传 self_id=（3.0 已改名 bot=，会 TypeError）
await delivery.send_message_chain(sid, chain, self_id=bot_id)

# ❌ 版本字符串判断（绑死某个版本，框架一演进必翻车）
if __version__.startswith("3.0"): ...

# ❌ 版本号上界（3.0 直接拒载）
"core_version": ">=2.24.3,<3.0.0"

# ❌ GA 弃用入口（@deprecated，将废弃）
await ctx.message_processor.send_message_chain(sid, chain)      # → await ctx.send_message_chain(sid, chain)
await ctx.message_processor.flush_session_messages(sid)         # → await ctx.flush_session_messages(sid)
await ctx.message_processor.handle_im_message(event)            # → await ctx.event_bus.publish(event)
adapters = ctx.adapter_mgr.get_adapter_infos()                  # → get_adapters_info()（2.x 已有新名）
els = adapter.message_types                                     # → adapter.get_capability(IMCapability).get_message_metadata().supported_elements
event = KiraMessageEvent(message_types=els, ...)                # → supported_elements=（双世代用 dataclasses.fields 探测字段名）
await adapter.send_group_message(gid, chain)                    # → adapter.get_capability(IMCapability).send_group_message(...)（2.x 无 get_capability ⇒ 回落直调）

# ❌ 会话接口不 await（3.0 全异步，拿到 coroutine 静默退化）
caps = sm.get_effective_capabilities(sid)

# ❌ 2.x 已删 API
sm.fetch_memory(sid); sm.write_memory(sid, ...); sm.chat_memory[sid]
# ❌ 直读 chat_memory 的「探测形态」也是坑：getattr(sm, "chat_memory", None) 在 3.0 拿到 None ⇒ 静默空结果

# ❌ 内部 ID 当名字展示
label = model_info.model_id   # uuid 形态 → 面板上一串乱码

# ❌ 已删的模块路径（3.0 拆包）
from core.plugin.plugin_registry import PluginManager
from core.plugin.plugin_handlers import event_handler_reg
from core.utils.model_clients import OpenAICompatibleLLM

# ❌ 阻塞 event loop / 静默吞错
time.sleep(10)
except: pass

# ❌ 插件根目录乱写（必须 get_plugin_data_dir）
open("./data.txt", "w")
```

## Pro Tips

- **schema.json auto-generates WebUI** ——改字段即出配置面板，零前端代码
- **默认聊天插件是活教材**（`core/plugin/builtin_plugins/chat/main.py`）——复杂缓冲/消息监听都在里面
- **测试用真框架跑**（cp 进 `data/plugins/`，从框架根跑脚本）；`PluginContext` 构造按签名探测填充新必填字段
- **3.0 会话是 SQLite 持久化**（`core/chat/session_manager.py`），`update_session(sid, content=[])` 是"清空上下文保元数据"的官法
