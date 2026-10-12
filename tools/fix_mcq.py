#!/usr/bin/env python3
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_model_config_query_plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
NL = "\r\n"
old = NL.join([
'    def _format_model_value(self, value: str) -> str:',
'        """\u683c\u5f0f\u5316\u6a21\u578b\u914d\u7f6e\u503c\uff0c\u5c06 provider_id \u66ff\u6362\u4e3a\u63d0\u4f9b\u5546\u540d\u79f0"""',
'        if not value or ":" not in value:',
'            return value',
'        provider_id, model_id = value.split(":", 1)',
'        if self.show_provider_name:',
'            provider_map = self._get_provider_name_map()',
'            provider_name = provider_map.get(provider_id, provider_id)',
'            return f"{provider_name}:{model_id}"',
'        else:',
'            # \u53ea\u663e\u793a\u6a21\u578b ID\uff0c\u5b8c\u5168\u9690\u85cf\u63d0\u4f9b\u5546',
'            return model_id',
])
new = NL.join([
'    def _format_model_value(self, value: str) -> str:',
'        """\u683c\u5f0f\u5316\u6a21\u578b\u914d\u7f6e\u503c\uff0c\u663e\u793a\u63d0\u4f9b\u5546\u540d\u79f0 + \u4eba\u7c7b\u53ef\u8bfb\u6a21\u578b\u540d\u3002',
'',
'        3.0 \u8d77\u5f15\u7528\u503c\u5192\u53f7\u540e\u662f\u5185\u90e8\u7a33\u5b9a ID\uff08uuid \u5f62\u6001\uff09\uff0c\u53ef\u8bfb\u540d\u5728 ModelInfo.model_name\uff1b',
'        2.x \u5192\u53f7\u540e\u672c\u5c31\u662f\u53ef\u8bfb\u540d\u3002\u7ecf provider_mgr.get_model_info \u89e3\u6790\uff08\u4e24\u4ee3\u7b7e\u540d\u4e00\u81f4\uff09\uff0c',
'        \u89e3\u6790\u5931\u8d25\u539f\u6837\u56de\u9000\uff0c\u7edd\u4e0d\u5f71\u54cd\u547d\u4ee4\u53ef\u7528\u6027\u3002"""',
'        if not value or ":" not in value:',
'            return value',
'        provider_id, model_id = value.split(":", 1)',
'        display = model_id',
'        try:',
'            pm = getattr(self.ctx, "provider_mgr", None)',
'            if pm is not None:',
'                info = pm.get_model_info(provider_id, model_id)',
'                if info is not None:',
'                    display = getattr(info, "model_name", None) or info.model_id',
'        except Exception:',
'            pass',
'        if self.show_provider_name:',
'            provider_map = self._get_provider_name_map()',
'            provider_name = provider_map.get(provider_id, provider_id)',
'            return f"{provider_name}:{display}"',
'        else:',
'            # \u53ea\u663e\u793a\u6a21\u578b\u540d\uff0c\u5b8c\u5168\u9690\u85cf\u63d0\u4f9b\u5546',
'            return display',
])
assert src.count(old) == 1, f"count={src.count(old)}"
open(p, "w", encoding="utf-8", newline="").write(src.replace(old, new))
print("replaced OK")
