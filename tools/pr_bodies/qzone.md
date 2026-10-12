## 修复：3.0 rc.1 会话能力接口异步化适配 —— 会话识图模式改 TTL 缓存 + 异步预热（v1.4.11）

### 问题
`main.py` `_session_image_mode` 同步调用 `ctx.get_session_capabilities(sid)`。
rc.1 起该接口已异步化（`core/plugin/plugin_context.py:105`），同步调用拿到 coroutine →
`.get("image_recognition")` 抛 AttributeError 被外层 except 吞掉 → **返回 ""，native 图兜底资格静默失效**
（native 模式下框架不写 caption 的图片永远进不了「近期图片」清单），还伴随 RuntimeWarning 刷屏。
2.x 不受影响。

### 修法（特征识别，不绑版本号）
约束：本仓有一条自有结构不变量——**`on_llm_request` 钩子函数体零 await**（`tests/test_manifest_hook.py` 的最强判据，
保证钩子纯读不阻塞）。因此不能直接 await 化，采用缓存 + 预热方案（与 S 版 v2.7.0 的 `_warm_caps_cache` 同族）：

- 新增 `_image_mode_cache`（{sid: (monotonic_ts, mode)}，TTL 30s）。
- `_session_image_mode` 保持**同步**：命中缓存直接返回；2.x 同步直读并回填；3.0 探测到 awaitable →
  `close()` 防告警 + 后台 `create_task` 预热 + 本轮返回 ""（与旧异常路径语义一致）。
- 新增 `_warm_image_mode_cache`（async，`isawaitable` 探测两代通吃），预热挂接点：
  `_collect_images`（消息到达，先于同轮钩子）、`_register_current_event_images`（同步点用 `_schedule_mode_warm`）、
  定时发布/序号解析/主动发布三处异步读清单前。
- 常规流程下消息到达先于本轮钩子完成预热，冷缓存极少出现；即便出现，退化语义与现状一致（不误判 native）。

### 变更面
- `main.py`：+66/-9（两方法重写 + 两个新方法 + 5 处预热挂接 + `import inspect`）
- `manifest.json`：version 1.4.10 → 1.4.11
- `README.md`：标题版本号同步 + 兼容性声明

### 验证
- 仓内全套件 **205/205 通过**（含钩子零 await 结构判据 `test_hook_has_no_await_at_all`、清单去重等）
- 两代桩功能实测：3.0 冷读 `""`→后台预热→下轮 `"native"`（零 never-awaited 告警）；2.x 直读行为不变
- 双世代静态检查全绿（含"rc1 异步 API 未 await"项——探测式封装已被套件识别为合法模式）
