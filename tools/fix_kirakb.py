#!/usr/bin/env python3
import sys
p = "/var/minis/shared/gen3audit/repos/znq19_KiraKB_Plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
old = '"label": f"{info.provider_name} / {info.model_id}",'
new = '"label": f"{info.provider_name} / {getattr(info, \'model_name\', None) or info.model_id}",'
assert src.count(old) == 1, f"count={src.count(old)}"
src = src.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(src)
print("replaced OK")
