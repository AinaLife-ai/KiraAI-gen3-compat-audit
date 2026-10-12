# znq19_KiraAI_typing_indicator_plugin
- 总级: SAFE
- 版本: manifest（未声明 core_version）
- 规模: 1 py（私聊"正在输入"状态）
- 命中裁决:
  - [F] main.py:56 adapter_mgr.get_adapter → rc1 AdapterManager.get_adapter 存在（adapter_registry.py:668）；随后 platform 判断 + adapter.get_client() → rc1 QQ 适配器 get_client() 返回 NapCatWebSocketClient（qq.py:167）
  - [F] main.py:74-76 `hasattr(client,'send_action')` 守卫 + `await client.send_action(...)` → rc1 napcat client.py:491 send_action 存在，且有守卫 → 安全
  - [G] on_llm_response 钩子两代一致
- 备注: get_client+send_action 模式 rc1 完整保留；hasattr 探测写法本身就是正确兼容范式。
