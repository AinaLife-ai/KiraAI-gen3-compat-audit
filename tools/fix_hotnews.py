#!/usr/bin/env python3
"""hotnews 双世代事件构造升级。"""
import ast
p = "/var/minis/shared/gen3audit/repos/AinaLife-ai_KiraAI_hotnews_plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"

# 1) 导入 inspect
old = "import asyncio"
new = "import asyncio" + CR + "import inspect"
assert src.count(old) == 1
src = src.replace(old, new, 1)

# 2) 助手 + 构造点改造
old2 = CR.join([
    '                event = KiraMessageEvent(',
    '                    adapter=ada.info,',
    '                    message_types=ada.message_types,',
    '                    message=msg,',
    '                    timestamp=cur_time,',
    '                )',
])
new2 = CR.join([
    '                event = await self._make_event(ada, msg, cur_time)',
])
assert src.count(old2) == 1
src = src.replace(old2, new2)

# 3) 在类里加 _make_event / _adapter_elements 助手（挂在 _push_to_all 前）
anchor = '    async def _push_to_all(self, content: str):'
helper = CR.join([
    '    async def _adapter_elements(self, adapter) -> list:',
    '        """取适配器可输出元素清单（双世代，特征识别不绑版本号）。',
    '',
    '        3.0：IMCapability.get_message_metadata().supported_elements；',
    '        2.x：适配器 message_types 属性（3.0 上它是 deprecated 兼容别名，能跑但刷告警）。',
    '        """',
    '        try:',
    '            get_cap = getattr(adapter, "get_capability", None)',
    '            if get_cap is not None:',
    '                from core.adapter import IMCapability  # 仅 3.0 能力架构存在',
    '                im = get_cap(IMCapability)',
    '                if im is not None:',
    '                    meta = im.get_message_metadata()',
    '                    meta = await meta if inspect.isawaitable(meta) else meta',
    '                    elems = getattr(meta, "supported_elements", None)',
    '                    if elems is not None:',
    '                        return list(elems)',
    '        except Exception:',
    '            pass',
    '        return list(getattr(adapter, "message_types", []) or [])',
    '',
    '    async def _make_event(self, adapter, msg, ts) -> KiraMessageEvent:',
    '        """构造消息事件：3.0 用 supported_elements 字段名，2.x 用 message_types。"""',
    '        elements = await self._adapter_elements(adapter)',
    '        try:',
    '            params = set(inspect.signature(KiraMessageEvent.__init__).parameters)',
    '        except Exception:',
    '            params = {"message_types"}',
    '        kw = ({"supported_elements": elements} if "supported_elements" in params else {"message_types": elements})',
    '        return KiraMessageEvent(adapter=adapter.info, message=msg, timestamp=ts, **kw)',
    '',
    anchor,
])
assert src.count(anchor) == 1
src = src.replace(anchor, helper)
open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("hotnews OK")
