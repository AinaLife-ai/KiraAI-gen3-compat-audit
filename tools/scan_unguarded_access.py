"""扫「钩子里的裸属性访问」：在 @on.* 钩子体内，对框架对象（event/resp/req/message/session）
的属性链访问若**不在 try 里**，一旦框架改了对象形状就会抛异常，把整条钩子中断
（S/Z 的 logger.DEBUG 就是这个失效模式：不在 try 里 ⇒ 后面的逻辑全被跳过）。

用法：python3 scan_unguarded_access.py <目录> [...]
"""
import ast
import pathlib
import sys

RISK_BASES = ("event", "resp", "req", "msg", "message", "session", "resp_", "batch")


def within_try(node, try_ranges):
    for lo, hi in try_ranges:
        if lo <= node.lineno <= hi:
            return True
    return False


def scan(path: pathlib.Path):
    out = []
    for p in sorted(path.rglob("*.py")):
        if ".git" in p.parts or "tests" in p.parts:
            continue
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        lines = src.splitlines()
        for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            decs = [ast.unparse(d) for d in fn.decorator_list]
            if not any(d.startswith("on.") or d.startswith("register.") for d in decs):
                continue
            try_ranges = [(t.lineno, t.end_lineno or t.lineno)
                          for t in ast.walk(fn) if isinstance(t, ast.Try)]
            for node in ast.walk(fn):
                if not isinstance(node, ast.Attribute):
                    continue
                # 取属性链的字面根名字
                root = node
                while isinstance(root, ast.Attribute):
                    root = root.value
                base = getattr(root, "id", "") or ""
                if not base.startswith(RISK_BASES):
                    continue
                # 只看"访问"（读），并且不在 try 里
                if within_try(node, try_ranges):
                    continue
                try:
                    expr = ast.unparse(node)
                except Exception:
                    expr = base
                if expr.count(".") < 1:
                    continue
                out.append((str(p), node.lineno, expr, lines[node.lineno - 1].strip()))
    return out


total = 0
for d in sys.argv[1:]:
    hits = scan(pathlib.Path(d))
    print(f"===== {d} =====")
    if not hits:
        print("  ✓ 钩子里没有裸访问框架对象属性（都在 try 内或无访问）")
    for f, ln, expr, code in hits:
        print(f"  ⚠ {f}:{ln}  {expr}\n      {code[:140]}")
    total += len(hits)
print(f"\n合计：{total} 处候选")
