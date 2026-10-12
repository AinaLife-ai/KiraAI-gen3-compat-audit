#!/usr/bin/env python3
"""KSM memory_access.py：dict 源改双世代（2.x live / 3.0 镜像）。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_session_merger_plugin/memory_access.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
def J(*ls): return CR.join(ls)

old_head = J('import time', 'from typing import Any, Dict, List, Optional, Tuple', '', 'from .timeout_utils import is_expired, session_type_of')
new_head = J('import time', 'from typing import Any, Dict, List, Optional, Tuple', '',
             'from .session_mirror import peek_mirror',
             'from .timeout_utils import is_expired, session_type_of',
             '',
             '',
             'def _chat_data(session_mgr) -> Optional[dict]:',
             '    """会话内容字典源（双世代）。',
             '',
             '    2.x：直读 live ``chat_memory``（同步、始终新鲜）；',
             '    3.0 rc.1+：无常驻缓存（SQLite 持久化），读 ``SessionMirror`` ——',
             '    由异步入口（消息钩子/命令/工具/API）先 ``refresh_mirror`` 预热。',
             '    镜像为空时返回 {}（与"无会话"语义一致），绝不抛错。',
             '    """',
             '    data = getattr(session_mgr, "chat_memory", None)',
             '    if isinstance(data, dict):',
             '        return data',
             '    try:',
             '        return peek_mirror(session_mgr)',
             '    except Exception:',
             '        return {}')
assert src.count(old_head) == 1
src = src.replace(old_head, new_head)

# list_existing_session_ids（独占形态：单列 return []）
old_a = J('    data = getattr(session_mgr, "chat_memory", None)', '    if not isinstance(data, dict):', '        return []')
new_a = J('    data = _chat_data(session_mgr)', '    if not isinstance(data, dict):', '        return []')
assert src.count(old_a) == 1, f"list_ids 形态 {src.count(old_a)}"
src = src.replace(old_a, new_a)

# safe_read_memory / safe_fetch_memory（组合判断 + return []）
old_b = J('    data = getattr(session_mgr, "chat_memory", None)', '    if not isinstance(data, dict) or sid not in data:', '        return []')
new_b = J('    data = _chat_data(session_mgr)', '    if not isinstance(data, dict) or sid not in data:', '        return []')
n = src.count(old_b)
assert n == 2, f"read/fetch 形态应为 2，实得 {n}"
src = src.replace(old_b, new_b)

# safe_session_meta（组合判断 + return empty）
old_c = J('    data = getattr(session_mgr, "chat_memory", None)', '    if not isinstance(data, dict) or sid not in data:', '        return empty')
new_c = J('    data = _chat_data(session_mgr)', '    if not isinstance(data, dict) or sid not in data:', '        return empty')
assert src.count(old_c) == 1
src = src.replace(old_c, new_c)

open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("memory_access OK")
