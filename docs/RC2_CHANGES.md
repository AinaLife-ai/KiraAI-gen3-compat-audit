# rc1 → rc2 破坏性变更（KiraAI v3.0.0-rc.2）

> 基线：`v3.0.0-rc.2` = `74efac3`。rc1 = `v3.0.0-rc.1` = `8a0b812`。
> rc2 相对 rc1 的改动**很小**（8 个文件、42 行插入），但有一处会让**把签名写死的插件直接崩**。

---

## 1. 出站身份：`self_id=` → `bot: User`（**会打死插件**）

| 位置 | rc1 | rc2 |
| --- | --- | --- |
| `MessageDeliveryService.send_message_chain` | `(session, chain, *, memory_message=None, self_id: str \| None = None)` | `(session, chain, *, memory_message=None, **`bot: User \| None = None`**)` |
| `MessageProcessor.send_message_chain`（已弃用，仅转发） | `…, self_id=self_id)` | `…, **`bot=bot`**)` |
| `PluginContext.send_message_chain` | `(session, chain)` | `(session, chain, *, **`bot=None`**)` |
| `core/workflow/src/im/stages/execute.py` | `send_message_chain(sid, action, memory_message=…)` | `send_message_chain(sid, action, memory_message=…, **`bot=event.bot`**)` |

**语义**：`bot` = "Bot identity to include in outgoing history"。框架用它记录出站消息：

```python
record_outgoing(session, chain, platform=…, self_id=str(bot.user_id), sender_name=bot.nickname)
```

⇒ **如果你也往发送 API 传身份**：rc2 必须传 `bot=`（传 `self_id=` 会 TypeError）；
**如果只是为了不炸**：按 [SIGNATURE_DRIFT_v3.md](SIGNATURE_DRIFT_v3.md) 改成原样透传即可。

### 正确写法（探测式，两代通吃）

```python
import inspect

def _accepts(fn, name: str) -> bool:          # 建议缓存（键=函数对象）
    try:
        params = inspect.signature(fn).parameters
        return name in params or any(p.kind == p.VAR_KEYWORD for p in params.values())
    except Exception:
        return False

fn = getattr(self.ctx, "send_message_chain", None) or mp.send_message_chain
kw = {"bot": getattr(event, "bot", None)} if _accepts(fn, "bot") else {}
result = await fn(sid, chain, **kw)           # ⚠️ 绝不 try/except 重试（发送有副作用）
```

---

## 2. 事件/消息新增 `bot: User` 字段

`core/chat/message_utils.py`：`KiraIMMessage` / `KiraMessageEvent` / `KiraMessageBatchEvent`
新增 `bot: User` 字段，并在 `__post_init__` 里与 `self_id` **双向同步**：

```python
bot: User = field(default=None, kw_only=True)
def __post_init__(self):
    if self.bot is None:
        self.bot = User(self.self_id)
    else:
        self.self_id = self.bot.user_id
```

* 读 `event.bot` / `message.bot` ⇒ 安全（不存在时按老逻辑回落）✓
* **写** `event.is_mentioned` 这类**只读 property** ⇒ 一直会崩（不是 rc2 引入的，但同类陷阱）：
  要写就写 `event.message.is_mentioned` ✓

---

## 3. 受影响面（自查）

```bash
# 我在 rc2 上会不会被打死？
python3 tools/scan_signature_drift.py /path/to/your_plugin     # P0-b 就是这类
grep -rn "send_message_chain" /path/to/your_plugin | grep self_id
```

**只要你不包装/不直接调用 `send_message_chain`（或已按第 1 节改成透传/探测），rc2 就没有影响。**

---

## 4. 其他（rc2 无关，但 v3 生态的通病）

| 变更 | 何时引入 | 处理 |
| --- | --- | --- |
| `MessageProcessor.send_xml_messages` 删除 | 3.0 | 发送改走 `send_message_chain`；解析走 `MessageDeliveryService.parse_xml` |
| `MessageProcessor._parse_xml_msg` 删除 | 3.0 | 同上 |
| 会话记忆改 SQLite：`fetch_memory`/`write_memory` 移除 | 3.0 | 用 `get_session(sid, ensure_session=False)` / `update_session(sid, content=…)`（**异步**） |
| `get_session_info`/`update_session_info` 改名 | 3.0 | 用 `get_sessions()` / `update_session(sid, title=…)`（**异步**） |
| `session_manager.get_effective_capabilities` 异步化 | 3.0 rc1 | `inspect.isawaitable` 探测；同步读点要改成异步预热 + 缓存 |

> 统一原则：**按能力探测（`hasattr` / `inspect.isawaitable`），绝不绑版本号字符串。**
