#!/usr/bin/env python3
"""ops 插件 rc1 适配：会话域全异步双世代 + 模型域语义 + skills/mcp 域探测。"""
import ast

def patch(path, edits, label):
    src = open(path, encoding="utf-8", newline="").read()
    CR = "\r\n" if "\r\n" in src else "\n"
    def conv(s):
        if isinstance(s, list):
            return CR.join(s)          # 直接以目标行尾连接，勿再二次替换
        return s.replace("\n", "\r\n") if CR == "\r\n" else s
    for i, (old, new) in enumerate(edits, 1):
        o, n = conv(old), conv(new)
        cnt = src.count(o)
        assert cnt == 1, f"{label} edit {i}: count={cnt}\nOLD: {o[:200]}"
        src = src.replace(o, n)
    open(path, "w", encoding="utf-8", newline="").write(src)
    ast.parse(src.replace("\r\n", "\n"))
    print(f"{label} OK ({len(edits)} edits)")

ROOT = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_ops_plugin"

# ═══════════ main.py ═══════════
E = []
# 1) session_inventory 双世代异步化
E.append(([
    '        sm = getattr(self.ctx, "session_mgr", None)',
    '        if sm is None:',
    '            return [], []',
    '        try:',
    '            return list(sm.get_session_info() or []), []',
    '        except Exception as exc:',
    '            logger.warning(f"[kira_ops] session enumeration failed ({exc}); using raw keys")',
  ],[
    '        sm = getattr(self.ctx, "session_mgr", None)',
    '        if sm is None:',
    '            return [], []',
    '        # 世代分流（特征识别）：2.x 有同步 get_session_info；3.0 rc.1 起全异步',
    '        if not hasattr(sm, "get_session_info"):',
    '            try:',
    '                return list(await sm.get_sessions(include_content=False) or []), []',
    '            except Exception as exc:',
    '                logger.warning(f"[kira_ops] session enumeration failed: {exc}")',
    '                return [], []',
    '        try:',
    '            return list(sm.get_session_info() or []), []',
    '        except Exception as exc:',
    '            logger.warning(f"[kira_ops] session enumeration failed ({exc}); using raw keys")',
  ]))
E.append(('    def session_inventory(self) -> tuple:',
          '    async def session_inventory(self) -> tuple:'))
# 2) 两个调用点 await 化
E.append(('            sessions, skipped = self.session_inventory()',
          '            sessions, skipped = await self.session_inventory()'))
E.append(('        sessions, _skipped = self.session_inventory()',
          '        sessions, _skipped = await self.session_inventory()'))
# 3) _panel_payload 异步化 + 调用点
E.append(('    def _panel_payload(self):', '    async def _panel_payload(self):'))
E.append(('        return self._panel_payload()', '        return await self._panel_payload()'))
patch(f"{ROOT}/main.py", E, "ops.main")

# ═══════════ caps/skill_cap.py ═══════════
E = [(
    '    def _sm(self):\n        mp = getattr(self.ctx, "message_processor", None)\n        return getattr(mp, "skills_manager", None)',
    '    def _sm(self):\n        # 3.0 起规范入口是 PluginContext.skills_mgr；旧路径兜底（特征识别，不绑版本号）\n        sm = getattr(self.ctx, "skills_mgr", None)\n        if sm is not None:\n            return sm\n        mp = getattr(self.ctx, "message_processor", None)\n        return getattr(mp, "skills_manager", None)')]
patch(f"{ROOT}/caps/skill_cap.py", E, "ops.skill_cap")

# ═══════════ caps/mcp_cap.py ═══════════
E = [(
    '    def _mgr(self):\n        mp = getattr(self.ctx, "message_processor", None)\n        return getattr(mp, "mcp_manager", None)',
    '    def _mgr(self):\n        # 3.0 起规范入口是 PluginContext.mcp_mgr；旧路径兜底（特征识别，不绑版本号）\n        mgr = getattr(self.ctx, "mcp_mgr", None)\n        if mgr is not None:\n            return mgr\n        mp = getattr(self.ctx, "message_processor", None)\n        return getattr(mp, "mcp_manager", None)')]
patch(f"{ROOT}/caps/mcp_cap.py", E, "ops.mcp_cap")

# ═══════════ caps/provider_cap.py ═══════════
E = []
# P1: models 列表显示可读名（3.0 的 entry 带 model_name；2.x 条目是裸 config）
E.append(([
    '            else:',
    '                # ids only: the full per-model config costs hundreds of chars and',
    '                # is rarely needed - pass args={"full": true} for it.',
    '                data = ok(provider_id=pid, counts=counts,',
    '                          models={str(k): sorted(v or {}) for k, v in models.items()})',
  ],[
    '            else:',
    '                # ids only: the full per-model config costs hundreds of chars and',
    '                # is rarely needed - pass args={"full": true} for it.',
    '                # 3.0 起 key 是内部稳定 ID（uuid 形态），可读名在 entry["model_name"]：',
    '                # 展示「可读名 [ID]」（同名时只显示一次），管理操作仍用 ID。',
    '                def _disp(_models):',
    '                    out = []',
    '                    for _mid, _entry in (_models or {}).items():',
    '                        _name = _entry.get("model_name") if isinstance(_entry, dict) else None',
    '                        if _name and _name != _mid:',
    '                            out.append(f"{_name} [{_mid}]")',
    '                        else:',
    '                            out.append(str(_mid))',
    '                    return sorted(out)',
    '                data = ok(provider_id=pid, counts=counts,',
    '                          models={str(k): _disp(v) for k, v in models.items()})',
  ]))
# P2: add_model 的 found 判定用 rc1 返回的内部 ID
E.append(([
    '            res = pm.register_model(pid, mtype, mid, cfg)',
    '            if hasattr(res, "__await__"):',
    '                res = await res',
    '            found = mid in ((pm.get_models(pid) or {}).get(mtype) or {})',
    '            return ok(provider_id=pid, model_type=mtype, model_id=mid, registered=bool(found))',
  ],[
    '            res = pm.register_model(pid, mtype, mid, cfg)',
    '            if hasattr(res, "__await__"):',
    '                res = await res',
    '            # 3.0 起 register_model 第三参是 model_name，返回生成的内部 ID；',
    '            # 2.x 返回 None 且 key 即入参。两代分别用正确键核对。',
    '            internal_id = res if isinstance(res, str) and res else None',
    '            entries = (pm.get_models(pid) or {}).get(mtype) or {}',
    '            found = (internal_id in entries) if internal_id else (mid in entries)',
    '            return ok(provider_id=pid, model_type=mtype, model_id=internal_id or mid,',
    '                      model_name=mid if internal_id else None, registered=bool(found))',
  ]))
patch(f"{ROOT}/caps/provider_cap.py", E, "ops.provider_cap")
print("OPS PART1 DONE")
