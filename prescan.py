#!/usr/bin/env python3
"""KiraAI 3.0rc1 兼容性机械预扫描：对每仓输出客观命中清单。
只报事实（文件:行:模式），不做结论。结论由审计者（人或子代理）做出。"""
import os, re, json, subprocess, sys

REPOS = "/var/minis/shared/gen3audit/repos"
OUT   = "/var/minis/shared/gen3audit/prescan"

# 分组模式：(组名, [(标签, 正则)], 严重度提示)
GROUPS = [
 ("A_会话API_rc1破坏", [
   ("fetch_memory",        r"\bfetch_memory\b"),
   ("write_memory",        r"\bwrite_memory\s*\("),
   ("read_memory",         r"\bread_memory\s*\("),
   ("update_memory",       r"\bupdate_memory\s*\("),
   ("get_session_info",    r"\bget_session_info\b"),
   ("update_session_info", r"\bupdate_session_info\b"),
   ("chat_memory直改",      r"\bchat_memory\b"),
   ("_save_memory",        r"\b_save_memory\b"),
   ("get_memory_count",    r"\bget_memory_count\b"),
   ("get_existing_memory_snapshot", r"\bget_existing_memory_snapshot\b"),
   ("delete_session",      r"\bdelete_session\s*\("),
   ("get_effective_capabilities", r"\bget_effective_capabilities\b"),
   ("get_session_capabilities",   r"\bget_session_capabilities\b"),
   ("update_session_capabilities",r"\bupdate_session_capabilities\b"),
   ("memory_json路径",      r"chat_memory\.json|data/memory"),
   ("clear/reset会话语义",  r"clear_session|reset_session|清空|清除上下文|重开会话|新会话"),
 ]),
 ("B_模型名展示_uuid风险", [
   ("get_models",       r"\bget_models\s*\("),
   ("get_model_info",   r"\bget_model_info\b"),
   ("model_id使用",      r"\bmodel_id\b"),
   ("model_name使用",    r"\bmodel_name\b"),
   ("register_model",   r"\bregister_model\b"),
   ("默认模型读取",       r"default_model|default_llm|chat_model"),
   ("模型选择引用",       r"provider_id:|provider:|model_ref"),
   ("legacy_ids",       r"\blegacy_ids\b"),
   ("sync_models",      r"\bsync_models\b"),
   ("update_model",     r"\bupdate_model\b"),
 ]),
 ("C_Provider客户端", [
   ("旧客户端路径",       r"core\.utils\.model_clients"),
   ("OpenAICompatible", r"OpenAICompatible\w+"),
   ("get_model_client", r"\bget_model_client\b"),
   ("provider_mgr",     r"\bprovider_mgr\b|\bprovider_manager\b"),
   ("ProviderAPIError", r"ProviderAPIError"),
   ("直接OpenAI",        r"openai\.|AsyncOpenAI|OpenAI\("),
 ]),
 ("D_插件模块路径", [
   ("旧plugin_registry", r"plugin_registry"),
   ("旧plugin_handlers", r"plugin_handlers"),
   ("旧plugin.plugin",  r"core\.plugin\.plugin\b"),
   ("手建PluginContext", r"PluginContext\s*\("),
   ("sticker_manager",  r"\bsticker_manager\b"),
   ("flush_session_messages", r"\bflush_session_messages\b"),
 ]),
 ("E_工作流与消息处理", [
   ("workflow_registry", r"workflow_registry|register_workflow|WorkflowType"),
   ("MessageProcessor", r"\bMessageProcessor\b"),
   ("SessionBuffer",    r"\bSessionBuffer\b|session_buffer"),
   ("message_format_to_text", r"message_format_to_text"),
   ("_iter_message_images",   r"_iter_message_images|_build_native_content"),
   ("handle_cmt_message",     r"handle_cmt_message"),
   ("send_xml_messages",      r"send_xml_messages"),
   ("_parse_xml_msg",         r"_parse_xml_msg|_add_message_ids"),
   ("ImageDescCache",         r"ImageDescCache|image_desc_cache"),
   ("MessageFormatter",       r"MessageFormatter"),
   ("message_delivery",       r"message_delivery|MessageDeliveryService"),
   ("message_history",        r"message_history|MessageHistory"),
   ("session_buffer_mgr",     r"session_buffer_mgr"),
 ]),
 ("F_适配器与能力", [
   ("旧适配器基类",      r"adapter_utils|IMAdapter|SocialMediaAdapter|LiveStreamAdapter"),
   ("emoji_dict",     r"\bemoji_dict\b"),
   ("message_types",  r"\bmessage_types\b"),
   ("supported_elements", r"supported_elements"),
   ("IMCapability",   r"\bIMCapability\b"),
   ("FeedCapability", r"\bFeedCapability\b"),
   ("直播/语音预留",     r"LiveEventCapability|VoiceChannelCapability"),
   ("send_direct_message", r"send_direct_message|send_group_message"),
   ("get_capability", r"\bget_capability\b"),
   ("adapter_mgr",    r"\badapter_mgr\b"),
 ]),
 ("G_事件与钩子", [
   ("on_im_message",  r"on_im_message|ON_IM_MESSAGE"),
   ("on_llm_request", r"on_llm_request|ON_LLM_REQUEST"),
   ("on_llm_response",r"on_llm_response|ON_LLM_RESPONSE"),
   ("ON_COMMENT",     r"ON_COMMENT|on\.comment"),
   ("comment钩子",     r"comment"),
 ]),
 ("H_人设与自拍", [
   ("persona_mgr",    r"\bpersona_mgr\b|persona_manager"),
   ("selfie",         r"\bselfie\b"),
   ("reference_image",r"reference_image"),
   ("chat_rules",     r"chat_rules|private_chat_rules|group_chat_rules"),
 ]),
 ("I_直读框架文件", [
   ("读框架文件",       r"open\s*\([^)]*(?:core|kira)[^)]*\.py|importlib|__import__"),
   ("猴子补丁",        r"setattr\s*\([^,]+,\s*['\"]\w+['\"]\s*,|monkeypatch|\.\w+\s*=\s*\w*\s*#.*patch"),
   ("替换框架文件",      r"shutil\.copy|覆盖|replace.*framework|patch_file"),
 ]),
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}

def scan_file(path, pats):
    hits = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return hits
    for i, line in enumerate(lines, 1):
        for label, pat in pats:
            if re.search(pat, line):
                hits.append((i, label, line.strip()[:160]))
    return hits

def main():
    os.makedirs(OUT, exist_ok=True)
    summary = {}
    for repo in sorted(os.listdir(REPOS)):
        rdir = os.path.join(REPOS, repo)
        if not os.path.isdir(rdir):
            continue
        report = {}
        for gname, pats in GROUPS:
            ghits = []
            for root, dirs, files in os.walk(rdir):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fn in files:
                    if not fn.endswith((".py", ".js", ".html", ".json", ".md")):
                        continue
                    # md 文件只扫配置声明相关
                    fp = os.path.join(root, fn)
                    if fn.endswith(".md") and gname not in ("A_会话API_rc1破坏",):
                        continue
                    for ln, label, text in scan_file(fp, pats):
                        ghits.append({"file": os.path.relpath(fp, rdir), "line": ln,
                                      "label": label, "text": text})
            if ghits:
                report[gname] = ghits
        # manifest core_version
        man_core = None
        for cand in ("manifest.json", "plugin.json"):
            mp = os.path.join(rdir, cand)
            if os.path.exists(mp):
                try:
                    man_core = json.load(open(mp, encoding="utf-8")).get("core_version")
                except Exception as e:
                    man_core = f"PARSE_ERROR:{e}"
        head = subprocess.run(["git", "-C", rdir, "log", "-1", "--format=%h %ci %s"],
                              capture_output=True, text=True).stdout.strip()
        report["_meta"] = {"repo": repo, "head": head, "core_version": man_core}
        with open(os.path.join(OUT, repo + ".json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        summary[repo] = {g: len(h) for g, h in report.items() if g != "_meta"}
        summary[repo]["core_version"] = man_core
    with open(os.path.join(OUT, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    # 打印紧凑汇总
    for repo, s in sorted(summary.items()):
        flags = [f"{g.split('_')[0]}{g.count('_')}:{n}" for g, n in s.items() if isinstance(n, int)]
        print(f"{repo:55s} cv={str(s.get('core_version')):10s} {' '.join(flags) if flags else 'CLEAN'}")

if __name__ == "__main__":
    main()
