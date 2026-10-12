# znq19_KiraAI_qzone_plugin
- 总级: NEEDS-FIX
- 版本: manifest version 1.4.10 / core_version 未声明（缺上界约束，见备注）
- 规模: 13 个 py（main.py 3391 行 + qzone/ 包 8 文件 + tests/）；入口 main.py（BasePlugin）
- 命中裁决:
  - [A] main.py:1949 `caps = self.ctx.get_session_capabilities(sid) or {}` → **真命中 NEEDS-FIX**：
    rc.1 中 `PluginContext.get_session_capabilities` 是 **async**（`core/plugin/plugin_context.py:105`
    `async def get_session_capabilities(...) -> dict`），插件在**同步**方法 `_session_image_mode` 里直接调用，
    拿到的是 coroutine 对象（truthy），随后 `caps.get("image_recognition")` → AttributeError →
    被外层 `except Exception: return ""` 静默吞掉。后果：**image_mode 永远为空串**，
    `native` 模式判定恒为 False → native 图（框架未写 caption）永远进不了「近期图片清单」，
    v1.4.8「只列已认识的图」兜底逻辑在 rc.1 静默失效。2.x 同步形态下正常，故只在 rc.1 破坏。
  - [A] main.py:501/535、qzone/utils.py:53、tests/test_silent_guard.py:6/41/115 → 误报（均为中文注释/字符串里的「清空/更新会话」字样，非会话 API 调用）
  - [B] 无模型名展示命中：全仓未读取/展示 `model_name`/`model_id`；`get_llm_client(model_uuid=...)` 用法在 rc.1 仍存在（plugin_context.py:132），无 uuid 乱码风险 → SAFE
  - [C] main.py:1813 `self.ctx.provider_mgr.get_default_vlm()` → SAFE（rc.1 `ctx.provider_mgr` 存在）；tests/_bootstrap.py:375 为测试桩 → 误报
  - [D] main.py:18 `from core.plugin import BasePlugin, register_tool, on, Priority` → SAFE（rc.1 `core/plugin/__init__.py` 仍导出 `register_tool/on/register`，decorators.py:242）；`from core.chat.message_utils import ...`、`from core.chat import MessageChain/...`、`from core.prompt_manager import Prompt`、`from core.provider import LLMRequest` 均在 rc.1 存在
  - [E] main.py:1801-1836 图片缓存（`ctx.db.get/add/update_image_desc_cache`）→ SAFE（rc.1 `core/db/mixins/image_cache.py` 三方法齐全，均 async 且已 await）；main.py:1670/2143 `message_format_to_text` 仅出现在**注释**里 → 误报；main.py:45 `from core.utils.common_utils import desc_img` → SAFE（rc.1 存在，签名 `(client, image, prompt, lang)`，调用处 main.py:1860 用关键字传参匹配）；tests/* 为桩 → 误报
  - [F] main.py:815/931/1049 `adapter_mgr.get_adapter(name)`、951-952 `get_adapters()`、1057 `get_adapters().keys()` → SAFE（rc.1 `adapter_registry.py:668/672` 两方法均在）；main.py:1353 `message_types=adapter.message_types` → **兼容但已废弃**：rc.1 `KiraMessageEvent` 有 `@_accept_legacy_message_types`（message_utils.py:87-108）接受旧 kwarg，`BaseAdapter.message_types` 仍是有 @deprecated 的 property（base.py:39），运行可用，但会触发 DeprecationWarning → SAFE-with-compat（建议改 `supported_elements=`）
  - [G] 预扫描 G 组 305 命中**全为误报**：本插件只用 `@on.im_message`（main.py:1900）、`@on.llm_request`（main.py:2135）、`@register_tool`；**未使用** `on.comment`/`ON_COMMENT`。305 命中的「comment」均是 QQ空间评论业务词或中文注释，与评论事件钩子无关。钩子签名两代一致（rc.1 decorators.py:150/168 提供 im_message/llm_request/comment）→ SAFE
  - [H] main.py:490-495 `persona_mgr.get_active_persona()/get_persona()` → SAFE（rc.1 `ctx.persona_mgr` 存在）；tests/_bootstrap.py:376 桩 → 误报
  - [I] 无直读/patch 框架文件行为：main.py:924 仅注释提及 adapter_registry.py；tests/_bootstrap.py 用 importlib 加载的是**插件自身** main.py（非框架文件）→ 误报
- 修复方案(NEEDS-FIX): `main.py:1949`，把同步调用改为 await，并按手册第1节做异步探测：
  ```python
  import inspect
  ...
  async def _session_image_mode(self, sid: str) -> str:
      try:
          res = self.ctx.get_session_capabilities(sid)
          caps = (await res) if inspect.isawaitable(res) else res
          caps = caps or {}
          rec = caps.get("image_recognition") or {}
          return str(rec.get("mode") or "")
      except Exception:
          return ""
  ```
  对应把其调用点（main.py:1962 `self._session_image_mode(sid)`）改为 `await self._session_image_mode(sid)`，
  并确认调用链位于 async 函数内。参照模式=手册第1节 `inspect.isawaitable` 探测；风险点=调用点若原在同步函数需一并 async 化。
- 备注: 唯一确认破坏=会话能力异步化未适配（静默退化）；另建议 manifest 补 `cores_version` 上界以避免 3.0 装载歧义；`message_types=` 建议升级为 `supported_elements=`。
