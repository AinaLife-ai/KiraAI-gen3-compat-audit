## 修复：3.0 下 buffer 路径消息文本化静默降级（v1.3.6）

### 问题
`main.py` 流入消息文本化的兜底路径调用 `self.ctx.message_processor.message_format_to_text(chain)`。3.0 起格式化职责迁到 `MessageFormatter` 服务，`MessageProcessor` 已无此方法——外层的 `except Exception` 会吞掉 AttributeError 并回退为原始 `text`，**不崩但 buffer 路径的流入消息丢失渲染结果（媒体 caption 等）**，静默降级。

### 修法（特征识别，不绑版本号）
逐级 `getattr` 探测 3.0 的格式化服务：`message_processor.im_workflow.ctx.message_formatter`
（已核实 rc1：`core/workflow/src/im/context.py:32` `IMWorkflowContext.message_formatter`，
`MessageFormatter.format_to_text(message_chain, session_id=None, capabilities=None)` 为异步）；
探测不到则回退 2.x 的 `MessageProcessor.message_format_to_text`；再外层原有的 except 兜底不变。
2.x 上探测链返回 None → 走原路径，行为零变化。

### 变更面
- `main.py`：兜底分支改双世代探测（+13/-1）
- `manifest.json`：version 1.3.5 → 1.3.6
- `README.md`：兼容性节补 3.0 全系列声明与本次改动说明

### 验证
- 仓内全套件 `tests/run_tests.py`：ALL TESTS PASSED（含 3.0 flush 还原兼容 F1-F6、幽灵轮清扫 G1-G5）
- 双世代静态检查全绿
