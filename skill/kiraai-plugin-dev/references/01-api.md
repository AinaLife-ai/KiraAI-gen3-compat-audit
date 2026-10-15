# KiraAI Plugin API Reference (3.0 GA)

> 对齐 `xxynet/KiraAI` **`v3.0.0` 正式版（GA）**（commit `9db3d67`）。rc2→GA 插件面零变更；**GA 起弃用标记正式生效**（`ctx.message_processor.{send_message_chain, flush_session_messages, handle_im_message}`、`get_adapter_infos`、适配器 `.message_types`、事件构造 `message_types=`、适配器直调 `send_*`、`ConfigType.Enum/EnumField`）——对照与双世代写法见仓根 `../docs/GA_DEPRECATIONS.md`。2.x 差异见 `02-patterns.md` 附录 A。

## Table of Contents

1. [BasePlugin](#1-baseplugin)
2. [Hooks (@on.*)](#2-hooks-on)
3. [Tools (@register.tool)](#3-tools-registertool)
4. [Tags (@register.tag)](#4-tags-registertag)
5. [PluginContext](#5-plugincontext)
6. [Message Objects](#6-message-objects)
7. [Adapters](#7-adapters)
8. [Config (schema.json)](#8-config-schemajson)
9. [Web UI](#9-web-ui)
10. [Async Patterns](#10-async-patterns)
11. [Logging & Utils](#11-logging--utils)
12. [Manifest](#12-manifest)
13. [3.0 会话与模型身份](#13-30-会话与模型身份)

---

## 1. BasePlugin

`core/plugin/base.py`（3.0 已从单文件拆为 `core/plugin/` 包）：

```python
from core.plugin import BasePlugin, on, register

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.logger.info("Plugin initializing")

    def on_load(self):
        """Called when plugin is loaded (register stuff here)"""
        self._register_my_tools()

    def on_unload(self):
        """Cleanup on unload"""
```

**Attributes:**
| Attr | Type | Description |
|------|------|-------------|
| `self.ctx` | PluginContext | Framework context (see §5) |
| `self.config` | dict | Plugin config (from schema.json) |
| `self.logger` | logging.Logger | Auto-prefixed logger |

---

## 2. Hooks (@on.*)

Defined in `core/plugin/handlers.py`（3.0 新路径；2.x 是 `core/plugin/plugin_handlers.py`）：

```python
from core.plugin import on

@on.im_message(priority=50)          # After message processing decision (read-only)
@on.message_received(priority=50)    # Raw message received (before processing)
@on.llm_request(priority=50)         # Before LLM call (can edit request)
@on.llm_response(priority=50)        # After LLM response
@on.stream_llm_response(priority=50) # Per-token stream events
@on.message_final(priority=50)       # Final composed message
@on.im_message_sent(priority=50)     # Before IM message is sent
@on.notice(priority=50)              # System notices
@on.error(priority=50)               # Error events
@on.comment(priority=50)             # Feed/comment events (KiraCommentEvent)
@on.tool_result(priority=50)         # After tool execution
```

**Signature:** `async def handler(self, event: KiraMessageEvent) -> None`

**Event properties (KiraMessageEvent):**
| Prop | Type | Description |
|------|------|-------------|
| `event.message_chain` | MessageChain | Received message |
| `event.adapter_name` | str | Source adapter ("qq", "wechat", ...) |
| `event.session_type` | str | "group" / "private" / "temp" |
| `event.session_id` | str | User/group ID |
| `event.sender_id` | str | Sender user ID |
| `event.sender_name` | str | Sender nickname |
| `event.stop()` | method | Stop propagation to lower-priority handlers |
| `event.is_stopped` | bool | Check if stopped |

**Priority:** Lower number = earlier execution. Use 50 (default) unless ordering matters.

**CRITICAL — 3.0 内部会话接口已全异步**：钩子里凡是碰 `session_mgr` 的方法都要 `await`（见 §13）。

---

## 3. Tools (@register.tool)

```python
from core.plugin import register
from core.agent.tool import ToolResult   # pydantic: content, image, video, file, extra

@register.tool(
    name="get_weather",
    description="Get current weather for a city. Returns JSON.",
    params={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
            "days": {"type": "integer", "description": "Forecast days", "default": 1}
        },
        "required": ["city"]
    }
)
async def get_weather(self, city: str, days: int = 1, **kwargs) -> ToolResult:
    try:
        data = await fetch_weather(city, days)
        return ToolResult(content=json.dumps(data, ensure_ascii=False))
    except Exception as e:
        return ToolResult(content=f"Error: {e}", is_error=True)
```

**Rules:**
- Tool name: snake_case, unique across ALL plugins (conflicts → both may fail)
- Description: Tell LLM **when** to call this (it decides based on description)
- Always return `ToolResult`, never raise
- `is_error=True` → LLM sees failure, can retry/report
- 工具返图/视频：`ToolResult(image=Image(...))` 或经 `media_refs.store_session_media` 生成引用（框架会把 refs 挪到工具结果后的 user 消息——部分 provider 不接受 tool 角色带图）

---

## 4. Tags (@register.tag)

Tags parse XML-like syntax in LLM output into rich messages:

```python
from core.plugin import register
from core.chat.message_utils import MessageChain, At, Image

@register.tag("mention")
def handle_mention(self, content: str, **attrs) -> MessageChain:
    """<mention uid="12345"/> → @user"""
    uid = attrs.get("uid")
    if not uid:
        return MessageChain([f"[invalid mention]"])
    return MessageChain([At(uid)])
```

**Usage in LLM prompt:**
```xml
<mention uid="12345"/>
<image url="https://..."/>
<mytag someattr="value">inner content</mytag>
```

**Available message elements** (`core/chat/message_elements.py`):
`Text, At, Image, Video, File, Reply, Forward, Xml, Json, Face(emoji), Music, Location`

**官方内置标签**（`core/plugin/builtin_plugins/kira-ai/tags.py` + `file_send_policy.py`）：`<at>/<img>/<video>/<file>/<reply>/<forward>/<json>/<music>/<face>`；`<file>` 发送受策略控制，引用它就不要再造一个。

---

## 5. PluginContext

Accessed via `self.ctx`. **3.0 注入面**（比 2.x 多出 7 个新字段）：

**Methods:**

| Method | Description |
|--------|-------------|
| `ctx.get_plugin_data_dir()` | Plugin's data directory (auto-created) |
| `ctx.send_message_chain(session, chain, *, bot=None)` | Send message to a session。`session` 形如 `adapter:dm|gm:id`；**rc2 起**可传 `bot=`（记录出站历史身份），**勿传 `self_id=`** |
| `ctx.get_llm_client(model_id, provider_id=None)` | Get LLM client by model config |
| `ctx.flush_session_messages(session_id, filter_fn=None)` | Force-flush message buffer（3.0 支持按事件过滤，返回 bool） |
| `ctx.publish_notice(...)` | 系统提示消息 |
| `ctx.get_session_capabilities(sid)` | **3.0 已异步**：`await` 后得能力 dict |
| `ctx.register_provider(provider)` | 插件自带 Provider |
| `ctx.register_adapter(adapter)` | 插件自带 Adapter |

**Direct attributes:**

| Attr | Description |
|------|-------------|
| `ctx.event_bus` | 事件订阅总线（KiraCustomEvent 是单处理器，**勿订阅**，走 @on） |
| `ctx.db` | DatabaseService（业务 mixin：贴纸/图描缓存/人格/商店源/遥测） |
| `ctx.session_mgr` | SessionManager（**3.0 全异步 + SQLite**，见 §13） |
| `ctx.persona_mgr` | 人设（PersonaInfo 新增 reference_image_path/chat_rules/私聊规则/群聊规则） |
| `ctx.config` | 框架全局配置 |
| `ctx.prompt_mgr` | Prompt 管理 |
| `ctx.llm_request_params` | 全局 LLM 参数模板 |
| `ctx.message_processor` | MessageProcessor（3.0 只剩转发/兼容入口） |
| `ctx.plugin_mgr` | 插件管理器 |
| `ctx.message_history` | **3.0 新增**：结构化消息历史服务 |
| `ctx.image_desc_cache` | **3.0 新增**：图片描述缓存 |
| `ctx.session_buffer_mgr` | **3.0 新增**：会话缓冲管理器 |
| `ctx.message_delivery` | **3.0 新增**：消息发送服务（`parse_xml`/`add_message_ids`/`min_message_delay` 都搬这了） |
| `ctx.skills_mgr` | **3.0 新增**：Skills 系统（2.x 在 `message_processor.skills_manager`） |
| `ctx.mcp_mgr` | **3.0 新增**：MCP 管理器（2.x 在 `message_processor.mcp_manager`） |
| `ctx.sticker_mgr` | 贴纸管理器（`sticker_manager` 为只读别名） |
| `ctx.adapter_manager` | 适配器注册表（`get_adapter(name)`） |

**3.0 已删**（勿再用）：`ctx.get_image_desc_cache()`（走 `ctx.image_desc_cache`）；`MessageProcessor.send_xml_messages/_parse_xml_msg/_add_message_ids`（搬进 `MessageDeliveryService`）。

---

## 6. Message Objects

### MessageChain

```python
from core.chat.message_utils import MessageChain

# Construct
chain = MessageChain(["Hello", At("123"), Image(url="...")])

# Iterate
for elem in chain.message_list:
    if isinstance(elem, Text): ...
    elif isinstance(elem, Image): ...

# Extract plain text
text = chain.get_plain_text()  # Concatenates all Text elements
```

### Message Elements

| Element | Constructor | Notes |
|---------|-------------|-------|
| `Text` | `Text("hello")` or just `"hello"` in list | Plain text |
| `At` | `At(user_id, name="")` | Mention |
| `Image` | `Image(url="...", base64="...", path="...")` | One source required |
| `Video` | `Video(url="...", path="...")` | |
| `File` | `File(path="...", name="...")` | |
| `Reply` | `Reply(message_id)` | Quote/reply |
| `Face` | `Face(id=...)` | Platform emoji |
| `Forward` | `Forward([chain1, chain2])` | Forwarded bundle |
| `Xml` | `Xml(xml_string)` | Raw XML card |
| `Json` | `Json(dict_or_str)` | JSON card |
| `Music` | `Music(type="qq", id="...")` | Music card |
| `Location` | `Location(lat=, lon=, title=)` | |

### KiraMessageEvent (received)

```python
event.message_chain       # MessageChain
event.adapter_name        # str
event.session_type        # "group" | "private" | "temp"
event.session_id          # str
event.sender_id           # str
event.sender_name         # str
event.is_group            # bool property
event.get_plain_text()    # shortcut
event.supported_elements  # 3.0 标准构造参数（message_types 是兼容别名，勿用）
```

### KiraCommentEvent（@on.comment）

3.0 字段：`comment_id / comment_content / target(FeedRef) / root_comment_id / platform / adapter_name / commenter_id / commenter_nickname / self_id / timestamp`；顶层评论 `root_comment_id == comment_id`。适配器侧能力查询走 `FeedCapability`（`core/adapter/capabilities.py`）。

### KiraCustomEvent（插件间通信）

```python
from core.chat.message_utils import KiraCustomEvent
# 发送
await self.ctx.event_bus.publish(KiraCustomEvent(event_name="my_event", source_plugin=self.plugin_id, payload={"k": 1}))
# 接收（event_name 过滤；不传 = 接收所有）
@on.custom(event_name="my_event")
```

**是单处理器路由**（只派给声明 event_name 的处理器），不是订阅广播——别用 `event_bus.subscribe`。

### KiraErrorEvent（@on.error）

`name / message / traceback / stage / source("plugin"|"provider"|"adapter") / comp_id / e / extra`。

### KiraFinalResult（@on.message_final）

判断单步 vs 多步（工具）轮、汇总发送审计。3.0 `AgentStepResult`：`model_id`=内部模型身份；新增 `model_name`（上游名）与 `assistant_message`（当前步骤 OpenAIMessage，供发送存档关联）。注意此时消息早已发出，`event.stop()` 只阻后续 final handler，不能撤回。

---

## 7. Adapters

### 3.0 能力架构（核心变化）

`adapter_utils.py` 的 `IMAdapter/SocialMediaAdapter/LiveStreamAdapter` **已删**——改为 `BaseAdapter` + 能力对象查询：

```python
from core.adapter.capabilities import IMCapability, FeedCapability

adapter = self.ctx.adapter_manager.get_adapter("qq")
im = adapter.get_capability(IMCapability) if adapter else None
if im:
    await im.send_group_message(group_id, chain)

feed = adapter.get_capability(FeedCapability) if adapter else None
if feed:
    await feed.get_feed(...)   # 全异步
```

**规则**：能力对象不存在 → 该适配器不支持 → 优雅跳过，**绝不 try/except 裸调**。

### 通用方法（BaseAdapter）

```python
adapter.is_running             # bool
await adapter.send_message(...)  # 视能力而定
```

### 拿原始适配器实例（需谨慎）

```python
adapter = self.ctx.adapter_manager.get_adapter("qq")
if adapter and hasattr(adapter, "send_group_message"):
    await adapter.send_group_message(group_id, chain)
```

**Built-in adapters:** `webchat`（3.0 内置，session_id `webchat:dm:admin`）/ `qq`（OneBot）/ `wechat` / `qq_official` / `bilibili_live` 等。**每个 adapter 的 send_xxx 签名不同**——索要对应源码或文档。

### 消息格式元数据

`core/adapter/message_format_metadata.py` 的 `MessageFormatMetadata`：`supported_elements` / `emojis`——适配器自报能力，比 hasattr 探测更可靠。表情目录 3.0 走 `await im.get_message_metadata()` 的 `emojis`（2.x 的 `adapter.emoji_dict` 已删）。

### 权限名单

`core/adapter/access.py` 的 `ListAccessPolicy`（白/黑名单策略），`ctx.config` 里 `session_whitelist/blacklist` 是框架级过滤。

---

## 8. Config (schema.json)

Defines WebUI config form. Plugin reads via `self.config.get("key")`.

```json
{
  "fields": [
    {
      "name": "api_key",
      "type": "text",
      "label": "API Key",
      "description": "Your API key",
      "required": true,
      "placeholder": "sk-..."
    },
    {
      "name": "max_results",
      "type": "number",
      "label": "Max Results",
      "description": "Max search results to return",
      "default": 5,
      "min": 1,
      "max": 20
    },
    {
      "name": "enabled_groups",
      "type": "list",
      "label": "Enabled Groups",
      "description": "Group IDs where plugin is active"
    },
    {
      "name": "model",
      "type": "model_select",
      "label": "LLM Model",
      "description": "Model to use",
      "required": true
    },
    {
      "name": "verbose",
      "type": "switch",
      "label": "Verbose Logging",
      "default": false
    },
    {
      "name": "mode",
      "type": "select",
      "label": "Mode",
      "options": [
        {"label": "Fast", "value": "fast"},
        {"label": "Accurate", "value": "accurate"}
      ],
      "default": "fast"
    }
  ]
}
```

**Field types:** `text, textarea, number, switch, select, list, model_select, provider_select, password, slider, date, time, color`

**Config access:**
```python
api_key = self.config.get("api_key")          # None if not set
max_r = self.config.get("max_results", 5)     # With default
```

**`model_select` 的 3.0 语义**：schema 的 model_select 字段框架自动规范化，**存的是内部 ID（uuid 形态）**，不是显示名——传 `get_llm_client(model_id=...)` 直接用；但**别把它当名字展示**。

---

## 9. Web UI

### API Endpoint

```python
from core.plugin import register

@register.api("/status", methods=["GET"])
async def get_status(self, request):
    return {"status": "ok", "count": self.counter}

# → Available at: /api/plugin/{plugin_id}/status
```

`kwargs` 透传 FastAPI `add_api_route`（`response_model, summary` 等）。

### Static Page

```python
@register.page("dashboard", "My Dashboard", menu=PageMenu(icon="assets/icon.svg"))
# → /page/plugin/{plugin_id}/dashboard
# PageMenu.icon：SVG 文件路径（相对插件根）或 Element Plus 图标名
```

**插件页面/静态资源由框架以 `Cache-Control: no-store` 提供**：更新插件后无需清浏览器缓存。

### Static Assets

```python
@register.static("assets", html=True)
# html=True 时目录请求尝试 index.html
# → /static/plugin/{plugin_id}/assets/...
```

### WebSocket

```python
@register.ws("/stream", auth=True)
# auth=True 时握手后 ws.state.user 可用
# → /ws/plugin/{plugin_id}/stream
```

---

## 10. Async Patterns

```python
import asyncio

class MyPlugin(BasePlugin):
    def on_load(self):
        self.task = asyncio.create_task(self._background_loop())

    def on_unload(self):
        if hasattr(self, 'task'):
            self.task.cancel()

    async def _background_loop(self):
        while True:
            try:
                await self._do_work()
            except Exception as e:
                self.logger.error(f"Background error: {e}")
            await asyncio.sleep(60)
```

**Rules:**
- Never `time.sleep()` in async code → blocks entire framework
- Never `asyncio.run()` inside plugin → already in event loop
- Always `try/except` in background loops → one error shouldn't kill the loop
- **3.0 会话接口全异步**——后台任务里碰 session_mgr 一律 await

---

## 11. Logging & Utils

```python
self.logger.info("message")      # Standard logging
self.logger.warning("message")
self.logger.error("message", exc_info=True)  # With traceback
```

**Useful utilities**（`core/utils/common_utils.py`）:

```python
from core.utils.common_utils import (
    text_to_speech, speech_to_text,
    generate_image, image_to_image, desc_img, image_to_base64,
)
from core.utils.media_refs import store_session_media, resolve_media_reference
from core.utils.image_compression import compress_image_element, compress_image_file
from core.utils.path_utils import get_data_path, get_config_path
from core.provider.llm_model import LLMRequest, LLMResponse, OpenAIMessage
from core.provider.openai_compatible import OpenAICompatibleLLM, OpenAICompatibleTTSClient, OpenAICompatibleSTTClient
```

---

## 12. Manifest

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "description": "Short description",
  "author": "your_name",
  "plugin_version": "1.0.0",
  "core_version": ">=3.0.0rc1",
  "configs": {
    "comment": "Optional config defaults that override schema.json defaults"
  },
  "dependencies": {
    "other_plugin_id": ">=1.0.0"
  },
  "python_dependencies": ["aiohttp>=3.8"]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | Unique, snake_case, `[a-z0-9_]+` |
| `name` | Yes | Display name |
| `plugin_version` | Yes | SemVer |
| `core_version` | No | **无上界**；`>=3.0.0` 不匹配 rc（PEP440），要兼容 rc 写 `>=3.0.0rc1` 或更低 |
| `configs` | No | Default overrides |
| `dependencies` | No | Plugin deps |
| `python_dependencies` | No | pip packages (auto-installed) |

---

## 13. 3.0 会话与模型身份

### 会话 API（全异步，rc1 实锤）

| 操作 | 3.0 写法 |
|------|---------|
| 读会话 | `s = await sm.get_session(sid, ensure_session=False)`；拍平 `s.flatten_content()`；分块 `s.content` |
| 读列表 | `await sm.get_sessions(include_content=False)` |
| 写覆盖 | `await sm.update_session(sid, content=chunks)`（**清空上下文保元数据的官法**：`content=[]`） |
| 追加块 | `await sm.update_memory(sid, chunk)` |
| 标题/描述 | `await sm.update_session(sid, title=..., description=...)` |
| 删除 | `await sm.delete_session(sid)` |
| 能力 | `await sm.get_effective_capabilities(sid)` / `await sm.update_session_capabilities(sid, caps)` |
| 缓冲冲刷 | `ctx.flush_session_messages(sid, filter_fn=...)` → bool |

**已删**（2.x 残留必崩/静默退化）：`fetch_memory / write_memory / read_memory / update_memory(同步版) / get_memory_count / get_session_info / update_session_info / clear_session / clear_all_sessions / chat_memory(dict 缓存)`。

**normalize_memory 要求**：`list[list[dict]]`，role ∈ {system, user, assistant, tool}。

### 模型身份（rc1 实锤）

- `model_id` = **内部稳定 ID**（uuid 形态）——存配置、传参用它
- `model_name` = **可读名**——面板/日志展示用它
- `get_models(provider_id)` 返回 `{类型: {内部ID: {"model_name": ..., "config": {...}}}}`
- 文本配置引用 `provider_id:model_id` 的冒号后 = **内部 ID**；面板/日志显示 uuid 形态 → 用 `model_name`（`getattr(info, "model_name", None) or info.model_id`）
- Provider 停用后调用会抛 `ProviderAPIError`（2.x 静默失败已修）
