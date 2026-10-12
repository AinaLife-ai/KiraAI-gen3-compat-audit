#!/usr/bin/env python3
"""qzone rc1 修复 v2b：edit7 改用行区间切片替换，避免长中文锚点失配。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_qzone_plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
def J(*ls): return CR.join(ls)

edits = []
edits.append((
    '    async def _manifest_entries(self, sid: str, apply_dedupe: bool = False) -> list[dict]:',
    '    def _manifest_entries(self, sid: str, apply_dedupe: bool = False) -> list[dict]:'))
edits.append((
    '        native_mode = (await self._session_image_mode(sid)) == "native"',
    '        native_mode = self._session_image_mode(sid) == "native"'))
edits.append((
    J('        entries = await self._manifest_entries(sid, apply_dedupe=True)'),
    J('        await self._warm_image_mode_cache(sid)',
      '        entries = self._manifest_entries(sid, apply_dedupe=True)')))
edits.append((
    J('            entries = await self._manifest_entries(sid, apply_dedupe=dedupe_active)'),
    J('            entries = self._manifest_entries(sid, apply_dedupe=dedupe_active)')))
edits.append((
    J('        entries = await self._manifest_entries(sid, apply_dedupe=apply_dedupe)'),
    J('        await self._warm_image_mode_cache(sid)',
      '        entries = self._manifest_entries(sid, apply_dedupe=apply_dedupe)')))
edits.append((
    J('                    entries = await self._manifest_entries(',
      '                        sid, apply_dedupe=task_policy is not None',
      '                    )'),
    J('                    await self._warm_image_mode_cache(sid)',
      '                    entries = self._manifest_entries(',
      '                        sid, apply_dedupe=task_policy is not None',
      '                    )')))
edits.append((
    '        self._image_registry: dict[str, list[dict]] = {}',
    J('        self._image_registry: dict[str, list[dict]] = {}',
      '        # 会话识图模式缓存：{sid: (monotonic_ts, mode)}，TTL 30s（见 _session_image_mode）',
      '        self._image_mode_cache: dict[str, tuple[float, str]] = {}')))
edits.append((
    J('            sender = ""',
      '            if event.message.sender:',
      '                sender = event.message.sender.nickname or str(event.message.sender.user_id or "")',
      '            registry = self._image_registry.setdefault(sid, [])'),
    J('            sender = ""',
      '            if event.message.sender:',
      '                sender = event.message.sender.nickname or str(event.message.sender.user_id or "")',
      '            await self._warm_image_mode_cache(sid)',
      '            registry = self._image_registry.setdefault(sid, [])')))
edits.append((
    J('        sid = getattr(event, "sid", "")',
      '        if not sid:',
      '            return',
      '        registry = self._image_registry.setdefault(sid, [])'),
    J('        sid = getattr(event, "sid", "")',
      '        if not sid:',
      '            return',
      '        self._schedule_mode_warm(sid)',
      '        registry = self._image_registry.setdefault(sid, [])')))

for i, (old, new) in enumerate(edits, 1):
    cnt = src.count(old)
    assert cnt == 1, f"edit {i}: count={cnt}\nOLD: {old[:200]}"
    src = src.replace(old, new)

# edit 7：_session_image_mode 整体行切片替换
lines = src.split(CR)
start = next(i for i, l in enumerate(lines) if l.strip() == "async def _session_image_mode(self, sid: str) -> str:")
end = next(i for i in range(start + 1, len(lines))
           if lines[i].startswith("    def _manifest_entries")
           or lines[i].startswith("    async def _manifest_entries"))
new_block = J(
    '    def _schedule_mode_warm(self, sid: str) -> None:',
    '        """在有事件循环的同步上下文里排一个后台预热（不阻塞调用方）。"""',
    '        try:',
    '            asyncio.get_running_loop().create_task(self._warm_image_mode_cache(sid))',
    '        except Exception:',
    '            pass',
    '',
    '    async def _warm_image_mode_cache(self, sid: str) -> None:',
    '        """异步路径到点时预热会话识图模式缓存（TTL 30s）。',
    '',
    '        3.0 rc.1 起 get_session_capabilities 已异步化，2.x 为同步返回。',
    '        isawaitable 探测两代通吃，不绑版本号。',
    '        """',
    '        ent = self._image_mode_cache.get(sid)',
    '        if ent and (time.monotonic() - ent[0]) < 30.0:',
    '            return',
    '        try:',
    '            res = self.ctx.get_session_capabilities(sid)',
    '            caps = (await res) if inspect.isawaitable(res) else res',
    '            rec = (caps or {}).get("image_recognition") or {}',
    '            self._image_mode_cache[sid] = (time.monotonic(), str(rec.get("mode") or ""))',
    '        except Exception:',
    '            pass',
    '',
    '    def _session_image_mode(self, sid: str) -> str:',
    '        """读该会话的识图模式（TTL 缓存；钩子内可安全同步调用）。',
    '',
    '        用来给"框架没写 caption"的 native 图兜底资格。结构不变量：',
    '        on_llm_request 钩子必须零 await（纯读不阻塞），而 3.0 rc.1 起该接口已',
    '        异步化，故同步读点只读缓存：2.x 同步直读并回填；3.0 冷缓存返回 ""',
    '        （与旧异常路径一致）并后台预热，下一轮即准。常规流程下消息到达',
    '        （_collect_images）先于本轮钩子，冷缓存极少见。',
    '        """',
    '        ent = self._image_mode_cache.get(sid)',
    '        if ent and (time.monotonic() - ent[0]) < 30.0:',
    '            return ent[1]',
    '        try:',
    '            res = self.ctx.get_session_capabilities(sid)',
    '        except Exception:',
    '            return ""',
    '        if inspect.isawaitable(res):',
    '            # 3.0：不能 await（钩子零 await 不变量），关闭 coroutine 防告警后后台预热',
    '            try:',
    '                res.close()',
    '            except Exception:',
    '                pass',
    '            self._schedule_mode_warm(sid)',
    '            return ""',
    '        try:',
    '            rec = (res or {}).get("image_recognition") or {}',
    '            mode = str(rec.get("mode") or "")',
    '            self._image_mode_cache[sid] = (time.monotonic(), mode)',
    '            return mode',
    '        except Exception:',
    '            return ""',
    '',
)
lines[start:end] = new_block.split(CR)
src = CR.join(lines)
open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("v2b ALL EDITS OK, syntax OK")
