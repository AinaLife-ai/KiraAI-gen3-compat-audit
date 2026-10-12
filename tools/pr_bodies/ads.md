## 适配：3.0 rc.1 会话接口全异步化 + SQLite 持久化（v2.1.5）

### 问题
rc.1 移除了 `fetch_memory`/`read_memory`/`write_memory`/`get_session_info`/`get_memory_count`，
`delete_session` 等转为异步。本插件的压缩/重开/计数全链路基于 2.x 同步 API，
且 `initialize()` 的必需方法检查在 rc.1 上会判缺 → **插件自我禁用（优雅但功能全失）**。

### 修法（特征识别，不绑版本号）
- 新增双世代会话层（`_sm_read_flat`/`_sm_read_chunks`/`_sm_write_chunks`/`_sm_count`），
  全部 `hasattr`/`inspect.isawaitable` 探测：
  - 读：2.x `fetch_memory`/`read_memory`；3.0 `await get_session(ensure_session=False)` + `flatten_content()`/`content`
  - 写：2.x `write_memory`；3.0 `await update_session(sid, content=...)`（upsert；**整体替换 content，
    标题/描述/能力设置全部保留**——与「写穿式重开」语义精确对应）
  - 计数：2.x `get_memory_count`；3.0 `len(session.content)`
- `_write_back` 异步化：write-through 与 delete+重建两条路径都双世代（3.0 删除后 `update_session` upsert 自建）。
- `initialize` 的必需方法检查改为**世代形态识别**（两代特征集满足其一即加载），不再因缺旧名自残。
- 涉及调用点：连续压缩、手动重开、异步摘要补写、后台合并写回、轮数/字数双触发——共 11 处。

### 测试桩同步升级（tests/run_tests.py）
原测试桩直接调 2.x 同步 API 驱动真框架 SessionManager——在 3.0 框架上桩自己先崩。
本次把桩也双世代化：**3.0 下用真 SQLite 会话库**（`DatabaseManager` + `DatabaseService.init_tables()` +
`SessionManager.initialize()`）跑同一套集成测试，会话 API 访问经 `_sm_flat/_sm_count/_sm_append` 助手两代分流。

### 验证
- **2.x（v2.34.8）：54/54 通过**（行为零回归）
- **3.0 rc.1（8a0b812，真 SQLite 持久化）：54/54 通过**
- 双世代静态检查全绿

### 变更面
`main.py` +75/-24；`tests/run_tests.py` +45/-16；`manifest.json` 2.1.4→2.1.5；`README.md` 新增兼容性节。

### 注意
与 reboot 插件的互操作契约（SUMMARY_MARKER 共享/指令接管）未动；建议与 reboot v2.1.1 同批联测。
