# KiraAI v3.0.0-rc.1 插件生态兼容性总审计与分级升级方案

> 生成：2026-10-12 ｜ 审计执行：主代理 + 子代理集群（全部论断经框架真实源码核实）
> 框架锚点：**3.0 = v3.0.0-rc.1 `8a0b812`**（本地 `/var/minis/shared/kira30`）｜ **2.x = v2.34.8**（`/var/minis/shared/kira_fw`）
> 备份仓：`https://github.com/AinaLife-ai/KiraAI-gen3-compat-audit`（本文件 + 44 份逐仓报告 + 双世代测试套件 + 预扫描数据）

## 0. 这份文档怎么用（给接手会话）

**你是修复执行者时**：在本文第 4 章找到你被指派的仓库小节，里面有【问题清单（文件:行）】【修复模式（可直接照抄的代码）】【验证方法】【PR 纪律】。严格按小节执行，不要自由发挥。修复前先读对应逐仓报告（`reports/<owner>_<repo>.md`）获取完整上下文。

**原则红线**（所有修复任务通用）：
1. 兼容判断**严禁绑版本号**（不写 `if version >= "3.0"`），一律**特征识别**（`hasattr` / `inspect.isawaitable` / try-import 候选链）。
2. 双世代同包：修完必须 2.x 与 rc1 都能跑，**功能零丢失**。
3. 推 PR 前必须重新 fork（保持上游最新）；提交身份 `AinaLife-ai <293270655+AinaLife-ai@users.noreply.github.com>`；**只有用户明确说可以推 PR 才推**。
4. PR 不得删除上游任何文件；推前逐文件与上游比对；推后核查「删除文件数=0」与本地⇄PR 哈希一致。
5. 每个修复任务都要跑双世代测试套件（`kit/`，用法见第 5 章）并附带该仓自有测试。

## 1. 审计覆盖

- **znq19**：全部 KiraAI 插件级仓库 34 个（orig 33 + fork 但视同维护的 kiraai-reboot-pulgin；按用户指示另纳入 fork 的 KiraAI-subagent-plugin）。排除：框架 fork（KiraAI）、纯 fork（github_tool/qq-enhance/api-balance/ai_html/Group-Manager/headless_browser——后两者以 Qixuan112 为准）、非插件（Alife fork、pixiv-token-tool 独立工具）。
- **AinaLife-ai**：KiraAI 插件级 orig 7 个（github_tool / kira_wiki / com3d2 / IndexTTS / fortune / hotnews / AinaLife.Notes）。排除：Alife 系插件 9 个（非 KiraAI）、全部 fork（它们的 orig 在 znq19 侧已覆盖）、Kira-Environment-Manager（桌面工具非插件）、SnowLuma（协议框架 fork）。
- **Qixuan112**：KiraAI_Group-Manager-Plugin、Kira_headless_browser（用户点名）。
- **合计 44 仓本次审计** + **5 仓已在前期会话完成 rc1 兼容**（第 3 章）。

## 2. 总分级表（44 仓）

### ✅ SAFE（25 仓，零改动可直接双世代运行）

| 仓库 | 一句话依据 |
| --- | --- |
| znq19: forward_fix / xml_tag_fixer / payload_defense / anti-harass / typing_indicator / group_member_viewer / speaker_identity / history / pixiv_image_searcher / bili_audio_sender / midi_play_sender / mimo-tts / logic_helper / sticker_control / sysinfo / output_word_replacer | 仅包级 core.plugin 导入 + 稳定钩子 + OneBot send_action 模式（rc1 QQ get_client/send_action 保留）；不碰会话库/模型身份 |
| znq19: token_stats | **已具备** model_name 优先双世代展示（main.py:1106-1130）；用量字段两代一致 |
| znq19: agnes_image_gen | 已显式做 2.x/3.0 自拍参考图双形态适配 |
| znq19: deepwiki | "clear"全是自有候选列表语义 |
| AinaLife-ai: fortune / IndexTTS / github_tool / com3d2 / AinaLife.Notes / kira_wiki | 导入与 API 面全部核实 rc1 存在 |
| Qixuan112: Group-Manager | 全走 send_action；message_types 为 deprecated 但可用 |

### 🟡 SAFE-NOTE（4 仓，能跑但有非契约依赖/小建议）

| 仓库 | 注意点 |
| --- | --- |
| znq19/ws_keepalive | 猴补丁 rc1 目标 `napcat_client.client.ws_compatible_connect` 仍在且签名兼容；但属内部路径耦合，**每次框架大版本必复查** |
| znq19/daily_report | 依赖 QQ 适配器保留的 `send_group_message` 委托（qq.py:170）；建议迁 IMCapability（非阻塞） |
| znq19/LLOneBot_patch | 它 patch 的是第三方 LLBot 的 js，不是 KiraAI 文件；与 KiraAI 版本解耦 |
| AinaLife-ai/hotnews | `message_types=` deprecated 但可用；建议迁 supported_elements |

### 🔴 NEEDS-FIX（15 仓）

| # | 仓库 | 核心破坏 | 严重度 | 承接 |
| --- | --- | --- | --- | --- |
| 1 | znq19/fold_fan_formatter | `core.plugin.plugin_handlers` 导入在 rc1 已删 → 无法加载 | 高 | **本会话可做** |
| 2 | znq19/KiraAI-subagent-plugin | 同上导入破坏 + 快速模型标签显 UUID | 高 | **本会话可做** |
| 3 | znq19/KiraKB_Plugin | 面板嵌入模型下拉 label 显 UUID（main.py:192） | 中 | **本会话可做** |
| 4 | znq19/KiraAI_midflight_message | `message_processor.message_format_to_text` rc1 已无（有兜底不崩，buffer 路径降级） | 低 | **本会话可做** |
| 5 | znq19/KiraAI-openai-stream-compat | 裸导入 `core.utils.model_clients` rc1 已删 → 无法加载 | 高 | **本会话可做** |
| 6 | znq19/KiraAI_model_config_query | 插件存在意义=展示模型名，rc1 下 `/模型` 输出 uuid 乱码 | 中 | **本会话可做** |
| 7 | znq19/KiraAI_qzone | `ctx.get_session_capabilities` rc1 变异步未 await → 图片模式静默失效 | 中 | 新会话（批次B） |
| 8 | Qixuan112/Kira_headless_browser | 5 处模型展示/判断用 model_id → uuid 乱码 + 视觉过滤失效 | 中 | 新会话（批次B） |
| 9 | znq19/KiraAI_accelerator | 招牌「边写边发」依赖的 `MessageProcessor.send_xml_messages`/`_parse_xml_msg` rc1 已删 → 功能静默失效；面板下拉显 UUID | 高 | 新会话（批次B） |
| 10 | znq19/kiraai-reboot-pulgin | 全套 2.x 同步会话 API（启动自检即自我禁用） | 高 | 新会话（批次C，三件套同批） |
| 11 | znq19/KiraAI_auto_delete_session | 同上 + 直读 `chat_memory` 内部缓存 | 高 | 新会话（批次C） |
| 12 | znq19/KiraAI_session_merger | `memory_access.py` 全层直读 `chat_memory` → rc1 静默全损 | 高 | 新会话（批次C） |
| 13 | znq19/KiraAI_ops | 会话域全灭（列举/信息/清空/删除/能力）+ 模型域 UUID/语义错配 + skills/mcp 域静默失效 | 高 | 新会话（批次D） |

> 注：#1-#6 标「本会话可做」= 改动小且边界清晰（单点导入/单行 label/单调用点），本审计会话可直接完成；但因 PR 推送需用户逐次确认，实际推送也可并入后续会话。

## 3. 已完成 rc1 兼容的仓库（无需再做，文档标出 ✓）

| 仓库 | 完成版本 | 证据 |
| --- | --- | --- |
| znq19/KiraAI_Alife_memory_Z_plugin | v2.22.8 | PR #150（rc1 兼容测试套件，双世代 1025 测试全绿；含"未来框架探针"） |
| znq19/KiraAI-qqbot-fullmsg-bridge-plugin | v1.6.45 | PR #53（会话 API 兼容层按能力探测零版本号，rc1/2.x 全套件全绿） |
| znq19/KiraAI_persona_progression_plugin | v1.2.1 | PR #2（rc1 会话 SQLite 化双形态层 + manifest core_version 声明，双世代 264/264） |
| znq19/KiraAI_sustained_chat_plugin | v2.7.0 | PR #52（rc1 适配：能力异步化/会话记忆双世代助手）+ README PR #53 |
| znq19/KiraAI_Default-Chat-Z- | v1.10.0 | PR #55（同 S 版适配）+ README PR #56 |

这些仓库的兼容模式（特征识别、双世代助手、防版本绑定测试）就是本方案第 4 章各修复任务的参照母版。

## 4. 逐仓修复投递包（新会话接手指引）

> 每个小节自包含：问题（文件:行）→ 修法（照抄级）→ 验证 → 纪律。
> 通用参照模式（下称「双模式」）：
> - **导入双形态**：`try: from core.plugin.handlers import X  # 3.0+` / `except ImportError: from core.plugin.plugin_handlers import X  # 2.x`
> - **模型展示名**（照抄 Z 插件已验证模式）：
>   ```python
>   def _model_entry_name(mid, entry):
>       if isinstance(entry, dict) and entry.get("model_name"):
>           return entry["model_name"]
>       return mid  # 2.x / 缺名兜底
>   ```
>   对 ModelInfo 对象则用 `getattr(info, "model_name", None) or info.model_id`。
> - **会话双世代助手**（照抄 KPP v1.2.1 / bridge v1.6.45 已验证模式）：
>   ```python
>   import inspect
>   async def _read_flat(sm, sid):
>       if hasattr(sm, "fetch_memory"):            # 2.x 同步形态
>           return list(sm.fetch_memory(sid) or [])
>       s = await sm.get_session(sid, ensure_session=False)  # 3.0rc1+
>       return s.flatten_content() if s else []
>   async def _write_chunks(sm, sid, chunks):      # 写穿覆写=保留标题/能力/data
>       if hasattr(sm, "write_memory"):
>           sm.write_memory(sid, chunks); return
>       await sm.update_session(sid, content=chunks)
>   ```
>   清空上下文同理：`update_session(sid, content=[])`，**禁用 delete+重建**（会误伤 capabilities/data/标题）。
> - **异步探测**：`res = ctx.get_session_capabilities(sid); caps = (await res) if inspect.isawaitable(res) else res`

### 批次 A —— 本会话可直接做（6 仓，改动最小）

**A1. znq19/KiraAI_fold_fan_formatter_plugin**
- 问题：`main.py:39` `from core.plugin.plugin_handlers import event_handler_reg, EventType` 在 rc1 无法加载。rc1 等效物已核实：`core/plugin/handlers.py:20(EventType)/102(event_handler_reg)`，同名同语义。
- 修法：该行改「导入双形态」try/except。其余不动。
- 验证：`kit` 静态套件全绿（当前会抓到此行）；2.x 下跑仓内 tests/test_no_duplicate.py。
- 版本：patch +0.0.1；README 兼容性声明加 3.0。

**A2. znq19/KiraAI-subagent-plugin**
- 问题①：`main.py:266` 同 A1 的导入破坏（同法修）。
- 问题②：`main.py:946-948` `_fast_model_label` 用 `getattr(m,"model_id","")` 拼展示 → 改 `getattr(m,"model_name",None) or getattr(m,"model_id","")`。
- 顺带（可选，文档注明即可）：`available_models` 配置在 rc1 需填内部 ID——schema hint 里说明「3.0 请从模型配置页复制内部 ID」。
- 验证：kit 静态套件 + `test_model_display_never_raw_uuid`（在仓根写 compat_targets.py 暴露 `_fast_model_label` 的纯函数部分）。

**A3. znq19/KiraKB_Plugin**
- 问题：`main.py:192` 面板嵌入模型下拉 label 用 `info.model_id`（rc1=UUID）。
- 修法：改 `f"{info.provider_name} / {getattr(info,'model_name',None) or info.model_id}"`。`uuid` 字段勿动（rc1 引用值本就内部 ID）。
- 验证：kit 模型展示测试；面板下拉人工看一眼。

**A4. znq19/KiraAI_midflight_message_plugin**
- 问题：`main.py:537` `await self.ctx.message_processor.message_format_to_text(chain)` rc1 已删（有 except 兜底不崩，但 buffer 路径文本化降级）。
- 修法：优先探测 rc1 的格式化服务：`fmt = getattr(self.ctx, "message_formatter", None)`（rc1 注入的公共服务 `MessageFormatter.format_to_text`），有则用；无则旧路径；再回退现状 text。注意核对 rc1 `MessageFormatter.format_to_text` 确切签名（kira30 里 grep 后再落码）。
- 验证：仓内 tests/ 全绿（该仓测试基建完善）+ kit 静态套件。

**A5. znq19/KiraAI-openai-stream-compat**
- 问题：`main.py:34-37` 裸导入 `core.utils.model_clients`（rc1 已删，迁至 `core.provider.openai_compatible`，三类客户端核实存在于该文件 :41/:202/:244）→ rc1 加载即 ModuleNotFoundError。
- 修法：改三代候选链（先 3.0 路径 except 再 2.x 路径）；STT 的可选 try 语义保留。覆写点已核实与 rc1 基类签名一致（chat/chat_stream/__init__），无需改。
- 验证：kit 静态套件（当前必抓）+ 仓内自带测试 + 实装冒烟（流式与信封兜底各一次）。

**A6. znq19/KiraAI_model_config_query_plugin**
- 问题：`main.py:43-52` `_format_model_value` 把 `default_llm` 值 `provider_id:model_id` 的冒号后段原样展示 → rc1 下 `/模型` 输出 uuid 乱码（该插件的全部存在意义）。
- 修法：解析冒号后段时，用 `ctx.provider_mgr.get_model_info(ref)`（rc1 支持内部 ID/无歧义旧别名）或直接读 providers 配置取 `model_config.<type>.<id>.model_name`；`getattr(...,"model_name",None) or mid` 兜底。注意 key→model_type 映射（default_llm→llm 等）。
- 验证：kit 模型展示测试；两代桩各跑一次命令。

### 批次 B —— 新会话项目（3 仓，中等工程量）

**B1. znq19/KiraAI_qzone_plugin**（报告：reports/znq19_KiraAI_qzone_plugin.md）
- 唯一破坏：`main.py:1949` 同步调 `ctx.get_session_capabilities(sid)`（rc1 已 async，plugin_context.py:105）→ coroutine 被 `.get()` → AttributeError 被吞 → 图片 native 模式恒失效。
- 修法：`_session_image_mode` 改 async + isawaitable 探测（报告里有现成代码），调用点 :1962 同步链改 await。
- 顺带建议：manifest 补 core_version；`message_types=` 迁 `supported_elements=`（非阻塞）。
- 验证：仓内 tests/ + kit 的 `test_no_unawaited_async_session_api`（当前会抓到 :1949）。

**B2. Qixuan112/Kira_headless_browser**（报告：reports/Qixuan112_Kira_headless_browser.md）
- 破坏面=模型展示/判断 5 处全用 model_id（rc1=uuid）：
  ① `main.py:2417-2435` api_models 面板下拉 label；② `main.py:1978-1993` 诊断工具展示+视觉过滤分组；③ `main.py:1960`、④ `main.py:2010` 诊断输出；⑤ `vlm.py:84` is_vision_model 过滤失效（uuid 永不命中标记 → 所有 llm 被当视觉模型）。
- 修法：报告 §修复方案 1-5 逐条给了代码；核心=展示/判断一律 `model_name`，引用仍用内部 ID。vlm.py 的判断源优先 model_name。
- 风险点（报告已标）：2.x 的 get_models 值不是 dict——必须 isinstance 守卫，别把 2.x 的配置 dict 当名字显示。
- 验证：kit 静态+模型展示测试；regression/ 目录自带回归全绿；面板下拉人工核查。

**B3. znq19/KiraAI_accelerator_plugin**（报告：reports/znq19_KiraAI_accelerator_plugin.md）
- 破坏①（招牌功能）：`main.py:1698` patch 目标 `MessageProcessor.send_xml_messages` rc1 已删 + `main.py:985` `mp._parse_xml_msg` rc1 已删 → 「边写边发/抢先发送」静默失效（install 护栏跳过、try/except 吞错，无报错）。
- 修法①：落点迁 `MessageDeliveryService`（kira30 core/workflow/src/im/message_delivery.py：parse_xml/add_message_ids/send_message_chain）；先探测旧目标存在性，不存在则改包 `ctx.message_delivery`。注意：rc1 发送按「链」而非「段」，剥离台账要对账口径重写——**这是本批次最难的点，需要理解 ExecuteAgentStage 的 XML 协调流程后再动手**。
- 破坏②：`main.py:1866` api_providers 面板 label 用 dict key（uuid）→ 按「模型展示名」模式改（报告给了现成代码）。
- 非阻断：`main.py:1435` `mp.min_message_delay` 迁 `ctx.message_delivery`（getattr 兜底不崩）。
- 验证：仓内 tests/ 50+ 自检桩全绿；两代真加载；面板下拉人工核查。

### 批次 C —— 新会话项目（会话三件套，必须同批做，互操作有契约）

> 三仓共享摘要头标记约定（reboot compat.py 的 SUMMARY_MARKER 互认）与指令避让约定，**必须同批修改同批联测**。参照母版：KPP v1.2.1（PR #2）与 bridge v1.6.45（PR #53）的双世代会话层。

**C1. znq19/kiraai-reboot-pulgin**（fork 视同 znq19 维护）
- 破坏：全套 2.x 同步会话 API（fetch_memory/read_memory/write_memory/delete_session/get_session_info/get_memory_count/update_memory）；rc1 上启动自检（main.py:547-560）即自我禁用。
- 修法：加双世代会话层（上文「会话双世代助手」），清空默认走 `update_session(sid, content=[])`（== 其 memory_only 语义，保留元数据）；delete_session 模式保留但 await 化。
- **专项难点**：`main.py:1200` 注释声明「read_memory→write_memory 之间禁止 await」的原子性假设——rc1 全异步后该窗口性质改变，需重审框架每轮末尾 update_memory 的时序，必要时改用「读快照→改→整体 update_session」的单写点模式。
- 验证：仓内 tests/（注意 tests/harness.py 是 2.x 形态桩，需扩成两代桩各跑一遍）+ kit 动态测试（写 compat_targets.py 暴露 clear_session，跑 `test_clear_session_preserves_metadata_both_gens`）。

**C2. znq19/KiraAI_auto_delete_session_plugin**
- 破坏：同 C1 的 API 面 + `main.py:753` 直读 `session_mgr.chat_memory`（rc1 已删）。
- 修法：同双世代会话层；写穿式重开（:757）映射 `update_session(sid, content=new_chunks)`；delete 模式（:760-763）await 化；压缩触发链（fetch/read/count）全部走助手。
- 验证：同 C1；并跑与 reboot 的互操作联测（摘要头互认、指令避让）。

**C3. znq19/KiraAI_session_merger_plugin**
- 破坏：`memory_access.py` 全层直读内部缓存 `chat_memory`（绕过 API 的刻意设计，:4 注释）→ rc1 属性删除 → **静默全损**（合并永远为空，无报错）；`hard_reset.py` 的 write_memory/delete_session/fetch_memory/get_session_info 同需迁移。
- 修法：memory_access 重写为 rc1 异步只读快照（`get_sessions(include_content=False)` / `get_session(sid, ensure_session=False)`+`flatten_content()`——语义恰好对应其「不触发写盘」初衷）；调用点同步→异步改造面较大，是主工程量。hard_reset 写穿映射 update_session。
- 验证：仓内 tests/（tests/test_integration_framework.py 引用已删的 plugin_registry/plugin_handlers，测试桩本身也要双世代化）+ 与 C1/C2 联测。

### 批次 D —— 新会话项目（1 仓，大）

**D1. znq19/KiraAI_ops_plugin**（报告：reports/znq19_KiraAI_ops_plugin.md，84 行详尽裁决）
- 破坏三面：
  ① **会话域**：session_inventory/session_cap 全用已删 API（get_session_info/update_session_info/write_memory/get_memory_count/chat_memory），4 个变异步的 API 未 await（delete_session 丢 coroutine→「没删却报 deleted=True」）；
  ② **模型域**：provider_cap 的 models 展示全是 uuid 键、register_model 第三参语义已变 model_name、add/update/delete 的 ID 语义错配；
  ③ **skills/mcp 域**：`getattr(message_processor,"skills_manager"/"mcp_manager")` rc1 为 None → 两域静默失效（应优先 ctx.skills_mgr/ctx.mcp_mgr）。
- 修法：报告「修复方案」1-4 逐条给了落点与参照模式。
- 验证：仓内 tests + kit 全套 + 逐工具实操冒烟（list/info/clear/delete/models/add_model）。

## 5. 双世代测试套件（kit/）用法与验收基线

位置：`/var/minis/shared/gen3audit/kit/`（备份仓同路径）。

```bash
cd /var/minis/shared/gen3audit/kit
python3 run.py --plugin /path/to/plugin   # 静态 4 条 + 动态（有 compat_targets.py 时）
```

**验收基线（每个修复任务完成 definition-of-done）**：
1. kit 静态 4 条全绿（无 rc1 已删符号 / 无版本绑定 / 无未 await 的 rc1 异步 API / 全部 core 导入在两代框架核实存在）。
2. 插件自有测试两代全绿（2.x 用 `/var/minis/shared/kira_fw`，3.0 用 `/var/minis/shared/kira30`；桩是 2.x 形态的要扩双世代桩）。
3. 触碰会话读写的插件：必须在仓根补 `compat_targets.py` 并跑通 kit 动态层（清空保元数据 / 模型展示非 uuid / 未来形态优雅降级）。
4. 行为对拍：修复前后在 2.x 的行为指纹一致（防止修 rc1 把 2.x 修坏）。
5. PR 纪律：重新 fork → 特性分支 → 单提交或少提交 → 身份自检（git log -1 --format=%ae 必须是 `293270655+AinaLife-ai@users.noreply.github.com`）→ 删除文件数=0 → mergeable 确认 → **用户确认后才推**。

## 6. 框架事实速查（核实过的，别凭印象）

| 主题 | 2.x (v2.34.8) | 3.0rc1 (8a0b812) |
| --- | --- | --- |
| 会话读 | `fetch_memory(sid)` 同步拍平 / `read_memory` 分块 | `await get_session(sid)` → `session.content` / `flatten_content()` |
| 会话写 | `write_memory(sid, chunks)` 同步 | `await update_session(sid, content=chunks)`（整体替换） |
| 会话列表/信息 | `get_session_info()` | `await get_sessions(include_content=False)` |
| 会话删除 | `delete_session(sid)` 同步 | 同名**异步** |
| 计数 | `get_memory_count(sid)` | `len(session.content)` / `await get_session_message_counts()` |
| 能力 | `get_effective_capabilities`/`update_session_capabilities`/`ctx.get_session_capabilities` 全同步 | 同名全**异步** |
| 内部缓存 | `session_mgr.chat_memory` dict | **已删**（SQLite + database_migrations） |
| 模型身份 | model_id 即可读名 | model_id=内部稳定 ID（uuid 形态），可读名在 `model_name`；配置 `model_config_version=2` |
| 模型引用 | `provider_id:模型名` | `provider_id:内部ID`（schema 选择器自动给内部 ID） |
| Provider 客户端 | `core.utils.model_clients` | `core.provider.openai_compatible`（旧路径已删） |
| 插件子模块 | `core.plugin.plugin_registry/plugin_handlers` | `core.plugin.{manager,handlers,metadata,decorators,pages,components}`（包级导入两代安全） |
| 消息格式化 | `MessageProcessor.message_format_to_text` 等 | `MessageFormatter` / `MessageMediaService` / `MessageDeliveryService`（plugin_context 注入） |
| 适配器发送 | adapter.send_group_message | 能力化 `adapter.get_capability(IMCapability)`；rc1 QQ 适配器仍保留委托方法 |
| 事件字段 | `message_types` | `supported_elements`（旧名兼容但 deprecated） |
| 预留能力 | — | LiveEventCapability/VoiceChannelCapability **已注释不导出** |
| ctx 新增 | — | `message_history` / `flush_session_messages(sid, filter_fn=)` / `skills_mgr` / `mcp_mgr` / `message_delivery` |

## 7. 审计过程产物索引

| 产物 | 路径 |
| --- | --- |
| 审计手册（子代理执行版） | `AUDIT_PLAYBOOK.md` |
| 44 份逐仓报告（含证据与修法） | `reports/<owner>_<repo>.md` |
| 机械预扫描原始数据 | `prescan/<repo>.json` + `_summary.json` |
| 双世代测试套件 | `kit/`（README 在内） |
| 仓清单（44） | `repo_list.txt` |
| 开发者迁移文档（用户给定底稿） | 附件 shared-cb5155ff.md（已核对与框架源码一致） |

**审计方法可信度说明**：44 仓全部经过「机械预扫描（9 组 60+ 模式）→ 逐命中人工/子代理裁决 → 框架侧 grep 符号核实 → 主代理抽查复核」四步；子代理报告（accelerator/headless/ops/qzone 等）的关键论断均由主代理二次核实（含两处独立重复审计结论一致：accelerator）。预扫描对 JS/HTML/MD 同样覆盖。
