#!/usr/bin/env python3
"""KSM 补丁 part2：main.py + cross_session.py。"""
import ast

def patch(path, edits, label):
    src = open(path, encoding="utf-8", newline="").read()
    CR = "\r\n" if "\r\n" in src else "\n"
    def conv(s):
        s = CR.join(s) if isinstance(s, list) else s
        return s.replace("\n", "\r\n") if CR == "\r\n" else s
    for i, (old, new) in enumerate(edits, 1):
        o, n = conv(old), conv(new)
        cnt = src.count(o)
        assert cnt == 1, f"{label} edit {i}: count={cnt}\nOLD: {o[:200]}"
        src = src.replace(o, n)
    open(path, "w", encoding="utf-8", newline="").write(src)
    ast.parse(src.replace("\r\n", "\n"))
    print(f"{label} OK ({len(edits)} edits)")

ROOT = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_session_merger_plugin"

# ═══════════ cross_session.py ═══════════
E = []
E.append(('def resolve_target_sid(ctx, target: str) -> Tuple[Optional[str], Optional[str]]:',
          'async def resolve_target_sid(ctx, target: str) -> Tuple[Optional[str], Optional[str]]:'))
E.append((['            valid = {n for n, _ in adapters}',
           '            for info in sm.get_session_info() or []:'],
          ['            valid = {n for n, _ in adapters}',
           '            # 双世代：2.x get_session_info() 同步列表；3.0 起 get_sessions 异步',
           '            if hasattr(sm, "get_session_info"):',
           '                _infos = sm.get_session_info() or []',
           '            else:',
           '                _infos = await sm.get_sessions(include_content=False) or []',
           '            for info in _infos:']))
E.append(('    resolved, err = resolve_target_sid(ctx, target)',
          '    resolved, err = await resolve_target_sid(ctx, target)'))
patch(f"{ROOT}/cross_session.py", E, "cross_session")

# ═══════════ main.py ═══════════
E = []
# P1: _wrap_update_memory 双世代包装器
E.append(([
    '        plugin = self',
    '        orig = self._orig_update_memory',
    '',
    '        def wrapped_update_memory(session, new_chunk, *args, **kwargs):',
    '            result = orig(session, new_chunk, *args, **kwargs)',
    '            try:',
    '                if plugin.enabled and plugin.group_queue and plugin.resolver:',
    '                    sid = str(session or "")',
    '                    gid = plugin.resolver.resolve_group_id(sid)',
    '                    if gid:',
    '                        # 同步钩子里调度异步 drain',
    '                        try:',
    '                            loop = asyncio.get_running_loop()',
    '                            loop.create_task(',
    '                                plugin._on_group_memory_written(sid, gid)',
    '                            )',
    '                        except RuntimeError:',
    '                            pass',
    '            except Exception:',
    '                logger.exception("[MERGER queue] post update_memory hook failed")',
    '            return result',
  ],
  [
    '        plugin = self',
    '        orig = self._orig_update_memory',
    '',
    '        def _post_write(session):',
    '            try:',
    '                if plugin.enabled and plugin.group_queue and plugin.resolver:',
    '                    sid = str(session or "")',
    '                    gid = plugin.resolver.resolve_group_id(sid)',
    '                    if gid:',
    '                        try:',
    '                            loop = asyncio.get_running_loop()',
    '                            loop.create_task(',
    '                                plugin._on_group_memory_written(sid, gid)',
    '                            )',
    '                        except RuntimeError:',
    '                            pass',
    '            except Exception:',
    '                logger.exception("[MERGER queue] post update_memory hook failed")',
    '',
    '        import inspect as _inspect',
    '        if _inspect.iscoroutinefunction(orig):',
    '            # 3.0 起 update_memory 已异步化 —— 包装器必须同为 async，',
    '            # 且钩子在真实落盘**之后**执行（先 await 再 drain）。',
    '            async def wrapped_update_memory(session, new_chunk, *args, **kwargs):',
    '                result = orig(session, new_chunk, *args, **kwargs)',
    '                if _inspect.isawaitable(result):',
    '                    result = await result',
    '                _post_write(session)',
    '                return result',
    '        else:',
    '            # 2.x：同步实现，保持同步包装（调用方不 await）',
    '            def wrapped_update_memory(session, new_chunk, *args, **kwargs):',
    '                result = orig(session, new_chunk, *args, **kwargs)',
    '                _post_write(session)',
    '                return result',
  ]))
# P2: _clear_session_context → 异步保元数据清空
E.append(([
    '    def _clear_session_context(self, sid: str) -> bool:',
    '        """清除单个会话上下文（对齐 reboot_plugin：delete_session）。"""',
    '        sm = getattr(self.ctx, "session_mgr", None)',
    '        if sm is None or not sid:',
    '            return False',
    '        sm.delete_session(sid)',
    '        return True',
  ],
  [
    '    async def _clear_session_context(self, sid: str) -> bool:',
    '        """清空单个会话上下文（**保留**会话标题/能力设置等元数据）。',
    '',
    '        原为 delete_session 整删 —— 会把会话级能力开关一起抹掉；',
    '        现两代都改为内容置空（对齐 reboot 的 memory_only 默认语义）：',
    '        2.x write_memory(sid, [])；3.0 update_session(sid, content=[])。',
    '        """',
    '        sm = getattr(self.ctx, "session_mgr", None)',
    '        if sm is None or not sid:',
    '            return False',
    '        from .session_mirror import sm_clear',
    '        await sm_clear(sm, sid)',
    '        return True',
  ]))
# P3: 调用点 await
E.append(('                    if self._clear_session_context(target_sid):',
          '                    if await self._clear_session_context(target_sid):'))
# P4: 镜像预热挂接（6 处入口）
E.append(('''    async def on_llm_request(self, event: KiraMessageBatchEvent, req: LLMRequest, *_):
        if not self.enabled or not self.engine:
            return''',
          '''    async def on_llm_request(self, event: KiraMessageBatchEvent, req: LLMRequest, *_):
        if not self.enabled or not self.engine:
            return
        # 3.0 下先刷新会话镜像（2.x 直通不做事）；同步合并链路只读镜像
        from .session_mirror import refresh_mirror
        try:
            await refresh_mirror(self.session_mgr)
        except Exception:
            pass'''))
E.append(('''    async def _handle_status(self, sid: str):
        if not self.resolver or not self.engine:''',
          '''    async def _handle_status(self, sid: str):
        from .session_mirror import refresh_mirror
        try:
            await refresh_mirror(self.session_mgr)
        except Exception:
            pass
        if not self.resolver or not self.engine:'''))
E.append(('''    async def _handle_preview(self, sid: str):
        if not self.engine:''',
          '''    async def _handle_preview(self, sid: str):
        from .session_mirror import refresh_mirror
        try:
            await refresh_mirror(self.session_mgr)
        except Exception:
            pass
        if not self.engine:'''))
E.append(('''    async def _handle_reboot_all(self, event: KiraMessageEvent, sid: str):''',
          '''    async def _handle_reboot_all(self, event: KiraMessageEvent, sid: str):
        from .session_mirror import refresh_mirror
        try:
            await refresh_mirror(self.session_mgr, force=True)
        except Exception:
            pass'''))
# P5: 会话事件处理器里失效镜像（外部写入后对镜像不可见）
E.append(('''    async def _on_session_deleted(self, event):''',
          '''    async def _on_session_deleted(self, event):
        try:
            from .session_mirror import invalidate_mirror
            _p = getattr(event, "payload", None) or {}
            invalidate_mirror(getattr(self.ctx, "session_mgr", None), _p.get("session"))
        except Exception:
            pass'''))
patch(f"{ROOT}/main.py", E, "main")
print("PART2 DONE")
