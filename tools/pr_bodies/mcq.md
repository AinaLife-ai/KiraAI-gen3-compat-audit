## 修复：3.0 下 `/模型` 输出 UUID 乱码（v1.0.1）

### 问题
`_format_model_value` 把 `default_llm` 等配置值（`provider_id:model_id`）的冒号后段**原样回显**。
3.0 起该值是内部稳定 ID（uuid 形态，rc1 `core/provider/model_identity.py`），可读名挪到 `ModelInfo.model_name`。
结果：3.0 上 `/模型` 命令与 `query_model_config` 工具输出全是 uuid 乱码——而这个插件的存在意义就是让用户看到模型名。

### 修法（特征识别，不绑版本号）
展示前经 `ctx.provider_mgr.get_model_info(provider_id, model_id)` 解析（两代签名一致，已核实
2.x `provider_manager.py:375` / rc1 `:393`）：命中则取 `getattr(info, "model_name", None) or info.model_id`；
任何异常/未命中原样回退旧行为。**2.x 上解析到的就是原名，输出逐字不变。**

### 变更面
- `main.py`：`_format_model_value` 改解析式展示（+14/-4）
- `manifest.json`：version 1.0.0 → 1.0.1
- `README.md`：补兼容性声明

### 验证
- 三代形态桩功能验证：3.0 形态显示可读名 ✓；2.x 形态输出不变 ✓；解析失败原样回退不崩 ✓
- 双世代静态检查全绿
