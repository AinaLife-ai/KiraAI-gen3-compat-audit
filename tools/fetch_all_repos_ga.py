"""GA 审查：枚举 + 全新拉取全部目标仓库（不落旧副本）。

范围：
  znq19 / AinaLife-ai 的全部非 fork、非 archived 仓库
  + znq19/kiraai-reboot-pulgin（fork 但 znq19 主力维护，例外纳入）
  + Qixuan112 的 KiraAI_Group-Manager-Plugin / KiraAI-subagent-plugin / Kira_headless_browser
产物：/var/minis/shared/audit_ga/<owner>__<repo>/  +  manifest 清单 JSON
"""
import io, json, pathlib, re, tarfile, time, urllib.error, urllib.request

TOK = re.search(r"ghp_[A-Za-z0-9]+",
                open("/var/minis/memory/GLOBAL.md", encoding="utf-8").read()).group(0)
H = {"Authorization": "token " + TOK, "Accept": "application/vnd.github+json", "User-Agent": "audit-ga"}
OUT = pathlib.Path("/var/minis/shared/audit_ga")
OUT.mkdir(parents=True, exist_ok=True)

direct = urllib.request.build_opener()
proxy = urllib.request.build_opener(urllib.request.ProxyHandler(
    {"http": "http://127.0.0.1:7899", "https": "http://127.0.0.1:7899"}))


def fetch(url, binary=False, retries=6):
    last = None
    for i in range(retries):
        for op in (direct, proxy):
            try:
                req = urllib.request.Request(url, headers=H)
                with op.open(req, timeout=90) as r:
                    data = r.read()
                return data if binary else json.loads(data)
            except urllib.error.HTTPError as e:
                print(f"  HTTP {e.code} {url[:90]}")
                e.read()
                return None
            except Exception as e:
                last = e
                time.sleep(1.5 + i)
    print(f"  ✗ 拉取失败 {url[:90]}: {type(last).__name__}")
    return None


def list_repos(owner):
    out = []
    for page in (1, 2, 3):
        d = fetch(f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}&sort=updated")
        if not isinstance(d, list) or not d:
            break
        out += d
    return out


targets = {}   # (owner, name) -> dict(meta)

for owner in ("znq19", "AinaLife-ai"):
    for r in list_repos(owner):
        if r.get("fork") or r.get("archived"):
            continue
        targets[(owner, r["name"])] = r

# 例外：fork 但 znq19 主力维护
r = fetch("https://api.github.com/repos/znq19/kiraai-reboot-pulgin")
if r:
    targets[("znq19", "kiraai-reboot-pulgin")] = r

# Qixuan112 三个
for name in ("KiraAI_Group-Manager-Plugin", "KiraAI-subagent-plugin", "Kira_headless_browser"):
    r = fetch(f"https://api.github.com/repos/Qixuan112/{name}")
    if r:
        targets[("Qixuan112", name)] = r

print(f"目标仓库共 {len(targets)} 个\n")

manifest = []
made = skipped = failed = 0
for (owner, name), r in sorted(targets.items(), key=lambda x: (x[0][1].lower())):
    branch = r.get("default_branch", "main")
    size = r.get("size", 0)
    tag = f"{owner}__{name}"
    dst = OUT / tag
    if size > 30000:
        print(f"  - {tag}: {size}KB 过大，跳过下载（仅登记）")
        manifest.append({"owner": owner, "name": name, "branch": branch, "size_kb": size,
                         "fetched": False, "reason": "too_big"})
        skipped += 1
        continue
    data = fetch(f"https://codeload.github.com/{owner}/{name}/tar.gz/refs/heads/{branch}", binary=True)
    if not data:
        manifest.append({"owner": owner, "name": name, "branch": branch, "size_kb": size,
                         "fetched": False, "reason": "download_failed"})
        failed += 1
        continue
    try:
        import shutil
        shutil.rmtree(dst, ignore_errors=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = tf.getmembers()
            root = members[0].name.split("/")[0]
            tf.extractall(OUT / "_tmp", filter="data")
        (OUT / "_tmp" / root).rename(dst)
        is_plugin = (dst / "manifest.json").exists()
        manifest.append({"owner": owner, "name": name, "branch": branch, "size_kb": size,
                         "fetched": True, "dir": tag, "has_manifest": is_plugin,
                         "fork": r.get("fork", False)})
        made += 1
        print(f"  ✓ {tag}  ({len(data)//1024}KB, plugin={is_plugin})")
    except Exception as e:
        print(f"  ✗ {tag}: 解压失败 {type(e).__name__} {e}")
        failed += 1
    finally:
        import shutil
        shutil.rmtree(OUT / "_tmp", ignore_errors=True)

(OUT / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
print(f"\n完成：拉取 {made} / 跳过 {skipped} / 失败 {failed}；清单 _manifest.json")
