#!/usr/bin/env python3
"""PR 流程助手：sync（同步fork到上游最新）/ pushpr（推分支+建PR）。
用法：
  python3 pr_helper.py sync znq19/KiraAI_x_plugin
  python3 pr_helper.py pushpr <local_repo_dir> znq19/KiraAI_x_plugin <branch> <标题> <正文文件>
身份与令牌从 /var/minis/shared/gen3audit/.gh_env 读。绝不打印 token。"""
import json, os, subprocess, sys, urllib.request

ENV = "/var/minis/shared/gen3audit/.gh_env"
TOKEN = ""
for line in open(ENV):
    if line.startswith("GH_TOKEN="):
        TOKEN = line.strip().split("=", 1)[1]
ME = "AinaLife-ai"
PROXY = "http://127.0.0.1:7899"


def api(method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "gen3-audit"})
    proxy = urllib.request.ProxyHandler({"https": PROXY})
    try:
        with urllib.request.build_opener(proxy).open(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def ensure_fork(upstream):
    """确保 ME/<name> 存在且与上游同步到同一 head。返回 (fork_default_branch, upstream_head)。"""
    name = upstream.split("/", 1)[1]
    st, up = api("GET", f"/repos/{upstream}")
    assert st == 200, f"上游读取失败 {st}: {up}"
    dflt = up["default_branch"]
    st, fk = api("GET", f"/repos/{ME}/{name}")
    if st != 200:
        st, fk = api("POST", f"/repos/{upstream}/forks", {})
        assert st in (200, 202), f"fork 失败 {st}: {fk}"
        import time
        for _ in range(30):
            st, fk = api("GET", f"/repos/{ME}/{name}")
            if st == 200:
                break
            time.sleep(2)
        assert st == 200, "fork 创建后仍不可见"
    # merge-upstream 同步
    st, r = api("POST", f"/repos/{ME}/{name}/merge-upstream", {"branch": dflt})
    if st not in (200, 409):  # 409=历史无关等，需硬同步
        print(f"merge-upstream 返回 {st}: {str(r)[:120]}")
    if st == 409:
        # 硬同步：直接把 fork 默认分支指到上游 head
        st, upref = api("GET", f"/repos/{upstream}/git/ref/heads/{dflt}")
        sha = upref["object"]["sha"]
        st, _ = api("PATCH", f"/repos/{ME}/{name}/git/refs/heads/{dflt}",
                    {"sha": sha, "force": True})
        assert st == 200, "硬同步失败"
    st, upref = api("GET", f"/repos/{upstream}/git/ref/heads/{dflt}")
    return dflt, upref["object"]["sha"]


def cmd_sync(upstream):
    dflt, sha = ensure_fork(upstream)
    print(json.dumps({"default": dflt, "upstream_head": sha}))


def cmd_pushpr(local, upstream, branch, title, body_file):
    name = upstream.split("/", 1)[1]
    dflt, up_sha = ensure_fork(upstream)
    env = dict(os.environ, https_proxy=PROXY, http_proxy=PROXY)
    def git(*args, check=True):
        r = subprocess.run(["git", "-C", local, *args], capture_output=True, text=True, env=env)
        if check and r.returncode != 0:
            raise SystemExit(f"git {' '.join(args)} 失败: {r.stderr[:300]}")
        return r.stdout.strip()
    # 远端配置
    remotes = git("remote")
    if "fork" not in remotes.split():
        git("remote", "add", "fork", f"https://x-access-token:{TOKEN}@github.com/{ME}/{name}.git")
    # 确认本地分支 head
    head = git("rev-parse", branch)
    # 推分支
    git("push", "-u", "fork", f"{branch}:{branch}")
    # 身份自检
    ae = git("log", "-1", "--format=%ae", branch)
    assert ae == f"293270655+{ME}@users.noreply.github.com", f"提交身份错误: {ae}"
    # 建 PR
    body = open(body_file, encoding="utf-8").read() if body_file and os.path.exists(body_file) else ""
    st, pr = api("POST", f"/repos/{upstream}/pulls",
                 {"title": title, "head": f"{ME}:{branch}", "base": dflt, "body": body})
    if st == 422 and "pull request already exists" in str(pr):
        st, prs = api("GET", f"/repos/{upstream}/pulls?head={ME}:{branch}&state=open")
        pr = prs[0]
        print(json.dumps({"pr": pr["html_url"], "number": pr["number"], "existed": True}))
        return
    assert st == 201, f"建PR失败 {st}: {str(pr)[:300]}"
    print(json.dumps({"pr": pr["html_url"], "number": pr["number"], "existed": False}))


if __name__ == "__main__":
    if sys.argv[1] == "sync":
        cmd_sync(sys.argv[2])
    elif sys.argv[1] == "pushpr":
        cmd_pushpr(*sys.argv[2:7])
