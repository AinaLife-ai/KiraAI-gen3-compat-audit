# znq19_KiraAI_forward_fix_plugin
- 总级: SAFE
- 版本: core_version >=2.33.1
- 规模: 7 py（修复 <forward> 合并转发）
- 命中裁决:
  - 机制：`@on.after_xml_parse`（main.py:158）拦截 + 自有 _send_forward(:242) 走 client send_action（send_group_forward_msg 等 OneBot 动作）→ rc1 after_xml_parse 钩子（decorators.py:186）、RootTagAction（core/tag/__init__.py:2）、QQ client send_action 全在 → SAFE
  - [E] send_xml_messages/_parse_xml_msg 命中全在 tests 与注释——生产不碰框架发送管线
  - [F] adapter_mgr.get_adapter + get_client 模式 rc1 保留
- 备注: 无。
