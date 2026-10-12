"""双世代框架桩：2.x (v2.34.8) 与 3.0rc1 (8a0b812) 的 SessionManager / PluginContext / Provider 形态。
全部按真实框架源码签名制作，用于在无真框架时驱动插件做双世代兼容测试。"""
import asyncio, copy, time, uuid
from dataclasses import dataclass, field


# ---------- 会话对象 ----------
@dataclass
class Session2x:  # 2.x 形态：简单对象，memory 在管理器侧
    session: str
    session_title: str = ""
    session_description: str = ""


@dataclass
class Session3x:  # rc.1 形态：content 分块 + data + internal_id
    sid: str
    internal_id: str = field(default_factory=lambda: "sess_" + uuid.uuid4().hex[:12])
    session_title: str = ""
    session_description: str = ""
    content: list = field(default_factory=list)   # list[list[dict]]
    data: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def flatten_content(self):
        return [m for chunk in self.content for m in chunk]


# ---------- 2.x 同步 SessionManager ----------
class SessionManager2x:
    def __init__(self):
        self._sessions = {}
        self._memory = {}
        self.deleted = []

    def _ensure(self, sid):
        self._sessions.setdefault(sid, Session2x(sid))
        self._memory.setdefault(sid, [])
        return self._sessions[sid]

    def get_session_info(self, session=None):
        if session is None:
            return [self._ensure(s) for s in self._sessions]
        return self._sessions.get(session)

    def update_session_info(self, session, title=None, description=None):
        s = self._ensure(session)
        if title is not None: s.session_title = title
        if description is not None: s.session_description = description

    def fetch_memory(self, session):
        return [m for chunk in self._memory.get(session, []) for m in chunk]

    def read_memory(self, session):
        return self._memory.get(session, [])

    def get_existing_memory_snapshot(self, session):
        return copy.deepcopy(self._memory.get(session)) if session in self._memory else None

    def write_memory(self, session, memory):
        self._ensure(session); self._memory[session] = memory

    def update_memory(self, session, new_chunk):
        self._ensure(session); self._memory[session].append(new_chunk)

    def get_memory_count(self, session):
        return len(self._memory.get(session, []))

    def delete_session(self, session):
        self.deleted.append(session)
        self._sessions.pop(session, None); self._memory.pop(session, None)

    def get_effective_capabilities(self, session, global_capabilities):
        caps = dict(global_capabilities)
        caps.update(getattr(self._sessions.get(session), "capabilities", {}) or {})
        return caps

    def update_session_capabilities(self, session, capabilities):
        s = self._ensure(session); s.capabilities = capabilities


# ---------- 3.0rc1 异步 SessionManager ----------
class SessionManager3x:
    def __init__(self):
        self._sessions = {}
        self.deleted = []

    async def initialize(self):
        return None

    async def get_sessions(self, include_content=True):
        out = []
        for s in self._sessions.values():
            yield_s = copy.deepcopy(s)
            if not include_content: yield_s.content = []
            out.append(yield_s)
        return out

    async def get_session(self, sid, ensure_session=True):
        if sid in self._sessions:
            return copy.deepcopy(self._sessions[sid])
        if not ensure_session:
            return None
        s = Session3x(sid)
        self._sessions[sid] = s
        return copy.deepcopy(s)

    async def update_session(self, sid, title=None, description=None, content=None, data=None):
        s = self._sessions.setdefault(sid, Session3x(sid))
        if title is not None: s.session_title = title
        if description is not None: s.session_description = description
        if content is not None:
            assert isinstance(content, list), "content 必须是 list[list[dict]]"
            for chunk in content:
                for m in chunk:
                    assert m.get("role") in ("system", "user", "assistant", "tool"), f"非法角色 {m.get('role')}"
            s.content = copy.deepcopy(content)
        if data is not None: s.data = copy.deepcopy(data)
        s.updated_at = time.time()

    async def update_memory(self, session, new_chunk):
        s = self._sessions.setdefault(session, Session3x(session))
        s.content.append(copy.deepcopy(new_chunk))

    async def get_session_message_counts(self):
        return {sid: len(s.content) for sid, s in self._sessions.items()}

    async def delete_session(self, session):
        self.deleted.append(session)
        self._sessions.pop(session, None)

    async def get_effective_capabilities(self, session, global_capabilities):
        caps = dict(global_capabilities)
        s = self._sessions.get(session)
        if s: caps.update((s.data or {}).get("capabilities", {}) or {})
        return caps

    async def update_session_capabilities(self, session, capabilities):
        s = self._sessions.setdefault(session, Session3x(session))
        s.data.setdefault("capabilities", {})
        if capabilities is None:
            s.data.pop("capabilities", None)
        else:
            s.data["capabilities"] = capabilities


# ---------- PluginContext 桩 ----------
class PluginMgrStub:
    def __init__(self, data_dir):
        self._data_dir = data_dir
    def get_plugin_data_dir(self, name=None):
        return self._data_dir


class PluginContextStub:
    """两代通用 ctx 桩：gen=2 同步会话 / gen=3 异步会话。"""
    def __init__(self, gen=2, data_dir="/tmp/kit_data"):
        self.gen = gen
        self.session_mgr = SessionManager2x() if gen == 2 else SessionManager3x()
        self.plugin_mgr = PluginMgrStub(data_dir)
        self.notices = []
        self.sent = []

    def get_session_capabilities(self, sid):
        """2.x 形态：同步。注意 gen=3 时此方法会被替换成异步（见 make_ctx）。"""
        return {}

    async def _get_session_capabilities_async(self, sid):
        return {}

    def publish_notice(self, *a, **kw):
        self.notices.append((a, kw))

    async def send_message_chain(self, sid, chain):
        self.sent.append((sid, chain))


def make_ctx(gen=2, data_dir="/tmp/kit_data"):
    ctx = PluginContextStub(gen=gen, data_dir=data_dir)
    if gen == 3:
        ctx.get_session_capabilities = ctx._get_session_capabilities_async
    return ctx


# ---------- 模型/Provider 两代形态 ----------
MODELS_2X = {  # 2.x：get_models 返回 {上游名: 参数}
    "myprovider": {"gpt-4o": {"temperature": 0.7}, "gpt-4o-mini": {}}
}
UUID_ID = "f1b2c3d4-aaaa-4bbb-8ccc-dddddddddddd"
MODELS_3X = {  # 3.0rc1：{内部ID: {model_name, config, legacy_ids?}}
    "myprovider": {
        UUID_ID: {"model_name": "gpt-4o", "config": {"temperature": 0.7}, "legacy_ids": ["gpt-4o"]},
        "9e8d7c6b-1111-4222-8333-eeeeeeeeeeee": {"model_name": "gpt-4o-mini", "config": {}},
    }
}


class ProviderMgr2x:
    def get_models(self, provider_id):
        return copy.deepcopy(MODELS_2X[provider_id])


class ProviderMgr3x:
    def get_models(self, provider_id):
        return copy.deepcopy(MODELS_3X[provider_id])

    def get_model_info(self, model_ref, model_type=None):
        pid, mid = model_ref.split(":", 1)
        e = MODELS_3X[pid][mid]
        return {"model_id": mid, "model_name": e["model_name"], "config": e["config"]}


def looks_like_uuid(s):
    return isinstance(s, str) and len(s) >= 32 and "-" in s and all(
        c in "0123456789abcdef-" for c in s.lower())


def run_maybe_async(fn, *a, **kw):
    """同步/异步通吃调用器：返回 (result, was_async)。"""
    import inspect
    r = fn(*a, **kw)
    if inspect.isawaitable(r):
        return asyncio.get_event_loop().run_until_complete(r) if not asyncio.get_event_loop().is_running() else _run_in_new_loop(r), True
    return r, False


def _run_in_new_loop(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
