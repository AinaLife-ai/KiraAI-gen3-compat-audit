#!/usr/bin/env python3
"""ops session_cap.py：会话域整体双世代化（行切片重写两个 handler + 两个助手）。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_ops_plugin/caps/session_cap.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
lines = src.split(CR)

def find_def(name, start=0):
    for i in range(start, len(lines)):
        if lines[i].startswith(f"    def {name}(") or lines[i].startswith(f"    async def {name}("):
            return i
    raise AssertionError(f"{name} not found")

def next_def_or_end(i):
    for j in range(i + 1, len(lines)):
        l = lines[j]
        if l.startswith("    def ") or l.startswith("    async def") or (l and not l[0] in " \t" and l.strip()):
            return j
    return len(lines)

# ── 新 _known/_exists（异步双世代）──
i1 = find_def("_known")
j1 = next_def_or_end(i1)  # 到 _exists
i2 = find_def("_exists", i1)
j2 = next_def_or_end(i2)

new_known_exists = [
    '    async def _known(self, sm, sid: str):',
    '        """Existing session ids（双世代枚举）。',
    '',
    '        ``None`` means "could not enumerate" (never "unknown"), so the caller',
    '        does not turn a framework hiccup into a hard rejection.',
    '        """',
    '        sessions, skipped = await self.plugin.session_inventory()',
    '        if not sessions and skipped:',
    '            return None',
    '        return {str(getattr(s, "sid", "") or s) for s in sessions}',
    '',
    '    async def _exists(self, sm, sid: str):',
    '        """True/False/None。2.x 先查 raw chat_memory（畸形键也可寻址）；',
    '        3.0 起 DB 约束已挡畸形键，直接 get_session(ensure_session=False) 探测。"""',
    '        raw = getattr(sm, "chat_memory", None)',
    '        if isinstance(raw, dict):',
    '            return sid in raw',
    '        if hasattr(sm, "get_session"):',
    '            try:',
    '                res = sm.get_session(sid, ensure_session=False)',
    '                if hasattr(res, "__await__"):',
    '                    res = await res',
    '                return res is not None',
    '            except Exception:',
    '                return None',
    '        known = await self._known(sm, sid)',
    '        return None if known is None else sid in known',
]
lines[i1:j2] = new_known_exists + [""]
src = CR.join(lines)

# ── 重写 handle_read ──
lines = src.split(CR)
i = find_def("handle_read")
j = next_def_or_end(i)
new_read = '''    async def handle_read(self, action, params):
        sm = self._sm()
        if not sm:
            return fail("session manager is unavailable")
        if action == "list":
            sessions, skipped = await self.plugin.session_inventory()
            items = []
            keyword = str(params.get("keyword") or "").lower()
            for s in sessions:
                sid = getattr(s, "sid", None) or str(s)
                title = getattr(s, "session_title", "") or ""
                if keyword and keyword not in f"{sid} {title}".lower():
                    continue
                try:
                    count = await _sm_count(sm, sid)
                except Exception:
                    count = -1
                items.append({
                    "session_id": sid,
                    "title": title,
                    "type": getattr(s, "session_type", "") or _type_of(sid),
                    "memory_count": count,
                })
            items.sort(key=lambda x: x["session_id"])
            data = ok(**paged(items, params, default=50))
            if skipped:
                data["malformed_keys"] = skipped[:10]
                data["hint"] = ("these chat_memory keys are malformed and break the "
                                "framework session list; delete them with "
                                "ops_action(domain=session, action=delete, target=<key>)")
            return data
        if action == "info":
            sid = self._sid(params)
            if not sid:
                return fail("session_id is required")
            bad = self._bad_sid(sid)
            if bad:
                return fail(bad)
            known = await self._known(sm, sid)
            if known is not None and sid not in known:
                return fail(f"session '{sid}' not found")
            s = await _sm_get(sm, sid)
            if s is None:
                return fail(f"session '{sid}' not found")
            merged = await _sm_caps(self.ctx, sid)
            if params.get("full"):
                caps = merged
            else:
                caps = {str(k): bool((v or {}).get("enabled", True))
                        for k, v in merged.items() if isinstance(v, dict)}
            overrides = await _sm_effective(sm, sid)
            data = ok(session_id=sid,
                      title=getattr(s, "session_title", "") or "",
                      description=getattr(s, "session_description", "") or "",
                      capabilities=caps)
            if overrides:
                data["overrides"] = overrides
            return data
        if action == "memory_count":
            sid = self._sid(params)
            if not sid:
                return fail("session_id is required")
            bad = self._bad_sid(sid)
            if bad:
                return fail(bad)
            known = await self._known(sm, sid)
            if known is not None and sid not in known:
                return fail(f"session '{sid}' not found")
            return ok(session_id=sid, memory_count=await _sm_count(sm, sid))
        return fail(f"unknown read action '{action}'")

'''.split("\n")
lines[i:j] = new_read
src = CR.join(lines)

# ── 重写 handle_write ──
lines = src.split(CR)
i = find_def("handle_write")
j = next_def_or_end(i)
new_write = '''    async def handle_write(self, action, params):
        sm = self._sm()
        if not sm:
            return fail("session manager is unavailable")
        sid = self._sid(params)
        if not sid:
            return fail("session_id is required")
        if action == "delete":
            # deleting is also the repair path for an already-broken key, so it
            # accepts any existing key rather than requiring a well-formed id.
            if not sid.strip():
                return fail("session_id is required")
        else:
            bad = self._bad_sid(sid)
            if bad:
                return fail(bad)
        if action == "title":
            await _sm_update_info(sm, sid, title=params.get("title"),
                                  description=params.get("description"))
            return ok(session_id=sid)
        if action == "caps":
            caps = params.get("capabilities")
            if caps is not None and not isinstance(caps, dict):
                return fail("capabilities must be a JSON object or null (null clears overrides)")
            await _sm_caps_update(sm, sid, caps)
            return ok(session_id=sid,
                      capabilities=(await _sm_effective(sm, sid)) if caps else {})
        if action == "memory_clear":
            # 清空只清对话内容，保留会话标题/能力设置（两代同语义）
            before = await _sm_count(sm, sid)
            await _sm_clear(sm, sid)
            return ok(session_id=sid, cleared_count=before)
        if action == "delete":
            exists = await self._exists(sm, sid)
            if exists is False:
                return fail(f"session '{sid}' not found")
            res = sm.delete_session(sid)
            if hasattr(res, "__await__"):
                await res
            # 删除后清理技能/MCP 的会话范围（3.0 起规范入口在 PluginContext 上）
            for attr in ("skills_mgr", "mcp_mgr"):
                try:
                    mgr = getattr(self.ctx, attr, None)
                    if mgr is None:
                        mp = getattr(self.ctx, "message_processor", None)
                        mgr = getattr(mp, "skills_manager" if attr == "skills_mgr"
                                      else "mcp_manager", None)
                    if mgr and hasattr(mgr, "remove_session_from_scopes"):
                        res2 = mgr.remove_session_from_scopes(sid)
                        if hasattr(res2, "__await__"):
                            await res2
                except Exception:
                    pass
            return ok(session_id=sid, deleted=True)
        return fail(f"unknown write action '{action}'")

'''.split("\n")
lines[i:j] = new_write
src = CR.join(lines)

# ── 文件头加双世代助手 ──
lines = src.split(CR)
# 找 imports 末尾（最后一个顶层 import/from 行）
last_import = max(i for i, l in enumerate(lines)
                  if l.startswith("import ") or l.startswith("from "))
helpers = '''

# ── 双世代会话助手（特征识别，不绑版本号）─────────────────────────────────
# 2.x：同步 API（get_session_info/write_memory/get_memory_count/delete_session）；
# 3.0 rc.1+：全异步（get_session/update_session/delete_session），SQLite 持久化，
# update_session(content=[]) 只清对话、保留标题/能力设置/data。

def _type_of(sid: str) -> str:
    parts = str(sid or "").split(":")
    return parts[1] if len(parts) >= 2 else ""


async def _sm_get(sm, sid: str):
    """取单个会话（不创建），两代统一返回 Session 或 None。"""
    if hasattr(sm, "get_session_info"):
        try:
            return sm.get_session_info(sid)
        except Exception:
            return None
    res = sm.get_session(sid, ensure_session=False)
    if hasattr(res, "__await__"):
        res = await res
    return res


async def _sm_count(sm, sid: str) -> int:
    if hasattr(sm, "get_memory_count"):
        return sm.get_memory_count(sid)
    s = await _sm_get(sm, sid)
    return len(getattr(s, "content", None) or []) if s else 0


async def _sm_update_info(sm, sid: str, title=None, description=None):
    if hasattr(sm, "update_session_info"):
        sm.update_session_info(sid, title=title, description=description)
        return
    res = sm.update_session(sid, title=title, description=description)
    if hasattr(res, "__await__"):
        await res


async def _sm_clear(sm, sid: str):
    """清空对话内容（保留标题/能力设置等元数据）。"""
    if hasattr(sm, "write_memory"):
        sm.write_memory(sid, [])
        return
    res = sm.update_session(sid, content=[])
    if hasattr(res, "__await__"):
        await res


async def _sm_caps(ctx, sid: str) -> dict:
    res = ctx.get_session_capabilities(sid)
    if hasattr(res, "__await__"):
        res = await res
    return res or {}


async def _sm_caps_update(sm, sid: str, caps):
    res = sm.update_session_capabilities(sid, caps)
    if hasattr(res, "__await__"):
        await res


async def _sm_effective(sm, sid: str) -> dict:
    res = sm.get_effective_capabilities(sid, {})
    if hasattr(res, "__await__"):
        res = await res
    return res or {}
'''
lines[last_import] = lines[last_import] + helpers
src = CR.join(lines)
open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("session_cap OK")
