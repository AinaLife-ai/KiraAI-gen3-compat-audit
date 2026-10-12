#!/usr/bin/env python3
"""reboot 插件 rc1 双世代会话层补丁。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_kiraai-reboot-pulgin/main.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
def J(*ls): return CR.join(ls)
E = []

# 1) import inspect
E.append(('import hashlib', 'import hashlib' + CR + 'import inspect'))

# 2) initialize 的必需方法检查 → 世代形态识别
E.append((
    J('        required = (',
      '            "fetch_memory",',
      '            "read_memory",',
      '            "write_memory",',
      '            "delete_session",',
      '            "get_session_info",',
      '            "get_memory_count",',
      '        )',
      '        missing = [name for name in required if not hasattr(self.session_mgr, name)]',
      '        if missing:',
      '            logger.error(f"[reboot] SessionManager is missing methods: {missing}")',
      '            self.session_mgr = None',
      '            return'),
    J('        # 世代形态识别（特征探测，不绑版本号）：',
      '        #   2.x  = 同步记忆 API（fetch_memory/read_memory/write_memory/...）',
      '        #   3.0+ = 全异步会话接口（get_session/update_session/delete_session，SQLite 持久化）',
      '        _req_2x = ("fetch_memory", "read_memory", "write_memory", "delete_session")',
      '        _req_rc1 = ("get_session", "update_session", "delete_session")',
      '        if all(hasattr(self.session_mgr, n) for n in _req_2x):',
      '            self._sm_gen = "2x"',
      '        elif all(hasattr(self.session_mgr, n) for n in _req_rc1):',
      '            self._sm_gen = "rc1"',
      '        else:',
      '            logger.error("[reboot] SessionManager 接口形态无法识别（既非 2.x 也非 3.0），插件停用")',
      '            self.session_mgr = None',
      '            return')))

# 3) _find_session_manager 的形态守卫放宽到两代
E.append((
    '            if obj is not None and hasattr(obj, "write_memory"):',
    '            if obj is not None and (hasattr(obj, "write_memory") or hasattr(obj, "update_session")):'))

# 4) 双世代会话层助手（插在 _write_memory 定义之前）
anchor4 = '    def _write_memory(self, sid: str, chunks: List[list]) -> None:'
helper4 = J(
    '    # ── 双世代会话层（特征识别，不绑版本号）──────────────────────────────',
    '    # 2.x：同步记忆 API（fetch_memory/read_memory/write_memory/get_session_info）。',
    '    # 3.0 rc.1+：全异步（get_session/update_session(content=)/delete_session），',
    '    #   会话持久化于 SQLite，无常驻 chat_memory 缓存；update_session 为 upsert，',
    '    #   content 整体替换，标题/能力设置/data 等元数据全部保留。',
    '    async def _sm_read_flat(self, sid: str) -> list:',
    '        sm = self.session_mgr',
    '        if hasattr(sm, "fetch_memory"):',
    '            return list(sm.fetch_memory(sid) or [])',
    '        s = await sm.get_session(sid, ensure_session=False)',
    '        return (s.flatten_content() if s else []) or []',
    '',
    '    async def _sm_read_chunks(self, sid: str) -> list:',
    '        sm = self.session_mgr',
    '        if hasattr(sm, "read_memory"):',
    '            return [list(c) for c in (sm.read_memory(sid) or [])]',
    '        s = await sm.get_session(sid, ensure_session=False)',
    '        return [list(c) for c in (s.content if s else [])]',
    '',
    '    async def _sm_write_chunks(self, sid: str, chunks) -> None:',
    '        sm = self.session_mgr',
    '        if hasattr(sm, "write_memory"):',
    '            sm.write_memory(sid, chunks)',
    '            return',
    '        await sm.update_session(sid, content=chunks)',
    '',
    '    async def _sm_recreate(self, sid: str, chunks) -> None:',
    '        """delete_session 模式：删除并重建空壳再写入（两代）。"""',
    '        sm = self.session_mgr',
    '        res = sm.delete_session(sid)',
    '        if inspect.isawaitable(res):',
    '            await res',
    '        if hasattr(sm, "get_session_info"):',
    '            sm.get_session_info(sid)  # 2.x：重建空壳',
    '            sm.write_memory(sid, chunks)',
    '        else:',
    '            await sm.update_session(sid, content=chunks)  # rc.1 upsert 自建',
    '',
)
E.append((anchor4, helper4 + anchor4))

# 5) _write_memory 本体异步双世代化
E.append((
    J('    def _write_memory(self, sid: str, chunks: List[list]) -> None:',
      '        """Replace the session memory, keeping every other session field.',
    ),
    J('    async def _write_memory(self, sid: str, chunks: List[list]) -> None:',
      '        """Replace the session memory content, keeping every other session field.',
    ),
))
E.append((
    J('        sm = self.session_mgr',
      '        if self.drop_pending_buffer:',
      '            self._drop_buffer(sid)',
      '        if self._event_bus is not None:',
      '            self._own_writes[sid] = [self._mem_fingerprint(chunks), time.monotonic()]',
      '        if self.clear_mode == "delete_session":',
      '            sm.delete_session(sid)',
      '            sm.get_session_info(sid)  # recreate an empty shell',
      '            sm.write_memory(sid, chunks)',
      '            self._log(f"session {sid} deleted and recreated (delete_session mode)")',
      '            return',
      '        sm.write_memory(sid, chunks)'),
    J('        if self.drop_pending_buffer:',
      '            self._drop_buffer(sid)',
      '        if self._event_bus is not None:',
      '            self._own_writes[sid] = [self._mem_fingerprint(chunks), time.monotonic()]',
      '        if self.clear_mode == "delete_session":',
      '            await self._sm_recreate(sid, chunks)',
      '            self._log(f"session {sid} deleted and recreated (delete_session mode)")',
      '            return',
      '        await self._sm_write_chunks(sid, chunks)')))

# 6) _reset_locked 的读取与 5 个写入调用点（多行锚点消歧）
E.append(('        old_flat = list(sm.fetch_memory(sid) or [])',
          '        old_flat = await self._sm_read_flat(sid)'))
E.append((J('        if not want_summary:',
            '            self._write_memory(sid, [])'),
          J('        if not want_summary:',
            '            await self._write_memory(sid, [])')))
E.append(('                self._write_memory(sid, [build_summary_chunk(final)])',
          '                await self._write_memory(sid, [build_summary_chunk(final)])'))
E.append((J('            else:',
            '                self._write_memory(sid, [])'),
          J('            else:',
            '                await self._write_memory(sid, [])')))
E.append(('            self._write_memory(sid, [build_summary_chunk(base)])',
          '            await self._write_memory(sid, [build_summary_chunk(base)])'))
E.append((J('        else:',
            '            self._write_memory(sid, [])'),
          J('        else:',
            '            await self._write_memory(sid, [])')))

# 7) _apply_summary 异步化（紧相邻双 await，文档如实更新）
E.append((
    J('    def _apply_summary(self, sid: str, expected_base: str, final: str):',
      '        """Replace the summary head. Deliberately synchronous.',
      '',
      '        There must be NO await between ``read_memory`` and ``write_memory``: the',
      '        framework appends a turn with ``update_memory`` at the end of every round,',
      '        and a suspension point here would let that append be overwritten by our',
      '        stale snapshot. With no await (single-threaded event loop) the race is',
      '        impossible by construction.',
    ),
    J('    async def _apply_summary(self, sid: str, expected_base: str, final: str):',
      '        """Replace the summary head.',
      '',
      '        2.x 下本函数同步、read→write 之间零 await，原子性由构造保证（框架在',
      '        每轮末尾用 ``update_memory`` 追加，同步段内无人能插进来）。3.0 rc.1 起',
      '        会话接口全异步，读改写是两个**相邻** await —— 窗口与框架自身',
      '        ``update_memory`` 的读-改-写窗口同级；两 await 之间不安排任何其它',
      '        挂起点，风险量级与框架自身一致。',
    ),
))
# 7b) _apply_summary 内的读取改双世代助手
E.append((
    J('        chunks = sm.read_memory(sid) or []',
      '        chunks = [list(chunk) for chunk in chunks]'),
    J('        chunks = await self._sm_read_chunks(sid)'),
))
# 7c) _apply_summary 内的写入改双世代助手（联合下一行锚点避开助手体内的同名行）
E.append((J('        sm.write_memory(sid, chunks)',
            '        return (True, head_now)'),
          J('        await self._sm_write_chunks(sid, chunks)',
            '        return (True, head_now)')))
E.append(('                    applied, head_now = self._apply_summary(sid, current_base, final)',
          '                    applied, head_now = await self._apply_summary(sid, current_base, final)'))

for i, (old, new) in enumerate(E, 1):
    cnt = src.count(old)
    assert cnt == 1, f"edit {i}: count={cnt}\nOLD: {old[:240]}"
    src = src.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("reboot ALL EDITS OK, syntax OK")
