#!/usr/bin/env python3
"""KSM main.py P1 专项：_wrap_update_memory 包装器双世代化（行切片）。"""
import ast
p = "/var/minis/shared/gen3audit/repos/znq19_KiraAI_session_merger_plugin/main.py"
src = open(p, encoding="utf-8", newline="").read()
CR = "\r\n" if "\r\n" in src else "\n"
lines = src.split(CR)

# 找 wrapped_update_memory 定义行 与 紧随的 `        wrapped_update_memory._merger_memory_wrapped` 标记行
start = next(i for i, l in enumerate(lines)
             if l.strip().startswith("def wrapped_update_memory(session, new_chunk"))
mark = next(i for i in range(start, len(lines))
            if lines[i].strip().startswith("wrapped_update_memory._merger_memory_wrapped"))
# 包装器函数体结束 = mark 行的上一行（空行）; 函数头行 = start
head = lines[start]
assert "def wrapped_update_memory" in head

new_block = [
    '        def _post_write(session):',
    '            try:',
    '                if plugin.enabled and plugin.group_queue and plugin.resolver:',
    '                    sid = str(session or "")',
    '                    gid = plugin.resolver.resolve_group_id(sid)',
    '                    if gid:',
    '                        # 调度异步 drain（钩子在真实落盘之后执行）',
    '                        try:',
    '                            loop = asyncio.get_running_loop()',
    '                            loop.create_task(',
    '                                plugin._on_group_memory_written(sid, gid)',
    '                            )',
    '                        except RuntimeError:',
    '                            pass',
    '            except Exception:',
    '                logger.exception("[MERGER queue] post update_memory hook failed")',
    '',
    '        import inspect as _inspect',
    '        if _inspect.iscoroutinefunction(orig):',
    '            # 3.0 起 update_memory 已异步化：包装器必须同为 async，',
    '            # 先 await 真实落盘，再触发组队列 drain。',
    '            async def wrapped_update_memory(session, new_chunk, *args, **kwargs):',
    '                result = orig(session, new_chunk, *args, **kwargs)',
    '                if _inspect.isawaitable(result):',
    '                    result = await result',
    '                _post_write(session)',
    '                return result',
    '        else:',
    '            # 2.x：同步实现保持同步包装（调用方不 await）',
    '            def wrapped_update_memory(session, new_chunk, *args, **kwargs):',
    '                result = orig(session, new_chunk, *args, **kwargs)',
    '                _post_write(session)',
    '                return result',
]
lines[start:mark] = new_block + [""]
src = CR.join(lines)
open(p, "w", encoding="utf-8", newline="").write(src)
ast.parse(src.replace("\r\n", "\n"))
print("P1 OK")
