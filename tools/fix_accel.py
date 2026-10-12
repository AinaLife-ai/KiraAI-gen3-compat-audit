#!/usr/bin/env python3
"""accelerator rc1 适配补丁：6 处编辑，全部锚点断言。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_accelerator_plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
def J(*ls): return CR.join(ls)
edits = []

# E1) __init__ 加 inflight 标志
edits.append((
    '        self._early_results: dict[str, list] = {}',
    J('        self._early_results: dict[str, list] = {}',
      '        self._early_inflight: int = 0  # 抢发自己的投递在飞标记（3.0 按链对账时跳过拦截）')))

# E2) 解析段动作的双世代助手 + 按链对账方法（插在 _ckey 前的 _mark_sent 后、_reset_turn_ledger 前）
anchor2 = '    def _reset_turn_ledger(self, sid: str, event_id=None) -> None:'
helper2 = J(
    '    async def _parse_seg_actions(self, seg, tag_set, mp):',
    '        """把一段 XML 解析成动作列表（双世代）。',
    '',
    '        3.0 起 `MessageProcessor._parse_xml_msg` 已删，解析迁到',
    '        `MessageDeliveryService.parse_xml`（静态异步方法，ctx.message_delivery 可达）；',
    '        2.x 用 `mp._parse_xml_msg`。逐级探测，不绑版本号。',
    '        """',
    '        delivery = getattr(self.ctx, "message_delivery", None)',
    '        parse = getattr(delivery, "parse_xml", None) if delivery is not None else None',
    '        if parse is not None:',
    '            return await parse(seg, tag_set)',
    '        return await mp._parse_xml_msg(seg, tag_set)',
    '',
    '    def _consume_early_match(self, sid, chain):',
    '        """3.0 按链对账：该链若与某已抢发段内容一致，消费台账并还回当时的结果。',
    '',
    '        2.x 的发送层剥离按"段文本"工作；3.0 的框架发送按"链"逐条走',
    '        MessageDeliveryService.send_message_chain —— 拦截点改到这里后，',
    '        用与 2.x 相同的 _norm_seg 规范化做内容比对，位置与动作天然 1:1',
    '        （每条链至多消费一条台账），add_message_ids 的位置对齐不破。',
    '        台账/结果数量不齐时放弃对账放行原发送（宁可重发，不还错结果）。',
    '        """',
    '        try:',
    '            text = "".join(getattr(e, "text", "") or "" for e in chain)',
    '        except Exception:  # noqa: BLE001',
    '            return None',
    '        from .early_sent import _norm_seg',
    '        norm = _norm_seg(text)',
    '        if not norm:',
    '            return None',
    '        prefix = sid + "\\x00"',
    '        for k in list(self._sent_ledger.keys()):',
    '            if not (isinstance(k, str) and k.startswith(prefix)):',
    '                continue',
    '            segs = self._sent_ledger.get(k) or []',
    '            for i, seg in enumerate(segs):',
    '                seg_norm = _norm_seg(seg)',
    '                if not seg_norm:',
    '                    continue',
    '                if norm == seg_norm or norm in seg_norm or seg_norm in norm:',
    '                    results = self._early_results.get(k) or []',
    '                    if i >= len(results):',
    '                        return None',
    '                    result = results.pop(i)',
    '                    segs.pop(i)',
    '                    if not segs:',
    '                        self._sent_ledger.pop(k, None)',
    '                        self._early_results.pop(k, None)',
    '                    return result',
    '        return None',
    '',
)
edits.append((anchor2, helper2 + anchor2))

# E3) 流式侧解析调用点
edits.append((
    '            actions = await mp._parse_xml_msg(seg, ctx.tag_set)',
    '            actions = await self._parse_seg_actions(seg, ctx.tag_set, mp)'))

# E4) 抢发投递加 inflight 标记
edits.append((
    J('            try:',
      '                result = await mp.send_message_chain(ctx.sid, action)',
      '            except Exception:  # noqa: BLE001',
      '                logger.exception("[accel] 抢先发送失败，本段交回框架发送（不丢内容）")',
      '                return delivered'),
    J('            self._early_inflight = getattr(self, "_early_inflight", 0) + 1',
      '            try:',
      '                result = await mp.send_message_chain(ctx.sid, action)',
      '            except Exception:  # noqa: BLE001',
      '                logger.exception("[accel] 抢先发送失败，本段交回框架发送（不丢内容）")',
      '                return delivered',
      '            finally:',
      '                self._early_inflight = max(0, getattr(self, "_early_inflight", 1) - 1)')))

# E5) 安装块：按特征分世代
old5 = J(
    '        h = PatchHandle("early_sent_strip")',
    '        if install(h, MessageProcessor, "send_xml_messages", factory) is not None:',
    '            self.patches.add(h)',
    '            logger.info("[accel] 发送层已接管（剥离已抢发段，避免重复发送）")',
)
new5 = J(
    '        h = PatchHandle("early_sent_strip")',
    '        if hasattr(MessageProcessor, "send_xml_messages"):',
    '            # 2.x 形态：类级包裹 send_xml_messages（按段文本剥离）',
    '            if install(h, MessageProcessor, "send_xml_messages", factory) is not None:',
    '                self.patches.add(h)',
    '                logger.info("[accel] 发送层已接管（剥离已抢发段，避免重复发送）")',
    '        else:',
    '            # 3.0+ 形态：send_xml_messages 已删，框架发送按链走',
    '            # MessageDeliveryService.send_message_chain —— 改包它做按链对账去重。',
    '            delivery = getattr(self.ctx, "message_delivery", None)',
    '            dcls = type(delivery) if delivery is not None else None',
    '            if dcls is not None and hasattr(dcls, "send_message_chain"):',
    '                def delivery_factory(original):',
    '                    async def send_message_chain(d_self, session, chain, *,',
    '                                                 memory_message=None, self_id=None):',
    '                        if not getattr(self, "_early_inflight", 0):',
    '                            try:',
    '                                hit = self._consume_early_match(session, chain)',
    '                                if hit is not None:',
    '                                    self._stats["strip_calls"] = self._stats.get("strip_calls", 0) + 1',
    '                                    return hit',
    '                            except Exception:  # noqa: BLE001',
    '                                logger.exception("[accel] 抢发对账异常（放行原发送）")',
    '                        return await original(d_self, session, chain,',
    '                                              memory_message=memory_message, self_id=self_id)',
    '                    return mark_side_effects(send_message_chain)',
    '',
    '                h2 = PatchHandle("early_sent_dedupe_delivery")',
    '                if install(h2, dcls, "send_message_chain", delivery_factory) is not None:',
    '                    self.patches.add(h2)',
    '                    logger.info("[accel] 发送层已接管（按链对账去重已抢发段）")',
    '            else:',
    '                logger.warning("[accel] 未找到可接管的发送服务，抢发剥离未安装（可能重复发送）")',
)
edits.append((old5, new5))

# E6) min/max delay 读点：3.0 在 delivery 服务上
edits.append((
    J('            lo = float(getattr(mp, "min_message_delay", 0.0) or 0.0)',
      '            hi = float(getattr(mp, "max_message_delay", lo) or lo)'),
    J('            # 3.0 起延迟配置在 MessageDeliveryService 上；2.x 在 MessageProcessor 上。',
      '            _delay_src = getattr(self.ctx, "message_delivery", None) or mp',
      '            lo = float(getattr(_delay_src, "min_message_delay", 0.0) or 0.0)',
      '            hi = float(getattr(_delay_src, "max_message_delay", lo) or lo)')))

# E7) 面板 api_providers label 可读名
edits.append((
    J('                    for mid in llm.keys():',
      '                        out.append({"value": f"{pid}:{mid}",',
      '                                    "label": f"{mid} ({pname})",'),
    J('                    for mid, entry in llm.items():',
      '                        # 展示名优先 3.0 的 model_name；2.x 条目非 dict 自动回退 mid。',
      '                        # value 保持 pid:内部ID（3.0 规范引用值）不动。',
      '                        mname = entry.get("model_name") if isinstance(entry, dict) else None',
      '                        mname = mname or mid',
      '                        out.append({"value": f"{pid}:{mid}",',
      '                                    "label": f"{mname} ({pname})",')))

for i, (old, new) in enumerate(edits, 1):
    cnt = src.count(old)
    assert cnt == 1, f"edit {i}: count={cnt}\nOLD: {old[:200]}"
    src = src.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("accelerator ALL EDITS OK, syntax OK")
