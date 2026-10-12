#!/usr/bin/env python3
"""auto_delete_session rc1 双世代会话层补丁。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_auto_delete_session_plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
def J(*ls): return CR.join(ls)
E = []

# 1) import inspect
E.append(('import asyncio', 'import asyncio' + CR + 'import inspect'))

# 2) initialize 门 → 世代形态识别
E.append((
    J("        required = ['fetch_memory', 'read_memory', 'write_memory', 'delete_session',",
      "                    'get_session_info', 'get_memory_count']",
      "        missing = [m for m in required if not hasattr(self.session_mgr, m)]",
      "        if missing:",
      "            logger.error(f\"AutoDelete: SessionManager 缺少方法: {missing}\")",
      "            self.session_mgr = None",
      "            return"),
    J("        # 世代形态识别（特征探测，不绑版本号）：",
      "        #   2.x  = 同步记忆 API（fetch_memory/read_memory/write_memory/...）",
      "        #   3.0+ = 全异步会话接口（get_session/update_session/...，SQLite 持久化）",
      "        _req_2x = ('fetch_memory', 'read_memory', 'write_memory', 'delete_session')",
      "        _req_rc1 = ('get_session', 'update_session', 'delete_session')",
      "        if all(hasattr(self.session_mgr, n) for n in _req_2x):",
      "            self._sm_gen = 'sync'",
      "        elif all(hasattr(self.session_mgr, n) for n in _req_rc1):",
      "            self._sm_gen = 'async'",
      "        else:",
      "            logger.error('AutoDelete: SessionManager 接口形态无法识别（既非旧版同步式也非新版异步式）')",
      "            self.session_mgr = None",
      "            return")))

# 3) 双世代助手 + _write_back 异步化（整体替换旧 _write_back）
old3 = J(
    '    def _write_back(self, sid: str, new_chunks: List[List[dict]]):',
    '        """写回新记忆。write_through（默认）：直接覆写，保留 title/description；',
    '        否则走旧的 delete + 重建路径。"""',
    '        if self.write_through:',
    '            data = getattr(self.session_mgr, "chat_memory", None)',
    '            if not isinstance(data, dict) or sid not in data:',
    '                # write_memory 是下标赋值，session 必须先存在',
    '                self.session_mgr.get_session_info(sid)',
    '            self.session_mgr.write_memory(sid, new_chunks)',
    '            logger.info(f"✅ 新历史已覆写（write-through）: {len(new_chunks)} 个chunk")',
    '            return',
    '        self.session_mgr.delete_session(sid)',
    '        logger.info(f"会话 {sid} 已删除（旧路径）")',
    '        self.session_mgr.get_session_info(sid)',
    '        self.session_mgr.write_memory(sid, new_chunks)',
    '        logger.info(f"✅ 新历史已写入: {len(new_chunks)} 个chunk")',
)
new3 = J(
    '    # ── 双世代会话层（特征识别，不绑版本号）──────────────────────────────',
    '    # 2.x：同步记忆 API（fetch_memory/read_memory/write_memory/get_session_info/',
    '    #   get_memory_count，直读 chat_memory 缓存）。',
    '    # 3.0 rc.1+：全异步（get_session/update_session(content=)/delete_session），',
    '    #   SQLite 持久化无常驻缓存；update_session 为 upsert，content 整体替换，',
    '    #   标题/描述/能力设置等元数据全部保留。',
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
    '    async def _sm_count(self, sid: str) -> int:',
    '        sm = self.session_mgr',
    '        if hasattr(sm, "get_memory_count"):',
    '            return sm.get_memory_count(sid)',
    '        s = await sm.get_session(sid, ensure_session=False)',
    '        return len(s.content) if s else 0',
    '',
    '    async def _sm_write_chunks(self, sid: str, chunks) -> None:',
    '        sm = self.session_mgr',
    '        if hasattr(sm, "write_memory"):',
    '            sm.write_memory(sid, chunks)',
    '            return',
    '        await sm.update_session(sid, content=chunks)',
    '',
    '    async def _write_back(self, sid: str, new_chunks: List[List[dict]]):',
    '        """写回新记忆。write_through（默认）：直接覆写，保留 title/description/',
    '        capabilities；否则走 delete + 重建路径（3.0 下删除后 update_session upsert 自建）。"""',
    '        sm = self.session_mgr',
    '        if self.write_through:',
    '            if hasattr(sm, "write_memory"):',
    '                data = getattr(sm, "chat_memory", None)',
    '                if not isinstance(data, dict) or sid not in data:',
    '                    # write_memory 是下标赋值，session 必须先存在',
    '                    sm.get_session_info(sid)',
    '                sm.write_memory(sid, new_chunks)',
    '            else:',
    '                await sm.update_session(sid, content=new_chunks)',
    '            logger.info(f"✅ 新历史已覆写（write-through）: {len(new_chunks)} 个chunk")',
    '            return',
    '        res = sm.delete_session(sid)',
    '        if inspect.isawaitable(res):',
    '            await res',
    '        logger.info(f"会话 {sid} 已删除（旧路径）")',
    '        if hasattr(sm, "write_memory"):',
    '            sm.get_session_info(sid)',
    '            sm.write_memory(sid, new_chunks)',
    '        else:',
    '            await sm.update_session(sid, content=new_chunks)',
    '        logger.info(f"✅ 新历史已写入: {len(new_chunks)} 个chunk")',
)
E.append((old3, new3))

# 4) 读取点逐一异步化
E.append(('                flat = self.session_mgr.fetch_memory(sid) or []',
          '                flat = await self._sm_read_flat(sid)'))
E.append((J('                    chunks = self.session_mgr.read_memory(sid) or []',
            '                    head_text = ""'),
          J('                    chunks = await self._sm_read_chunks(sid)',
            '                    head_text = ""')))
E.append((J('                    chunks = self.session_mgr.read_memory(sid) or []',
            '                    if chunks and is_summary_chunk(chunks[0]):'),
          J('                    chunks = await self._sm_read_chunks(sid)',
            '                    if chunks and is_summary_chunk(chunks[0]):')))
E.append(('        old_flat = self.session_mgr.fetch_memory(sid) or []',
          '        old_flat = await self._sm_read_flat(sid)'))
E.append(('            if not (self.session_mgr.fetch_memory(sid) or []):',
          '            if not (await self._sm_read_flat(sid)):'))
E.append(('            flat = self.session_mgr.fetch_memory(sid) or []',
          '            flat = await self._sm_read_flat(sid)'))

# 4b) 后台合并的两处直接写回（1146 final / 1470 new_summary）
E.append((J('                    self.session_mgr.write_memory(sid, chunks)',
            '                    if self.cumulative_summary and self._summary_store is not None:',
            '                        self._summary_store.set(sid, final)'),
          J('                    await self._sm_write_chunks(sid, chunks)',
            '                    if self.cumulative_summary and self._summary_store is not None:',
            '                        self._summary_store.set(sid, final)')))
E.append((J('                        self.session_mgr.write_memory(sid, chunks)',
            '                        if self.cumulative_summary and self._summary_store is not None:'),
          J('                        await self._sm_write_chunks(sid, chunks)',
            '                        if self.cumulative_summary and self._summary_store is not None:')))

# 5) 计数点（先 16 空格变体，12 空格是其子串，顺序不能反）
E.append(('                rounds = self.session_mgr.get_memory_count(sid)',
          '                rounds = await self._sm_count(sid)'))
E.append(('            rounds = self.session_mgr.get_memory_count(sid)',
          '            rounds = await self._sm_count(sid)'))

# 6) _write_back 调用点
E.append(('        self._write_back(sid, fused)',
          '        await self._write_back(sid, fused)'))

for i, (old, new) in enumerate(E, 1):
    cnt = src.count(old)
    assert cnt == 1, f"edit {i}: count={cnt}\nOLD: {old[:240]}"
    src = src.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("ADS ALL EDITS OK, syntax OK")
