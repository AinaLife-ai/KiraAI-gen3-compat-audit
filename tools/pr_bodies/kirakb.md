## 修复：3.0 下面板嵌入模型下拉显示 UUID 乱码（v1.1.5）

### 问题
`main.py` 的嵌入模型清单（面板「嵌入模型」下拉数据源）用 `info.model_id` 拼 label。
3.0 起 `ModelInfo.model_id` 是内部稳定 ID（uuid 形态，见 rc1 `core/provider/provider.py:51`），
可读名挪到 `model_name`。结果：3.0 上面板下拉全是 `provider / 3f2a9c…uuid` 乱码，用户无法辨认模型。
引用值 `uuid = provider_id:model_id` 字段本身在 3.0 语义正确（内部 ID 正是规范引用值），不受影响。

### 修法（1 行，特征识别不绑版本号）
`label` 改为 `getattr(info, 'model_name', None) or info.model_id`——3.0 显示可读名，2.x 无 `model_name` 属性自动回退旧行为。

### 变更面
- `main.py`：+1/-1
- `manifest.json`：version 1.1.4 → 1.1.5
- `README.md`：运行环境行补 3.0 全系列兼容说明

### 验证
- 仓内测试 `tests/run_tests.py`：42/42 通过
- 双世代静态检查全绿（两代框架导入核实 / 无已删符号 / 无版本号绑定）
