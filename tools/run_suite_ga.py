"""通用插件测试套件运行器：对指定仓逐个跑 tests/test_*.py，分别用 2.x 与 GA 框架。

用法：python3 run_suite_ga.py <repo_dir> [repo_dir2 ...]
环境：KIRA_FW 由本脚本按世代注入；结果打印 + 写 /tmp/suite_ga_<repo>.json
"""
import json, os, pathlib, subprocess, sys

FW2 = "/var/minis/shared/kira_fw"
FW3 = "/var/minis/shared/kira30ga"


def run_one(repo: pathlib.Path, f: pathlib.Path, fw: str):
    env = dict(os.environ, KIRA_FW=fw)
    try:
        r = subprocess.run([sys.executable, str(f)], capture_output=True, text=True,
                           timeout=240, env=env, cwd=str(repo))
        return r.returncode, (r.stdout + r.stderr)[-300:]
    except subprocess.TimeoutExpired:
        return "timeout", ""


def suite(repo_dir: str):
    repo = pathlib.Path(repo_dir)
    skip = {"_env.py", "measure_lock_hold.py", "conftest.py"}
    files = sorted({f for f in repo.rglob("test_*.py") if f.name not in skip
                    and "__pycache__" not in f.parts})
    res = {}
    for f in files:
        rel = str(f.relative_to(repo))
        row = {}
        for gen, fw in (("2.x", FW2), ("GA", FW3)):
            rc, tail = run_one(repo, f, fw)
            row[gen] = "PASS" if rc == 0 else f"FAIL({rc})"
            if rc != 0 and rc != "timeout":
                row[gen + "_tail"] = tail
        res[rel] = row
        mark = "✓" if row["2.x"] == "PASS" and row["GA"] == "PASS" else "✗"
        print(f"  {mark} {rel:58} 2.x={row['2.x']:10} GA={row['GA']}")
    out = f"/tmp/suite_ga_{repo.name}.json"
    pathlib.Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    ok2 = sum(1 for v in res.values() if v["2.x"] == "PASS")
    ok3 = sum(1 for v in res.values() if v["GA"] == "PASS")
    print(f"== {repo.name}: 2.x {ok2}/{len(res)}  GA {ok3}/{len(res)}  → {out}")
    return res


for d in sys.argv[1:]:
    suite(d)
