# KiraAI 3.0.0 正式版（GA）弃用方法 → 最新方法 对照表

> 基线：`xxynet/KiraAI` tag **`v3.0.0`** = `9db3d67`（= 当时 main HEAD）。
> 来源：对 GA 源码全仓扫描 `@deprecated` 装饰器 + 「Deprecated compatibility wrapper」docstring 标记。
> 对照：同时标注 **2.x（v2.34.8）** 是否有替代方法 —— 决定双世代插件怎么改最稳。
>
> **rc2 → GA 无新增弃用**：GA 相对 rc2 只加了 7 个提交（消息历史类型化查询、
> `flush_session_messages` 的 `filter_fn`、WebUI 批量更新等），插件 API 面零变更；
> 下表各项的弃用标记在 **rc1/rc2 即已存在**，但直到 GA 才应作为「正式基线」执行清理。

## 一、正式 @deprecated 装饰器标记（会发 DeprecationWarning 或同等效力）

| ID | 弃用项 | 最新方法 | 2.x 是否有新方法 | 双世代迁移建议 |
|---|---|---|---|---|
| DEP-1 | `AdapterManager.get_adapter_infos()` | **`get_adapters_info()`** | ✅ 2.x 已有新名（两者并存） | **直接改名**，两代通用，零风险 |
| DEP-2 | `BaseAdapter.message_types`（属性读/写） | `adapter.get_capability(IMCapability).get_message_metadata().supported_elements` | ❌ 2.x 只有 `message_types` | 探测：`hasattr(adapter, "get_capability")` 走新法，否则保留旧法 |
| DEP-3 | `MessageMetadata(message_types=…)` 构造关键字 / `.message_types` 属性 | **`supported_elements`** | ❌ 2.x 只有 `message_types` 字段 | 构造前用 `dataclasses.fields(MessageMetadata)` 探测字段名 |
| DEP-4a | `MessageProcessor.flush_session_messages(sid, extra_event=…)` | **`ctx.flush_session_messages(sid, filter_fn=…)`** | ✅ 2.x ctx 已有（**无 filter_fn**） | 一律走 `ctx.`；`filter_fn` 是 GA 新增，2.x 别传 |
| DEP-4b | `MessageProcessor.send_message_chain(session, chain, …)` | **`ctx.send_message_chain(session, chain, *, bot=…)`** | ✅ 2.x ctx 已有（**无 bot**） | 一律走 `ctx.`；`bot` 仅 3.0 需要时传 |
| DEP-4c | `MessageProcessor.handle_im_message(event)` | **`await ctx.event_bus.publish(event)`** | ✅ 两代 ctx 都有 `event_bus` | 直接替换，两代通用 |

## 二、docstring 标记「Deprecated compatibility wrapper」（适配器直调）

| ID | 弃用项 | 最新方法 | 2.x 状态 | 双世代迁移建议 |
|---|---|---|---|---|
| DEP-5 | 各适配器实例 `.send_group_message(gid, chain)` / `.send_direct_message(uid, chain)` 直调（webchat/qq/qq_official/telegram/discord/bilibili/weixin_oc 全部同款标记） | `adapter.get_capability(IMCapability).send_group_message/...`，或**统一走 `ctx.send_message_chain(session, chain)`** | 2.x 直调是**正常 API**（未标记） | 双世代插件：优先统一走 `ctx.send_message_chain`；必须直调适配器时探测 `get_capability` |

## 三、配置字段（两代均已标记弃用）

| ID | 弃用项 | 最新方法 | 说明 |
|---|---|---|---|
| DEP-6 | `ConfigType.Enum` / `EnumField` | **StringField / IntField / FloatField + `options`** | 2.x 与 3.0 的 `config_field.py` 都有同样的弃用注释；插件的 schema/配置代码应迁移 |

## 四、3.0 GA 新增、2.x 没有的 ctx 成员（双世代插件**用前必须探测**，不算弃用但同属兼容面）

| 成员 | 说明 |
|---|---|
| `ctx.message_history`（MessageHistoryService） | GA 新增；类型化、可过滤的消息历史查询（#366）。2.x 无此字段 |
| `ctx.message_delivery`（MessageDeliveryService） | GA 新增为 ctx 字段（2.x 要经 `ctx.message_processor.message_delivery`）。⚠️ 接管/包装它的方法仍需 `*args, **kwargs` 透传铁律 |
| `ctx.flush_session_messages(..., filter_fn=…)` | `filter_fn` 关键字仅 GA |
| `ctx.send_message_chain(..., *, bot=…)` | `bot` 关键字仅 3.0（rc2 起） |

## 五、扫描规则（对应 `tools/scan_deprecated_ga.py`）

| 规则 | 匹配 | 豁免 |
|---|---|---|
| DEP-1 | `get_adapter_infos(` | 定义点本身（`def get_adapter_infos`） |
| DEP-2/3 | `.message_types`（读/写/构造 kw） | 框架内部兼容层写法不扫；插件命中即报 |
| DEP-4 | `message_processor.flush_session_messages(` / `message_processor.send_message_chain(` / `message_processor.handle_im_message(` | — |
| DEP-5 | `adapter.send_group_message(` / `adapter.send_direct_message(`（含 `self.<x>adapter.`、`adapter.` 形态） | 已带 capability 探测的分支 |
| DEP-6 | `ConfigType.Enum` / `EnumField(` | — |
