## 适配：3.0 rc.1 会话接口全异步化 + SQLite 持久化（v2.1.1）

### 问题
rc.1（#360 会话 SQLite 化）移除了 `fetch_memory`/`read_memory`/`write_memory`/`get_session_info`/`get_memory_count`，
`delete_session` 等改为异步。本插件的会话读写全部基于 2.x 同步 API，且 `initialize()` 的必需方法检查
在 rc.1 上会判定缺失 → **插件自我禁用（优雅但功能全失）**。

### 修法（特征识别，不绑版本号）
新增双世代会话层（全部走 `hasattr`/`inspect.isawaitable` 探测）：
- `_sm_read_flat` / `_sm_read_chunks`：2.x `fetch_memory`/`read_memory`；3.0 `await get_session(ensure_session=False)` + `flatten_content()`/`content`
- `_sm_write_chunks`：2.x `write_memory`；3.0 `await update_session(sid, content=chunks)` —— **upsert，整体替换 content，标题/能力设置/data 全部保留**（与本插件「只清空上下文，不删会话」的招牌语义精确对应）
- `_sm_recreate`（delete_session 模式）：结果 isawaitable 探测；3.0 下删除后用 `update_session` upsert 重建
- `initialize` 的「必需方法」检查改为**世代形态识别**（两代的特征集满足其一即加载），不再因 rc.1 缺旧名而自残
- `_write_memory`/`_apply_summary`/`_reset_locked` 随之异步化；`_apply_summary` 的注释如实更新：
  rc.1 下读-改-写是两个相邻 await（窗口与框架自身 `update_memory` 的读改写同级，无新增风险量级）

### 变更面
- `main.py`：+66/-24
- `manifest.json`：version 2.1.0 → 2.1.1
- `README.md`：新增「兼容性」节

### 验证
- 仓内全套件（2.x 形态桩）：**126/126 通过**（2.x 行为零回归）
- 新增双世代功能实测（基于两代框架签名制作的桩）：
  - rc1 清空保元数据 ✓（标题/能力保留、未走删除重建）
  - rc1 `delete_session` 模式 ✓（删除→upsert 重建内容正确）
  - rc1 空会话读 ✓ ｜ 2.x 路径输出与旧版一致 ✓
- 双世代静态检查全绿（已删符号零裸用——双世代封装经 hasattr 探测豁免核实）

### 注意
- 与 ADS 的互操作契约（SUMMARY_MARKER 共享/指令让位）未动；建议与 ADS 的 3.0 适配版同批联测。
