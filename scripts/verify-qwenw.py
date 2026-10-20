"""Live QwenW smoke test. Uses only supplied test data; restores model/mode/canvas."""
import asyncio
import json
from pathlib import Path
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]


async def main():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8765/api', timeout=20, trust_env=False) as client:
        async def request(method, path, body=None):
            response = await client.request(method, path, json=body)
            response.raise_for_status()
            return response.json()
        initial = await request('GET', '/state')
        pack = await request('GET', '/packs/qwenw')
        integrations = await request('GET', '/integrations')
        if not pack['installed'] or any(a['status'] in ('running', 'session_working') or a['queued'] for a in initial['agents']):
            raise RuntimeError('Install QwenW and let the dashboard become idle before verification')
        if not integrations['codex_auth']['signed_in'] or integrations['codex_auth']['method'] != 'chatgpt':
            raise RuntimeError('Codex CLI ChatGPT sign-in required for subscription smoke test')
        models = integrations['codex_models']
        if not models:
            raise RuntimeError('No cached Codex model catalogue; open Codex CLI once and retry')
        ident = pack['profiles']['communicator']
        original = next(a for a in initial['agents'] if a['id'] == ident)
        spec_keys = ('name', 'role', 'directive', 'provider', 'model', 'server', 'tools', 'qwen_profile', 'x', 'y')
        saved = {k: original[k] for k in spec_keys}
        reports = []
        try:
            for mode, provider, model in [('local', 'ollama', integrations['local_model']), ('cloud', 'codex', models[0]['id'])]:
                await request('PUT', f'/agents/{ident}', {**saved, 'provider': provider, 'model': model})
                await request('PUT', '/mode', {'mode': mode})
                prompt = 'Integration check only. Do not use tools, browse, poll or send messages. Return exactly this JSON object: {"answer":"QwenW adapter is ready.","canvas":{},"files":[],"draft":null}'
                job = await request('POST', '/goals', {'agent_id': ident, 'prompt': prompt})
                async with asyncio.timeout(190):
                    while True:
                        snapshot = await request('GET', '/state')
                        finished = next(j for j in snapshot['jobs'] if j['id'] == job['id'])
                        if finished['status'] in ('completed', 'failed'):
                            break
                        await asyncio.sleep(1)
                agent = next(a for a in snapshot['agents'] if a['id'] == ident)
                report = {'mode': mode, 'provider': provider, 'model': model, 'job_id': job['id'], 'status': finished['status'], 'effective_provider': agent['metrics'].get('effective_provider'), 'output': agent['output']}
                reports.append(report)
                print(json.dumps(report, indent=2), flush=True)
                if finished['status'] != 'completed' or agent['metrics'].get('effective_provider') != provider:
                    raise RuntimeError('Provider/adapter validation failed; inspect dashboard mission log')
            current_pack = await request('GET', '/packs/qwenw')
            assert current_pack['canvas'] == pack['canvas'], 'Test unexpectedly changed the shared canvas'
        finally:
            state = await request('GET', '/state')
            agent = next(a for a in state['agents'] if a['id'] == ident)
            if agent['status'] == 'running' or agent['queued']:
                await request('POST', f'/agents/{ident}/abort')
                await request('POST', f'/agents/{ident}/resume')
            await request('PUT', f'/agents/{ident}', saved)
            await request('PUT', '/mode', {'mode': initial['mode']})
            (ROOT / 'data/qwenw-verification.json').write_text(json.dumps({'checked_at': time.time(), 'reports': reports}, indent=2), encoding='utf-8')


asyncio.run(main())
