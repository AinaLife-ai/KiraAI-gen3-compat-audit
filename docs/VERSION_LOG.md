# 框架版本沿革（每次 KiraAI 发新版都在这里加一节）

> **约定**：框架每发一个版（rc3 / 正式版 / 2.x 补丁），就在本文件**追加一节**，内容固定三块：
> ① **破坏性变更**（逐条：改了什么 / 谁会被打死 / 怎么改）② **扫描复跑结果**（跑 `tools/scan_signature_drift.py`
> + `tools/scan_logger_levels.py`，记"哪些仓库需要改、改到了哪个版本") ③ **本仓相应更新**（文档/清单是否同步）。
> 这样这个仓就是"**插件升级到 v3 的最新资料**"的唯一入口。

---

## v3.0.0-rc.2（2026-10-13）

**基线**：`74efac3`（`v3.0.0-rc.1` = `8a0b812`）

### ① 破坏性变更

| 条目 | 内容 | 谁会被打死 |
| --- | --- | --- |
| **出站身份改名** | `send_message_chain(..., self_id: str \| None)` → **`bot: User \| None`**；弃用入口 `MessageProcessor.send_message_chain` 与 `PluginContext.send_message_chain` 同步改名；`execute.py` 传 `bot=event.bot` | ①**包装它**却把签名写死的插件（TypeError）；②**直接传 `self_id=`** 的插件 |

细节与正确写法：[RC2_CHANGES.md](RC2_CHANGES.md)；签名规范：[SIGNATURE_DRIFT_v3.md](SIGNATURE_DRIFT_v3.md)。

### ② 扫描复跑结果（62 仓）

| 类别 | 结果 |
| --- | --- |
| 签名漂移（P0） | 产品代码仅 **2 仓**：`KiraAI_accelerator_plugin`（6 处）、`KiraAI-qqbot-fullmsg-bridge-plugin`（2 处）⇒ **均已修** |
| 其余 60 仓 | 无 |
| 3.0 已删/改名 API 直接调用（P1） | 4 条，逐条核实**全是**带能力探测的 2.x 回退分支 ⇒ 不是问题 |
| 日志级别误用 | 0 |

修复版本：acc **v1.0.90**（[PR #106](https://github.com/znq19/KiraAI_accelerator_plugin/pull/106)）、
bridge **v1.6.48**（[PR #55](https://github.com/znq19/KiraAI-qqbot-fullmsg-bridge-plugin/pull/55)）。
完整报告：[reports/RC2_SCAN_2026-10-13.md](reports/RC2_SCAN_2026-10-13.md)。

### ③ 本仓相应更新

- 基线全部改到 rc2（README / AUDIT_PLAYBOOK / kit README / skill）；
- 新增 [SIGNATURE_DRIFT_v3.md](SIGNATURE_DRIFT_v3.md)、[RC2_CHANGES.md](RC2_CHANGES.md)、
  [V3_UPGRADE_CHECKLIST.md](V3_UPGRADE_CHECKLIST.md)；
- 开发指南出新版：[Agent插件开发指南_v3.0rc2.md](Agent插件开发指南_v3.0rc2.md)；
- 工具入库 6 个（签名漂移 / 日志级别 / 裸属性访问 / 批量拉取 / 逐套件 rc / pygrep）。

---

## v3.0.0-rc.1（2026-10-12）

**基线**：`8a0b812`

### ① 破坏性变更（首轮全生态审计）

- 会话管理全异步化 + JSON 缓存移除（`fetch_memory`/`write_memory` 移除，改 `get_session`/`update_session`）；
- 模型身份分离（`model_id` vs `model_name` ⇒ 面板显示 uuid 化）；
- `send_xml_messages` / `_parse_xml_msg` 删除（发送/解析服务化）；
- `get_effective_capabilities` 异步化；
- 适配器能力架构（`IMCapability` / `FeedCapability`）与插件模块路径拆分。

### ② 扫描复跑结果（44 仓）

分级：SAFE 25 / SAFE-NOTE 4 / **NEEDS-FIX 15**（四批：小修 → 中 → 大（会话域）→ 大（ops））；
逐仓报告见 [`reports/`](reports/)，分级方案见 [`GEN3_COMPAT_PLAN.md`](GEN3_COMPAT_PLAN.md)。
**修复全部提出并合并**（13 + 2 个 PR）。

### ③ 本仓相应更新

首版：`reports/`（44 仓）、`prescan/`、`kit/`（双世代套件）、开发指南（rc1 版）、
`AUDIT_PLAYBOOK.md`、`DEV_MIGRATION_DOC.md`。

---

## 模板（下一次发版复制这段）

```markdown
## vX.Y.Z（YYYY-MM-DD）

**基线**：<commit>

### ① 破坏性变更
| 条目 | 内容 | 谁会被打死 |
| --- | --- | --- |
| … | … | … |

### ② 扫描复跑结果（N 仓）
| 类别 | 结果 |
| --- | --- |
| 签名漂移（P0） | … |
| 已删/改名 API（P1） | … |
| 日志级别误用 | … |
需要改的仓库与改到的版本：…

### ③ 本仓相应更新
- …
```
