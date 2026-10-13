import os, re, sys
root = sys.argv[1] if len(sys.argv) > 1 else '.'
pats = sys.argv[2:] or ['x']
rx = re.compile('|'.join(pats))
hits = 0
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in ('.git', '__pycache__', 'node_modules', 'venv')]
    for f in fn:
        if not f.endswith('.py'):
            continue
        p = os.path.join(dp, f)
        try:
            for i, line in enumerate(open(p, encoding='utf-8', errors='ignore'), 1):
                if rx.search(line):
                    print(f"{p}:{i}: {line.rstrip()[:190]}")
                    hits += 1
                    if hits > 120:
                        sys.exit(0)
        except Exception:
            pass
