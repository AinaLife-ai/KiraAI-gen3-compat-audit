#!/usr/bin/env python3
"""qzone rc1 修复补丁：_session_image_mode 异步化 + 探测，_manifest_entries 异步化，4 调用点 await。"""
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_qzone_plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"

def J(*lines):
    return CR.join(lines)

edits = []

# 1) import inspect（放在 import hashlib 后）
edits.append((
    J('import hashlib'),
    J('import hashlib') + CR + 'import inspect',
    1,
))

# 2) _session_image_mode 异步化 + isawaitable 探测
edits.append((
    J(
        '    def _session_image_mode(self, sid: str) -> str:',
        '        """\u8bfb\u8be5\u4f1a\u8bdd\u7684\u8bc6\u56fe\u6a21\u5f0f\uff08\u6846\u67b6\u81ea\u5df1\u4e5f\u662f\u8fd9\u4e48\u8bfb\u7684\uff09\u3002',
    ),
    J(
        '    async def _session_image_mode(self, sid: str) -> str:',
        '        """\u8bfb\u8be5\u4f1a\u8bdd\u7684\u8bc6\u56fe\u6a21\u5f0f\uff08\u6846\u67b6\u81ea\u5df1\u4e5f\u662f\u8fd9\u4e48\u8bfb\u7684\uff09\u3002',
    ),
    1,
))
edits.append((
    J(
        '        try:',
        '            caps = self.ctx.get_session_capabilities(sid) or {}',
        '            rec = caps.get("image_recognition") or {}',
    ),
    J(
        '        try:',
        '            # \u53cc\u4e16\u4ee3\uff1a3.0 rc.1 \u8d77\u8be5\u63a5\u53e3\u5df2\u5f02\u6b65\u5316\uff08\u8fd4\u56de coroutine\uff09\uff1b2.x \u540c\u6b65\u8fd4\u56de dict\u3002',
        '            # isawaitable \u63a2\u6d4b\uff0c\u4e24\u4ee3\u901a\u5403\uff0c\u4e0d\u7ed1\u7248\u672c\u53f7\u3002',
        '            _caps_res = self.ctx.get_session_capabilities(sid)',
        '            caps = (await _caps_res) if inspect.isawaitable(_caps_res) else _caps_res',
        '            caps = caps or {}',
        '            rec = caps.get("image_recognition") or {}',
    ),
    1,
))

# 3) _manifest_entries 异步化
edits.append((
    J('    def _manifest_entries(self, sid: str, apply_dedupe: bool = False) -> list[dict]:'),
    J('    async def _manifest_entries(self, sid: str, apply_dedupe: bool = False) -> list[dict]:'),
    1,
))
edits.append((
    J('        native_mode = self._session_image_mode(sid) == "native"'),
    J('        native_mode = (await self._session_image_mode(sid)) == "native"'),
    1,
))

# 4) 四个调用点 await 化
edits.append((
    J('        entries = self._manifest_entries(sid, apply_dedupe=True)'),
    J('        entries = await self._manifest_entries(sid, apply_dedupe=True)'),
    1,
))
edits.append((
    J('            entries = self._manifest_entries(sid, apply_dedupe=dedupe_active)'),
    J('            entries = await self._manifest_entries(sid, apply_dedupe=dedupe_active)'),
    1,
))
edits.append((
    J('        entries = self._manifest_entries(sid, apply_dedupe=apply_dedupe)'),
    J('        entries = await self._manifest_entries(sid, apply_dedupe=apply_dedupe)'),
    1,
))
edits.append((
    J(
        '                    entries = self._manifest_entries(',
        '                        sid, apply_dedupe=task_policy is not None',
        '                    )',
    ),
    J(
        '                    entries = await self._manifest_entries(',
        '                        sid, apply_dedupe=task_policy is not None',
        '                    )',
    ),
    1,
))

for i, (old, new, want) in enumerate(edits, 1):
    cnt = src.count(old)
    assert cnt == want, f"edit {i}: count={cnt} want={want}\nOLD:\n{old[:200]}"
    src = src.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(src)
import ast
ast.parse(src.replace("\r\n", "\n"))
print("ALL EDITS OK, syntax OK")
