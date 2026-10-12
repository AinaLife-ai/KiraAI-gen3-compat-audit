#!/usr/bin/env python3
"""KSM：跨适配器合并开关（webchat 与 QQ 等任意适配器同组）。3 文件。"""
import ast, json

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

# ── group_resolver.py ──
E = []
E.append(('''        merge_all_dms: bool = True,
        merge_groups_with_dms: bool = True,
        extra_sessions: Optional[List[str]] = None,
        exclude_sessions: Optional[List[str]] = None,
    ):''',
          '''        merge_all_dms: bool = True,
        merge_groups_with_dms: bool = True,
        extra_sessions: Optional[List[str]] = None,
        exclude_sessions: Optional[List[str]] = None,
        merge_across_adapters: bool = False,
    ):'''))
E.append(('''        self.merge_groups_with_dms = merge_groups_with_dms''',
          '''        self.merge_groups_with_dms = merge_groups_with_dms
        # 跨适配器合并：True 时所有适配器的会话归入同一个 all_merged 组
        #（典型用法：webchat:dm:admin 与 QQ 会话共享同一条人生时间线）
        self.merge_across_adapters = bool(merge_across_adapters)'''))
E.append(('''        # 群私互通：同一条人生时间线
        if self.merge_groups_with_dms:
            return f"{adapter}:{self.GROUP_ALL}"''',
          '''        # 跨适配器互通（含 webchat 等内置适配器）：全部会话同组
        if self.merge_across_adapters:
            return self.GROUP_ALL

        # 群私互通：同一条人生时间线
        if self.merge_groups_with_dms:
            return f"{adapter}:{self.GROUP_ALL}"'''))
E.append(('''        parts = group_id.split(":", 1)
        if len(parts) != 2:
            return []
        adapter, gtype = parts[0], parts[1]

        known = set(self.list_known_sessions())''',
          '''        parts = group_id.split(":", 1)
        if len(parts) != 2:
            # 跨适配器组（无前缀的 all_merged）：不筛适配器
            if group_id == self.GROUP_ALL:
                adapter, gtype = None, self.GROUP_ALL
            else:
                return []
        else:
            adapter, gtype = parts[0], parts[1]

        known = set(self.list_known_sessions())'''))
E.append(('''            meta = self.parse_sid(sid)
            if meta["adapter"] != adapter:
                continue''',
          '''            meta = self.parse_sid(sid)
            if adapter is not None and meta["adapter"] != adapter:
                continue'''))
patch(f"{ROOT}/group_resolver.py", E, "group_resolver")

# ── main.py：配置读取 + 装配 ──
E = []
E.append(('''        self.merge_groups_with_dms = bool(mode.get("merge_groups_with_dms", True))''',
          '''        self.merge_groups_with_dms = bool(mode.get("merge_groups_with_dms", True))
        # 跨适配器合并（如把 webchat 面板会话与 QQ 会话并入同一条时间线）
        self.merge_across_adapters = bool(mode.get("merge_across_adapters", False))'''))
E.append(('''            merge_groups_with_dms=self.merge_groups_with_dms,
            extra_sessions=self.extra_sessions,''',
          '''            merge_groups_with_dms=self.merge_groups_with_dms,
            merge_across_adapters=self.merge_across_adapters,
            extra_sessions=self.extra_sessions,'''))
patch(f"{ROOT}/main.py", E, "main(webchat)")

# ── schema.json：section_mode 加开关 ──
sp = f"{ROOT}/schema.json"
s = json.load(open(sp, encoding="utf-8"))
import json as J2
done = False
for sec_key, sec in s.items():
    if not isinstance(sec, dict):
        continue
    fields = sec.get("fields") or sec
    if isinstance(fields, dict) and "merge_groups_with_dms" in fields:
        fields["merge_across_adapters"] = {
            "type": "bool",
            "name": "跨适配器合并",
            "default": False,
            "hint": "开启后所有适配器的会话合并到同一组（不再按适配器分治）。典型用法：把 webui 内置聊天的 webchat:dm:admin 与 QQ 会话并入同一条时间线。3.0 起可用。",
        }
        done = True
        break
assert done, "schema 里没找到 merge_groups_with_dms 所在段"
json.dump(s, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("schema OK")
