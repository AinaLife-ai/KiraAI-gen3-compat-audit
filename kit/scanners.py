"""AST 静态扫描器：版本绑定 / core 导入核实 / 未 await 的异步会话 API。"""
import ast, os, re, subprocess

SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv", "tests", "test", "testing"}

# rc.1 已转为异步的会话 API（插件在同步上下文直接调用 = 拿到 coroutine 静默退化）
ASYNC_IN_RC1 = {
    "update_memory", "delete_session", "get_effective_capabilities",
    "update_session_capabilities", "get_session_capabilities",
    "get_session", "get_sessions", "update_session", "get_session_message_counts",
}
# rc.1 已删除的会话 API
REMOVED_IN_RC1 = {
    "fetch_memory", "write_memory", "read_memory", "get_session_info",
    "update_session_info", "get_memory_count", "get_existing_memory_snapshot",
}
# rc.1 已删除的模块/符号
REMOVED_IMPORTS = {
    "core.plugin.plugin_registry", "core.utils.model_clients",
    "core.workflow.workflow_registry", "core.adapter.adapter_utils",
}
REMOVED_SYMBOLS = {"IMAdapter", "SocialMediaAdapter", "LiveStreamAdapter",
                   "LiveEventCapability", "VoiceChannelCapability", "register_workflow", "WorkflowType"}
VERSION_PAT = re.compile(r"rc\.?1|3\.0\.0|alpha\.?\d|v?3\.0\b", re.I)


def iter_py(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def _docstring_ids(tree):
    """收集全部 docstring 的 Constant 节点 id（真正的文档字符串豁免版本号扫描）。"""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                ids.add(id(node.body[0].value))
    return ids


def scan_plugin(root):
    """返回 dict：version_hits / removed_hits / unawaited_hits / core_imports。
    core_imports 元素: (rel, lineno, module, names, guarded) —— guarded=True 表示
    位于 try/except ImportError 结构内（双形态候选导入，属正确兼容模式）。"""
    out = {"version_hits": [], "removed_hits": [], "unawaited_hits": [], "core_imports": []}
    for path in iter_py(root):
        rel = os.path.relpath(path, root)
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception as e:
            out["removed_hits"].append((rel, 0, f"PARSE_ERROR {e}"))
            continue
        awaited = set()
        guarded_ids = set()
        doc_ids = _docstring_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                awaited.add(id(node.value))
            if isinstance(node, ast.Try):
                catches_importerror = any(
                    h.type and ((isinstance(h.type, ast.Name) and h.type.id in
                                 ("ImportError", "ModuleNotFoundError", "Exception"))
                                or (isinstance(h.type, ast.Attribute)))
                    for h in node.handlers)
                if catches_importerror:
                    for sub in ast.walk(node):
                        if isinstance(sub, (ast.Import, ast.ImportFrom)):
                            guarded_ids.add(id(sub))
        for node in ast.walk(tree):
            # 版本字符串（排除 docstring；注释本就不在 AST；超长字符串是模板/数据非逻辑）
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if len(node.value) > 500:
                    continue
                if VERSION_PAT.search(node.value) and id(node) not in doc_ids:
                    out["version_hits"].append((rel, node.lineno, node.value[:80]))
            # 已删除符号调用（豁免：同函数内有 hasattr 探测过任一已删符号 = 双世代封装分支）
            if isinstance(node, ast.Attribute) and node.attr in REMOVED_IN_RC1:
                probed = set()
                for fn_node in ast.walk(tree):
                    if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and any(n is node for n in ast.walk(fn_node)):
                        for sub in ast.walk(fn_node):
                            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                                    and sub.func.id == "hasattr" and len(sub.args) == 2
                                    and isinstance(sub.args[1], ast.Constant)
                                    and isinstance(sub.args[1].value, str)):
                                probed.add(sub.args[1].value)
                        break
                if node.attr not in probed and not (probed & REMOVED_IN_RC1):
                    out["removed_hits"].append((rel, node.lineno, node.attr))
            if isinstance(node, ast.Name) and node.id in REMOVED_SYMBOLS:
                out["removed_hits"].append((rel, node.lineno, node.id))
            # 未 await 的 rc1 异步 API（豁免：同函数内存在 isawaitable 探测 = 条件 await 兼容封装）
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
                if name in ASYNC_IN_RC1 and id(node) not in awaited:
                    enclosing_probe = False
                    for fn_node in ast.walk(tree):
                        if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if any(n is node for n in ast.walk(fn_node)):
                                for sub in ast.walk(fn_node):
                                    if (isinstance(sub, ast.Call)
                                            and ((isinstance(sub.func, ast.Attribute) and sub.func.attr == "isawaitable")
                                                 or (isinstance(sub.func, ast.Name) and sub.func.id == "isawaitable"))):
                                        enclosing_probe = True
                                        break
                                # close() 防告警模式也视为已正确处理
                                for sub in ast.walk(fn_node):
                                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                                            and sub.func.attr == "close"):
                                        enclosing_probe = True
                                        break
                                # hasattr(x, "__await__") 鸭子探测（bridge/ops 生态惯例）
                                for sub in ast.walk(fn_node):
                                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                                            and sub.func.id == "hasattr" and len(sub.args) == 2
                                            and isinstance(sub.args[1], ast.Constant)
                                            and sub.args[1].value == "__await__"):
                                        enclosing_probe = True
                                        break
                                # hasattr 探测过任一已删符号 = 双世代封装分支（其内调用必然在旧代分支）
                                for sub in ast.walk(fn_node):
                                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                                            and sub.func.id == "hasattr" and len(sub.args) == 2
                                            and isinstance(sub.args[1], ast.Constant)
                                            and sub.args[1].value in REMOVED_IN_RC1):
                                        enclosing_probe = True
                                        break
                                break
                    if not enclosing_probe:
                        out["unawaited_hits"].append((rel, node.lineno, name))
            # core 导入（仅绝对导入；`from .core.x` 是插件自有子包，不算框架引用）
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("core.") \
                    and (node.level or 0) == 0:
                out["core_imports"].append((rel, node.lineno, node.module,
                                            [a.name for a in node.names],
                                            id(node) in guarded_ids))
                if node.module in REMOVED_IMPORTS and id(node) not in guarded_ids:
                    out["removed_hits"].append((rel, node.lineno, f"module {node.module}"))
    return out


def symbol_exists(fw_root, module, names):
    """在真实框架源码里核实模块与符号存在性。返回 {symbol: bool}（module 不存在则全 False）。"""
    rel = module.replace(".", "/")
    cand = [os.path.join(fw_root, rel + ".py"), os.path.join(fw_root, rel, "__init__.py")]
    target = next((c for c in cand if os.path.exists(c)), None)
    if target is None:
        # 包级重导出：在父包 __init__ 里找
        parent = os.path.join(fw_root, os.path.dirname(rel), "__init__.py")
        if os.path.exists(parent):
            src = open(parent, encoding="utf-8").read()
            return {n: (n in src) for n in names}
        return {n: False for n in names}
    src = open(target, encoding="utf-8").read()
    res = {}
    for n in names:
        res[n] = bool(re.search(rf"(def\s+{re.escape(n)}|class\s+{re.escape(n)}|{re.escape(n)}\s*=|{re.escape(n)}[,\)])", src))
        if not res[n]:  # 可能在 __init__ 里 re-export
            res[n] = n in src
    return res
