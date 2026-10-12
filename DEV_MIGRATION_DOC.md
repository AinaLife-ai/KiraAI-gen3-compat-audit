# KiraAI v3.0.0 预发布版本变化与开发者迁移文档

整理日期：2026-10-12。范围：`dev-v3` 上的 `v3.0.0-alpha.1`、`alpha.2`、`alpha.3`、`alpha.4`、`rc.1`。

本文依据本地 Git 标签、各标签之间的提交和实际代码整理。当前分支版本为 `v3.0.0-rc.1`，对应提交 `8a0b81279e3d563c83495c7db66eab0ee9f490c3`；本地 `dev-v3` 与已有的 `origin/dev-v3` 引用一致，本次未刷新远程。版本日期采用版本提交日期，不等同于 GitHub Release 发布时间。

前半部分按版本概括功能和使用体验变化；最后一部分面向插件、适配器、Provider、自定义工作流和 WebUI 集成开发者。接口迁移以 `v2.34.8 → v3.0.0-rc.1` 为总对照，并注明变更首次进入的 v3 版本。这里的 `rc.1` 是候选版本，不代表 v3.0.0 正式版已经发布。

## 一、v3 的整体变化

v3 的主要方向是把平台连接与具体业务能力分开，同时建立更完整的消息与会话数据体系。

- 平台适配器统一到新的能力架构，聊天、动态和评论由各自的能力对象负责，便于一个平台提供多种能力。
- Bilibili 增强私信、动态发布以及评论回复与提及通知，配套默认评论回复插件。
- 模型拥有稳定的内部身份，上游模型名称可以调整；Provider 可以单独启用或停用。
- 人设支持独立的自拍参考图，以及全局、私聊、群聊规则。
- 聊天记录与模型上下文分开展示和管理，实际收发消息支持结构化存档和媒体查看。
- WebUI 增加管理员内置聊天，可直接发送文字、图片和文件。
- LLM 会话与上下文转入数据库持久化，旧 JSON 记忆自动导入，会话接口随之转为异步。

## 二、各预发布版本改了什么

### v3.0.0-alpha.1 — 新平台架构与基础能力

**版本日期：2026-10-05；提交：`65b5ef1`。**

这是 v3 第一阶段的主要功能和架构落地版本。

- **统一平台能力架构**：Bilibili、QQ、QQ 官方机器人、个人微信、Telegram、Discord 迁移到新的适配器与能力体系；聊天输出格式由相应能力声明。
- **增强 Bilibili**：加入结构化动态浏览、搜索与发布能力，并监听评论回复和提及通知；新增默认评论回复插件。
- **Provider 启停控制**：可以暂时停用模型服务商而保留配置；被停用的服务商不会继续接受通过管理器获取的客户端的新调用。
- **模型身份更稳定**：内部模型身份与上游名称分开，调整名称不再等同于更换内部标识；旧模型配置与引用支持迁移。
- **人设能力增强**：自拍参考图归属到具体人设，支持管理；增加全局、私聊、群聊规则，并根据聊天场景组合提示内容。
- **消息缓冲更灵活**：支持筛选后批量处理缓冲消息，未匹配的消息继续留在缓冲区。
- **稳定性与维护性改进**：统一适配器运行和停止约定，改善 QQ、Discord 关闭过程；拆分插件管理、商店和 WebUI 集成代码，减少模块耦合。

### v3.0.0-alpha.2 — 收敛新架构，修复平台消息

**版本日期：2026-10-06；提交：`749f5f4`。相对 alpha.1 的增量。**

- **移除旧适配器架构**：完成旧基类和旧调用路径的清理，第三方适配器需要采用新的能力接口。
- **修复 QQ 官方机器人消息处理**：保留完整消息内容，恢复引用和提及处理，减少解析过程中丢失内容的问题。
- **修复 Bilibili 私信发图**：图片先上传再发送，修正此前发送流程。
- **调整 Provider 公共实现位置**：OpenAI 兼容客户端移入 Provider 层，明确模型调用实现的归属。
- **调整遥测统计范围**：评论事件不再作为普通 IM 消息参与相关遥测统计。

### v3.0.0-alpha.3 — 结构化消息历史与上下文查看

**版本日期：2026-10-09；提交：`a1f4bfd`。相对 alpha.2 的增量。**

- **加入结构化消息存档**：实际收发消息独立入库，保存方向、发送者、消息链和发送状态；媒体文件归档，避免只剩下模型上下文里的文本描述。
- **关联聊天消息与 LLM 上下文**：可以根据关联标识查到对应的模型上下文；上下文裁剪后，消息存档仍按独立保留策略管理。
- **重做会话记录展示**：WebUI 使用聊天气泡显示结构化消息，支持媒体与引用内容；会话查看区分“历史消息”和“LLM 上下文”两个页签。
- **加入历史清理配置**：可按保存时间或每会话记录数量清理消息历史，配合回收未引用媒体。
- **拆分 IM 处理流程**：消息接收、批处理、请求构建、Agent 执行和收尾形成独立阶段，服务通过上下文注入。
- **扩展插件批量触发入口**：插件可以直接调用带筛选条件的缓冲消息发布接口，并得到是否发布批次的结果。

### v3.0.0-alpha.4 — WebUI 内置聊天与流程整合

**版本日期：2026-10-11；提交：`71d8d0c`。相对 alpha.3 的增量。**

- **增加管理员内置聊天**：直接在 WebUI 与 Kira 对话，支持文字、图片和文件、聊天资料设置、记录分页及清空。
- **接入现有消息链路**：内置聊天作为应用管理的 IM 适配器运行，回复经过现有插件、Agent 和消息发送流程；文件工具和命令执行可分别控制。
- **集中 IM 公共服务**：统一消息格式化、媒体处理、缓冲、发送和图片描述缓存等服务，让工作流与插件使用同一组服务对象。
- **改善关闭稳定性**：处理消息历史清理任务取消，减少退出过程中的异常。
- **改善前端恢复页面**：前端资源不可用时提供更清晰的恢复页面，并调整图标样式。
- **同步 dev 分支修复**：合入 JPEG MIME 规范化和参考图片类型推断修复。这是从 v2 开发线带入的修复，不是 v3 新增业务能力。

### v3.0.0-rc.1 — 会话数据库持久化与能力声明校准

**版本日期：2026-10-12；提交：`8a0b812`。相对 alpha.4 的增量。**

- **LLM 会话与上下文入库**：会话标题、描述、上下文和扩展数据通过数据库保存，不再依赖常驻的 JSON 记忆缓存。
- **导入旧会话记忆**：首次初始化时导入旧 `chat_memory.json`，保留原文件并记录导入完成状态，避免后续启动重复导入或复活已删除会话。
- **区分会话内部身份和路由标识**：新增内部会话 ID、创建时间与更新时间；原有平台路由 SID 继续用于寻址。
- **调整会话开发接口**：会话读取和写入改为异步，使用独立快照；插件和工作流应通过接口显式保存修改。
- **校准输出能力声明**：WebChat 的图片标签声明统一为 `img`；Bilibili IM 只声明实际支持的文字、图片和表情输出，减少模型生成无法发送的格式。
- **收起未落地的预留能力**：直播事件、语音频道的预留接口暂时取消导出，不能作为 rc.1 已提供的能力使用。

## 三、面向开发者的接口变动文档

以下按能力领域组织。除特别说明外，示例均以 rc.1 的最终接口为准。示例中的 `self.ctx` 是 `BasePlugin` 提供的 `PluginContext`。

### 3.1 变更索引

| 首次版本 | 影响范围 | 开发者需要处理的变化 |
| --- | --- | --- |
| alpha.1 | 适配器 | 使用 `BaseAdapter`、`AdapterContext` 和能力对象；采用新的生命周期、权限与格式元数据接口 |
| alpha.1 | 插件模块 | 内部模块拆分；`core.plugin` 包级常用导出保留，旧子模块导入需要迁移 |
| alpha.1 | Provider / 模型 | 分离 `model_id` 与 `model_name`；配置升级为 `model_config_version = 2`；处理停用状态 |
| alpha.1 | 人设 / 评论 | 新增参考图、场景规则、类型化 Feed 接口和评论钩子 |
| alpha.2 | 适配器 / Provider | 移除 `adapter_utils.py` 旧基类；OpenAI 兼容客户端移动路径 |
| alpha.3 | 历史 / 消息 / 工作流 | 新增历史服务、消息身份元数据和发送历史 ID；拆分 IM 阶段；插件缓冲发布新增筛选参数 |
| alpha.4 | 公共服务 / WebChat | 集中服务注入，简化 `MessageProcessor`；新增管理员聊天 REST 接口 |
| rc.1 | 会话 / 插件 | 会话接口转异步并替换旧记忆接口；`get_session_capabilities()` 也必须 `await` |
| rc.1 | 能力声明 | 图片输出格式使用 `img`；移除直播事件和语音频道预留接口的公开导出 |

### 3.2 适配器：从继承平台业务基类到组合能力

**首次进入 alpha.1；旧架构在 alpha.2 移除。**

旧 `core.adapter.adapter_utils` 中的 `IMAdapter`、`SocialMediaAdapter`、`LiveStreamAdapter` 已移除。自定义适配器使用：

```python
from core.adapter import BaseAdapter, AdapterContext, IMCapability
```

构造函数从 `(info, event_queue)` 改为 `(ctx: AdapterContext)`。上下文提供 `info` 和 `event_queue`；`BaseAdapter` 负责能力登记、事件发布和权限控制，具体平台对象负责共享客户端与生命周期。

```python
class MyAdapter(BaseAdapter):
    def __init__(self, ctx: AdapterContext):
        super().__init__(ctx)
        self.register_capability(IMCapability, MyIMCapability(self))
```

这个片段仅展示构造方式；完整适配器仍须实现 `start()`、`stop()`、`get_client()`，对应 IM 能力须实现下述抽象方法。

| 接口 | rc.1 约定 |
| --- | --- |
| `register_capability(capability_type, capability)` | 登记属于当前适配器的能力实例；同种能力不允许重复登记 |
| `get_capability(capability_type)` | 返回唯一匹配能力；没有或不唯一时抛出 `ValueError` |
| `get_capabilities()` | 返回登记表副本；修改副本不改变登记表，能力对象本身仍共享 |
| `capabilities` | 只读映射视图 |
| `publish(event)` | 同步入队；支持不同能力的事件，不限于 IM |
| `create_qrcode_login_handler(config)` | 仍是类方法；默认返回 `None` |

插件不应根据具体适配器类型判断能否聊天，改为查询 `IMCapability`。也不要假定每个已启用适配器都登记了 IM 能力，例如 Bilibili 可以关闭 IM 而保留 Feed 能力。

```python
from core.adapter import IMCapability

adapter = self.ctx.adapter_mgr.get_adapter(adapter_name)
if adapter is None:
    raise ValueError("Adapter unavailable")
im = adapter.get_capability(IMCapability)
result = await im.send_direct_message(user_id, chain)
```

需要经过统一发送历史等流程时，优先使用 `await self.ctx.send_message_chain(sid, chain)`；直接调用能力适合明确需要平台发送接口的场景。

**生命周期语义改变**：`async start()` 是完整运行协程，应持续到停止、取消或失败，返回表示运行结束；不能启动后台任务后立即返回。适配器应在退出前释放所属资源，传播不可恢复错误，并防止并发调用创建重复运行任务。`AdapterManager.start_adapter()` 负责调度和观察运行协程，其返回不表示登录或连接已经就绪。

**权限接口改变**：通用层不再依赖旧基类的 `group_list`、`user_list`。使用 `core.adapter.access.ListAccessPolicy` 配置名单，通过 `adapter.access.set_policy(capability_type=..., permission=..., policy=...)` 登记；检查使用 `capability.is_allowed(target_id, permission=...)`。策略按“登记能力类型 + 权限字符串”隔离，没有策略时拒绝。内置 IM 接收权限包括 `im.direct.receive`、`im.group.receive`；格式支持、权限与登录状态是三个不同维度。

依据：`core/adapter/base.py`、`context.py`、`access.py`、`adapter_registry.py`、`capabilities.py`。

### 3.3 消息输出格式与事件字段

**alpha.1 引入；rc.1 校准部分内置能力声明。**

`IMCapability` 提供：

```python
async def get_message_metadata(self) -> MessageFormatMetadata: ...
async def send_direct_message(self, user_id, message) -> KiraIMSentResult | None: ...
async def send_group_message(self, group_id, message) -> KiraIMSentResult | None: ...
```

`MessageFormatMetadata` 包含 `supported_elements: list[str]` 和 `emojis: dict[str, str] | None`。元数据描述可输出格式，不代表权限或当前连接状态；`emojis=None` 表示不支持表情，空字典表示没有可枚举目录。原先读取适配器 `emoji_dict` 的代码应迁移到相应能力的元数据接口。

`KiraMessageEvent`、`KiraMessageBatchEvent` 的规范字段由 `message_types` 改为 `supported_elements`。生产事件时应使用新名称：

```python
metadata = await im.get_message_metadata()
event = KiraMessageEvent(
    supported_elements=metadata.supported_elements,
    timestamp=timestamp,
    message=message,
    adapter=adapter.info,
)
```

**输出标签与存档元素类型要区分**：图片输出标签名是 `img`，历史消息链中的图片类型是 `image`。rc.1 修正了 WebChat 的标签声明；Bilibili IM 输出格式收敛到 `text`、`img`、`emoji`，不再声明 `at`、`reply`、`share_video`。

**保留的向后兼容**：两个事件类仍接受弃用的 `message_types=` 关键字，并保留读写别名；适配器也保留弃用的 `message_types` 属性，映射到 IM 的声明。旧构造关键字不能和 `supported_elements=` 或位置参数混用。兼容目的是让旧插件逐步迁移，并不恢复已删除的旧适配器基类。

**rc.1 公开能力边界**：已提供的通用能力包括 `IMCapability`、`FeedCapability`。`LiveEventCapability`、`VoiceChannelCapability` 已注释且不再导出；在早期 alpha 使用这些预留名称的扩展应移除相关依赖。

依据：`core/adapter/message_format_metadata.py`、`capabilities.py`、`core/chat/message_utils.py`。

### 3.4 Feed 与评论接口

**alpha.1 引入。**

动态浏览、搜索、发布和评论从旧社交适配器接口迁移到 `FeedCapability`：

| 操作 | 新接口 |
| --- | --- |
| 浏览 | `await feed.get_feed(FeedQuery(...)) -> FeedPage` |
| 搜索 | `await feed.search_feed(FeedSearchQuery(...)) -> FeedPage` |
| 发布 | `await feed.send_post(FeedPost(content=chain, extra=...))` |
| 评论 | `await feed.send_comment(message, target, root=..., parent=...)` |
| 格式声明 | `await feed.get_comment_metadata()` / `await feed.get_post_metadata()` |

`FeedPage` 返回 `items`、`next_cursor`、`has_more`。`FeedItem` 提供资源引用、内容、作者、附件和平台扩展信息；`FeedRef(resource_type, id)` 是由具体适配器解释的资源引用。查询游标属于签发它的适配器实例；平台特有筛选或发布参数保留在 `extra` 中。

新增 `EventType.ON_COMMENT` 和 `@on.comment`。`KiraCommentEvent` 以 `comment_id`、`comment_content` 表示当前评论，`target` 表示目标资源，`root_comment_id` 表示根评论；顶层评论默认以自身 ID 作为根评论。

```python
from core.adapter import FeedCapability
from core.chat import MessageChain
from core.chat.message_elements import Text
from core.plugin import Priority, on

@on.comment(priority=Priority.HIGH)
async def reply_comment(self, event):
    event.stop()
    adapter = self.ctx.adapter_mgr.get_adapter(event.adapter_name)
    if adapter is None:
        return
    feed = adapter.get_capability(FeedCapability)
    await feed.send_comment(
        MessageChain([Text("收到")]),
        event.target,
        root=event.root_comment_id,
        parent=event.comment_id,
    )
```

在确定接管评论后、首次外部 `await` 前调用 `event.stop()`，阻止后续插件重复处理。内置默认评论插件以系统低优先级处理未被接管的事件；用户插件不要使用 `SYS_LOW` 或 `SYS_HIGH` 优先级。

依据：`core/adapter/feed.py`、`capabilities.py`、`core/chat/message_utils.py`、`core/plugin/builtin_plugins/comment/main.py`。

### 3.5 插件模块路径与 PluginContext

**模块拆分进入 alpha.1；服务注入主要在 alpha.3 / alpha.4 完成；会话能力查询在 rc.1 转异步。**

常用包级导出仍保留，推荐从 `core.plugin` 导入 `BasePlugin`、`PluginContext`、`register`、`register_tool`、`on`、`EventType`、`Priority` 等。

| 旧内部导入 | 新位置 |
| --- | --- |
| `core.plugin.plugin.BasePlugin` | `core.plugin.base.BasePlugin`，或包级导入 |
| `core.plugin.plugin_handlers` | `core.plugin.handlers` |
| `core.plugin.plugin_registry.PluginManager` | `core.plugin.manager.PluginManager` |
| `core.plugin.plugin_registry.PluginInfo` | `core.plugin.metadata.PluginInfo` |
| `core.plugin.plugin_registry.register/on/register_tool` | `core.plugin.decorators` |
| `core.plugin.plugin_registry.PluginPage/PageMenu` | `core.plugin.pages` |

原 `plugin_registry.py` 已删除；新的 `registry.py` 管理注册状态，不是旧大模块的兼容替代。工具、标签、页面等组件类型拆到 `components.py`，商店能力拆到 `store.py`，WebUI 绑定由 `webui/plugin_bindings.py` 负责。

`PluginContext` 新增/明确注入的服务包括 `prompt_mgr`、`skills_mgr`、`mcp_mgr`、`message_history`、`image_desc_cache`、`session_buffer_mgr`、`message_delivery`；原 `sticker_manager` 规范名称改为 `sticker_mgr`。运行中的插件由系统创建上下文；手工构造 `PluginContext` 的测试或扩展需要补齐新的必填字段。

保留 `ctx.sticker_manager` 的只读属性作为旧名称兼容入口，实际返回 `ctx.sticker_mgr`；旧构造关键字和对该属性直接赋值并不受这个兼容属性支持。

缓冲消息发布接口现在为：

```python
published = await self.ctx.flush_session_messages(
    sid,
    filter_fn=lambda event: not event.is_notice,
)
```

筛选器是同步谓词，接收 `KiraMessageEvent`。返回 `True` 表示已发布批次，`False` 表示没有匹配消息；不表示 Agent 已执行完成。未匹配事件继续留在缓冲区，错误向上传播。

rc.1 中 `get_session_capabilities(sid)` 改为异步：

```python
capabilities = await self.ctx.get_session_capabilities(sid)
```

发送消息继续使用 `await ctx.send_message_chain(sid, chain)`；注入通知继续使用 `await ctx.publish_notice(...)`。`MessageProcessor.flush_session_messages()`、`send_message_chain()`、`handle_im_message()` 保留为弃用入口，分别建议迁移到 `PluginContext` 的发布/发送入口或 `await ctx.event_bus.publish(event)`。依赖其内部格式化、Agent 或缓存字段的代码应改用明确的服务。

依据：`core/plugin/__init__.py`、`plugin_context.py`、`core/message_manager.py`、`core/workflow/src/im/batching.py`。

### 3.6 Provider：稳定模型 ID、上游名称与启停状态

**alpha.1 引入；公共客户端路径在 alpha.2 改变。**

`ModelInfo.model_id` 现在是稳定的内部标识，新增 `model_name` 表示实际发送给上游 API 的模型名称。自定义 Provider 请求中的 `model` 参数应使用 `model.model_name`，不能再把内部 ID 发送给上游。

模型配置从“上游名称直接作为 key，参数直接作为 value”升级为：

```json
{
  "model_config_version": 2,
  "model_config": {
    "llm": {
      "<internal_id>": {
        "model_name": "upstream-model-name",
        "config": {"temperature": 0.7}
      }
    }
  }
}
```

迁移产生的条目还可能包含 `legacy_ids`。模型选择引用仍为 `provider_id:model_id`，但冒号后的规范值改为内部 ID；不要通过展示名称重新拼接引用。

| Python 接口 | 新语义 |
| --- | --- |
| `register_model(provider_id, model_type, model_name, config=None)` | 返回生成的内部 ID；不存在 Provider 时返回 `None` |
| `get_models(provider_id)` | 按类型、内部 ID 返回 `{model_name, config}` 条目 |
| `get_model_info(..., model_type=None)` | 可指定模型类型，支持内部 ID 或无歧义旧别名 |
| `get_model_client(..., model_type=None)` | 可指定 `ModelType` 或其字符串值；停用状态会阻止获取或新调用 |
| `update_model(..., config=None, model_name=None)` | 可修改上游名称而保留内部 ID；提供的 config 整体替换模型参数 |
| `sync_models(..., add_ids, delete_ids, config=None)` | 两个列表仍按上游名称处理，虽然字段名含 ids；保留条目的内部 ID 和参数不变 |

同一 Provider、同一模型类型内的上游名称须非空且唯一。

Provider 配置增加 `status: active | inactive`，旧配置缺失时按 `active` 处理。停用保留配置但移除运行实例；通过管理器获取并缓存的客户端在新异步调用时也重新检查 Provider 状态，停用时抛出 `ProviderAPIError`。这不是撤销已经发出的上游请求。

对应 REST 变化：

- `PATCH /api/providers/{provider_id}/status`：请求 `{"status":"active"}` 或 `{"status":"inactive"}`。
- `POST /api/providers/{provider_id}/models`：请求使用 `model_type`、`model_name`、`config`；返回 `{"success":true,"model_id":"<internal_id>"}`。
- `PUT /api/providers/{provider_id}/models/{model_type}/{model_id}`：路径使用内部 ID，请求可包含 `model_name` 和 `config`。
- 模型列表与 Provider 响应中的模型配置按内部 ID 组织，客户端展示名称应取 `model_name`。
- `POST /api/providers/{provider_id}/models/sync/{model_type}` 的 `add_ids`、`delete_ids` 仍传上游名称。

**向后兼容与迁移**：旧配置会先生成 `.model-identity-v1.bak` 备份，再迁移模型条目和默认模型引用；schema 声明的模型选择字段也支持引用规范化。旧名称作为 `legacy_ids` 保留，仅在能无歧义解析时使用；不存在或含糊的引用不会强行替换。创建模型 REST 请求仍接受旧 `model_id` 字段作为 `model_name` 的输入别名。直接构造 `ModelInfo` 而未提供 `model_name` 时，暂以 `model_id` 作为上游名称，方便旧集成过渡。

公共 OpenAI 兼容客户端由 `core.utils.model_clients` 移至 `core.provider.openai_compatible`，包括 `OpenAICompatibleLLMClient`、`OpenAICompatibleTTSClient`、`OpenAICompatibleSTTClient`；旧路径已移除。

依据：`core/provider/provider.py`、`provider_manager.py`、`model_identity.py`、`model_migration.py`、`webui/models.py`、`webui/routes/providers.py`。

### 3.7 人设规则与参考图

**alpha.1 引入。**

`PersonaInfo` 增加 `reference_image_path`、`chat_rules`、`private_chat_rules`、`group_chat_rules`。WebUI 的人设请求增加三个规则字段，响应增加参考图路径和规则。规则组合为“全局规则 + 当前私聊或群聊规则”，由提示管理器注入。

参考图使用异步管理接口：

```python
path = await self.ctx.persona_mgr.get_reference_image(persona_id)
path = await self.ctx.persona_mgr.set_reference_image(persona_id, image_bytes, filename)
await self.ctx.persona_mgr.remove_reference_image(persona_id)
```

REST 使用 `GET / PUT / DELETE /api/personas/{persona_id}/reference-image`；上传为 multipart 的 `file` 字段。支持 PNG、JPEG、WebP，限制 10 MiB，GIF 不支持。图片按人设保存到 `data/selfie_refs/`，不要直接假定旧全局自拍路径仍生效。

旧 `bot_config.selfie.path` 会尝试复制到当前活动人设；已有参考图时不覆盖，失败时保留旧配置以便后续重试，成功后清理旧配置键。原始图片不会因迁移被删除。这是为保留旧用户自拍设置提供的数据兼容。

依据：`core/persona/model.py`、`persona_manager.py`、`reference_image.py`、`core/db/migrate_to_db.py`、`core/prompt_manager.py`、`webui/routes/personas.py`。

### 3.8 结构化历史、消息身份与发送结果

**alpha.3 引入，部分调用位置在 alpha.4 调整。**

平台收发记录和 LLM 上下文现在是两份数据：前者保存实际消息链与发送状态，后者是供模型使用、可能被裁剪的分块上下文。不要再把上下文条目数量当作平台消息数量。

`PluginContext.message_history` 提供异步查询：

```python
page = await self.ctx.message_history.list_messages(sid, limit=50)
record = await self.ctx.message_history.get_message(message_id)
linked = await self.ctx.message_history.get_linked_memory(record)
page = await self.ctx.message_history.get_messages_by_llm_message_id(
    sid, llm_message_id, limit=50,
)
```

分页返回 `{"messages": [...], "next_cursor": ...}`，按存档创建时间和记录 ID 倒序。`limit` 为 1–200；游标必须属于该会话。模型上下文已经裁剪或关联不存在时，`get_linked_memory()` 返回 `None`。

`OpenAIMessage` 新增 `extra`，持久化名称为 `_extra`。`to_memory_dict()` 保存私有元数据，其中 `llm_message_id` 是稳定消息身份；`to_dict()` 和 Provider 序列化不会把 `_extra` 发往模型服务商。旧上下文会补身份；重复身份或改变角色的条目会重新分配身份。

`KiraIMSentResult` 增加 `history_id`，表示历史存档内部 ID；`message_id` 仍是平台发送结果 ID，两者用途不同。统一发送服务保存 `pending / sent / failed / unknown` 状态；启动时把遗留 `pending` 标成 `unknown`，不会因此自动重发。

新增 REST：

| 接口 | 作用 |
| --- | --- |
| `GET /api/messages?session_id=...&cursor=...&limit=50&llm_message_id=...` | 分页查询实际消息，关联过滤可省略 |
| `GET /api/messages/{message_id}` | 返回 `message` 与仍存在的关联 `memory` |
| `GET /api/messages/{message_id}/media?element_path=0` | 读取存档消息元素对应的媒体；嵌套路径可用 `0.1` |

消息历史使用 `messages` 表，媒体归档在 `data/session_media/archive/`。新增 `bot_config.message_history_cleanup` 配置：默认启用、每会话最多 500 条、每 3600 秒检查；`max_age_days=0` 表示不按天数限制。此策略独立于 LLM 上下文的 `max_memory_length`。

依据：`core/chat/message_history.py`、`memory_metadata.py`、`message_history_cleanup.py`、`core/agent/message.py`、`core/workflow/src/im/message_delivery.py`、`webui/routes/sessions.py`。

### 3.9 IM 工作流与公共服务

**alpha.3 拆分流程；alpha.4 集中服务。**

默认工作流以 `IMWorkflowContext` 注入服务，构造方式为 `DefaultIMWorkflow(ctx, max_concurrent_messages=3)`。`MessageProcessor` 构造方式收敛为 `MessageProcessor(im_workflow)`，主要负责转发与插件入口。

事件流程使用 `ReceiveStage → RouteStage`；批次流程使用 `PrepareBatchStage → BuildRequestStage → AssembleRequestStage → ExecuteAgentStage → FinalizeStage`。扩展阶段继承 `BaseStage[ContextT]`，实现 `async run(ctx) -> bool`；`True` 继续，`False` 结束流程。

`IMEventContext` 保存单事件状态，`IMBatchContext` 保存批次请求、标签、模型组和执行结果；阶段实例不保存每个请求的可变状态。Agent 已启动后的终止策略须保留最终结果钩子和记忆写入等收尾语义，不能只因 `event.stop()` 就跳过全部收尾。

公共服务分别为：`MessageFormatter`、`MessageMediaService`、`SessionBufferManager`、`MessageDeliveryService`、`ImageDescCache`。此前直接访问 `MessageProcessor` 的内部处理函数或嵌套缓存的扩展应迁移到服务对象或对应上下文字段。

直接使用旧消息处理器内部接口的扩展，可按以下位置迁移：

| 旧入口或导入 | rc.1 位置或调用方式 |
| --- | --- |
| `core.message_manager.SessionBuffer / SessionBufferManager` | `core.chat.session_buffer` |
| `core.message_manager.ImageDescCache` | `core.image_desc_cache.ImageDescCache` |
| `message_format_to_text(...)` | `MessageFormatter.format_to_text(...)` |
| `_iter_message_images(...)` / `_build_native_content(...)` | `MessageMediaService.iter_images(...)` / `build_native_content(...)` |
| `handle_event(...)` / `handle_im_batch_message(...)` | 通过事件总线发布单条/批次事件，交给默认工作流路由 |
| `handle_cmt_message(...)` | 发布 `KiraCommentEvent`；调度器内部处理方法改名为 `handle_cmt_event(...)` |
| `send_xml_messages(...)` | 由 `ExecuteAgentStage` 协调 XML、钩子与消息发送，没有保留同名单一替代入口 |
| `_parse_xml_msg(...)` / `_add_message_ids(...)` | `MessageDeliveryService.parse_xml(...)` / `add_message_ids(...)` |
| `cleanup_image_desc_cache_task()` | `ImageDescCache.cleanup_task()`；运行实例生命周期由系统管理 |

自定义 Agent 步骤消费者也应注意：`AgentStepResult.model_id` 对应内部模型身份，新增 `model_name` 用于上游名称；新增 `assistant_message` 引用当前步骤的 `OpenAIMessage`，供发送存档关联。`AgentExecutionContext.append_messages(...)` 将同一消息对象同时加入请求和本轮记忆，扩展应保留这种共享关系，避免复制出不同的消息身份。

原 `core.workflow.workflow_registry.py` 已删除，`register_workflow`、`WorkflowType` 不再从 `core.workflow` 导出。旧 `WorkflowContext` 类仍存在并导出，但默认 IM 工作流使用的是 `IMWorkflowContext`；不要据此假定原装饰器注册式工作流扩展仍可直接运行。

依据：`core/workflow/__init__.py`、`base_stage.py`、`src/im/context.py`、`src/im/workflow.py`、`core/message_manager.py`、`core/lifecycle.py`。

### 3.10 WebUI 管理员聊天接口

**alpha.4 引入。**

内置适配器名称为 `webchat`，路由 SID 为 `webchat:dm:admin`。它由应用注册，不出现在普通适配器类型目录中，不应当作为可任意替换的用户适配器操作。

| 接口 | 请求或返回要点 |
| --- | --- |
| `GET /api/webchat` | 返回 `profile`、最近的 `request` 与 `config` |
| `PUT /api/webchat/profile` | `nickname`、`peer_nickname`、`description` |
| `PUT /api/webchat/config` | 布尔值 `allow_file_tools`、`allow_exec` |
| `POST /api/webchat/messages` | JSON：UUID 格式 `request_id`、非空 `text`，文字最多 16000 字符 |
| `POST /api/webchat/messages/upload` | multipart：`request_id`、`text`、重复的 `kinds` 与 `files`；kinds 为 `image` 或 `file` |
| `GET /api/webchat/messages` | 用 `before` 或 `after` 序号分页，不能同时使用；返回 `messages` 和 `has_more` |
| `DELETE /api/webchat/messages` | 清理内置聊天存档、请求记录和该存档媒体，返回 `{"ok":true}` |
| `GET /api/webchat/messages/{message_id}/media?element_path=...` | 查询内置聊天存档中的媒体 |

最多 10 个附件，总量不超过 20 MiB。未配置聊天资料时发送返回 `409 setup_required`。相同请求 ID 与相同内容重复提交返回原请求，不重复入队；相同 ID 搭配不同内容返回 `409 request_conflict`。

发送返回的是已提交请求状态，不是 LLM 回答；`sent` 表示输入已提交。回复需要从消息列表读取，当前协议不是直接返回模型流的接口。

内置聊天展示记录独立存于 `data/webchat/webchat.db`，媒体位于 `data/webchat/media/`；LLM 上下文仍由会话管理器管理。清空这份聊天存档不等于清空 `webchat:dm:admin` 的模型上下文。默认允许文件工具、默认禁用命令执行。上述接口接入项目现有 WebUI 鉴权。

依据：`core/adapter/builtin/webchat/`、`core/webchat/service.py`、`store.py`、`webui/routes/webchat.py`。

### 3.11 rc.1 会话接口迁移：同步 JSON 记忆到异步数据库快照

**rc.1 的主要破坏性变更。**

`SessionManager` 不再暴露常驻 `chat_memory` 缓存，不再提供原同步记忆 API。会话读取返回独立快照；修改快照不会自动写回数据库，必须显式调用保存接口。自行创建管理器时，应在数据库准备好后调用 `await manager.initialize()`。

| v2 / 早期 v3 用法 | rc.1 替代方式 |
| --- | --- |
| `get_session_info()` | `await get_sessions(include_content=False)` 获取轻量列表 |
| `get_session_info(sid)` | `await get_session(sid)`；不存在时返回 `None` |
| `update_session_info(sid, title, description)` | `await update_session(sid, title=..., description=...)` |
| `read_memory(sid)` | 获取 session 后读取 `session.content` |
| `fetch_memory(sid)` | 获取 session 后调用 `session.flatten_content()` |
| `get_existing_memory_snapshot(sid)` | `await get_session(sid)`，不存在则保持 `None`，不自动创建 |
| `write_memory(sid, chunks)` | `await update_session(sid, content=chunks)` |
| `update_memory(sid, chunk)` | 同名接口改为异步，必须 `await` |
| `get_memory_count(sid)` | 读取 `len(session.content)`；批量使用 `await get_session_message_counts()` |
| `get_effective_capabilities(...)` | 同名接口改为异步，必须 `await` |
| `update_session_capabilities(...)` | 同名接口改为异步，必须 `await` |
| `delete_session(sid)` | 同名接口改为异步，必须 `await` |
| 直接修改 `manager.chat_memory` / `_save_memory()` | 使用异步会话读写接口，不能再直接修改缓存或 JSON 文件 |

`get_session(sid, ensure_session=True)` 可显式创建缺失会话；`include_content=False` 省略上下文正文的加载，不表示会话真实上下文为空。

```python
session = await self.ctx.session_mgr.get_session(sid, ensure_session=True)
chunks = session.content
flat_messages = session.flatten_content()
await self.ctx.session_mgr.update_session(sid, title="新的标题")
await self.ctx.session_mgr.update_memory(sid, new_chunk)
await self.ctx.session_mgr.update_session(sid, content=edited_chunks)
```

`update_session()` 支持 `title`、`description`、`content`、`data`：省略字段保持原值；`content` 和 `data` 是整体替换，不是增量合并。上下文结构为 `list[list[dict]]`，允许角色 `system / user / assistant / tool`；写入会规范化 `_extra.llm_message_id`。会话能力覆盖放在 `session.data['capabilities']`，推荐通过专用接口维护。

`Session` 新增 `internal_id`、`created_at`、`updated_at`、`content`、`data`；`sid` 仍是 `adapter_name:dm|gm:target_id`。数据库内部 ID 类似 `sess_<uuid>`，不能替代路由 SID。

REST 会话路径保持 `/api/sessions`，但响应新增 `internal_id`、`created_at`、`updated_at`。详情中的 `messages` 继续表示 LLM 分块上下文；`message_count` 是上下文分块数量，`history_count` 是结构化历史记录数量。不要把 `/api/messages` 的实际聊天记录和会话详情 `messages` 混用。

REST 更新仍传 `messages`、`title`、`description`、`capabilities` 等现有字段，后端再映射到内部 `content` / `data`。Python 的 `update_session(..., data=...)` 并不等于 REST 接口公开了任意 `data` 写入。能力覆盖传 `null` 表示恢复跟随全局配置。

**数据库与兼容导入**：新增 `chat_sessions`、`database_migrations` 表；首次启动导入 `data/memory/chat_memory.json` 的标题、描述、上下文及扩展字段，不覆盖已有数据库会话。导入记录名为 `chat_memory_json_to_sessions`，与导入数据同事务提交；之后不再重新读该 JSON，也不会把新会话同步写回旧文件。原文件保留用于恢复，不能把它当作实时数据来源。无效的顶层 JSON 会让导入报错；异常会话条目尽量保留供人工修复，并非静默抛弃全部旧数据。

会话生命周期事件包括 `session_memory_updated`、`session_memory_written`、`session_deleted`，在持久化完成后发布。依赖这些事件的插件应保留异步处理，不能假定写入尚未完成。数据库服务仍从 `core.db.service.DatabaseService` 使用，内部拆分成业务 mixin，不要求普通插件跟随拆分导入。

依据：`core/chat/session_manager.py`、`session.py`、`core/db/mixins/sessions.py`、`core/db/models.py`、`webui/routes/sessions.py`。

### 3.12 迁移核对顺序与文档依据

建议按以下顺序迁移：

1. 修正已删除的内部导入路径、旧适配器基类和工作流注册器依赖。
2. 将平台操作改为能力查询，检查生命周期、权限和输出格式声明。
3. 将所有会话读写与能力查询改为异步，移除对 `chat_memory` 和旧 JSON 实时写入的依赖。
4. Provider 请求使用 `model_name`，模型选择与配置引用保存内部 ID；处理停用与旧别名解析失败。
5. 区分平台历史 ID、平台消息 ID、LLM 消息 ID 与会话内部 ID，检查历史媒体和上下文关联。
6. 按扩展类型回归：普通消息收发、缓冲筛选、评论接管、Provider 停用、旧数据导入、重启恢复及关闭过程。

本文为代码和历史核对结果，本次没有改动业务代码、运行应用或执行回归测试；上面的回归项是开发者完成迁移后的验证建议，不能视为已通过的测试报告。

版本边界可通过以下仓库对比核对：

- [v2.34.8 → alpha.1](https://github.com/KiraAI-Dev/KiraAI/compare/v2.34.8...v3.0.0-alpha.1)
- [alpha.1 → alpha.2](https://github.com/KiraAI-Dev/KiraAI/compare/v3.0.0-alpha.1...v3.0.0-alpha.2)
- [alpha.2 → alpha.3](https://github.com/KiraAI-Dev/KiraAI/compare/v3.0.0-alpha.2...v3.0.0-alpha.3)
- [alpha.3 → alpha.4](https://github.com/KiraAI-Dev/KiraAI/compare/v3.0.0-alpha.3...v3.0.0-alpha.4)
- [alpha.4 → rc.1](https://github.com/KiraAI-Dev/KiraAI/compare/v3.0.0-alpha.4...v3.0.0-rc.1)

alpha.4 合入了 dev 中 v2.34.8 的 JPEG 修复，因此上述前后标签采用提交集合差异判断版本归属，不能仅按日期分组。GitHub 链接用于方便查阅；本文内容的直接依据为本次检查的本地 Git 数据与源码。

| 固定版本 | 提交 |
| --- | --- |
| v3.0.0-alpha.1 | `65b5ef11c8153b34090e12574acf1960f54bb664` |
| v3.0.0-alpha.2 | `749f5f478a9bc8e3d3347cef3b33e2946f0a7c88` |
| v3.0.0-alpha.3 | `a1f4bfd306aa57ed0fb34c7f3c8c0261c4f1d531` |
| v3.0.0-alpha.4 | `71d8d0c081d4df61584967b8effea27329f7bce9` |
| v3.0.0-rc.1 | `8a0b81279e3d563c83495c7db66eab0ee9f490c3` |
