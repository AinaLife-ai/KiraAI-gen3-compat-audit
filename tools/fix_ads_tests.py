#!/usr/bin/env python3
"""ADS tests/run_tests.py 双世代化：rc1 下用真 SQLite SessionManager。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_auto_delete_session_plugin/tests/run_tests.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
def J(*ls): return CR.join(ls)
E = []

# 1) import inspect
E.append(('import asyncio', 'import asyncio' + CR + 'import inspect'))

# 2) 模块级双世代助手（插在 import 区后）
anchor2 = 'from pathlib import Path'
helpers = J(*[
    'from pathlib import Path',
    '',
    '',
    '# ── 双世代会话桩助手（仅测试侧）：2.x 同步 API 直调；3.0 异步 API await ──',
    'async def _sm_flat(sess, sid):',
    '    if hasattr(sess, "fetch_memory"):',
    '        return list(sess.fetch_memory(sid) or [])',
    '    s = await sess.get_session(sid, ensure_session=False)',
    '    return (s.flatten_content() if s else []) or []',
    '',
    '',
    'async def _sm_count(sess, sid):',
    '    if hasattr(sess, "get_memory_count"):',
    '        return sess.get_memory_count(sid)',
    '    s = await sess.get_session(sid, ensure_session=False)',
    '    return len(s.content) if s else 0',
    '',
    '',
    'async def _sm_append(sess, sid, chunk):',
    '    r = sess.update_memory(sid, chunk)',
    '    if inspect.isawaitable(r):',
    '        await r',
])
E.append((anchor2, helpers))

# 3) 构造点：main() 里先占位，main_run() 里按世代构造
E.append((
    '    sess = SessionManager(db=None, kira_config=cfg, event_bus=None)',
    J('    # 会话管理器在 main_run()（asyncio.run 的循环内）按世代构造：',
      '    # 2.x 直接内存形态；3.0 需要真 SQLite 库且 initialize() 是异步。',
      '    sess = None')))
E.append((
    J('    async def main_run():',
      '        from core.chat import Session, MessageChain, User'),
    J('    async def main_run():',
      '        nonlocal sess',
      '        _probe = SessionManager(db=None, kira_config=cfg, event_bus=None)',
      '        if hasattr(_probe, "fetch_memory"):',
      '            sess = _probe  # 2.x：内存 JSON 形态',
      '        else:',
      '            # 3.0：会话持久化在 SQLite —— 起真库（临时文件）跑真实持久化路径',
      '            from core.db.db_mgr import DatabaseManager',
      '            from core.db.service import DatabaseService',
      '            _db_file = Path(tempfile.mkdtemp(prefix="ads_gen3_")) / "test.db"',
      '            _dbm = DatabaseManager(f"sqlite+aiosqlite:///{_db_file}")',
      '            await _dbm.init()',
      '            _svc = DatabaseService(_dbm)',
      '            await _svc.initialize()  # 建表（含 database_migrations）',
      '            sess = SessionManager(db=_svc, kira_config=cfg, event_bus=None)',
      '            await sess.initialize()',
      '        ctx.session_mgr = sess  # 构造完成后挂回共享 ctx（占位期是 None）',
      '        from core.chat import Session, MessageChain, User')))

# 4) 16 个调用点
reps = [
    ('            sess.update_memory(sid, [', '            await _sm_append(sess, sid, ['),
    ('        flat = sess.fetch_memory(sid3)', '        flat = await _sm_flat(sess, sid3)'),
    ('        head = str(sess.fetch_memory(sid3)[0].get("content", ""))',
     '        head = str((await _sm_flat(sess, sid3))[0].get("content", ""))'),
    ('        sess.update_memory(sid5, [', '        await _sm_append(sess, sid5, ['),
    ('            sess.update_memory(sid6, [', '            await _sm_append(sess, sid6, ['),
    ('        head_missing = not str(sess.fetch_memory(sid6)[0].get("content", "")).startswith("[前情摘要")',
     '        head_missing = not str((await _sm_flat(sess, sid6))[0].get("content", "")).startswith("[前情摘要")'),
    ('        req6 = LR(messages=sess.fetch_memory(sid6)[:])',
     '        req6 = LR(messages=(await _sm_flat(sess, sid6))[:])'),
    ('        mem_head6 = str(sess.fetch_memory(sid6)[0].get("content", ""))',
     '        mem_head6 = str((await _sm_flat(sess, sid6))[0].get("content", ""))'),
    ('        n7 = sess.get_memory_count(sid7)', '        n7 = await _sm_count(sess, sid7)'),
    ('        head7 = str(sess.fetch_memory(sid7)[0].get("content", ""))',
     '        head7 = str((await _sm_flat(sess, sid7))[0].get("content", ""))'),
    ('            sess.update_memory(sid12, [', '            await _sm_append(sess, sid12, ['),
    ('        req12 = LR(messages=sess.fetch_memory(sid12)[:])',
     '        req12 = LR(messages=(await _sm_flat(sess, sid12))[:])'),
    ('        req13 = LR(messages=sess.fetch_memory(sid13)[:])',
     '        req13 = LR(messages=(await _sm_flat(sess, sid13))[:])'),
    ('        flat13 = sess.fetch_memory(sid13)', '        flat13 = await _sm_flat(sess, sid13)'),
]
for i, (old, new) in enumerate(E, 1):
    cnt = src.count(old)
    assert cnt == 1, f"E{i}: count={cnt}: {old[:120]}"
    src = src.replace(old, new)
for item in reps:
    if len(item) == 2:
        old, new = item
        cnt = src.count(old)
        assert cnt == 1, f"count={cnt}: {old[:120]}"
        src = src.replace(old, new)
# S11 的 f-string 双调用点单独处理
old11 = '        check("S11 记忆已重写", sess.get_memory_count(sid11) <= 4, f"chunks={sess.get_memory_count(sid11)}")'
new11 = J('        _n11 = await _sm_count(sess, sid11)',
          '        check("S11 记忆已重写", _n11 <= 4, f"chunks={_n11}")')
assert src.count(old11) == 1
src = src.replace(old11, new11)

open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("ADS harness ALL EDITS OK, syntax OK")
