# znq19_KiraAI_model_config_query_plugin
- 总级: NEEDS-FIX
- 版本: manifest version=1.0.0；core_version=未声明（无上界，不会被版本门槛挡，但也无兼容意图声明）
- 规模: 1 个 py 文件（main.py，124 行）+ manifest.json + schema.json；入口 ModelConfigQueryPlugin(BasePlugin)
- 命中裁决:
  - [B] main.py:44-52 `_format_model_value`（`provider_id, model_id = value.split(":",1)` → `f"{provider_name}:{model_id}"`）→ **真命中**。证据：rc.1 `core/config/default.py:71` `"default_llm": None,  # Provider ID - Model ID`，即 `models.*` 的值 = `provider_id:model_id`；而 rc.1 `model_id` 是**内部稳定 ID**（迁移模型为 `uuid5(...).hex`，见 `core/provider/model_migration.py:44-46`；新模型 `uuid4().hex`，见 `core/provider/model_identity.py:35`），人类可读名挪到 `ModelInfo.model_name`（`core/provider/provider.py:51-71`）。插件只用 `provider_map`（providers 配置的 `name` 字段）替换冒号**前**段，冒号**后**的 model_id 原样展示 → rc.1 上 `/模型` 会输出 `OpenAI:3f2a9c...uuid`（uuid 乱码），未解析 model_name。2.x 上 model_id 即可读名，故 2.x 正常、rc.1 破坏。
  - [B] main.py:57 `models_config.get("default_llm")` 等键名 → 误报（键名在 rc.1 仍存在，`default.py` 同名列齐全；破坏点在值语义而非键名）。
  - [G] main.py:89 `on_im_message(self, event: KiraMessageEvent)` → SAFE。rc.1 `core/plugin/decorators.py:150` `on.im_message(priority=...)` 存在；`KiraMessageEvent` 存在（`core/chat/message_utils.py:110`）。
  - 框架符号存在性核实（import 清单全部通过）: `core.plugin` 导出 `BasePlugin/logger/register_tool/on/Priority`（`core/plugin/__init__.py:6,21`）；`core.chat.message_utils.KiraMessageBatchEvent/KiraMessageEvent` 存在；`core.chat.MessageChain`（message_utils.py:340）存在；`core.chat.message_elements.Text`（:133）存在；`ctx.message_processor.send_message_chain(session=...)`（main.py:108）rc.1 签名 `send_message_chain(self, session, chain, ...)` 一致（`core/message_manager.py:60`）；`event.discard(force=True)`（`message_utils.py:200`）存在；`ctx.config.get_config`（`core/config/config_loader.py:82`）存在；`event.session.sid`（`core/chat/session.py:78`）存在。以上均无 rc.1 破坏。
- 修复方案: **main.py:43-52 `_format_model_value`**。不要直接回显 `value.split(":")[1]`，需把内部 model_id 解析为上游可读名。两种改法：
  1) 优先 `ctx.provider_mgr`（main.py:4055 同仓另一插件用法），rc.1 有 `get_model_info(provider_id, model_type, model_id)` / `get_models(provider_id)`（`core/provider/provider_manager.py:372,393`），从 `ModelInfo.model_name` 取名；
  2) 或直接读配置：`cfg = providers_config.get(provider_id, {})`，按 key→type 映射（default_llm→llm 等，见 `model_identity.DEFAULT_MODEL_TYPES`）取 `cfg["model_config"][type][model_id]["model_name"]`，取不到再回退 model_id。
  参照顾问手册 B 节已验证模式 `_model_entry_name(mid, entry)`：`entry.get("model_name") or mid`（2.x 无 model_name 自动回退，行为不变）。风险点：当前函数**不知道 model_type**，需把 `_get_model_config` 里的 key 一并传入（key 名→type 有固定映射）；若保持 2.x/rc.1 双世代，须先 `getattr(entry,"model_name",None)` 再回退。
- 备注: 唯一破坏点是"模型标识展示"，恰是本插件存在的全部意义（查询默认模型名称），rc.1 下将退化为显示内部 uuid；其余 import/钩子/发送路径均安全。
