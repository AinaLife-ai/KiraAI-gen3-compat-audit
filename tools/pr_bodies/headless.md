## 修复：3.0 下模型展示 UUID 乱码 + 视觉过滤失效（v2.2.2）

### 问题
3.0 起 `ModelInfo.model_id` 是内部稳定 ID（uuid 形态），可读名挪到 `model_name`。本插件五处把 `model_id` 直接展示给用户或用于判断：

1. `main.py` `api_models`（面板「VLM 模型」下拉数据源）：`name` 用 dict key → 面板下拉全是 uuid 乱码；
2. `_diag_vlm` 当前 VLM 展示（`mid = getattr(m, "model_id", "?")`）；
3. `_diag_vlm` 可选模型清单：展示 uuid，且**视觉过滤分组拿 uuid 去匹配 `embedding/tts/...` 标记 → 永不命中 → 所有 LLM 都被归到「可能支持视觉」**（分组完全失效）；
4. `_diag_vlm` 框架默认 VLM 展示；
5. `vlm.py` `is_vision_model`：同上，uuid 永不命中非视觉标记 → **宽松判断退化为恒真**（embedding/tts 模型也会被认为"支持视觉"）；另有两处日志打印 uuid。

### 修法（特征识别，不绑版本号）
- 展示与判断一律「`model_name` 优先、`model_id` 兜底」（`getattr(m, "model_name", None) or model_id`；2.x 无该属性自动回退，行为逐字不变）。
- **引用值不动**：`api_models` 的 `id` 仍是 `provider_id:model_id`（3.0 的规范引用值就是内部 ID）；诊断清单改为「可读名 + 可粘贴引用值」双栏式展示。
- 2.x 兼容已实测：`model_config.llm` 的 value 在 2.x 是配置 dict（无 `model_name` 键），有 `isinstance(entry, dict)` 守卫 + 回退，**不会把配置字典当模型名显示**。

### 变更面
- `main.py`：三处诊断输出 + `api_models`（+21/-6）
- `vlm.py`：`is_vision_model` 判断源 + 两处日志（+9/-3）
- `manifest.json`：version 2.2.1 → 2.2.2
- `README.md`：新增 v2.2.2 更新日志（含兼容性声明）

### 验证
- 两代桩解析验证：3.0 形态（uuid key + model_name entry）下拉显示 `gpt-4o (OpenAI)`、引用值保持 `pid:uuid`；2.x 形态输出与旧版逐字一致
- `regression/run_all.py`（`KIRA_FW_DIR` 指 2.x v2.34.8）：**全 PASS**；指向 3.0rc1 时 B0b/B1/B2/B7/A16 五条红——**对照实验（改动前 stash 复跑）确认这 5 条在未修改的上游代码上同样红**，属该套件行为探针对 3.0 框架目录的既有适配缺口，与本 PR 无关（本 PR 只动展示/判断，且 2.x 全套回归零回归）
- 双世代静态检查全绿
