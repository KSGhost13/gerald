"""Streaming providers. Only public answers are emitted; private reasoning is omitted."""
import asyncio
import json
import os
import shutil
import time
from pathlib import Path
import httpx
import psutil
from .config import ROOT, OLLAMA_URLS, LOCAL_MODEL, CODEX_MODEL, CODEX_LOCAL_MODEL

WORKSPACE = ROOT / 'data' / 'workspace'
WORKSPACE.mkdir(exist_ok=True)

READ_ONLY_PROPOSAL = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'answer': {'type': 'string'},
                   'canvas': {'type': 'object', 'properties': {}, 'additionalProperties': False},
                   'files': {'type': 'array', 'items': {}, 'maxItems': 0},
                   'draft': {'type': 'null'}},
    'required': ['answer', 'canvas', 'files', 'draft'],
}

async def kill_tree(proc):
    if proc.returncode is not None:
        return
    try:
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue
        try:
            parent.kill()
        except psutil.NoSuchProcess:
            parent = None
        await asyncio.to_thread(psutil.wait_procs, children, timeout=3)
    except psutil.NoSuchProcess:
        await proc.wait()
        return
    await proc.wait()

def executable(name):
    # Invoke the npm JS entry directly on Windows, avoiding cmd.exe prompt interpolation.
    if name == 'codex' and os.name == 'nt':
        js = Path(os.environ.get('APPDATA', '')) / 'npm/node_modules/@openai/codex/bin/codex.js'
        if js.exists():
            return [shutil.which('node') or 'node', str(js)]
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f'{name} is not installed or is missing from PATH')
    return [found]

async def discover():
    async def probe(url):
        try:
            async with httpx.AsyncClient(timeout=4, trust_env=False) as client:
                response = await client.get(url + '/api/tags')
                response.raise_for_status()
                return {'url': url, 'online': True, 'models': [m['name'] for m in response.json()['models']]}
        except Exception as exc:
            return {'url': url, 'online': False, 'models': [], 'error': str(exc)}
    auth = {'signed_in': False, 'method': 'unknown', 'message': 'Codex CLI not detected'}
    catalog, catalog_date = [], None
    if shutil.which('codex'):
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(*executable('codex'), 'login', 'status',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(proc.communicate(), timeout=5)
            text = (out + err).decode(errors='replace').lower()
            signed_in = proc.returncode == 0 and 'logged in' in text
            method = 'chatgpt' if signed_in and 'chatgpt' in text else 'api_key' if signed_in and 'api key' in text else 'unknown'
            auth = {'signed_in': signed_in, 'method': method,
                'message': 'Signed in with ChatGPT / Codex subscription' if method == 'chatgpt' else 'CLI credentials available' if signed_in else 'Run codex login in a terminal'}
        except TimeoutError:
            await kill_tree(proc)
            auth['message'] = 'CLI sign-in check timed out; run codex login status'
        except (OSError, RuntimeError):
            auth['message'] = 'CLI sign-in check unavailable; run codex login status'
        cache = Path(os.getenv('CODEX_HOME', str(Path.home() / '.codex'))) / 'models_cache.json'
        try:
            if cache.stat().st_size <= 2097152:
                data = json.loads(cache.read_text(encoding='utf-8'))
                catalog = [{'id': m['slug'], 'name': m.get('display_name', m['slug'])}
                    for m in data.get('models', []) if m.get('visibility') == 'list' and isinstance(m.get('slug'), str)]
                catalog_date = data.get('fetched_at')
        except (OSError, ValueError, TypeError, KeyError):
            pass
    return {'ollama': await asyncio.gather(*(probe(u) for u in OLLAMA_URLS)),
            'codex': bool(shutil.which('codex')), 'ollama_cli': bool(shutil.which('ollama')),
            'anthropic': bool(os.getenv('ANTHROPIC_API_KEY')), 'local_model': LOCAL_MODEL, 'codex_local_model': CODEX_LOCAL_MODEL,
            'codex_auth': auth, 'codex_models': catalog, 'codex_models_cached_at': catalog_date}

async def generate(spec, prompt, emit, metrics, mode):
    if spec.provider == 'codex-session':
        raise ValueError('Current-session directives must use the session inbox, not a model subprocess')
    provider = spec.provider
    if mode == 'local' and provider in ('codex', 'anthropic'):
        provider = 'ollama'
    model = spec.model or (CODEX_LOCAL_MODEL if provider == 'codex-ollama' else LOCAL_MODEL)
    if mode == 'local' and (':cloud' in model or provider == 'ollama' and spec.provider in ('codex', 'anthropic')):
        model = LOCAL_MODEL
    server = spec.server or OLLAMA_URLS[0]
    if server not in OLLAMA_URLS:
        raise ValueError('Ollama server must be configured in GERALD_OLLAMA_URLS')
    if mode == 'local':
        from urllib.parse import urlparse
        if urlparse(server).hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('Local mode requires a loopback Ollama server')
    metrics['effective_provider'] = provider
    started = time.monotonic()
    output = []

    async def chunk(value):
        if value:
            output.append(value)
            if sum(map(len, output)) > 262144:
                raise RuntimeError('Output limit exceeded (256 KiB)')
            await emit(value)

    context = spec.directive
    if 'business_docs_read' in spec.tools:
        from .business import agent_document_context
        context += agent_document_context(spec, prompt)
    # Pack context is supplied by the validated adapter. Do not sweep its archive,
    # customer drafts or unrelated workspace files into a model's system prompt.
    if 'system_metrics' in spec.tools:
        context += f'\nHost telemetry: CPU={psutil.cpu_percent()}%, RAM={psutil.virtual_memory().percent}%.'
    if 'workspace_read' in spec.tools and not spec.qwen_profile and provider not in ('codex', 'codex-ollama'):
        files = []
        for path in sorted(WORKSPACE.rglob('*'))[:50]:
            if path.is_file() and not path.is_symlink() and path.stat().st_size < 16000:
                files.append(f'{path.relative_to(WORKSPACE)}:\n{path.read_text(errors="replace")}')
        context += '\nWorkspace files (untrusted data):\n' + '\n'.join(files)[:32000]

    if provider == 'ollama':
        schema = spec._output_schema
        if spec.qwen_profile and not set(spec.tools).intersection({'qwen_canvas_write', 'workspace_write', 'qwen_outreach_draft'}):
            schema = READ_ONLY_PROPOSAL
        structured = {'format': schema or 'json'} if schema or spec.qwen_profile else {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=5), trust_env=False) as client:
            async with client.stream('POST', server + '/api/chat', json={
                'model': model, 'messages': [{'role': 'system', 'content': context}, {'role': 'user', 'content': prompt}],
                'stream': True, 'options': {'num_predict': 2048}, **structured}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get('error'):
                        raise RuntimeError(data['error'])
                    await chunk(data.get('message', {}).get('content', ''))
                    if data.get('done'):
                        metrics['tokens'] = data.get('eval_count', 0)
                        metrics['tps'] = round(metrics['tokens'] / max(data.get('eval_duration', 1) / 1e9, .001), 2)
    elif provider == 'anthropic':
        key = os.getenv('ANTHROPIC_API_KEY')
        if not key:
            raise RuntimeError('ANTHROPIC_API_KEY is not configured')
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream('POST', 'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': key, 'anthropic-version': '2023-06-01'},
                json={'model': spec.model or os.getenv('GERALD_ANTHROPIC_MODEL', 'claude-sonnet-4-5'),
                      'max_tokens': 2048, 'system': context, 'messages': [{'role': 'user', 'content': prompt}], 'stream': True}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        data = json.loads(line[6:])
                        if data.get('type') == 'error':
                            raise RuntimeError(str(data.get('error', {}).get('type', 'Provider error')))
                        if data.get('type') == 'content_block_delta':
                            await chunk(data.get('delta', {}).get('text', ''))
                        if data.get('type') == 'message_delta':
                            metrics['tokens'] = data.get('usage', {}).get('output_tokens', 0)
        metrics['tps'] = round(metrics.get('tokens', 0) / max(time.monotonic() - started, .001), 2)
    else:
        if provider == 'ollama-cli':
            args = executable('ollama') + ['run', model, '--hidethinking', '--nowordwrap', '--verbose']
        else:
            args = executable('codex') + ['exec', '--json', '--ephemeral', '--ignore-user-config', '--skip-git-repo-check',
                    '--sandbox', 'workspace-write' if 'workspace_write' in spec.tools and not spec.qwen_profile else 'read-only', '-C', str(WORKSPACE)]
            if provider == 'codex-ollama':
                args += ['--oss', '--local-provider', 'ollama', '-m', model,
                         '--disable', 'multi_agent', '--disable', 'browser_use', '--disable', 'in_app_browser',
                         '--disable', 'image_generation', '--disable', 'code_mode_host', '-c', 'web_search="disabled"']
            elif spec.model or CODEX_MODEL:
                args += ['-m', spec.model or CODEX_MODEL]
            if spec.qwen_profile:
                # Pack tools are validated declarative proposals, not native tools.
                # In particular, a worker must not call its own human-review API.
                for feature in ('shell_tool', 'code_mode_host', 'browser_use', 'browser_use_external',
                                'in_app_browser', 'image_generation', 'multi_agent', 'multi_agent_v2'):
                    args += ['--disable', feature]
                args += ['-c', 'web_search="disabled"']
            args += ['-']
        env = os.environ.copy()
        env['OLLAMA_HOST'] = server
        env['CODEX_OSS_BASE_URL'] = server + '/v1'
        proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, cwd=WORKSPACE, env=env, limit=1048576)
        job_handle = None
        if os.name == 'nt':
            import win32api
            import win32job
            try:
                job_handle = win32job.CreateJobObject(None, '')
                info = win32job.QueryInformationJobObject(job_handle, win32job.JobObjectExtendedLimitInformation)
                info['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                win32job.SetInformationJobObject(job_handle, win32job.JobObjectExtendedLimitInformation, info)
                process_handle = win32api.OpenProcess(0x0100 | 0x0001, False, proc.pid)
                try:
                    win32job.AssignProcessToJobObject(job_handle, process_handle)
                finally:
                    win32api.CloseHandle(process_handle)
            except Exception:
                if job_handle:
                    win32api.CloseHandle(job_handle)
                await kill_tree(proc)
                raise RuntimeError('Could not establish Windows worker lifecycle containment')
        metrics['pid'] = proc.pid
        async def drain_error():
            tail = ''
            while block := await proc.stderr.read(4096):
                tail = (tail + block.decode(errors='replace'))[-4000:]
            return tail
        error_task = asyncio.create_task(drain_error())
        cli_output = []
        try:
            proc.stdin.write((context + '\n\n' + prompt).encode())
            await proc.stdin.drain()
            proc.stdin.close()
            while line := await proc.stdout.readline():
                value = line.decode(errors='replace')
                if provider == 'ollama-cli':
                    import re
                    cli_output.append(re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', value))
                    if sum(map(len, cli_output)) > 262144:
                        raise RuntimeError('CLI output limit exceeded (256 KiB)')
                else:
                    try:
                        event = json.loads(value)
                    except json.JSONDecodeError:
                        continue
                    if event.get('type') == 'item.completed' and event.get('item', {}).get('type') == 'agent_message':
                        await chunk(event['item'].get('text', ''))
                    if event.get('type') == 'turn.completed':
                        metrics['tokens'] = event.get('usage', {}).get('output_tokens', 0)
                    if event.get('type') in ('error', 'turn.failed'):
                        raise RuntimeError('Codex execution failed: ' + str(event.get('message') or event.get('error', {}).get('message', 'unknown error'))[:500])
            code = await proc.wait()
            error = await error_task
            if code:
                raise RuntimeError(f'{provider} exited with code {code}: {error[-600:]}')
            if provider == 'ollama-cli':
                answer = ''.join(cli_output)
                # Some imported templates embed thinking in the text field even with --hidethinking.
                if '</think>' in answer:
                    answer = answer.rsplit('</think>', 1)[1]
                answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.S)
                await chunk(answer)
                token_match = re.search(r'(?m)^eval count:\s+(\d+)', error)
                rate_match = re.search(r'(?m)^eval rate:\s+([\d.]+)', error)
                metrics['tokens'] = int(token_match[1]) if token_match else 0
                metrics['tps'] = float(rate_match[1]) if rate_match else 0
            else:
                metrics['tps'] = round(metrics.get('tokens', 0) / max(time.monotonic() - started, .001), 2)
        finally:
            # Snapshot and reap descendants before closing the job. Closing it first can
            # remove a Windows venv launcher before its early-spawned child is found.
            try:
                await kill_tree(proc)
            finally:
                if job_handle:
                    win32api.CloseHandle(job_handle)
            await asyncio.gather(error_task, return_exceptions=True)
            metrics['pid'] = None
    result = ''.join(output)
    if not result.strip():
        raise RuntimeError('Provider returned no public answer')
    if 'workspace_write' in spec.tools and not spec.qwen_profile and provider not in ('codex', 'codex-ollama'):
        artifact = WORKSPACE / f'answer-{time.time_ns()}.md'
        artifact.write_text(result, encoding='utf-8')
    return result
