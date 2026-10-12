"""双世代兼容测试套件。用法：
  KIRA_PLUGIN_DIR=/path/to/plugin KIRA_FW2=/var/minis/shared/kira_fw KIRA_FW3=/var/minis/shared/kira30 \
      python3 -m pytest test_dualgen.py -q
插件可选地在仓库根放 compat_targets.py 声明适配钩子，开启动态测试：
  clear_session(ctx, sid)          —— 插件的清空上下文入口
  format_model_name(mid, entry)    —— 插件的模型展示名格式化
  make_plugin(ctx)                 —— 用桩 ctx 构造插件实例
"""
import os, sys, asyncio, inspect, importlib.util, warnings
import pytest

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
from framework_stubs import (make_ctx, MODELS_2X, MODELS_3X, UUID_ID,
                             looks_like_uuid, SessionManager3x)
from scanners import scan_plugin, symbol_exists

PDIR = os.environ.get("KIRA_PLUGIN_DIR", "")
FW2 = os.environ.get("KIRA_FW2", "/var/minis/shared/kira_fw")
FW3 = os.environ.get("KIRA_FW3", "/var/minis/shared/kira30")

pytestmark = pytest.mark.skipif(not PDIR or not os.path.isdir(PDIR),
                                reason="KIRA_PLUGIN_DIR 未设置")

SCAN = None

def scan():
    global SCAN
    if SCAN is None:
        SCAN = scan_plugin(PDIR)
    return SCAN


def load_targets():
    p = os.path.join(PDIR, "compat_targets.py")
    if not os.path.exists(p):
        return None
    spec = importlib.util.spec_from_file_location("compat_targets", p)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, PDIR)
    try:
        spec.loader.exec_module(m)
    finally:
        sys.path.remove(PDIR)
    return m


# ---------- 静态层 ----------
def test_no_removed_rc1_symbols():
    hits = scan()["removed_hits"]
    assert not hits, "使用了 rc.1 已删除的符号/模块: " + "; ".join(
        f"{f}:{l} {t}" for f, l, t in hits[:10])


def test_no_version_binding():
    hits = [h for h in scan()["version_hits"]]
    assert not hits, "代码里出现版本号绑定（注释/docstring不算）: " + "; ".join(
        f"{f}:{l} {t!r}" for f, l, t in hits[:10])


def test_no_unawaited_async_session_api():
    hits = scan()["unawaited_hits"]
    # 启发式：兼容层封装里的调用常见，报告但不直接失败？——不，宁可严格：这些API在rc1全是async
    assert not hits, "疑似未 await 的 rc1 异步会话 API: " + "; ".join(
        f"{f}:{l} {n}()" for f, l, n in hits[:12])


def test_core_imports_exist_in_both_generations():
    problems = []
    for fw, tag in ((FW2, "2.x"), (FW3, "rc1")):
        if not os.path.isdir(fw):
            continue
        for rel, ln, module, names in scan()["core_imports"]:
            res = symbol_exists(fw, module, names)
            for n, ok in res.items():
                if not ok:
                    problems.append(f"[{tag}] {rel}:{ln} {module}.{n} 不存在")
    assert not problems, "框架导入核实失败: " + "; ".join(problems[:12])


# ---------- 动态层（需要 compat_targets.py） ----------
def test_clear_session_preserves_metadata_both_gens():
    t = load_targets()
    if t is None or not hasattr(t, "clear_session"):
        pytest.skip("插件未声明 compat_targets.clear_session")
    for gen in (2, 3):
        ctx = make_ctx(gen=gen)
        sid = "test:dm:u1"
        if gen == 2:
            ctx.session_mgr.write_memory(sid, [[{"role": "user", "content": "hi"}]])
            ctx.session_mgr.update_session_info(sid, title="标题")
            ctx.session_mgr.update_session_capabilities(sid, {"x": 1})
        else:
            asyncio.new_event_loop().run_until_complete(_seed3(ctx, sid))
        r = t.clear_session(ctx, sid)
        if inspect.isawaitable(r):
            _run(r)
        if gen == 2:
            s = ctx.session_mgr.get_session_info(sid)
            assert s is not None, "gen2 清空后会话本体被删（元数据丢失）"
            assert ctx.session_mgr.fetch_memory(sid) == [], "gen2 清空后记忆非空"
            assert getattr(s, "capabilities", None) == {"x": 1}, "gen2 能力设置被误伤"
        else:
            loop = asyncio.new_event_loop()
            s = loop.run_until_complete(ctx.session_mgr.get_session(sid, ensure_session=False))
            assert s is not None, "rc1 清空后会话本体被删（标题/能力/data 全丢）"
            assert s.content == [], "rc1 清空后 content 非空"
            assert s.data.get("capabilities") == {"x": 1}, "rc1 能力设置被误伤"
            assert s.session_title == "标题", "rc1 标题被误伤"


async def _seed3(ctx, sid):
    await ctx.session_mgr.update_session(sid, title="标题",
        content=[[{"role": "user", "content": "hi"}]])
    await ctx.session_mgr.update_session_capabilities(sid, {"x": 1})


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_model_display_never_raw_uuid():
    t = load_targets()
    if t is None or not hasattr(t, "format_model_name"):
        pytest.skip("插件未声明 compat_targets.format_model_name")
    for pid, models in MODELS_3X.items():
        for mid, entry in models.items():
            shown = t.format_model_name(mid, entry)
            assert shown == entry["model_name"], f"3.0 形态下展示 {shown!r} 而非 model_name"
            assert not looks_like_uuid(shown), f"展示成了内部ID(uuid): {shown!r}"
    for pid, models in MODELS_2X.items():
        for mid, entry in models.items():
            shown = t.format_model_name(mid, entry)
            assert shown == mid, f"2.x 形态下展示应变 {mid!r}，实际 {shown!r}"


def test_future_framework_degrades_gracefully():
    """第三种假想未来形态：会话接口全改名。插件兼容层应安全跳过+告警而非崩溃。"""
    t = load_targets()
    if t is None or not hasattr(t, "make_plugin"):
        pytest.skip("插件未声明 compat_targets.make_plugin")
    ctx = make_ctx(gen=3)
    class FutureSM:  # 接口全改名
        pass
    ctx.session_mgr = FutureSM()
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        try:
            plugin = t.make_plugin(ctx)
        except AttributeError as e:
            pytest.fail(f"未来形态下插件直接 AttributeError（静默兼容层缺失）: {e}")
