# znq19_KiraAI_ws_keepalive_plugin
- 总级: SAFE-NOTE
- 版本: core_version >=2.29.6
- 规模: 2 py（OneBot WS 保活调优）
- 命中裁决:
  - [I] main.py:225-270 猴子补丁 `core.adapter.src.qq.napcat_client.client.ws_compatible_connect` → rc1 该模块与函数**仍存在**（client.py:33），connect 调用点仍以 kwargs 传 ping/open_timeout（client.py:151）→ 补丁机制 rc1 有效
  - 优雅降级：导入失败/函数缺失只 return False 不崩溃（main.py:236-241）
- 备注: 依赖框架内部模块路径（非公开 API），属结构性耦合——本次 rc1 核实通过，但未来框架重构 napcat_client 时需复查。建议纳入"每次框架大版本必复查"清单。
