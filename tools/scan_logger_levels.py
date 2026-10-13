"""通用扫描：把「日志级别当属性用」（`xxx.DEBUG` 这类）全找出来 —— AST 判定，
注释/文档字符串里的示例不算。

用法：python3 scan_logger_levels.py <目录> [<目录> ...]
额外还会报出几种相邻的可疑写法：
  · `logger.level` 与字符串比较（如 `== "DEBUG"`）—— 级别不是字符串；
  · `setLevel("DEBUG")` 传字符串；
"""
import ast
import pathlib
import sys

LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET"}


def scan(root: pathlib.Path):
    hits = []
    for p in sorted(root.rglob("*.py")):
        if any(part in (".git", "node_modules") for part in p.parts):
            continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except SyntaxError as exc:
            hits.append((str(p), 0, f"语法错误 {exc}", "ERR"))
            continue
        lines = src.splitlines()
        for node in ast.walk(tree):
            # ① xxx.DEBUG 这种把级别当属性用
            if isinstance(node, ast.Attribute) and node.attr in LEVELS:
                try:
                    base = ast.unparse(node.value)
                except Exception:
                    base = getattr(node.value, "id", "") or ""
                if base.endswith("logging"):
                    continue                      # logging.DEBUG / _logging.DEBUG 合法
                hits.append((str(p), node.lineno,
                             lines[node.lineno - 1].strip(), f"{base}.{node.attr}"))
            # ② 级别与字符串比较
            if isinstance(node, ast.Compare):
                left = node.left
                if isinstance(left, ast.Attribute) and left.attr == "level":
                    for c in node.comparators:
                        if isinstance(c, ast.Constant) and isinstance(c.value, str) \
                                and c.value.upper() in LEVELS:
                            hits.append((str(p), node.lineno,
                                         lines[node.lineno - 1].strip(),
                                         f"level == '{c.value}'（级别不是字符串）"))
            # ③ setLevel("DEBUG")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "setLevel":
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                            and a.value.upper() in LEVELS:
                        hits.append((str(p), node.lineno,
                                     lines[node.lineno - 1].strip(),
                                     f'setLevel("{a.value}")（应传 logging 常量/整数）'))
    return hits


bad_total = 0
for d in sys.argv[1:]:
    root = pathlib.Path(d)
    hits = scan(root)
    print(f"===== {d} =====")
    if not hits:
        print("  ✓ 没找到「级别当属性 / 级别与字符串比较 / setLevel(字符串)」的写法")
    for f, ln, code, why in hits:
        print(f"  ✗ {f}:{ln}  [{why}]\n      {code[:150]}")
    bad_total += len(hits)
print(f"\n合计可疑点：{bad_total}")
