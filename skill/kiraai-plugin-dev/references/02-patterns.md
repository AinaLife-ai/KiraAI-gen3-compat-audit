# KiraAI Plugin Patterns (3.0 rc1)

Copy-paste proven patterns. Replace placeholders. Keep it simple.

## Table of Contents

1. [Pattern 1: Simple Message Hook](#pattern-1-simple-message-hook)
2. [Pattern 2: LLM Tool](#pattern-2-llm-tool)
3. [Pattern 3: Custom XML Tag](#pattern-3-custom-xml-tag)
4. [Pattern 4: Web API + Config](#pattern-4-web-api--config)
5. [Pattern 5: Scheduled Task](#pattern-5-scheduled-task)
6. [Pattern 6: 会话能力感知钩子（3.0 异步写法）](#pattern-6-会话能力感知钩子30-异步写法)
7. [XML Tag DSL Reference](#xml-tag-dsl-reference)
8. [rc1 陷阱清单（全生态审计实锤）](#rc1-陷阱清单全生态审计实锤)
9. [Testing & Debugging](#testing--debugging)
10. [Plugin Structure Templates](#plugin-structure-templates)
11. [附录 A：2.x 双世代兼容写法](#附录-a2x-双世代兼容写法)

---

## Pattern 1: Simple Message Hook

**Use case:** Log messages, keyword triggers, read-only monitoring.

```python
from core.plugin import BasePlugin, on

class KeywordLoggerPlugin(BasePlugin):
    def on_load(self):
        self.keywords = self.config.get("keywords", ["urgent", "help"])
        self.logger.info(f"Monitoring keywords: {self.keywords}")

    @on.im_message(priority=50)
    async def on_message(self, event):
        text = event.get_plain_text().lower()
        for kw in self.keywords:
            if kw in text:
                self.logger.info(
                    f"Keyword '{kw}' from {event.sender_name}({event.sender_id}) "
                    f"in {event.adapter_name}:{event.session_id}"
                )
                # Do NOT reply here - use on.message_received or tools for replies
                break
```

**Key points:**
- `@on.im_message` = after bot decided to process (read-only, don't reply)
- For "bot should reply" logic → use `tools` or `@on.message_received` with careful filtering
- Always use `event.get_plain_text()` not `str(event.message_chain)`

---

## Pattern 2: LLM Tool

**Use case:** LLM can query external API (search, database, calculation).

```python
import json
from core.plugin import BasePlugin, register
from core.agent.tool import ToolResult

class SearchToolPlugin(BasePlugin):
    @register.tool(
        name="web_search",
        description="Search the web for current information. Use when user asks about recent events, facts, or things you don't know.",
        params={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results (1-10)", "default": 5}
            },
            "required": ["query"]
        }
    )
    async def web_search(self, query: str, max_results: int = 5, **kwargs) -> ToolResult:
        try:
            max_results = max(1, min(10, max_results))  # Clamp
            results = await self._do_search(query, max_results)
            return ToolResult(content=json.dumps({
                "query": query,
                "results": results
            }, ensure_ascii=False))
        except Exception as e:
            self.logger.error(f"Search failed: {e}", exc_info=True)
            return ToolResult(
                content=f"Search temporarily unavailable: {str(e)}",
                is_error=True
            )

    async def _do_search(self, query: str, limit: int):
        # Your search implementation
        return [{"title": "...", "url": "...", "snippet": "..."}]
```

**Key points:**
- `description` is the LLM's ONLY hint for when to call → be specific
- Return structured JSON (LLM parses it well)
- `is_error=True` lets LLM know to inform user / retry
- Never raise → LLM gets "tool crashed" with no context

---

## Pattern 3: Custom XML Tag

**Use case:** LLM outputs `<mytag>` → rich message (image, card, button).

```python
from core.plugin import BasePlugin, register
from core.chat.message_utils import MessageChain, Image, At, Text

class DiceTagPlugin(BasePlugin):
    """LLM can output <dice sides="20"/> to roll dice"""

    @register.tag("dice")
    def handle_dice(self, content: str, **attrs) -> MessageChain:
        try:
            sides = int(attrs.get("sides", 6))
            if sides < 2:
                return MessageChain([Text("[dice: sides must be >= 2]")])
            import random
            result = random.randint(1, sides)
            return MessageChain([Text(f"🎲 Rolled d{sides}: {result}")])
        except ValueError:
            return MessageChain([Text("[dice: invalid sides]")])
```

**In system prompt (via @on.llm_request):**
```python
@on.llm_request(priority=50)
async def inject_prompt(self, event):
    event.request.system_prompt += "\nYou can roll dice: <dice sides=\"20\"/> (2-100 sides)"
```

**Key points:**
- Tag handler is **synchronous** (called during message parsing)
- Return MessageChain, not str
- Invalid input → return error text element (don't crash the whole message)
- **官方已有 `<at>/<img>/<video>/<file>/<reply>/<forward>/<json>/<music>/<face>`**（`core/plugin/builtin_plugins/kira-ai/tags.py`）——别重复造

---

## Pattern 4: Web API + Config

**Use case:** Plugin exposes REST API for external tools.

**schema.json:**
```json
{
  "fields": [
    {"name": "api_token", "type": "password", "label": "API Token", "required": true},
    {"name": "rate_limit", "type": "number", "label": "Rate Limit (req/min)", "default": 60}
  ]
}
```

**main.py:**
```python
import time
from collections import defaultdict
from core.plugin import BasePlugin, register

class ApiPlugin(BasePlugin):
    def on_load(self):
        self.token = self.config.get("api_token")
        self.rate_limit = self.config.get("rate_limit", 60)
        self.requests = defaultdict(list)  # ip -> timestamps

    def _check_auth(self, request) -> bool:
        auth = request.headers.get("Authorization", "")
        return auth == f"Bearer {self.token}"

    def _rate_ok(self, ip: str) -> bool:
        now = time.time()
        self.requests[ip] = [t for t in self.requests[ip] if now - t < 60]
        if len(self.requests[ip]) >= self.rate_limit:
            return False
        self.requests[ip].append(now)
        return True

    @register.api("/data", methods=["GET"])
    async def get_data(self, request):
        if not self._check_auth(request):
            return {"error": "unauthorized"}, 401
        ip = request.client.host
        if not self._rate_ok(ip):
            return {"error": "rate limited"}, 429
        return {"data": "your data here"}
```

**Key points:**
- Always validate auth on every endpoint
- Rate limit to prevent abuse
- Return tuple `(dict, status_code)` for non-200

---

## Pattern 5: Scheduled Task

**Use case:** Periodic cleanup, polling external API, daily reports.

```python
import asyncio
from core.plugin import BasePlugin

class PollerPlugin(BasePlugin):
    def on_load(self):
        self.running = True
        self.task = asyncio.create_task(self._poll_loop())

    def on_unload(self):
        self.running = False
        if hasattr(self, 'task'):
            self.task.cancel()

    async def _poll_loop(self):
        # Initial delay to let framework fully start
        await asyncio.sleep(10)
        while self.running:
            try:
                await self._check_updates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Poll error: {e}", exc_info=True)
            # Use wait_for with timeout instead of sleep for clean shutdown
            try:
                await asyncio.wait_for(asyncio.Event().wait(), timeout=300)
            except asyncio.TimeoutError:
                pass

    async def _check_updates(self):
        # Your polling logic — 3.0 里碰 session_mgr 记得 await
        pass
```

**Key points:**
- Initial `await asyncio.sleep(10)` → framework fully loaded before first run
- `asyncio.wait_for(Event().wait(), timeout)` → interruptible sleep (clean unload)
- Catch `CancelledError` separately → clean shutdown
- Catch generic `Exception` → log, continue loop

---

## Pattern 6: 会话能力感知钩子（3.0 异步写法）

**Use case:** 读取会话有效能力（如图像能力）决定注入策略——3.0 必须 await。

```python
from core.plugin import BasePlugin, on

class CapAwarePlugin(BasePlugin):
    @on.llm_request(priority=50)
    async def tweak_prompt(self, event):
        sm = self.ctx.session_mgr
        # ✅ 3.0 全异步：必须 await
        caps = await sm.get_effective_capabilities(event.session_id)
        if caps.get("image_input"):
            event.request.system_prompt += "\n你可以直接看图。"
        else:
            event.request.system_prompt += "\n用户发的图你会先收到文字描述。"
```

**清空上下文（保元数据的官法）：**

```python
await sm.update_session(sid, content=[])   # 只清对话，标题/能力设置/数据全保留
```

---

## XML Tag DSL Reference

LLM outputs XML-like tags in responses. Framework parses and converts to rich messages.

**Syntax:**
```xml
<tagname attr1="value1" attr2="value2"/>
<tagname attr="value">inner content</tagname>
```

**Official built-in tags**（`core/plugin/builtin_plugins/kira-ai/tags.py` + `file_send_policy.py`）：

| Tag | Attributes | Result |
|-----|-----------|--------|
| `<at uid="123"/>` | uid | @mention |
| `<img url="..."/>` | url/path/base64 | Image |
| `<video url="..."/>` | url/path | Video |
| `<file path="..." name="..."/>` | path, name | File attachment（受 file_send_policy 控制） |
| `<reply id="msg_id"/>` | id | Quote/reply |
| `<forward>` | nested chains | Forwarded bundle |
| `<json>{...}</json>` | JSON string | JSON card |
| `<music type="qq" id="..."/>` | type, id | Music card |
| `<face id="..."/>` | id | Platform emoji |

**Custom tag registration:**
```python
@register.tag("mytag")
def handle_mytag(self, content: str, **attrs) -> MessageChain:
    # content = inner text (if any)
    # attrs = dict of attributes
    return MessageChain([...])
```

**Rules:**
- Tag names: lowercase, no spaces
- Handler is **synchronous**
- Always return MessageChain (even for errors → return error text element)
- Unknown tags are left as-is (LLM sees raw text)

---

## rc1 陷阱清单（全生态审计实锤）

> 44 仓审计 + 15 仓 NEEDS-FIX 修复 + 17 PR 验证出的真坑。每条都有源码证据。

### 🔴 会话与上下文

| 坑 | 后果 | 正法 |
|----|------|------|
| `sm.fetch_memory/write_memory/read_memory/get_memory_count/get_session_info/update_session_info/clear_session` | 2.x API 全删 | 见 §13（01-api.md）全异步接口 |
| 会话接口**不 await** | 拿到 coroutine，静默退化+RuntimeWarning | 全部 `await`；拿不准就 `inspect.isawaitable(res)` |
| 用「delete+重建」清空上下文 | 误伤会话能力设置/标题等元数据 | `await sm.update_session(sid, content=[])` |
| 直读 `sm.chat_memory` dict | 3.0 已 SQLite 化，dict 没了 | 见附录 A.5 镜像模式 |
| 文本型模型配置当内部 ID 直传 | rc1 `resolve_model_entry` 不认显示名 | 直传失败按 `model_name` 反查（`provider_id:model_id` 引用规范化） |

### 🔴 模型身份

| 坑 | 后果 | 正法 |
|----|------|------|
| 面板/日志显示 `model_id` | 一串 uuid 乱码 | `getattr(info, "model_name", None) or info.model_id` |
| `provider_id:model_id` 冒号后当名字 | 引用解析错 | 冒号后 = 内部 ID，展示查 `model_name` |

### 🔴 模块路径（3.0 拆包）

```python
# ❌ 全已删（裸导入直接 ImportError 崩加载）
from core.plugin.plugin_registry import PluginManager
from core.plugin.plugin_handlers import event_handler_reg, EventType
from core.utils.model_clients import OpenAICompatibleLLM
from core.adapter.adapter_utils import IMAdapter, SocialMediaAdapter

# ✅ 3.0 路径
from core.plugin.handlers import event_handler_reg, EventType
from core.plugin.manager import PluginManager
from core.provider.openai_compatible import OpenAICompatibleLLM
from core.adapter.capabilities import IMCapability, FeedCapability
```

**包级导入安全**：`from core.plugin import BasePlugin, on, register` 两代都行。

### 🔴 消息发送与内部接口

| 坑 | 后果 | 正法 |
|----|------|------|
| `MessageProcessor._parse_xml_msg/_add_message_ids/send_xml_messages` | 已删 | `ctx.message_delivery.parse_xml / add_message_ids`；XML 由 ExecuteAgentStage 协调 |
| `MessageFormatter.format_to_text` 当同步用 | 3.0 经 `mp.im_workflow.ctx.message_formatter` 可达，但要对 `inspect.isawaitable` 分流 | 双世代探测 |
| `mp.skills_manager / mcp_manager` | 已搬 | `ctx.skills_mgr / ctx.mcp_mgr` |
| 猴补丁包 `send_xml_messages` | 3.0 没这函数了 | 包 `MessageDeliveryService.send_message_chain`（按链对账） |

### 🔴 适配器

| 坑 | 后果 | 正法 |
|----|------|------|
| `isinstance(adapter, IMAdapter)` | 类已删，永远 False | `adapter.get_capability(IMCapability)` |
| `adapter.emoji_dict` | 已删 | `await im.get_message_metadata()` 的 `emojis` |
| `KiraMessageEvent(message_types=[...])` | 3.0 兼容别名但非法定 | 构造用 `supported_elements=`（或按签名分流） |
| 假定 `send_group_message` 存在于所有适配器 | 崩/静默 | 能力探测 + `adapter_name` 白名单 |

### 🟡 版本与配置

| 坑 | 后果 | 正法 |
|----|------|------|
| `"core_version": ">=2.24.3,<3.0.0"` | 3.0 直接拒载 | 无上界：`">=2.24.3"` |
| `>=3.0.0` 想兼容 rc1 | PEP440 不匹配 rc | `>=3.0.0rc1` 或更低 |
| `if __version__ >= "3.0"` 判断世代 | rc/alpha/未来版全翻车 | 特征识别（hasattr/isawaitable/try-import） |

---

## Testing & Debugging

### 测试规范（全生态审计沉淀）

1. **装真框架跑**——把插件 cp 进 `data/plugins/`，从框架根当脚本跑；别只靠 mock。
2. **PluginContext 构造**——3.0 多了 7 个必填字段（`prompt_mgr/skills_mgr/mcp_mgr/message_history/image_desc_cache/session_buffer_mgr/message_delivery`）。测试桩别模块级求值，用**懒探测**（import 期框架还不可见）。
3. **假传输接线**——rc1 传输走 `message_delivery`，测试补假 delivery；用**实例级遮蔽**（`ctx.send_message_chain = fake`）两代通吃。
4. **dataclass 探测**——`PluginContext`/`Session`/`KiraIMMessage` 全是 dataclass；`hasattr(cls, x)` 对无默认值字段为 False，必须 `dataclasses.fields()`。
5. **双世代全量测试**——2.x 与 3.0 各跑一遍全量套件。

### Enable debug logging

```python
# In on_load()
self.logger.setLevel("DEBUG")
```

### Check if hook is registered

```python
def on_load(self):
    self.logger.info(f"Plugin {self.ctx.plugin_id} loaded")
    # If you don't see this in logs, plugin didn't load
```

### Test tool locally

```python
# Standalone test (run from framework root)
import asyncio
from core.plugin import BasePlugin

async def test():
    plugin = MyPlugin()
    plugin.ctx = MockContext()  # Your mock
    plugin.config = {"api_key": "test"}
    result = await plugin.my_tool(param="value")
    print(result.content)

asyncio.run(test())
```

### Common import errors

```python
# ❌ Wrong
from plugin import BasePlugin

# ✅ Correct
from core.plugin import BasePlugin
```

---

## Plugin Structure Templates

### Minimal (single-purpose tool)

```
my_plugin/
├── manifest.json
├── schema.json        # Optional
└── main.py            # ~50-100 lines
```

### Standard (tool + config + data)

```
my_plugin/
├── manifest.json
├── schema.json
├── main.py
├── README.md
└── data/              # Created at runtime via get_plugin_data_dir()
    └── cache.json
```

### Advanced (web UI + multiple modules)

```
my_plugin/
├── manifest.json
├── schema.json
├── main.py
├── api.py             # @register.api endpoints
├── tags.py            # @register.tag handlers
├── tools/             # Multiple tool files
│   ├── search.py
│   └── calc.py
├── static/            # Web assets
│   ├── index.html
│   └── app.js
└── README.md
```

---

## 附录 A：2.x 双世代兼容写法

> 新插件按正文写（面向 3.0）。需要兼容 2.x 用户群时用**特征识别**，严禁版本字符串判断。

### A.1 会话 API 分流

```python
import inspect

async def read_flat(sm, sid):
    if hasattr(sm, "fetch_memory"):            # 2.x 同步
        return sm.fetch_memory(sid)
    s = await sm.get_session(sid, ensure_session=False)   # 3.0 异步
    return s.flatten_content() if s else []

async def write_chunks(sm, sid, chunks):
    if hasattr(sm, "write_memory"):            # 2.x
        sm.write_memory(sid, chunks)
    else:                                       # 3.0
        await sm.update_session(sid, content=chunks)

async def clear_context(sm, sid):
    """两代都保元数据的清空"""
    if hasattr(sm, "write_memory"):
        sm.write_memory(sid, [])
    else:
        await sm.update_session(sid, content=[])

async def read_caps(sm, sid):
    """同名但同步→异步的通用分流"""
    res = sm.get_effective_capabilities(sid)
    return (await res) if inspect.isawaitable(res) else res
```

### A.2 模块路径 try-import

```python
try:    # 3.0
    from core.plugin.handlers import event_handler_reg, EventType
except ImportError:  # 2.x
    from core.plugin.plugin_handlers import event_handler_reg, EventType

try:    # 3.0
    from core.provider.openai_compatible import OpenAICompatibleLLM
except ImportError:  # 2.x
    from core.utils.model_clients import OpenAICompatibleLLM
```

### A.3 模型名展示（两代安全）

```python
def model_label(info):
    return getattr(info, "model_name", None) or info.model_id
```

### A.4 适配器事件构造分流

```python
import inspect
from core.chat.message_utils import KiraMessageEvent

_sig = inspect.signature(KiraMessageEvent.__init__).parameters
_kw = "supported_elements" if "supported_elements" in _sig else "message_types"
event = KiraMessageEvent(**{_kw: ["text", "image"]}, ...)
```

### A.5 同步链路只读会话（镜像模式）

同步内部函数族在 3.0 无法 await 时：
- **2.x**：直读 `sm.chat_memory` dict（在的）
- **3.0**：异步入口（消息钩子/命令/API）先 `await sm.get_sessions()` 预热 sid→meta 镜像（TTL 1–2s 节流），同步链路只读镜像；写入后失效镜像；`asyncio.to_thread` 区的写入放延迟队列由异步方冲刷。

### A.6 测试桩的 PluginContext 构造

```python
import inspect
from core.plugin.plugin_context import PluginContext

def make_ctx(**overrides):
    """按 3.0 签名懒探测填充；2.x 多给的字段会被 **kwargs 吃掉"""
    params = inspect.signature(PluginContext.__init__).parameters
    base = {"event_bus": ..., "db": ..., "session_mgr": ..., ...}
    if "message_history" in params: base["message_history"] = ...
    if "session_buffer_mgr" in params: base["session_buffer_mgr"] = ...
    if "message_delivery" in params: base["message_delivery"] = ...
    base.update(overrides)
    return PluginContext(**base)
```
