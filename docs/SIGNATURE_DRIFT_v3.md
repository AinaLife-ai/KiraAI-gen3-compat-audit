# 签名漂移：接管点**必须**原样透传参数

> 本文档来自一次**线上事故**（2026-10-13）：框架给已有方法加了一个参数，插件把签名写死，
> 结果**消息一条都发不出去**。这类问题在 v3 生态里会反复出现（框架还在快速演进），
> 所以把它单列成规范：**凡"接管/包装框架方法"的代码，签名一律原样透传。**

---

## 1. 事故现场

```
TypeError: AcceleratorPlugin._install_early_sent_strip.<locals>.
           delivery_factory.<locals>.send_message_chain()
           got an unexpected keyword argument 'bot'
[accel] 接管点 early_sent_dedupe_delivery 出错；该实现有不可撤销的副作用，
        **不回退原实现**（否则会重复发送）
```

框架侧只是做了一次**常规演进**（KiraAI v3.0.0-rc.2 把 `send_message_chain` 的
`self_id=` 换成了 `bot: User`），插件把签名写死 ⇒ 直接 TypeError。

**为什么后果被放大**：这类接管点通常声明"有不可撤销的副作用 ⇒ 出错**不回退**原实现"
（回退 = 把已经发出去的东西再发一遍）。于是出错不是"降级"，而是**主流程被打死**：
实测框架直发 / 弃用入口 / 插件抢发**三条路径全灭，实际投递次数 0**。

---

## 2. 判据：什么算"接管点"

只要符合下面任意一条，就必须按本文的规则写：

* 通过 `setattr(cls, name, wrapper)` / `install(...)` / `PatchHandle(...)` 装到**框架类**上的方法；
* 在 `def factory(original)` 里定义、并且**调用了 `original`**（或替换它）的实现体；
* 名字与框架方法同名（`send_message_chain` / `send_xml_messages` / `parse_xml` /
  `add_message_ids` / `get_model_client` / `execute_tool` / `_save_memory` / `handle` …）。

---

## 3. 规则：只取自己要的，其余原样透传

```python
# ❌ 反面：把框架的签名抄下来
def factory(original):
    async def send_message_chain(d_self, session, chain, *,
                                 memory_message=None, self_id=None):
        ...
        return await original(d_self, session, chain,
                              memory_message=memory_message, self_id=self_id)

# ✅ 正确：按位置取自己要的，其余 *args / **kwargs 全部穿过去
def factory(original):
    async def send_message_chain(d_self, session=None, chain=None, *args, **kwargs):
        ...
        return await original(d_self, session, chain, *args, **kwargs)
```

**需要用到某个参数时**，从 `args/kwargs` 里取，不要改签名：

```python
async def execute_tool(self, *args, **kwargs):
    event = args[0] if args else kwargs.get("event")
    resp = args[1] if len(args) > 1 else kwargs.get("resp")
    ...
    return await original(self, *args, **kwargs)      # 原样转发
```

### 三个必须记住的坑

1. **`staticmethod` 的包装/还原**：`parse_xml` / `add_message_ids` 这类是静态方法，
   `setattr` 普通函数后**实例调用会多传一个 self** ⇒ 包完要 `staticmethod(...)` 套回去，
   还原时也要还原成 `staticmethod`。
2. **`*args/**kwargs` 的作用域**：把 `original(..., *args, **kwargs)` 写在**别的函数**里
   会 `NameError: name 'args' is not defined` ⇒ 参数要一路穿到那个函数（本仓 `tools/` 里
   有 AST 作用域自检脚本可以照抄）。
3. **绝不 try/except 重试**：发送有副作用，重试 = 重发。要判断"目标是否接受某参数"，
   用 `inspect.signature` 探测（可缓存），不要"先试着传，报错再退"。

---

## 4. 加一条静态守卫（推荐所有插件都加）

AST 扫描自己的 `main.py`：**凡"工厂内嵌套 + 调用 `original`"的实现体，必须带 `**kwargs`**。
漏了就报红，不再依赖人肉 review。参考实现见 acc 仓库的
`tests/test_framework_signature_drift.py::S7b`：

```python
import ast
tree = ast.parse(open("main.py", encoding="utf-8").read())
bad = []
for fn in ast.walk(tree):
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    names = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
    if not (names & {"original", "orig", "_orig", "raw", "inner"}):
        continue
    for sub in ast.walk(fn):                      # 工厂里嵌套的实现体
        if not isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) or sub is fn:
            continue
        body = ast.unparse(sub)
        if "original(" not in body and "await original" not in body:
            continue                              # 不调 original ⇒ 内部辅助函数，跳过
        if sub.args.kwarg is None:
            bad.append(f"{sub.name}@{sub.lineno}")
assert not bad, f"这些包装点缺 **kwargs：{bad}"
```

---

## 5. 自动扫描（全仓体检）

```bash
python3 tools/scan_signature_drift.py <仓库目录…> [--json out.json]
```

判三类：

| 级别 | 含义 |
| --- | --- |
| **P0-a** | 包装框架方法的实现体**没有 `**kwargs`**（本文这类） |
| **P0-b** | 给发送 API 传 `self_id=`（rc2 已改名 `bot=`） |
| **P1** | 直接调用 3.0 已删/改名 API（带 `hasattr/getattr` 探测的回退分支**不算**） |

**已知局限**（2026-10-13）：扫描器把"工厂内部辅助函数"（只服务本工厂、框架不会直接调）
偶尔也列为候选；"探测写在更外层函数"的回退分支也可能被误报 ⇒ 结果当**候选**看，
用第 4 节那条精确守卫做权威判定。

---

## 6. 案例与修法（可直接照抄）

| 仓库 | 版本 | 改了什么 |
| --- | --- | --- |
| `KiraAI_accelerator_plugin` | v1.0.88 → v1.0.90 | 发送层 `send_message_chain`、2.x `send_xml_messages`、解析层 `parse_xml`/`add_message_ids`，以及 `_build_client`/`get_model_client`/`execute_tool`/`_save_memory` 全部改为透传；新增 S7b 守卫 |
| `KiraAI-qqbot-fullmsg-bridge-plugin` | v1.6.48 | 发送落点 `_send_message`（含其内部 `_send_message_inner`）与旁听包装 `_handle_message` 透传 |

验证方式（**"真组件 + 计数假依赖"** 是本仓推荐的标准手法）：造一个"**新版框架类**"
（多一个关键字参数）+ 真接管点，跑三条路径，看**实际投递次数**是否归零 ⇒ 30 行脚本
就能把线上事故钉死并做反向验证。
