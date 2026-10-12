# znq19_KiraAI-openai-stream-compat
- 总级: NEEDS-FIX
- 版本: core_version >=2.29.7
- 规模: 1 py（577 行，自定义 Provider 桥：流式优先+信封兜底）
- 命中裁决:
  - [C] main.py:34-37 **裸导入** `from core.utils.model_clients import OpenAICompatibleLLMClient/TTSClient`（无 try 包裹）→ rc1 该模块已删除（迁至 core.provider.openai_compatible，核实 kira30 此文件在、三类客户端在 :41/:202/:244）→ **rc1 上插件直接 ModuleNotFoundError 无法加载**
  - [C] 覆写兼容性核实：子类覆写 chat(request,**kwargs)/chat_stream(request,**kwargs) 与 rc1 基类签名一致（:78/:130）；super().__init__(model) 一致（:42）；请求构建继承基类 _build_request_kwargs（rc1 内部已用 model_name 发上游）→ 只需修导入
  - [C] set_provider（main.py:570）rc1 provider_manager.py:752 在；register_provider_type :97 在；ModelInfo 字段（model_id/model_name/config）齐
  - [C] main.py:46 回退路径 core.provider.src.openai.model_clients（Image/Embedding 客户端）rc1 仍在 → SAFE
- 修复方案: 主导入改三代候选链：
  ```python
  try:    # 3.0+
      from core.provider.openai_compatible import OpenAICompatibleLLMClient, OpenAICompatibleTTSClient
      try: from core.provider.openai_compatible import OpenAICompatibleSTTClient
      except Exception: OpenAICompatibleSTTClient = None
  except ImportError:  # 2.x
      from core.utils.model_clients import OpenAICompatibleLLMClient, OpenAICompatibleTTSClient
      try: from core.utils.model_clients import OpenAICompatibleSTTClient
      except Exception: OpenAICompatibleSTTClient = None
  ```
  修后跑一遍流式/信封两条路径的冒烟（自有测试）。
- 备注: **本会话可直接修**（单点导入 + 回归冒烟）。
