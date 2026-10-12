## 3.0 rc.1 兼容（会话镜像双世代层）+ 跨适配器合并（webchat 入局）（v2.9.0）

### A. rc.1 兼容修复（核心）

rc.1 移除常驻 `chat_memory` 缓存与全部同步记忆 API（`fetch_memory`/`read_memory`/`write_memory`/
`get_session_info`/`get_memory_count`），`update_memory`/`delete_session` 变异步。本插件的破坏面：

- `memory_access.py` 全层直读内部 `chat_memory` dict → rc.1 下属性不存在 → **静默全损（合并永远为空）**
- `merge_engine.py` 三处 `read_memory` + `asyncio.to_thread(write_memory)` 摘要写回
- `hard_reset.py` 的写穿/delete 重开（且在 `to_thread` 线程区内，rc.1 下无法直接 await）
- `main.py` 猴补丁 `session_mgr.update_memory`（rc.1 变异步，同步包装会破坏「落盘后 drain」语义）
- `_clear_session_context` 用 `delete_session` 整删（连会话能力设置一起抹掉）
- `cross_session.resolve_target_sid` 用 `get_session_info()`（rc.1 已删）

### 修法（特征识别，不绑版本号；同步内部架构零改动）

新增 `session_mirror.py`：
- **读**：`SessionMirror` —— 3.0 的 chat_memory 等价镜像，异步入口（on_llm_request/命令/工具/API）预热，
  TTL 1.5s 节流；2.x 直通 live dict。**memory_access 五个同步函数签名一个没改**，合并引擎/时间线/
  组解析器全部不用动。
- **写**：异步区 `sm_write_chunks`（2.x 保持 to_thread 语义；3.0 原生 `update_session` upsert，
  标题/能力/描述全保留）；线程区（to_thread 的 `_apply_sync`）3.0 下写操作入**延迟队列**，
  `apply_to_request` 在 to_thread 返回后冲刷；超时走 `shield` + done-callback 兜底冲刷迟到写。
- `_wrap_update_memory` 按 `iscoroutinefunction` 分流：2.x 同步包装 / 3.0 async 包装（先 await 落盘再 drain）。
- `_clear_session_context` 改**内容置空式清空**（两代都保元数据；对齐 reboot 的 memory_only 语义）。
- `resolve_target_sid` 异步化（2.x `get_session_info()` / 3.0 `await get_sessions()`）。
- 会话事件处理器里同步失效镜像（`session_memory_written`/`session_deleted` 载荷两代一致，已核实）。

### B. 新特性：跨适配器合并（用户点名要 webchat 入局）

`merge_across_adapters`（默认关，schema「运行模式」节）：
- 关 = 现状（按适配器分治，行为逐字不变）；
- 开 = 所有适配器会话并入同一个 `all_merged` 组 —— **webui 内置聊天 `webchat:dm:admin` 与 QQ 群/私聊
  从此共享同一条人生时间线**；`allowed_adapters` 白名单照常生效（实测：限 qq 时 webchat 不进组）。

### 验证
- 2.x（v2.34.8）真实框架集成测试：**33/33 通过**（零回归）；其余套件 15+110+70+26+10 全过
- 3.0 rc.1 功能实测（按 rc.1 真实签名制作的 SQLite 形态桩）：
  镜像读（list/meta/flat/chunks，含 webchat 会话）✓ 双世代写+镜像失效 ✓ 清空保元数据 ✓
  延迟队列冲刷 ✓ 2.x 直读直写零变化 ✓ 跨适配器合并/白名单共存 ✓
- 双世代静态检查全绿

### 变更面
`session_mirror.py`（新增 190 行）+ `memory_access.py`/`merge_engine.py`/`hard_reset.py`/`main.py`/
`cross_session.py`/`group_resolver.py`/`schema.json`/`manifest.json`（2.8.5→2.9.0）/`README.md`

### 注意
与 reboot v2.1.1 / ADS v2.1.5 的互操作契约（SUMMARY_MARKER 共享、指令让位）未动，建议同批联测。
