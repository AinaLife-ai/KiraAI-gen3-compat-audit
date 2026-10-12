# znq19_KiraAI_LLOneBot_patch
- 总级: SAFE-NOTE
- 版本: 无 manifest.json（非 KiraAI 插件）/ core_version 不适用；README 标注「LLBot 7.12.14 兼容补丁 v12」
- 规模: 3 个文件（llbot.js 72076 行、README.md 179 行、LICENSE）；**0 个 py**（非标准插件结构，无可被框架装载的 KiraAI 代码）
- 结构澄清（任务关切点）: 本仓**不是 KiraAI 插件**，也**不 patch KiraAI 任何框架文件**。
  它是一个**对第三方 OneBot 实现 LLOneBot/LuckyLilliaBot 的 `bin/llbot/llbot.js` 的整文件替换补丁**
  （README：「全程只覆盖一个文件，不会动 KiraAI 本体」——该"一个文件"是 LLBot 的 `llbot.js`，不是 kira30 下的文件）。
  `llbot.js` 是被 rolldown 打包的 Node/TS 单文件（内含 node_modules 内联代码）。它只**产出** OneBot v11 协议数据供 KiraAI 的 QQ 适配器消费。
  核实：仓库内不含任何 `core/*.py`、无 `from core.` 导入、无对 `/var/minis/shared/kira30` 文件的引用。
- 命中裁决（预扫描仅有 F 组 5 + G 组 59 + I 组 1，**全部落在打包 JS 上，均为误报**）:
  - [F] 5 命中 → 误报：llbot.js:44339/44343/44481/49123/49521 的 `send_group_message`/`send_group_message_reaction` 是 **LLBot 自身的 OneBot API 名 + zod schema**（`defineApi("send_group_message", ...)`），非 KiraAI 侧 `send_direct_message` 破坏点；与 rc.1 的 `IMCapability`/`supported_elements` 无关
  - [G] 59 命中 → 误报：全部是打包 JS 里的 `comment` 标识符——群申请附加信息字段（`comment: string$1().describe("申请附加信息")`，llbot.js:43632 等）、XML/HTML 解析器变量（:`commentPropName`、:`const { curly, comment }`）、内联 nodemailer 代码（:65860-65867）等。**与 KiraAI 的 `ON_COMMENT`/`on.comment` 钩子无任何关系**
  - [I] 1 命中 → 误报：llbot.js:25365 注释「仅使用上方 llbot.js 常量，不读 config_*.json」——是补丁对**自身**配置读取的说明，非读/patch KiraAI 框架文件
  - 无 A/B/C/D/E/H 命中；无 core_version 声明问题（非插件）
- 兼容性核实（该补丁在 rc.1 下的**协议面**是否仍匹配）:
  - rc.1 QQ 适配器 `core/adapter/src/qq/im.py` 支持的合并转发元素为 `forward`（`_SUPPORTED_ELEMENTS` 含 "forward"，im.py:60），
    收消息时对 `type=="forward"` 取 `msg["message_id"]` 后调 `bot.get_forward_msg(message_id)`（im.py:355-360）；
    补丁在 llbot.js:10962-10973 产出的 Forward 段 `data` 同时带 `id/message_id/res_id/preview`，`:25879` 的 `get_forward_msg`
    参数 schema 明确接受 `message_id` 为 number(shortId) 或 string(long msgId/resid) → **字段与 rc.1 消费侧一致**
  - 语音：rc.1 走 `get_record(file_id, output_format="mp3")` 并读 `data.base64`（im.py:363-369）；补丁在 llbot.js:24950+ 的 get_record
    **始终返回 base64**，并将内置精简 ffmpeg 不支持的 mp3 自动回落为 wav（:25015 注释 / decodeSilk）→ 返回结构满足 rc.1 的 `.data.base64` 读取，**不会因版本变化失败**
  - 结论：补丁仅依赖 **OneBot v11 协议契约**（而非 KiraAI 版本 API），KiraAI 2.x→rc.1 的破坏点（SessionManager/Provider/Adapter 基类等）**均不触及本仓**
- 备注: 该仓跨版本最脆的其实是**LLBot 上游**版本（README 明示「升级 LLBot 后补丁会没掉，官方更新会覆盖 llbot.js」），属补丁与 LLOneBot 自身的版本耦合，与 KiraAI 3.0rc1 兼容性无关。就 KiraAI 侧而言：**零破坏点，双世代可用**。
