"""AST 静态扫描器：版本绑定 / core 导入核实 / 未 await 的异步会话 API。"""
import ast, os, re, subprocess

SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv"}

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
VERSION_PAT = re.compile(r"rc\.?1|3\.0\.0|alpha\.?\d|__version__|v?3\.0\b", re.I)


def iter_py(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def _is_docstring(tree, node):
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            if child is node and isinstance(parent, (ast.Module, ast.FunctionDef,
                                                     ast.AsyncFunctionDef, ast.ClassDef)):
                if parent.body and parent.body[0] is child:
                    return True
    return False


def scan_plugin(root):
    """返回 dict：version_hits / removed_hits / unawaited_hits / core_imports。"""
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
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                awaited.add(id(node.value))
        for node in ast.walk(tree):
            # 版本字符串（排除 docstring；注释本就不在 AST）
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if VERSION_PAT.search(node.value) and not _is_docstring(tree, node):
                    out["version_hits"].append((rel, node.lineno, node.value[:80]))
            # 已删除符号调用
            if isinstance(node, ast.Attribute) and node.attr in REMOVED_IN_RC1:
                out["removed_hits"].append((rel, node.lineno, node.attr))
            if isinstance(node, ast.Name) and node.id in REMOVED_SYMBOLS:
                out["removed_hits"].append((rel, node.lineno, node.id))
            # 未 await 的 rc1 异步 API
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
                if name in ASYNC_IN_RC1 and id(node) not in awaited:
                    # 排除定义处与同义赋值接收（保守只报直白调用）
                    out["unawaited_hits"].append((rel, node.lineno, name))
            # core 导入
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("core."):
                out["core_imports"].append((rel, node.lineno, node.module,
                                            [a.name for a in node.names]))
                if node.module in REMOVED_IMPORTS:
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
