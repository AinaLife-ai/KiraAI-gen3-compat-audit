# znq19_KiraAI_sysinfo_plugin
- 总级: SAFE
- 版本: manifest 1.0.0 / core_version 未声明
- 规模: 1 py（psutil 系统信息工具）
- 命中裁决: 预扫描 CLEAN。导入 core.plugin(BasePlugin/logger/register)+KiraMessageBatchEvent，rc1 均在（core/plugin/__init__.py:6 导出 register）。psutil 为外部依赖与框架无关。
- 备注: 建议补 core_version 声明。
