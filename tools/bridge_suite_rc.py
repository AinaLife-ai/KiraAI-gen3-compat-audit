"""逐个跑 bridge 的套件，只报 rc≠0 的（runner 不打印是哪个失败）。"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path("/var/minis/shared/qqbot_fullmsg/tests")
src = (HERE / "run_tests.py").read_text(encoding="utf-8")
m = re.search(r"SUITES\s*=\s*\[(.*?)\]", src, re.S)
suites = re.findall(r'"([^"]+\.py)"|\'([^\']+\.py)\'', m.group(1))
suites = [a or b for a, b in suites]
print(f"套件数 {len(suites)}")
bad = []
for s in suites:
    r = subprocess.run([sys.executable, str(HERE / s)], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        bad.append((s, r.returncode))
        tail = (r.stdout or "")[-1500:] + (r.stderr or "")[-800:]
        print(f"\n★ rc={r.returncode}  {s}")
        for line in tail.splitlines():
            if re.search(r"(✗|FAIL|失败|不通过|Traceback|Error|assert)", line) and "INFO" not in line:
                print("   ", line[:170])
    else:
        print(f"  ok {s}")
print("\n失败套件：", bad or "无")
