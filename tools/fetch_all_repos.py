"""枚举 + 拉取我们（znq19 / AinaLife-ai）的全部仓库，供批量体检。

排除：fork（别人的仓）、archived、以及明显不是插件的（框架副本/文档）。
产物：/var/minis/shared/audit_rc2/<repo>/  （tarball 解压，最新 main）
"""
import io
import json
import os
import pathlib
import re
import tarfile
import time
import urllib.error
import urllib.request

TOK = re.search(r"ghp_[A-Za-z0-9]+",
                open("/var/minis/memory/GLOBAL.md", encoding="utf-8").read()).group(0)
H = {"Authorization": "token " + TOK, "Accept": "application/vnd.github+json",
     "User-Agent": "audit"}
op = urllib.request.build_opener(urllib.request.ProxyHandler({"https": "http://127.0.0.1:7899"}))
OUT = pathlib.Path("/var/minis/shared/audit_rc2")
OUT.mkdir(parents=True, exist_ok=True)


def api(url):
    req = urllib.request.Request(url, headers=H)
    for _ in range(4):
        try:
            with op.open(req, timeout=45) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            print("  HTTP", e.code, url)
            return []
        except Exception:
            time.sleep(2)
    return []


def list_repos(owner):
    out = []
    for page in (1, 2):
        d = api(f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}&sort=updated")
        if not isinstance(d, list) or not d:
            break
        out += d
    return out


all_repos = []
for owner in ("znq19", "AinaLife-ai"):
    for r in list_repos(owner):
        if r.get("fork") or r.get("archived"):
            continue
        all_repos.append((owner, r["name"], r.get("description") or "", r["default_branch"],
                          r.get("size", 0)))
print(f"候选仓库 {len(all_repos)} 个\n")

skip_kw = ("kirai", "framework", "core", "docs", "market")
made = 0
for owner, name, desc, branch, size in sorted(all_repos, key=lambda x: x[1]):
    dst = OUT / name
    if dst.is_dir():
        print(f"  = {name}（已存在，跳过）")
        continue
    if size > 20000:                      # >20MB 的多半是框架副本/素材，跳过下载
        print(f"  - {name}: 体积 {size}KB，跳过")
        continue
    url = f"https://codeload.github.com/{owner}/{name}/tar.gz/refs/heads/{branch}"
    try:
        req = urllib.request.Request(url, headers=H)
        with op.open(req, timeout=180) as r:
            data = r.read()
    except Exception as e:
        print(f"  ✗ {name}: 下载失败 {type(e).__name__}")
        continue
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = tf.getmembers()
            root = members[0].name.split("/")[0]
            tf.extractall(OUT / "_tmp", filter="data")
        (OUT / "_tmp" / root).rename(dst)
        made += 1
        print(f"  ✓ {owner}/{name}  ({len(data)//1024}KB)")
    except Exception as e:
        print(f"  ✗ {name}: 解压失败 {type(e).__name__} {e}")
    finally:
        import shutil
        shutil.rmtree(OUT / "_tmp", ignore_errors=True)

print(f"\n本次新拉取 {made} 个；目录：{OUT}")
