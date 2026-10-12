import os, urllib.request, urllib.parse, json, base64, time, re
H={'Authorization':'token '+os.environ['GH_TOKEN'],'User-Agent':'dbg'}
op=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7899'}))
def get(u):
    last=None
    for i in range(5):
        try: return json.load(op.open(urllib.request.Request(u,headers=H),timeout=25))
        except Exception as e: last=e; time.sleep(3)
    raise last
def content(repo,path,ref):
    d=get('https://api.github.com/repos/%s/contents/%s?ref=%s'%(repo,path,urllib.parse.quote(ref,safe='')))
    return base64.b64decode(d['content']).decode()
# (fork_repo, branch, manifest_version)
REPOS=[
 ('AinaLife-ai/KiraAI-openai-stream-compat','fix/rc1-import-chain-1.1.1','1.1.1'),
 ('AinaLife-ai/KiraAI_model_config_query_plugin','fix/rc1-model-name-1.0.1','1.0.1'),
 ('AinaLife-ai/KiraAI_qzone_plugin','fix/rc1-caps-async-1.4.11','1.4.11'),
 ('AinaLife-ai/kiraai-reboot-pulgin','fix/rc1-session-api-2.1.1','2.1.1'),
 ('AinaLife-ai/KiraAI_auto_delete_session_plugin','fix/rc1-session-api-2.1.5','2.1.5'),
 ('AinaLife-ai/KiraAI_session_merger_plugin','feat/rc1-mirror-cross-adapter-2.9.0','2.9.0'),
 ('AinaLife-ai/KiraAI_ops_plugin','fix/rc1-session-model-mgr-1.2.1','1.2.1'),
 ('AinaLife-ai/KiraAI_daily_report_plugin','fix/rc1-capability-send-1.3.1','1.3.1'),
 ('AinaLife-ai/Kira_headless_browser','fix/rc1-model-display-2.2.2','2.2.2'),
 ('AinaLife-ai/KiraAI_kira_wiki_plugin','main','1.0.1'),
 ('AinaLife-ai/KiraAI_hotnews_plugin','main','1.0.2'),
]
for repo,ref,ver in REPOS:
    try:
        rd=content(repo,'README.md',ref)
    except Exception as e:
        print(repo,'README读取失败',str(e)[:60]); continue
    has_md_hdr = bool(re.search(r'^##[^\n]*更新日志',rd,re.M))
    has_det = bool(re.search(r'<summary>[^<]*(?:更新日志|changelog)',rd,re.I)) or ('<b>更新日志</b>' in rd) or ('📜 更新日志' in rd)
    note=''
    top_ver=None
    if has_det or has_md_hdr:
        # 找更新日志块/段后的第一个 ### vX.Y.Z
        m=re.search(r'更新日志.{0,3000}?###\s*v?(\d+\.\d+\.\d+)',rd,re.S)
        if m: top_ver=m.group(1)
    print(f'{repo.split("/")[1][:40]:42s} manifest={ver:8s} md头={has_md_hdr!s:5s} details块={has_det!s:5s} 日志首版本={top_ver}')
print('DONE')
