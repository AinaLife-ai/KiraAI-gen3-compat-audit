# znq19_KiraAI_agnes_image_gen_plugin
- 总级: SAFE
- 版本: core_version >=2.6.1
- 规模: 1 py（Agnes 图片生成，约 1000+ 行）
- 命中裁决:
  - [H] main.py:311-339 **已显式做 2.x/3.0 双形态自拍参考图适配**：注释自述"3.0 已把 selfie 迁移到 persona 表"，代码先读 bot_config.selfie.path（2.x），再探测 persona_mgr.get_reference_image（3.0，rc1 persona_manager 有此异步接口）→ 作者已针对 3.0 适配，SAFE
  - [F] adapter_mgr.get_adapter 模式安全；A组"清空"为自有任务登记表注释——误报
- 备注: 本仓是"双世代特征识别"的正面教材。
