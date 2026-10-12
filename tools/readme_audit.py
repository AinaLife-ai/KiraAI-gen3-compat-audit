#!/usr/bin/env python3
"""17 仓 README 一致性审查：版本号 / 更新日志 / 默认折叠 / 与 manifest 对齐"""
import json, os, re, urllib.request, base64

TOKEN = os.environ["GH_TOKEN"]
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json",
     "User-Agent": "readme-audit"}
PROXY = "http://127.0.0.1:7899"
urllib.request.install_opener(urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})))

# (repo, pr_no, our_version)  our_version = PR 里 manifest 的版本
REPOS = [
    ("znq19/KiraAI_fold_fan_formatter_plugin", 3, None),
    ("znq19/KiraAI-subagent-plugin", 2, None),
    ("znq19/KiraKB_Plugin", 7, None),
    ("znq19/KiraAI_midflight_message_plugin", 17, None),
    ("znq19/KiraAI-openai-stream-compat", 3, None),
    ("znq19/KiraAI_model_config_query_plugin", 1, None),
    ("znq19/KiraAI_qzone_plugin", 6, None),
    ("znq19/KiraAI_accelerator_plugin", 100, None),
    ("znq19/kiraai-reboot-pulgin", 3, None),
    ("znq19/KiraAI_auto_delete_session_plugin", 4, None),
    ("znq19/KiraAI_session_merger_plugin", 19, None),
    ("znq19/KiraAI_ops_plugin", 5, None),
    ("znq19/KiraAI_daily_report_plugin", 6, None),
    ("Qixuan112/Kira_headless_browser", 38, None),
    ("Qixuan112/KiraAI_Group-Manager-Plugin", 8, None),
    ("AinaLife-ai/KiraAI_kira_wiki_plugin", 1, None),
    ("AinaLife-ai/KiraAI_hotnews_plugin", 1, None),
]

def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}", headers=H)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def get_file(repo, path, ref=None):
    q = f"?ref={ref}" if ref else ""
    try:
        d = api(f"/repos/{repo}/contents/{path}{q}")
        return base64.b64decode(d["content"]).decode("utf-8", "replace")
    except Exception:
        return None

def analyze_readme(rd, manifest_ver):
    if rd is None:
        return {"exists": False}
    out = {"exists": True}
    # 更新日志区段
    m = re.search(r"^#{1,4}\s*.*(更新日志|更新记录|变更日志|changelog|Changelog|CHANGELOG).*$",
                  rd, re.M)
    out["has_changelog_section"] = bool(m)
    if m:
        sec_start = m.start()
        # 区段内容 = 到下一个同级或更高级标题
        lvl = len(re.match(r"^(#+)", m.group(0)).group(1))
        rest = rd[m.end():]
        nxt = re.search(rf"^#{{1,{lvl}}}\s", rest, re.M)
        sec = rest[:nxt.start()] if nxt else rest
        out["changelog_in_details"] = "<details" in sec.lower()
        # 区段里出现的版本号
        vers = re.findall(r"v?(\d+\.\d+\.\d+)", sec)
        out["changelog_versions"] = sorted(set(vers), key=lambda v: [int(x) for x in v.split(".")], reverse=True)[:6]
        out["changelog_has_manifest_ver"] = manifest_ver in vers if manifest_ver else None
        # <details> 里 summary 提到的最新版本
        dm = re.search(r"<summary>.*?(v?\d+\.\d+\.\d+).*?</summary>", sec, re.S | re.I)
        out["details_summary_ver"] = dm.group(1) if dm else None
    # README 全文里的版本声明（标题/徽标/"版本"字样）
    vm = re.findall(r"(?:版本|version|Version|v)\s*[:：]?\s*v?(\d+\.\d+\.\d+)", rd[:3000])
    out["readme_version_mentions"] = sorted(set(vm), key=lambda v: [int(x) for x in v.split(".")], reverse=True)[:6]
    return out

report = {}
for repo, pr_no, _ in REPOS:
    e = {}
    # PR 状态
    try:
        pr = api(f"/repos/{repo}/pulls/{pr_no}")
        e["pr_state"] = pr["state"] + ("(merged)" if pr.get("merged_at") else "")
        e["pr_head"] = f"{pr['head']['user']['login']}:{pr['head']['ref']}"
        e["base_branch"] = pr["base"]["ref"]
    except Exception as ex:
        e["pr_state"] = f"ERR {ex}"
        e["base_branch"] = None
    # manifest（open PR 看 fork 分支树 = 我们推的版本；merged 看 base 主干）
    is_open = e["pr_state"].startswith("open")
    mrepo = pr["head"]["repo"]["full_name"] if is_open and pr["head"].get("repo") else repo
    ref = pr["head"]["ref"] if is_open else e.get("base_branch")
    man = get_file(mrepo, "manifest.json", ref)
    if man:
        try:
            mj = json.loads(man)
            e["manifest_version"] = mj.get("plugin_version") or mj.get("version")
        except Exception:
            e["manifest_version"] = "PARSE_ERR"
    else:
        e["manifest_version"] = None
    rd = get_file(mrepo, "README.md", ref)
    e["readme"] = analyze_readme(rd, e.get("manifest_version"))
    report[repo] = e
    print(f"== {repo}")
    print(f"   PR#{pr_no}: {e['pr_state']}  head={e.get('pr_head')}")
    print(f"   manifest: {e['manifest_version']}")
    r = e["readme"]
    if not r["exists"]:
        print("   README: 不存在")
    else:
        print(f"   README 版本提及: {r['readme_version_mentions']}")
        print(f"   更新日志区段: {r['has_changelog_section']}  折叠: {r.get('changelog_in_details')}  "
              f"含manifest版本: {r.get('changelog_has_manifest_ver')}  区内版本: {r.get('changelog_versions')}  "
              f"summary版本: {r.get('details_summary_ver')}")

with open("/var/minis/shared/gen3audit/readme_audit.json", "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("\nsaved readme_audit.json")
