# KiraAI v3 兼容升级资料仓（gen3-compat-audit）

> **这是什么**：把 KiraAI 插件生态从 2.x 升级到 **3.0** 的全部资料 —— 结论、逐仓报告、
> 双世代测试套件、自动扫描工具、升级清单。**以后涉及"插件升到 v3"的事，都以这个仓为准。**
>
> **当前基线：`KiraAI v3.0.0-rc.2`**（tag `74efac3`）。rc1 的资料保留在 `reports/`/`prescan/` 里作为历史。

---

## 🚀 我只想升级一个插件 → 三步

```bash
# 1) 拉套件 + 把插件交给双世代跑
git clone https://github.com/AinaLife-ai/KiraAI-gen3-compat-audit && cd KiraAI-gen3-compat-audit
python3 kit/run.py --plugin /path/to/your_plugin \
    --core2x /path/to/KiraAI-2.x --core30 /path/to/KiraAI-3.0-rc2

# 2) 跑"签名漂移"扫描（本次线上事故的那类问题，2 秒出结果）
python3 tools/scan_signature_drift.py /path/to/your_plugin

# 3) 按清单逐条过
#    docs/V3_UPGRADE_CHECKLIST.md
```

**必须先看的四份文档**：

| 文档 | 什么时候看 |
| --- | --- |
| 🧭 **[docs/V3_UPGRADE_CHECKLIST.md](docs/V3_UPGRADE_CHECKLIST.md)** | **升级一个插件**时逐条打勾（含代码模板） |
| 🧨 **[docs/SIGNATURE_DRIFT_v3.md](docs/SIGNATURE_DRIFT_v3.md)** | **接管/包装框架方法**之前务必看（写死签名 = 线上事故） |
| 🔀 **[docs/RC2_CHANGES.md](docs/RC2_CHANGES.md)** | rc1 → **rc2** 的破坏性变更逐条（`self_id=` → `bot=`） |
| 📋 **[AUDIT_PLAYBOOK.md](AUDIT_PLAYBOOK.md)** | 要**全仓体检**或复现历史结论时看（流程 + 判据 + 坑） |

---

## 📌 最新一轮结论（2026-10-13，基线 rc2）

**扫描范围：62 个仓库**（znq19 非 fork + AinaLife-ai + Qixuan112 三个 + reboot fork 例外）。

| 类别 | 结论 |
| --- | --- |
| **签名漂移**（包装框架方法却写死签名） | 产品代码命中 **2 个仓库**：`KiraAI_accelerator_plugin`、`KiraAI-qqbot-fullmsg-bridge-plugin` ⇒ **均已修**（见下） |
| 其余 60 仓 | 无签名漂移、无日志级别误用 |
| **3.0 已删/改名 API** 的直接调用 | 仅 4 条，逐条核实**全是**带能力探测的 2.x 回退分支 ⇒ **不是问题** |

**两个参考实现（可直接照抄的 PR）**：

* acc **[#106](https://github.com/znq19/KiraAI_accelerator_plugin/pull/106)**（v1.0.90）——
  "全仓签名体检"：一处一处改成 `*args, **kwargs` 原样透传，并加了**通用静态守卫**
  （AST 扫描：凡"工厂内嵌套 + 调用 `original`"的实现体必须带 `**kwargs`）。
* bridge **[#55](https://github.com/znq19/KiraAI-qqbot-fullmsg-bridge-plugin/pull/55)**（v1.6.48）——
  发送落点 `_send_message` + 旁听包装 `_handle_message` 的透传修法。

详细扫描表：[reports/RC2_SCAN_2026-10-13.md](reports/RC2_SCAN_2026-10-13.md)

---

## 🗂 目录导航

```
README.md                      ← 你在这里（入口 + 最新结论）
docs/
  V3_UPGRADE_CHECKLIST.md      ★ 升级清单（逐条打勾）
  SIGNATURE_DRIFT_v3.md        ★ 签名漂移：为什么、怎么查、怎么修
  RC2_CHANGES.md               ★ rc1→rc2 破坏性变更
  Agent插件开发指南_v3.0rc1.md   开发指南（rc1 版，rc2 的差异见上面那份）
AUDIT_PLAYBOOK.md              ★ 全仓体检流程（判据/坑/复现方式）
GEN3_COMPAT_PLAN.md            最初的分级方案与批次计划（历史）
DEV_MIGRATION_DOC.md           给插件作者的迁移说明（历史）
kit/                           双世代测试套件（桩 + 运行器 + 扫描器）
tools/                         自动扫描/修复脚本（含签名漂移、日志级别、批量拉取）
reports/                       逐仓报告（rc1 轮，44 仓）+ 最新的 RC2 扫描表
prescan/                       逐仓预扫描 JSON（rc1 轮）
skill/kiraai-plugin-dev/       给 AI 编码用的插件开发 skill
```

---

## 🧰 工具速查

| 工具 | 用途 |
| --- | --- |
| `tools/scan_signature_drift.py <目录…>` | **签名漂移**：包装框架方法却写死签名 / 传 rc2 已改名参数（P0）· 直接调用已删 API（P1） |
| `tools/scan_logger_levels.py <目录…>` | 日志级别误用（`logger.DEBUG` 这类 ⇒ 会让整条钩子中断） |
| `tools/scan_unguarded_access.py <目录…>` | 钩子里的裸属性访问（同一个"异常 ⇒ 整条中断"的失效模式） |
| `tools/fetch_all_repos.py` | 按 GitHub API 枚举"我们的"仓库并批量拉源码（体检前置步骤） |
| `tools/bridge_suite_rc.py` | 逐个跑测试套件、只报 `rc≠0`（runner 不打印是哪个失败时用） |
| `tools/pygrep.py <root> <正则…>` | 沙箱里递归 `grep` 不可靠 ⇒ 用这个（python 遍历） |
| `kit/run.py` | 双世代（2.x / 3.0）跑插件的兼容套件 |

---

## 📝 本仓更新记录

| 日期 | 内容 |
| --- | --- |
| 2026-10-13 | **基线升到 rc2**；新增签名漂移规范 / rc2 变更 / 升级清单；补 62 仓 rc2 扫描报告与工具；收到两个参考 PR 的修法 |
| 2026-10-12 | 首轮：44 仓 rc1 全生态审计（`reports/`）、分级方案（`GEN3_COMPAT_PLAN.md`）、双世代套件（`kit/`）、开发指南 |
