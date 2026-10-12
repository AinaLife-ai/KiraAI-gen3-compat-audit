# dualgen-compat-kit — KiraAI 插件 2.x/3.0rc1 双世代兼容测试套件

一个可复用的 pytest 套件 + 框架桩库，用于验证任意 KiraAI 插件在 **2.x (v2.34.8)** 与 **3.0rc1 (8a0b812)** 两个世代的兼容性。本次世代工程（2026-10-12 全生态审计）的配套工具。

## 快速开始

```bash
# 对某插件跑全套静态+动态检查
python3 run.py --plugin /path/to/plugin_repo \
    --fw2 /var/minis/shared/kira_fw --fw3 /var/minis/shared/kira30
```

- 无 `compat_targets.py` 的插件：跑 4 条静态测试（见下），动态测试自动 skip。
- 需要 pytest（`apk add py3-pytest`）。

## 静态测试（零配置，所有插件直接可用）

| 测试 | 检查内容 |
| --- | --- |
| `test_no_removed_rc1_symbols` | AST 扫描插件源码，不得调用 rc1 已删除的会话 API（fetch_memory/write_memory/get_session_info 等）、已删模块（core.plugin.plugin_registry / core.utils.model_clients / adapter_utils / workflow_registry）、已删符号（IMAdapter/LiveEventCapability 等） |
| `test_no_version_binding` | 生产代码不得绑死版本号字符串（rc1/3.0.0/alpha/__version__），AST 级，注释与 docstring 豁免 |

> 静态扫描只覆盖**生产代码**：`tests/`/`test/` 目录整体豁免（测试桩天然是世代特异的，跨世代保证由动态层承担）。
| `test_no_unawaited_async_session_api` | rc1 已变异步的 API（update_session/delete_session/get_effective_capabilities/get_session_capabilities 等）不得在非 await 位置直接调用 |
| `test_core_imports_exist_in_both_generations` | 插件全部 `from core.* import` 符号逐一在两个真实框架 checkout 里核实存在性 |

## 动态测试（插件根目录放一个 `compat_targets.py` 声明钩子后启用）

```python
# compat_targets.py 示例（放在被测插件仓库根）
def clear_session(ctx, sid): ...      # 插件的清空上下文入口（同步或异步均可）
def format_model_name(mid, entry): ... # 插件的模型展示名格式化
def make_plugin(ctx): ...              # 用桩 ctx 构造插件实例
```

| 测试 | 检查内容 |
| --- | --- |
| `test_clear_session_preserves_metadata_both_gens` | 两代桩上分别验证：清空后对话内容为空 **且** 标题/能力设置/session.data 全部保留（防 delete+重建误伤元数据） |
| `test_model_display_never_raw_uuid` | 喂 3.0 形态（uuid 内部 ID + model_name）与 2.x 形态条目，断言展示名永远是人类可读名、绝不是 uuid |
| `test_future_framework_degrades_gracefully` | 注入「接口全改名」的假想未来 SessionManager，插件不得抛 AttributeError（特征识别兜底） |

## 框架桩库（framework_stubs.py）也可单独复用

```python
from framework_stubs import make_ctx, MODELS_2X, MODELS_3X
ctx2 = make_ctx(gen=2)   # 2.x：同步 SessionManager（fetch_memory/write_memory/...）
ctx3 = make_ctx(gen=3)   # rc1：异步 SessionManager（get_session/update_session/...，Session.content 分块 + flatten_content）
```

桩的签名全部对照真实框架源码制作（kira30: core/chat/session_manager.py / plugin_context.py；kira_fw 同名文件）。
`SessionManager3x.update_session` 还内置了 rc1 的结构断言（content 必须 list[list[dict]]、角色白名单）。

## 注意

- `test_no_unawaited_async_session_api` 是启发式：兼容层封装内部的调用也可能被报，此时把兼容层文件加入该测试的豁免（或直接修成 await 探测封装，推荐后者）。
- 桩是「行为等价物」不是完整框架：用于驱动插件的兼容分支，不替代真机回归。
