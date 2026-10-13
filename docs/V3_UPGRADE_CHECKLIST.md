# v3 兼容升级清单（逐条打勾）

> 用法：升级一个插件时，从第 0 步开始，逐条过；每条都给了**判据**和**修法模板**。
> 基线：**KiraAI v3.0.0-rc.2**（同时要保证 2.x 不回归）。

---

## 第 0 步：先扫描（3 条命令，2 分钟）

```bash
python3 tools/scan_signature_drift.py /path/to/plugin     # 签名漂移（P0/P1）
python3 tools/scan_logger_levels.py  /path/to/plugin      # 日志级别误用
python3 kit/run.py --plugin /path/to/plugin \
    --core2x /path/to/KiraAI-2.x --core30 /path/to/KiraAI-3.0-rc2
```

- [ ] 三条命令都跑过，结果已逐条看过（P1 要人工确认是不是"带探测的回退分支"）

---

## 第 1 步：接管点签名（最容易出人命的一条）

- [ ] 所有**包装/接管框架方法**的实现体都是"只取自己要的 + 其余 `*args, **kwargs` 原样透传"
- [ ] 静态方法（`parse_xml` / `add_message_ids` 等）包装/还原时都套了 `staticmethod`
- [ ] `*args/**kwargs` 的引用都在**声明它们的函数**内（否则 `NameError`）
- [ ] 判断"目标是否接受某参数"用 `inspect.signature` 探测 + 缓存，**没有** try/except 重试
- [ ] 仓库里加了那条静态守卫（AST：工厂内嵌套 + 调 `original` ⇒ 必须 `**kwargs`）

参见：[SIGNATURE_DRIFT_v3.md](SIGNATURE_DRIFT_v3.md)

---

## 第 2 步：rc2 破坏性变更

- [ ] 不再给发送 API 传 `self_id=`；要传身份就传 `bot=`（探测式）
- [ ] 没有对**只读 property** 赋值（如 `event.is_mentioned` ⇒ 应写 `event.message.is_mentioned`）

参见：[RC2_CHANGES.md](RC2_CHANGES.md)

---

## 第 3 步：3.0 已删/改名 API

- [ ] 没有直接调用（要探测 + 换代实现）：

| 已删/改名 | 3.0 的替代 |
| --- | --- |
| `MessageProcessor.send_xml_messages` | 发送走 `MessageDeliveryService.send_message_chain` |
| `MessageProcessor._parse_xml_msg` | `MessageDeliveryService.parse_xml(xml, tag_set)` |
| `fetch_memory(sid)` / `write_memory(sid, chunks)` | `await get_session(sid, ensure_session=False)` / `await update_session(sid, content=…)` |
| `get_session_info(sid)` / `update_session_info(…)` | `get_sessions()` / `await update_session(sid, title=…)` |
| `get_effective_capabilities()`（同步） | **异步**：`await …` + 缓存预热 |

- [ ] 世代判断一律是**能力探测**（`hasattr` / `inspect.isawaitable` / 结构性特征），
      **代码里没有 `rc1`/`3.0.0`/`__version__` 这类版本号字符串**（注释除外）

---

## 第 4 步：标签 / 消息元素

- [ ] 标签注册走 `tag_set.register(...)`（`@on.llm_request` 里），**用的是框架同一个 tag_set**
- [ ] 自定义元素带 `text` 或可识别的身份字段（否则对账/去重类插件认不出它）
- [ ] 若插件会**改写消息链**：在发送层改写要在**发送之前**留下你要的形态（别让下游看到半成品）

> 抢发 / 去重类插件额外要求：**两侧同源**（台账与链用同一个函数取签名）+ **解析前剥离**
> （让框架不再解析已发段），细节见 acc 仓库的 `early_sent.py`/`main.py` 与
> `tests/test_media_dedupe.py`、`tests/test_preparse_strip.py`。

---

## 第 5 步：测试

- [ ] 双世代全量都绿（2.x + 3.0-rc2）
- [ ] 关键修复都有**反向验证**（把新测试跑在修前代码上 ⇒ 必须报红）
- [ ] 涉及框架形状的测试用"**真组件 + 计数假依赖**"，不要只读代码下结论

---

## 第 6 步：发版（**容易漏**）

- [ ] `manifest.json` 的 `version` +1
- [ ] README **标题**里的版本号同步
- [ ] README 的**变更小节**（新版本在最上，格式随仓库既有风格）
- [ ] 仓库里的**版本一致性测试**（如 `tests/test_version_bump.py`）跑过
- [ ] **提交前**先 `git ls-remote <upstream>` 确认自己不是在旧克隆上改（血泪教训：我撞过版本号）

---

## 第 7 步：PR

- [ ] 从**最新 main** 切分支（不要拿旧克隆接着干）
- [ ] 逐文件与 `origin/main` 比对，确认"只带上我要的改动、没有误删上游文件"
- [ ] PR 正文写清：现象 → 根因 → 修法 → 验证（含反向验证结果）
