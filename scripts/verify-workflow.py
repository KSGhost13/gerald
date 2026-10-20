"""Provision useful starter workers and verify a complete local multi-agent mission."""
import asyncio
import json
from pathlib import Path
import httpx

async def main():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8765', timeout=10, trust_env=False) as c:
        async def call(method, path, body=None):
            r = await c.request(method, '/api' + path, json=body)
            r.raise_for_status()
            return r.json()
        state = await call('GET', '/state')
        atlas = next(a for a in state['agents'] if a['name'] == 'ATLAS')
        scribe = next((a for a in state['agents'] if a['name'] == 'SCRIBE'), None)
        if not scribe:
            scribe = await call('POST', '/agents', {'name':'SCRIBE','role':'Synthesis & delivery','provider':'ollama',
                'directive':'Summarize the provided analysis into a short final answer. Maximum 3 bullets.',
                'model':'ornith-1.5:9b','x':720,'y':300})
        await call('PATCH', f'/agents/{atlas["id"]}/position', {'x':400,'y':90})
        await call('PATCH', '/agents/gerald/position', {'x':40,'y':220})
        await call('PUT', '/graph', {'edges':[{'source':'gerald','target':atlas['id']},{'source':atlas['id'],'target':scribe['id']}]})
        job = await call('POST', '/goals', {'prompt':'Give a brief three-step checklist for planning a personal coding project. Keep the answer under 80 words.'})
        print('Submitted workflow mission ' + job['id'], flush=True)
        async with asyncio.timeout(180):
            while True:
                state = await call('GET', '/state')
                job = next(j for j in state['jobs'] if j['id'] == job['id'])
                if job['pending'] == 0:
                    break
                await asyncio.sleep(1)
        report = {'job':job, 'agents':[{'name':a['name'],'status':a['status'],'output':a['output'], 'metrics':a['metrics']} for a in state['agents']]}
        (Path(__file__).resolve().parents[1] / 'WORKFLOW-VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)
        assert job['status']=='completed', job
        assert next(a for a in state['agents'] if a['name']=='SCRIBE')['output'].strip()

asyncio.run(main())
