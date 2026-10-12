## 修复：3.0 下「边写边发」静默失效 + 面板下拉 UUID（v1.0.82）

### 问题（rc.1 实测三处破坏，全部静默无报错）
1. **抢先发送失效**：发送层剥离的 patch 目标 `MessageProcessor.send_xml_messages` 在 rc.1 已删除（XML 解析/发送迁到 `ExecuteAgentStage` + `MessageDeliveryService`），`install()` 取不到 attr → warning 跳过 → 已抢发段在最终发送时**整段重发**的风险被框架侧"恰好"掩盖，实际表现为抢先发送完全不生效（退回整段写完才发）。
2. **段解析失效**：流式中途调 `mp._parse_xml_msg(seg, ctx.tag_set)`（rc.1 已删），AttributeError 被 except 吞掉 → `return False` 交回框架 → 同样不抢发。
3. **面板下拉乱码**：`api_providers` 的 label 用 `model_config.llm` 的 key（rc.1 起是内部 uuid）→ 面板显示 32 位十六进制乱码。

### 修法（特征识别，不绑版本号）
1. **发送层按世代分流**（`hasattr(MessageProcessor, "send_xml_messages")` 判定）：
   - 2.x：照旧类级包裹 `send_xml_messages`（原逻辑一字未动）；
   - 3.0+：改包 `type(ctx.message_delivery).send_message_chain`，做**按链对账去重**——每条待发链与抢发台账按 `_norm_seg` 规范化内容比对（含 XML 实体反转义，与 2.x 同源），命中则消费台账并**还回抢发时的真实结果**（结果与链 1:1 对齐 ⇒ `add_message_ids` 不错位），未命中原样放行；台账/结果不齐时放弃对账（宁可重发，不还错结果）；本插件自己的抢发投递用 `_early_inflight` 在飞标记跳过拦截。
2. **段解析双世代**：新增 `_parse_seg_actions`，优先 `ctx.message_delivery.parse_xml`（rc.1 静态方法，已核实签名 `parse_xml(xml_data, tag_set)` 且返回 `list[MessageChain|RootTagAction]` 与旧用法一致），回退 `mp._parse_xml_msg`。
3. **延迟读取双源**（`min/max_message_delay` rc.1 迁到 MessageDeliveryService）：先探 delivery、回落 mp，保留原有"读框架属性"的源码契约。
4. **面板 label**：`model_name` 优先、`model_id` 兜底（2.x 条目非 dict 自动回退）；`value` 保持 `pid:内部ID` 不动（那才是 3.0 的规范引用值）。

### 变更面
- `main.py`：+96/-7（两个新方法 + 安装块世代分流 + 3 处探测/标记 + label 修复）
- `manifest.json`：1.0.81 → 1.0.82；`README.md`：安装节补兼容声明

### 验证
- 仓内自检套件 `sh run_tests.sh`：改动前后**逐项对照**——基线已有 4 个环境性失败（媒体评分/世代兼容/真实广播/挂载链路，均因沙箱缺完整框架环境），本改动**零新增失败**；`test_early_sent.py`（抢先发送专项，含与框架段间隔逐项一致性）全 PASS
- `_consume_early_match` 功能实测：实体反转义匹配 ✓ FIFO 消费 ✓ 桶清空 ✓ 跨会话隔离 ✓ 结果不齐安全放弃 ✓
- 双世代静态检查全绿
