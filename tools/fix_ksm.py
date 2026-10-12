#!/usr/bin/env python3
"""KSM 全部调用点补丁：merge_engine / hard_reset / main / cross_session。"""
import ast

def patch(path, edits, label):
    src = open(path, encoding="utf-8", newline="").read()
    CR = "\r\n" if "\r\n" in src else "\n"
    def conv(s):
        s = CR.join(s) if isinstance(s, list) else s
        if CR == "\r\n":
            s = s.replace("\n", "\r\n")
        return s
    for i, (old, new) in enumerate(edits, 1):
        old_n, new_n = conv(old), conv(new)
        cnt = src.count(old_n)
        assert cnt == 1, f"{label} edit {i}: count={cnt}\nOLD: {old_n[:200]}"
        src = src.replace(old_n, new_n)
    open(path, "w", encoding="utf-8", newline="").write(src)
    ast.parse(src.replace("\r\n", "\n"))
    print(f"{label} OK ({len(edits)} edits)")

ROOT = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_session_merger_plugin"

# ═══════════ merge_engine.py ═══════════
me = f"{ROOT}/merge_engine.py"
E = []
# M1: 三个异步写入点 read_memory → 双世代读
E.append(('                chunks = self.session_mgr.read_memory(sid) or []\n                cur_head = ""',
          '                chunks = await sm_read_chunks(self.session_mgr, sid)\n                cur_head = ""'))
E.append(('                chunks = self.session_mgr.read_memory(sid) or []\n                summary_msg = build_summary_chunk(final)[0]',
          '                chunks = await sm_read_chunks(self.session_mgr, sid)\n                summary_msg = build_summary_chunk(final)[0]'))
E.append(('                            chunks = self.session_mgr.read_memory(sid) or []\n                            cur_head = ""',
          '                            chunks = await sm_read_chunks(self.session_mgr, sid)\n                            cur_head = ""'))
# M2: 三个 to_thread(write_memory) → 双世代写
E.append(('                # write_memory 是同步全量 JSON 落盘，挪到线程避免冻结事件循环\n                await asyncio.to_thread(self.session_mgr.write_memory, sid, chunks)\n            self._update_store_after_reset([sid], {sid: new_final})',
          '                # 双世代：2.x 同步全量落盘挪线程；3.0 原生异步 upsert（见 session_mirror）\n                await sm_write_chunks(self.session_mgr, sid, chunks)\n            self._update_store_after_reset([sid], {sid: new_final})'))
E.append(('                # write_memory 是同步全量 JSON 落盘，挪到线程避免冻结事件循环\n                await asyncio.to_thread(self.session_mgr.write_memory, sid, chunks)\n            self._update_store_after_reset([sid], {sid: final})',
          '                # 双世代：2.x 同步全量落盘挪线程；3.0 原生异步 upsert（见 session_mirror）\n                await sm_write_chunks(self.session_mgr, sid, chunks)\n            self._update_store_after_reset([sid], {sid: final})'))
E.append(('                                # write_memory 是同步全量 JSON 落盘，挪到线程\n                                await asyncio.to_thread(\n                                    self.session_mgr.write_memory, sid, chunks\n                                )',
          '                                # 双世代：2.x 同步全量落盘挪线程；3.0 原生异步 upsert\n                                await sm_write_chunks(self.session_mgr, sid, chunks)'))
# M3: 顶部导入助手
E.append(('from .memory_access import pick_member_sids',
          'from .memory_access import pick_member_sids\nfrom .session_mirror import (\n    flush_deferred, refresh_mirror, sm_read_chunks, sm_write_chunks,\n)'))
# M4: hard_reset_members 调用加 defer
E.append(('''                        hard_reset_members(
                            self.session_mgr,
                            reset_members,
                            keep,
                            logger=self.logger,
                            summary_chunks=sub_summaries,
                            write_through=self.write_through,''',
          '''                        hard_reset_members(
                            self.session_mgr,
                            reset_members,
                            keep,
                            logger=self.logger,
                            summary_chunks=sub_summaries,
                            write_through=self.write_through,
                            defer=defer_q,'''))
# M5: build_merged_history 签名 + 传递 defer
E.append(('    def build_merged_history(\n        self,',
          '    def build_merged_history(\n        self,\n        defer: Optional[list] = None,'))
# M6: _apply_sync 签名 + defer_q 兜底
E.append(('''    def _apply_sync(
        self,
        event,
        req: LLMRequest,
        summary_chunks: Optional[dict] = None,
        out_info: Optional[dict] = None,
        summary_texts: Optional[dict] = None,
    ) -> bool:''',
          '''    def _apply_sync(
        self,
        event,
        req: LLMRequest,
        summary_chunks: Optional[dict] = None,
        out_info: Optional[dict] = None,
        summary_texts: Optional[dict] = None,
        defer_q: Optional[list] = None,
    ) -> bool:
        # 3.0 下线程区不能 await：写操作入延迟队列，由异步方冲刷
        if defer_q is None:
            defer_q = []'''))
# M7: apply_to_request：镜像预热 + to_thread 任务化 + 冲刷
E.append(('''        out_info: dict = {}
        try:
            ok = await asyncio.wait_for(
                asyncio.to_thread(
                    self._apply_sync, event, req, summary_chunks, out_info, sync_finals
                ),
                timeout=self._merge_timeout(),
            )
        except asyncio.TimeoutError:''',
          '''        out_info: dict = {}
        defer_q: list = []
        await refresh_mirror(self.session_mgr)
        _task = asyncio.ensure_future(asyncio.to_thread(
            self._apply_sync, event, req, summary_chunks, out_info, sync_finals, defer_q
        ))
        try:
            ok = await asyncio.wait_for(asyncio.shield(_task), timeout=self._merge_timeout())
            await flush_deferred(self.session_mgr, defer_q, logger=self.logger)
        except asyncio.TimeoutError:'''))
# M8: 超时分支加迟到冲刷回调
E.append(('''            self.logger.warning(
                    "[MERGER] merge timeout (%.1fs mode=%s), skip merge",
                    self._merge_timeout(),
                    self.merge_reset_mode,
                )
            return False''',
          '''            self.logger.warning(
                    "[MERGER] merge timeout (%.1fs mode=%s), skip merge",
                    self._merge_timeout(),
                    self.merge_reset_mode,
                )
            # to_thread 不可取消：线程仍在跑，迟到的延迟写由完成回调兜底冲刷
            def _flush_late(_t, _q=defer_q):
                if _q:
                    try:
                        asyncio.get_running_loop().create_task(
                            flush_deferred(self.session_mgr, _q, logger=self.logger))
                    except Exception:
                        pass
            _task.add_done_callback(_flush_late)
            return False'''))
patch(me, E, "merge_engine")

# ═══════════ hard_reset.py ═══════════
hr = f"{ROOT}/hard_reset.py"
E = []
# H1: hard_reset_session 签名 + defer
E.append(('''def hard_reset_session(
    session_mgr,
    sid: str,
    keep_turns: int,
    logger=None,
    summary_chunk: Optional[list] = None,
    write_through: bool = True,
) -> int:''',
          '''def hard_reset_session(
    session_mgr,
    sid: str,
    keep_turns: int,
    logger=None,
    summary_chunk: Optional[list] = None,
    write_through: bool = True,
    defer: Optional[list] = None,
) -> int:'''))
# H2: 读取改镜像安全读
E.append(('        old_flat = _norm_messages(session_mgr.fetch_memory(sid) or [])',
          '        old_flat = _norm_messages(safe_fetch_memory(session_mgr, sid) or [])'))
# H3: 写回区双世代（写穿 / 删除重建）
E.append(('''        if write_through:
            data = getattr(session_mgr, "chat_memory", None)
            if not isinstance(data, dict) or sid not in data:
                # write_memory 是下标赋值，session 必须先存在
                try:
                    session_mgr.get_session_info(sid)
                except Exception:
                    pass
            session_mgr.write_memory(sid, to_write)
        else:
            session_mgr.delete_session(sid)
            try:
                session_mgr.get_session_info(sid)
            except Exception:
                pass
            session_mgr.write_memory(sid, to_write)''',
          '''        # 双世代写回（特征识别，不绑版本号）：
        #   2.x：直写（write_memory / delete+重建，本函数在 to_thread 线程区运行）；
        #   3.0：异步接口不能在此 await —— 写操作入 defer 队列，由异步调用方冲刷。
        if write_through:
            defer_or_write(session_mgr, sid, to_write, defer, logger=logger)
        else:
            defer_or_recreate(session_mgr, sid, to_write, defer, logger=logger)'''))
# H4: 导入助手
E.append(('from .summarizer import SUMMARY_MARKER, extract_summary_text',
          'from .summarizer import SUMMARY_MARKER, extract_summary_text\nfrom .memory_access import safe_fetch_memory\nfrom .session_mirror import defer_or_recreate, defer_or_write'))
# H5: hard_reset_members 透传 defer
E.append(('''        results[sid] = hard_reset_session(
            session_mgr, sid, keep_turns, logger, summary_chunk=sc,
            write_through=write_through,
        )''',
          '''        results[sid] = hard_reset_session(
            session_mgr, sid, keep_turns, logger, summary_chunk=sc,
            write_through=write_through, defer=defer,
        )'''))
E.append(('''def hard_reset_members(
    session_mgr,
    sids: List[str],
    keep_turns: int,
    logger=None,
    summary_chunks: Optional[dict] = None,
    write_through: bool = True,
) -> dict:''',
          '''def hard_reset_members(
    session_mgr,
    sids: List[str],
    keep_turns: int,
    logger=None,
    summary_chunks=None,
    write_through: bool = True,
    defer: Optional[list] = None,
) -> dict:'''))
patch(hr, E, "hard_reset")
print("PART1 DONE")
