#!/usr/bin/env python3
"""双世代兼容测试 CLI：
  python3 run.py --plugin /path/to/plugin [--fw2 PATH] [--fw3 PATH] [-k expr]
无 pytest 时自动降级为内置最小 runner。"""
import argparse, os, subprocess, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--fw2", default="/var/minis/shared/kira_fw")
    ap.add_argument("--fw3", default="/var/minis/shared/kira30")
    ap.add_argument("-k", default="")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    env = dict(os.environ, KIRA_PLUGIN_DIR=os.path.abspath(a.plugin),
               KIRA_FW2=a.fw2, KIRA_FW3=a.fw3)
    kit = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, "-m", "pytest", os.path.join(kit, "test_dualgen.py"),
           "-q", "--tb=short"] + (["-k", a.k] if a.k else []) + (["-v"] if a.v else [])
    try:
        import pytest  # noqa
    except ImportError:
        print("需要 pytest：apk add py3-pytest 或 pip install pytest", file=sys.stderr)
        return 2
    return subprocess.call(cmd, env=env, cwd=kit)

if __name__ == "__main__":
    sys.exit(main())
