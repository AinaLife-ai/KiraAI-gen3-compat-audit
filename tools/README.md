# tools —— v3 兼容体检脚本

> 全是**只读扫描器**（不改被扫仓库）。**沙箱里递归 `grep` 不可靠**（会静默返回空），
> 所以这里统一用 python 遍历。

## 用法速查

```bash
# ① 批量拉"我们的"仓库（GitHub API 枚举：znq19 非 fork + AinaLife-ai；可自行扩展）
python3 tools/fetch_all_repos.py                 # → /var/minis/shared/audit_rc2/<repo>/

# ② 签名漂移（本次线上事故那一类）
python3 tools/scan_signature_drift.py <目录…> [--json out.json]
#   P0-a 包装框架方法的实现体没有 **kwargs        （会让发送整条失败）
#   P0-b 给发送 API 传 self_id=                   （rc2 已改名 bot=）
#   P1   直接调用 3.0 已删/改名 API（带探测的回退分支不算）

# ③ 日志级别误用（logger.DEBUG 这种 ⇒ 异常会把整条钩子打断）
python3 tools/scan_logger_levels.py <目录…>

# ④ 钩子里的裸属性访问（同一个失效模式）
python3 tools/scan_unguarded_access.py <目录…>

# ⑤ 逐个跑测试套件、只报 rc≠0（runner 不打印是哪个失败时用）
#    用法：改脚本顶部的 HERE 指向目标仓库的 tests/
python3 tools/bridge_suite_rc.py

# ⑥ 沙箱内可靠的正则搜索
python3 tools/pygrep.py <root> <正则…>
```

## 已知局限（当"候选"看，人工复核）

1. 扫描器可能把"工厂内部辅助函数"列为候选（框架不会直接调它们）；
2. "能力探测写在**更外层函数**"的回退分支会被误报；
3. 权威判定请用插件仓库里的**精确静态守卫**（AST：工厂内嵌套 + 调 `original` ⇒ 必须 `**kwargs`），
   模板见 [../docs/SIGNATURE_DRIFT_v3.md](../docs/SIGNATURE_DRIFT_v3.md) 第 4 节。

## 本仓历史脚本

`fix_*.py` / `pr_bodies/` / `pr_helper.py` / `final_check.py` / `readme_audit.py`
是 rc1 那轮**批量修复与提 PR**用的（保留作追溯）；`clone_all.sh` 是早期的拉取脚本
（已被 `fetch_all_repos.py` 取代）。
