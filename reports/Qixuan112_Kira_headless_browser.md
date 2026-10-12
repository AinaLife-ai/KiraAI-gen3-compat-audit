# Qixuan112_Kira_headless_browser
- 总级: NEEDS-FIX
- 版本: manifest version=2.2.1 / core_version=">=2.30.0"（上界不挡 3.0，OK）
- 规模: 62 个 py（生产码仅 13 个：main/bridge/vlm/security/tokens/cookies/protocol/setup_guide + backends/*；其余 47 个在 regression/ 且仅测试用 + stubs）。主入口 main.py（BrowserPlugin(BasePlugin)），工具/页面/api/ws 全在 main.py。
- 预扫描 153 个 I 命中绝大多数是 **误报**（中文注释里的"覆盖"两字、或中文"清空/会话"字样），生产码没有真正的框架文件 patch/重写。

## 命中裁决

- [A] 会话 API：**全部误报**。生产码 `grep -n "session_mgr\|get_session\|read_memory\|fetch_memory\|update_session\|delete_session\|flush_session\|write_memory"` = 0 命中；A 组命中全是 WS 连接的"会话"(bridge.py 的 socket session/清空监听)与 README 文案。本插件不读写框架会话，**清空上下文破坏面完全不适用**。→ SAFE
- [B] 模型身份（⭐ 真命中，user 关注的"展示变 UUID"）：
  - `main.py:1986-1987`（`_diag_vlm`）真命中。迭代 `mgr.get_model_infos(pid)`，把 `f"{pid}:{mi.model_id}"` 直接展示给用户当"可选的视觉模型"。核实：`ModelInfo.model_id` 在 rc.1 = `generate_model_id()` = `uuid.uuid4().hex`（`core/provider/provider.py:51`、`core/provider/model_identity.py:20-36`、`provider_manager.py:477`）；rc.1 存的是 `models[uuid]={"model_name":..,"config":..}`（`provider_manager.py:366-367`）。2.x 该 key 就是模型名（`kira_fw/core/provider/provider_manager.py:353`）。⇒ rc.1 上这里显示成 32 位 uuid 乱码。**NEEDS-FIX**
  - `main.py:1987` `lower = str(mi.model_id).lower()` 再用 `("embedding","tts",...)` 过滤 → rc.1 上 model_id 是 uuid，**永不命中**，"可能不支持视觉"的分组完全失效（所有 llm 都进 vision，含 embedding/TTS）。**NEEDS-FIX**（同一处，改用 `entry.model_name` 判断）
  - `main.py:1960` `mid = getattr(m, "model_id", "?")` → `info.append(f"  ✅ {pid}:{mid}")`，同样给用户展示 uuid。**NEEDS-FIX**
  - `main.py:2010` `f"{dv.model.provider_id}:{dv.model.model_id}"` → 展示 uuid。**NEEDS-FIX**
  - `main.py:2417-2435` `api_models`（面板下拉数据源）真命中：读 `pm.kira_config["providers"][pid]["model_config"]["llm"]`，`for mid in llm:` 后 `name=f"{mid} ({pname})"`。rc.1 中 `mid` 是内部 uuid 键 ⇒ 面板下拉标签显示 uuid；`web/app.js` 的 `loadModelOptions()` 直接把这个 name 当 label 渲染（`app.js:700-737`）。**NEEDS-FIX**（下拉展示，正是 user 说的"展示变 UUID"）
  - `vlm.py:84` `is_vision_model()` 用 `model_id` 做 `_NON_VISION_MARKERS` 匹配 → uuid 下永不命中，永久返回 True；`vlm.py:137/155` 日志里打印 model_id（仅日志，低影响）。**NEEDS-FIX**（同机制）
  - `main.py:2409 / vlm.py:93 / web/app.js:718` 仅注释描述格式，误报。
- [C] Provider 客户端：真命中但**兼容**。`ctx.provider_mgr`、`get_default_vlm()`、`get_model_infos()`、`get_all_providers()`、`ctx.get_llm_client(model_uuid=)`、`ctx.get_default_llm_client()` 均核实存在于 rc.1（`provider_manager.py:207/406/785`、`plugin_context.py:124/132`）。`desc_img(client,image,prompt,lang)`（`common_utils.py:48`）与 `compress_image_element(media,config)`（`image_compression.py:131`）签名一致。→ SAFE
- [D] 插件模块路径：`bridge.py:330` 只是在 docstring 里提到 `plugin_registry._register_plugin_ws_for`，**无 import、无调用** → 误报。真实导入仅 `from core.plugin import ...`（两代安全）+ 若干 `core.*` 子模块，全部核实存在。
- [F] 适配器：`main.py:830-846` 真用到 `ctx.adapter_mgr.get_adapter(name)`（rc.1 `adapter_registry.py:672` 存在）+ `adapter.send_group_message/send_direct_message`（`capabilities.py:32/37` 存在）。**SAFE-NOTE**：手册建议"判断能否聊天改查 `adapter.get_capability(IMCapability)`"，此处按方法直调；但代码包了 try/except 且用 `getattr(r,"ok",False)`，不支持群聊的适配器只会令该次发送返回 False、不崩。可接受。
- [G] 事件/钩子：真用 `@on.llm_request(priority=Priority.HIGH|MEDIUM)`（`decorators.py:168` 存在；`handlers.py:15/16` MEDIUM/HIGH 存在，未用 SYS_*，正确）。回调签名 `(event, req, *_)` 与 rc.1 调用点 `handler.exec_handler(event, request, tag_set)`（`core/workflow/src/im/stages/assemble.py:24`）一致。G 组其余命中（30 个里 27 个）是 `regression/harness.py` 等里英文 `comment/state="block_comment"` 字面量 → 误报。→ SAFE
- [H] 人设：无命中（未触碰 persona/selfie）。
- [I] 直读/patch 框架文件：生产码真命中经核均为**兼容或误报**。
  - `main.py` 16 处全是中文注释"覆盖(override)" → 误报；`stage` 实际只读**插件自己的** schema.json/manifest.json（`Path(__file__)`）。
  - `backends/headless_backend.py:45` `importlib.import_module("playwright.sync_api")` = 第三方 playwright，非框架；`:570` `shutil.copytree` 复制的是 **Chromium user-data（登录态）**，非框架文件 → 误报。
  - `tokens.py:182,274` `from webui.utils import _access_token_fingerprint, _create_jwt_token` —— 真实依赖框架**私有**符号。核实 rc.1 仍在：`webui/utils.py:141`（`_access_token_fingerprint`）、`:150`（`_create_jwt_token`）。且 `tokens.py` 读 `<data>/webui.json` 的 `access_token`、`tv=sha256(access_token)[:16]`、`auth_mode` 语义与 rc.1 `verify_session_token`（`webui/utils.py:180-201`）完全对齐（代码注释已显式说明 tv 不得掺私货）。**SAFE-NOTE**：可用，但依赖框架私有符号，跨版本最脆，建议加 try/except 兜底。
  - 读 `<data>/webui.json` 取 `port`（`main.py:2500`）与 `access_token`（`tokens.py:68`）：rc.1 仍写/读该文件（`core/launcher.py:116/126`、`webui/utils.py:100-124`）→ SAFE。

## 修复方案（NEEDS-FIX，最小改动）
统一原则：**展示/判断模型一律用人类可读的 `model_name`，`model_id` 只用于引用拼接**（rc.1 引用格式 `provider_id:model_id` 本身没错，仅"显示名"坏了）。参照手册 Z 插件模式可写一个 `_model_entry_name(model_id, entry)` 兜底（3.0 取 `entry["model_name"]`，2.x/缺名回落 `mid`）。

1. `main.py:2417-2435` `api_models`：把
   `llm = (mc.get("llm") or {})` 后遍历改为兼容两代结构：
   ```python
   for mid, entry in llm.items():
       name = entry.get("model_name") if isinstance(entry, dict) else mid
       name = name or mid
       models.append({"id": f"{pid}:{mid}", "name": f"{name} ({pname})"})
   ```
   （`id` 保持 `pid:mid`，rc.1 下 `mid` 即内部 uuid，引用正确；`name` 改为 `model_name`。）
2. `main.py:1978-1993`：`mi.model_id` 展示项改读 `getattr(mi, ...)` 无 `model_name` 字段，应用 `mgr.kira_config` 或 `mi.model_config`/`model_name`。可用 `get_model_infos` 返回的 `ModelInfo` 若含 `model_name` 则用之；否则回落到 `self.ctx.provider_mgr` 的配置字典 `providers[pid]["model_config"]["llm"][mi.model_id]["model_name"]`。展示 `f"{pid}:{name}"`，过滤判断改用 `name.lower()`。
3. `main.py:1960` 与 `main.py:2010`：`m`/`dv.model` 是客户端的 `model` 对象，rc.1 客户端对象取人类名的字段需核实（`client.model` 上游名 → 建议用 `getattr(m,"model_name", None) or getattr(m,"model_id","?")`）。
4. `vlm.py:84`：`is_vision_model()` 内 `model_id` 改名判断源（优先 `model.model_name`，缺失回退 `model_id`）；`vlm.py:137/155` 日志同理。
5. 风险点：改 `api_models` 时须兼容 2.x —— 2.x 的 `llm` 值不是 dict（直接就是 config dict，`kira_fw:353`），所以必须 `isinstance(entry, dict) and entry.get("model_name")` 守卫，否则 2.x 会把 `entry` 当模型名显示成配置字典。

## 备注
框架内部交互面（导入/钩子/装饰器/provider/适配器）经本地 rc.1 grep 全部核实存在，唯一确证破坏集中在"模型展示用 model_id"（uuid 化）这一处，且同时命中命令输出、诊断工具与面板下拉。
