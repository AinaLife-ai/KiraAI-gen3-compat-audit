#!/usr/bin/env python3
"""全量终检：日志块存在性 / 顶端版本=manifest / 默认折叠（日志块内无 details open）"""
import os, re, json
B = "/var/minis/shared/chk/"
def strip_tags(s): return re.sub(r'<[^>]+>', '', s)
def blocks(t):
    out = []; i = 0
    while True:
        a = t.find('<details', i)
        if a < 0: break
        op = t[a:].startswith('<details open')
        j = t.find('>', a) + 1
        depth = 1
        while j < len(t) and depth:
            nd = t.find('<details', j); cd = t.find('</details>', j)
            if cd < 0: break
            if nd >= 0 and nd < cd: depth += 1; j = nd + 8
            else: depth -= 1; j = cd + 10
        out.append((t[a:j], op)); i = max(j, a + 1)
    return out
def find_changelog(t):
    for blk, op in blocks(t):
        m = re.search(r'<summary>(.*?)</summary>', blk, re.S)
        sm = strip_tags(m.group(1)) if m else ''
        if re.search(r'更新日志|Changelog|更新记录|版本历史|历史版本', sm, re.I):
            return blk, op
    # md 头形式
    m = re.search(r'^#{1,6}[^\n]*(更新日志|更新记录|Changelog|版本历史)[^\n]*\n(.*?)(?=^## |\Z)', t, re.M | re.S | re.I)
    if m:
        seg = m.group(0)
        return seg, ('<details open' in seg)
    return None, None
REPOS = ['KiraAI_fold_fan_formatter_plugin','KiraAI-subagent-plugin','KiraKB_Plugin',
 'KiraAI-openai-stream-compat','KiraAI_Group-Manager-Plugin','KiraAI_auto_delete_session_plugin',
 'KiraAI_daily_report_plugin','KiraAI_ops_plugin','KiraAI_session_merger_plugin',
 'Kira_headless_browser','kiraai-reboot-pulgin','KiraAI_model_config_query_plugin',
 'KiraAI_qzone_plugin','KiraAI_kira_wiki_plugin','KiraAI_hotnews_plugin']
for r in REPOS:
    d = B + r + "/"
    try:
        mv = str(json.load(open(d+'manifest.json')).get('plugin_version') or json.load(open(d+'manifest.json')).get('version'))
    except Exception: mv = '?'
    t = open(d+'README.md', encoding='utf-8').read()
    blk, op = find_changelog(t)
    # 非 README 的独立日志文件
    extra = [f for f in os.listdir(d) if re.search(r'changelog|更新记录|history', f, re.I) and f.endswith(('.md', '.txt'))]
    vers = re.findall(r'^#{2,4}\s*v?(\d+\.\d+(?:\.\d+)?)', blk, re.M)[:1] if blk else []
    extra_top = ''
    for f in extra:
        e = open(d+f, encoding='utf-8').read()
        v = re.findall(r'^#{1,4}\s*v?(\d+\.\d+(?:\.\d+)?)', e, re.M)[:1] or re.findall(r'v?(\d+\.\d+\.\d+)', e)[:1]
        extra_top = f'{f}:{v}'
    print(f'{r:38s} manifest={mv:8s} README日志块={"有" if blk else "无"} 顶端={vers} 默认折叠={"否!!" if op else "是"} 独立日志={extra_top}')
