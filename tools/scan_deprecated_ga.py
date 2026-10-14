"""批量体检：**3.0 正式版（GA）弃用方法使用扫描**。

依据 docs/GA_DEPRECATIONS.md（基线 v3.0.0 = 9db3d67）。全部用 AST，注释/字符串不误报。

  DEP-1  get_adapter_infos(          ⇒ 改用 get_adapters_info(（2.x 也有新名，直接换）
  DEP-2  .message_types 属性读/写     ⇒ GA 弃用；双世代需探测 supported_elements
  DEP-3  调用 kw message_types=…      ⇒ 同上（构造 MessageMetadata 等）
  DEP-4  message_processor.flush_session_messages / send_message_chain / handle_im_message
                                    ⇒ 改用 ctx. 同名方法 / ctx.event_bus.publish
  DEP-5  adapter.send_group_message / adapter.send_direct_message 直调
                                    ⇒ GA docstring 弃用；3.0 走 capability 或 ctx
  DEP-6  ConfigType.Enum / EnumField( ⇒ 用 StringField/IntField/FloatField + options

豁免：hasattr/getattr 探测分支里的命中不报（与 scan_signature_drift 同套逻辑）；
      定义点本身不报（如 def get_adapter_infos 是框架/兼容层）。

用法：python3 scan_deprecated_ga.py <目录> [<目录> ...] [--json out.json]
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

GUARD_CALLS = {"getattr", "hasattr", "setattr", "delattr", "install", "PatchHandle"}
DEP4_METHODS = {"flush_session_messages": "改用 ctx.flush_session_messages(sid[, filter_fn])",
                "send_message_chain": "改用 ctx.send_message_chain(session, chain[, bot=…])",
                "handle_im_message": "改用 await ctx.event_bus.publish(event)"}
DEP5_METHODS = {"send_group_message", "send_direct_message"}


def _fname(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _recv_text(node) -> str:
    """取调用的接收者文本（adapter / self.adapter / x.y.adapter 等）。"""
    try:
        if isinstance(node, ast.Attribute):
            return ast.unparse(node.value).lower()
    except Exception:
        pass
    return ""


def scan_file(p: pathlib.Path):
    hits = []
    try:
        src = p.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
    except Exception:
        return hits
    lines = src.splitlines()

    def add(kind, node, why, code=None):
        ln = getattr(node, "lineno", 0)
        hits.append({"kind": kind, "sev": "DEP", "line": ln, "why": why,
                     "code": (code if code is not None else lines[ln - 1].strip())[:180]})

    # ── 能力探测豁免（与 scan_signature_drift 同款）：函数体内出现过 hasattr/getattr(x,"名")
    probed = []   # (起, 止, 名字集)
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
            probed.append((fn.lineno, getattr(fn, "end_lineno", fn.lineno), names))

    def is_probed(node, name):
        return any(lo <= node.lineno <= hi and name in ns for lo, hi, ns in probed)

    defined_names = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_names.add((n.name, n.lineno))

    for n in ast.walk(tree):
        # DEP-1：调用 get_adapter_infos(
        if isinstance(n, ast.Call) and _fname(n.func) == "get_adapter_infos":
            if not is_probed(n, "get_adapter_infos"):
                add("DEP-1 弃用: get_adapter_infos()", n,
                    "GA 已 @deprecated ⇒ 直接改用 get_adapters_info()（2.x 两代都有新名，零风险）")

        # DEP-4：message_processor.<方法>(
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in DEP4_METHODS and "message_processor" in _recv_text(n.func):
            if not is_probed(n, n.func.attr):
                add(f"DEP-4 弃用: MessageProcessor.{n.func.attr}()", n,
                    f"GA 已 @deprecated ⇒ {DEP4_METHODS[n.func.attr]}")

        # DEP-5：adapter.send_group_message / send_direct_message 直调
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in DEP5_METHODS:
            recv = _recv_text(n.func)
            # 新式：capability/im 对象调用（接收者不含 adapter 字样）⇒ 不报
            if "adapter" in recv and not is_probed(n, "get_capability"):
                add(f"DEP-5 弃用: 适配器直调 {n.func.attr}()", n,
                    "GA 标记 Deprecated wrapper ⇒ 3.0 走 adapter.get_capability(IMCapability)."
                    f"{n.func.attr}(…) 或统一 ctx.send_message_chain")

        # DEP-3：任何调用带 message_types= 关键字
        if isinstance(n, ast.Call):
            for kw in n.keywords:
                if kw.arg == "message_types":
                    add("DEP-3 弃用: message_types= 构造参数", n,
                        "GA 弃用 ⇒ 改用 supported_elements=（双世代请先探测字段名）")

        # DEP-2：.message_types 属性读写（不含 kw 构造、不含 def）
        if isinstance(n, ast.Attribute) and n.attr == "message_types":
            if not is_probed(n, "message_types"):
                add("DEP-2 弃用: .message_types 属性", n,
                    "GA 弃用 ⇒ 元数据用 supported_elements；适配器用 get_capability(IMCapability)"
                    ".get_message_metadata().supported_elements（2.x 无此属性，双世代需探测）")

        # DEP-6：ConfigType.Enum / EnumField(
        if isinstance(n, ast.Attribute) and n.attr == "Enum" and "configtype" in _recv_text(n):
            add("DEP-6 弃用: ConfigType.Enum", n,
                "两代均已弃用 ⇒ 改用 StringField/IntField/FloatField + options")
        if isinstance(n, ast.Call) and _fname(n.func) == "EnumField":
            add("DEP-6 弃用: EnumField()", n,
                "两代均已弃用 ⇒ 改用 StringField/IntField/FloatField + options")

        # DEP-7：直读 SessionManager.chat_memory（2.x-only 常驻字典；3.0 无此属性，
        # getattr 拿到 None ⇒ 静默空结果 —— session_merger 实战挖出的一类潜伏 bug）。
        # 豁免：兼容/镜像层自身的探测写法（同函数内有 "chat_memory" 的 hasattr/getattr 探测）。
        if isinstance(n, ast.Attribute) and n.attr == "chat_memory":
            if not is_probed(n, "chat_memory"):
                add("DEP-7 高危: 直读 chat_memory（3.0 无此属性）", n,
                    "3.0 已移除常驻缓存 ⇒ 改走镜像层/异步 get_session；"
                    "2.x 分支须探测并带 3.0 回退")

    return hits


def main():
    argv = sys.argv[1:]
    out_json = None
    if "--json" in argv:
        i = argv.index("--json")
        out_json = argv[i + 1]
        del argv[i:i + 2]
    report = {}
    for d in argv:
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
                hits.sort(key=lambda h: (h["file"], h["line"]))
                report[repo.name] = hits
    if out_json:
        pathlib.Path(out_json).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    prod = {r: [h for h in hs if not h.get("test")] for r, hs in report.items()}
    prod = {r: hs for r, hs in prod.items() if hs}
    print(f"仓库数（产品代码有命中）：{len(prod)}   命中总数={sum(len(v) for v in prod.values())}\n")
    for repo, hits in sorted(prod.items(), key=lambda kv: -len(kv[1])):
        print(f"· {repo}: {len(hits)} 条")
        for h in hits[:8]:
            print(f"    {h['file']}:{h['line']}  [{h['kind']}] {h['why']}")
            print(f"          {h['code']}")
        if len(hits) > 8:
            print(f"    … 还有 {len(hits)-8} 条")


main()
