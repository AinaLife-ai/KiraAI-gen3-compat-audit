# KiraAI v3.0.0-rc.1 插件兼容性审计手册（子代理执行版）

> 你是插件兼容性审计员。本手册包含全部所需背景。**不要修改任何仓库代码**，你只读、分析、写报告。
> 所有框架事实以**本地真实源码**为准，不确定就去 grep 框架，禁止凭印象下结论。

## 0. 环境锚点（本地路径）

| 内容 | 路径 |
| --- | --- |
| 框架 3.0 rc.1（commit 8a0b812） | `/var/minis/shared/kira30` |
| 框架 2.x（v2.34.8） | `/var/minis/shared/kira_fw` |
| 待审仓库 | `/var/minis/shared/gen3audit/repos/<owner>_<repo>/` |
| 你的预扫描命中（JSON） | `/var/minis/shared/gen3audit/prescan/<owner>_<repo>.json` |
| 报告输出目录（你必须写这里） | `/var/minis/shared/gen3audit/reports/<owner>_<repo>.md` |

## 1. rc.1 已验证的破坏点清单（审计靶子）

以下每条都已在 `/var/minis/shared/kira30` 源码核实。审计就是检查插件**是否踩到**这些点。

### A. 会话管理（rc.1 最大破坏面，SessionManager 全异步化 + JSON 缓存移除）

**2.x 有、rc.1 已删除**（插件若在 rc.1 上调用 = AttributeError 或被 hasattr 守卫静默跳过）：

| 2.x 同步 API | rc.1 替代（全异步） |
| --- | --- |
| `get_session_info()` / `get_session_info(sid)` | `await get_sessions(include_content=False)` / `await get_session(sid)`（不存在返回 None） |
| `update_session_info(sid, title, description)` | `await update_session(sid, title=..., description=...)` |
| `read_memory(sid)` | 先 `get_session` 再读 `session.content`（分块 list[list[dict]]） |
| `fetch_memory(sid)` | `session.flatten_content()`（拍平为 list[dict]） |
| `get_existing_memory_snapshot(sid)` | `await get_session(sid)`（不自动创建；`ensure_session=True` 才创建） |
| `write_memory(sid, chunks)` | `await update_session(sid, content=chunks)`（**整体替换**，非增量） |
| `get_memory_count(sid)` | `len(session.content)` 或 `await get_session_message_counts()` |

**两代都有但 rc.1 变异步**（2.x 同步调用习惯在 rc.1 会拿到 coroutine → 静默退化 + RuntimeWarning）：
`update_memory(sid, chunk)`、`delete_session(sid)`、`get_effective_capabilities(session, global_caps)`、
`update_session_capabilities(...)`、`ctx.get_session_capabilities(sid)`（PluginContext 上的，2.x 同步 / rc.1 异步）。

**rc.1 新增约束**：`content` 结构为 `list[list[dict]]`，角色只允许 `system/user/assistant/tool`；
`Session` 新增 `internal_id/created_at/updated_at/data`；会话能力覆盖存 `session.data['capabilities']`；
会话事件 `session_memory_updated/written/deleted` 在持久化完成后发布。
验证锚点：`kira30/core/chat/session_manager.py`、`session.py`。

**⭐ 清空上下文的正确姿势（用户特别关注）**：有会话能力设置（`capabilities`/`data`/标题）的插件，
"清空上下文"应优先 **`update_session(sid, content=[])`**（只清对话，保留标题/能力/data），
而**不是** `delete_session` + 重建（会误伤会话元数据）。审计时看插件清空/重开会话用的是哪种，
用 delete+重建的标为「建议升级为内容置空」。特征识别写法参考：
```python
sm = ctx.session_mgr
if hasattr(sm, "update_session") and inspect.iscoroutinefunction(getattr(sm, "update_session")):
    await sm.update_session(sid, content=[])          # rc.1+
elif hasattr(sm, "write_memory"):
    sm.write_memory(sid, [])                           # 2.x / 3.0-alpha 同步形态
else:
    # 最老兜底才考虑 delete+重建
```

### B. 模型身份分离（model_id vs model_name，⭐ 用户特别关注"展示变 UUID"）

rc.1 起 `ModelInfo.model_id` 是**稳定内部 ID**（常是 uuid 形态），`model_name` 才是人类可读的上游模型名；
`model_config_version = 2`，模型配置按内部 ID 组织，迁移条目带 `legacy_ids`。
验证锚点：`kira30/core/provider/provider.py:51-71`、`provider_manager.py:352-406`。

**审计靶子**：插件凡是把模型标识**展示给用户**（命令回复、面板下拉、状态文本、日志、统计表）的地方，
在 rc.1 上是否只会显示内部 ID（uuid 乱码）？正确做法（照抄 Z 插件已验证模式）：
```python
def _model_entry_name(mid, entry):
    # entry 来自 get_models(provider_id)[mid]，3.0 是 dict 含 model_name；2.x 形态不同
    if isinstance(entry, dict) and entry.get("model_name"):
        return entry["model_name"]
    return mid  # 2.x / 缺名兜底
```
另外注意：`get_model_info`/`get_model_client` 在 rc.1 多了 `model_type=` 关键字参数；
`register_model(provider_id, model_type, model_name, config)` 返回内部 ID；
引用格式 `provider_id:model_id` 冒号后是内部 ID，**不能**用展示名拼接。
插件若把模型引用字符串**存库后按名字解析**，要检查 rc.1 的 legacy_ids 兼容路径是否覆盖其用法。

### C. Provider 客户端与启停

`core.utils.model_clients` **已删除** → `core.provider.openai_compatible`
（`OpenAICompatibleLLMClient/TTS/STTClient`）。Provider 增加 `status: active|inactive`，
停用后 `get_model_client` 抛 `ProviderAPIError`；自定义 Provider 请求必须用 `model.model_name` 发给上游。
验证锚点：`kira30/core/provider/openai_compatible.py`、`provider_manager.py`。

### D. 插件模块路径（alpha.1 拆分）

`core.plugin.plugin_registry` **已删除**。新位置：`base/handlers/manager/metadata/decorators/pages/components`。
包级导入 `from core.plugin import BasePlugin, PluginContext, register, on, EventType, Priority` **两代都安全**。
`PluginContext` 新增必填注入字段（`prompt_mgr/skills_mgr/mcp_mgr/message_history/image_desc_cache/
session_buffer_mgr/message_delivery`），手工构造 PluginContext 的测试桩要补字段；
`sticker_manager` 规范名改 `sticker_mgr`（有只读兼容属性，但不支持构造关键字/赋值）。
`ctx.flush_session_messages(sid, filter_fn=...)`：alpha.3 起支持筛选谓词，返回 bool。

### E. 工作流与消息处理（alpha.3/4 拆分集中）

`core.workflow.workflow_registry` 已删除，`register_workflow/WorkflowType` 不再导出。
旧入口迁移：`SessionBuffer` → `core.chat.session_buffer`；`message_format_to_text` → `MessageFormatter.format_to_text`；
`_iter_message_images/_build_native_content` → `MessageMediaService`；`_parse_xml_msg/_add_message_ids` →
`MessageDeliveryService.parse_xml/add_message_ids`；`handle_cmt_message` → 发布 `KiraCommentEvent`；
`ImageDescCache` → `core.image_desc_cache`。**依赖 MessageProcessor 内部字段/方法的插件是重点怀疑对象**。
验证锚点：`kira30/core/message_manager.py`（看还剩什么兼容入口）、`core/workflow/src/im/`。

### F. 适配器与能力声明

旧基类 `IMAdapter/SocialMediaAdapter/LiveStreamAdapter`（`adapter_utils.py`）**已删除**。
事件字段 `message_types` → `supported_elements`（旧关键字仍兼容但插件**生产**事件要用新名）。
图片输出标签是 `img`，历史链元素类型是 `image`（两者不同）。
`LiveEventCapability/VoiceChannelCapability` **已注释不导出**（在 alpha 期用过的插件会 ImportError）。
读适配器 `emoji_dict` 属性 → 改为 `await im.get_message_metadata()` 的 `emojis`。
判断能否聊天：查 `adapter.get_capability(IMCapability)`，不要按适配器类型判断。
验证锚点：`kira30/core/adapter/__init__.py`、`capabilities.py`。

### G. 事件/钩子

`ON_COMMENT` + `@on.comment` 新增（评论插件相关才关心）。钩子签名两代一致。
用户插件不得用 `SYS_LOW/SYS_HIGH` 优先级。

### H. 人设

`persona_mgr` 新增参考图异步接口与 chat_rules；旧全局 `bot_config.selfie.path` 会被迁移。
只有动到人设/自拍字段的插件需要查。

### I. 直读/patch 框架文件（高危行为）

直接 open 框架 .py、importlib 加载框架内部、猴子补丁框架函数、shutil 覆盖框架文件 —— 
这类插件跨版本最脆。逐处确认目标文件/符号在 rc.1 是否还存在。

## 2. 审计方法（每个仓库按此执行）

1. **读预扫描 JSON**：`/var/minis/shared/gen3audit/prescan/<repo>.json` —— 已列出全部客观命中（文件:行）。
2. **逐组裁决**：对每个有命中的组（A~I），打开对应源码看**上下文**，判断：
   - 误报（注释/字符串/文档提到而已）→ 标注「误报」；
   - 真用到了且该 API 在 rc.1 已删/变异步 → **NEEDS_FIX**，写出具体文件:行 + 破坏机制；
   - 用到了但有两代兼容处理（hasattr/isawaitable 探测等）→ 验证探测逻辑对不对 → SAFE-with-compat；
   - 不确定 → 去 `/var/minis/shared/kira30` grep 框架源码确认符号存在与否，**严禁猜测**。
3. **补充扫盲点**（预扫描没覆盖的必查）：
   - manifest.json 的 `core_version`：是否声明、上界是否会挡 3.0（如 `>=2.x,<3.0` 这类写法）。
   - `import` 清单：任何 `from core.xxx import` 都要在 rc.1 里确认存在（`cd /var/minis/shared/kira30 && grep -rn "符号" core/`）。
   - 同步调用异步 API 的隐患：rc.1 变异步的那几个会话 API，插件是否**没 await** 或**在同步函数里直接调**。
   - 前端/面板（web 目录、js）：展示模型名、会话名的地方调什么 REST，rc.1 响应字段变了没（会话详情新增 internal_id 等）。
   - schema.json 里 `source=model` 选择器：rc.1 引用值是内部 ID。
4. **分级结论**（每仓一个总级）：
   - `SAFE`：零破坏点命中，可在 2.x 与 rc.1 双世代直接运行；
   - `SAFE-NOTE`：有命中但属误报/已有正确兼容/影响为零（附一句理由）；
   - `SUSPICIOUS`：有疑点需要人工复核（说明你卡在哪）；
   - `NEEDS-FIX`：确认破坏，列出**最小修复方案**（改哪个文件哪几行、参照什么模式、风险点）。
5. **写报告**：`/var/minis/shared/gen3audit/reports/<owner>_<repo>.md`，用第 3 节模板。

## 3. 报告模板（严格遵守，后续要机械汇总）

```markdown
# <owner>_<repo>
- 总级: SAFE | SAFE-NOTE | SUSPICIOUS | NEEDS-FIX
- 版本: manifest version 值 / core_version 值
- 规模: py 文件数 / 主要入口
- 命中裁决:
  - [A] fetch_memory main.py:123 → 真命中，rc1 已删 → NEEDS-FIX
  - [B] model_id xxx → 误报（只是日志）
- 修复方案(NEEDS-FIX时必填): 文件:行 + 怎么改 + 参照模式
- 备注: 一句话
```

## 4. 纪律

- 只读 `repos/` 与框架目录；**绝不修改** repos 下任何文件；报告只写 `reports/`。
- 结论必须给证据（文件:行 + 框架侧核实的符号存在性）。
- 不确定标 SUSPICIOUS 并写清疑点，**禁止硬编结论**。
- 每仓报告控制在 60 行内，命中多的也只列真命中和代表性误报。
