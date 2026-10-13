"""批量体检：**签名漂移 / rc2 兼容**。

针对这次线上事故的家族（也是会话最初的目标）做三件事，全部用 AST（注释/文档不误报）：

  P0-a **包装点签名写死**：包装/接管框架方法的函数（名字撞框架方法、或在
       `factory(original)` 里、或调用了捕获的 `original`）却**没有 `**kwargs`**
       ⇒ 框架一加参数就 TypeError。若该接管点还"不回退原实现"，后果是**主流程被打死**。
  P0-b **传了 rc2 已改名的参数**：给发送 API 传 `self_id=`（rc2 已换成 `bot=`）。
  P1   **直接调用 3.0 已删/改名的 API**：`send_xml_messages` / `_parse_xml_msg` /
       `fetch_memory` / `write_memory` / `get_session_info` / `update_session_info`
       （patch/getattr/hasattr/setattr 守卫式用法不算，那是兼容层）。

用法：python3 scan_signature_drift.py <目录> [<目录> ...] [--json out.json]
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

#: 框架侧"会被插件包装"的方法名（框架加参数就是打到这些点上）
WRAPPED = {
    "send_message_chain", "send_xml_messages", "parse_xml", "add_message_ids",
    "_parse_xml_msg", "_parse_xml", "chat_stream", "chat", "get_model_client",
    "_send_message", "send_group_message", "send_direct_message", "send_message",
    "handle", "record_outgoing", "finish_outgoing", "get_session_capabilities",
}
#: 发送类 API（rc2 把 self_id= 换成了 bot=）
SEND_APIS = {"send_message_chain", "send_xml_messages", "send_group_message",
             "send_direct_message"}
#: 3.0 已删/改名（rc1 起）
REMOVED = {"send_xml_messages", "_parse_xml_msg", "fetch_memory", "write_memory",
           "get_session_info", "update_session_info"}
#: 守卫式用法（patch / 探测）：出现在这些调用里就不算"直接调用"
GUARD_CALLS = {"getattr", "hasattr", "setattr", "delattr", "install", "PatchHandle"}


def _fname(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _captures_original(fn: ast.AST) -> bool:
    """函数体里是否引用了 `original` 之类的"原实现"（说明它是包装器）。"""
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and n.id in ("original", "orig", "_orig", "raw", "inner"):
            return True
        if isinstance(n, ast.Attribute) and n.attr in ("original", "__wrapped__"):
            return True
    return False


def scan_file(p: pathlib.Path):
    hits = []
    try:
        src = p.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
    except Exception:
        return hits
    lines = src.splitlines()

    def add(kind, sev, node, why, code=None):
        ln = getattr(node, "lineno", 0)
        hits.append({
            "kind": kind, "sev": sev, "line": ln, "why": why,
            "code": (code if code is not None else lines[ln - 1].strip())[:180],
        })

    # ── P0-a：包装点签名写死 ─────────────────────────────────
    #   判定"这是包装器"：①名字撞框架方法；或②它**嵌在 factory(original) 之类**的函数里
    #   （那才是"接管框架方法"的实现体）。工厂本身（只收 original）不参与判定 —— 它
    #   不需要 **kwargs，误报过一轮。
    factories = {}
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        a = fn.args
        names = {x.arg for x in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)}
        if names & {"original", "orig", "_orig", "raw", "inner"} and len(names) <= 2:
            for sub in ast.walk(fn):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub is not fn:
                    factories[id(sub)] = fn.name

    # ★ 工厂**内部辅助函数**不算接管点：判据 = 既不调 original、也**没有被工厂 return 出去**
    #   （被 return 的才是"装上去替换框架方法"的实现，如 _save_memory；
    #     parse_args/run_one 这类只服务本工厂，框架不会直接调它们）。
    internal = set()
    for fnode in [n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        names = {x.arg for x in list(fnode.args.posonlyargs) + list(fnode.args.args) + list(fnode.args.kwonlyargs)}
        if not (names & {"original", "orig", "_orig", "raw", "inner"}):
            continue
        called = {_fname(c.func) for c in ast.walk(fnode) if isinstance(c, ast.Call)}
        returned = {_fname(r.value) for r in ast.walk(fnode)
                    if isinstance(r, ast.Return) and r.value is not None}
        for sub in ast.walk(fnode):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub is not fnode:
                if sub.name in called and not _captures_original(sub) \
                        and sub.name not in returned:
                    internal.add(id(sub))

    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        inside_factory = id(fn) in factories
        if id(fn) in internal:
            continue
        if fn.name not in WRAPPED and not inside_factory:
            continue
        # 工厂本身、纯 lambda 式转发不判
        a = fn.args
        own = {x.arg for x in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)}
        if own and own <= {"original", "orig", "_orig", "raw"} and len(own) == 1:
            continue
        if a.kwarg is None:
            n_pos = len(a.posonlyargs) + len(a.args)
            where = f"（{factories[id(fn)]} 里）" if inside_factory else ""
            add("P0-a 包装点签名写死", "P0", fn,
                f"{fn.name}(){where} 有 {n_pos} 个位置参数、无 **kwargs ⇒ 框架加参数即 TypeError",
                code=f"def {fn.name}({ast.unparse(a)})")

    # ── P0-b / P1：调用面 ────────────────────────────────────
    guard_lines = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _fname(n.func) in GUARD_CALLS:
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    guard_lines.add((n.lineno, a.value))
    # ★ 真正的"能力探测"：外层 if/elif 的判据里有 hasattr(x, "<名字>")，
    #   或**同一个函数体**里出现过 hasattr(x, "<名字>") ⇒ 说明该调用处在世代分支里。
    if_func_has = []          # (起, 止, 名字)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = set()
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and _fname(c.func) in ("hasattr", "getattr") and len(c.args) >= 2:
                a2 = c.args[1]
                if isinstance(a2, ast.Constant) and isinstance(a2.value, str):
                    names.add(a2.value)
        if names:
            if_func_has.append((fn.lineno, getattr(fn, "end_lineno", fn.lineno), names))

    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = _fname(n.func)
        guarded = any(abs(n.lineno - ln) <= 1 and nm == name for ln, nm in guard_lines)
        for kw in n.keywords:
            if kw.arg == "self_id" and name in SEND_APIS:
                add("P0-b 传了 rc2 已改名参数", "P0", n,
                    f"{name}(self_id=…) —— rc2 起该参数改名为 bot=，会 TypeError")
        if name in REMOVED and not guarded:
            # 外层 if 里带 hasattr("<name>") ⇒ 世代分支，不算直接调用
            probed = any(lo <= n.lineno <= hi and name in names
                         for lo, hi, names in if_func_has)
            if probed:
                continue
            add("P1 直接调用 3.0 已删/改名 API", "P1", n,
                f"{name}(…) 在 KiraAI 3.0（含 rc2）已删/改名 ⇒ 需要能力探测或换代实现")
    return hits


def main():
    argv = sys.argv[1:]
    out_json = None
    if "--json" in argv:
        i = argv.index("--json")
        out_json = argv[i + 1]
        del argv[i:i + 2]
    args = argv

    report = {}
    sev_order = {"P0": 0, "P1": 1}
    for d in args:
        root = pathlib.Path(d)
        if not root.exists():
            continue
        for repo in ([root] if any(root.glob("*.py")) else sorted(x for x in root.iterdir() if x.is_dir())):
            hits = []
            for p in sorted(repo.rglob("*.py")):
                if any(part in (".git", "node_modules", "__pycache__") for part in p.parts):
                    continue
                for h in scan_file(p):
                    rel = str(p.relative_to(repo))
                    h["file"] = rel
                    h["test"] = ("/tests/" in "/" + rel) or pathlib.Path(rel).name.startswith("test_")
                    hits.append(h)
            if hits:
                hits.sort(key=lambda h: (sev_order.get(h["sev"], 9), h["file"], h["line"]))
                report[repo.name] = hits

    if out_json:
        pathlib.Path(out_json).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    # 摘要
    def prod(hits):
        return [h for h in hits if not h.get("test")]
    total_p0 = sum(1 for hs in report.values() for h in prod(hs) if h["sev"] == "P0")
    total_p1 = sum(1 for hs in report.values() for h in prod(hs) if h["sev"] == "P1")
    print(f"仓库数（有命中）：{len(report)}   P0={total_p0}   P1={total_p1}\n")
    for repo, hits in sorted(report.items(),
                             key=lambda kv: (-sum(1 for h in prod(kv[1]) if h["sev"] == "P0"), kv[0])):
        p0 = sum(1 for h in prod(hits) if h["sev"] == "P0")
        hits = prod(hits) or hits
        if not hits:
            continue
        flags = "★" * min(p0, 3)
        print(f"{flags or '·'} {repo}: P0={p0} P1={sum(1 for h in hits if h['sev']=='P1')}")
        for h in hits[:6]:
            print(f"    [{h['sev']}] {h['file']}:{h['line']}  {h['why']}")
            print(f"          {h['code']}")
        if len(hits) > 6:
            print(f"    … 还有 {len(hits)-6} 条")


main()
