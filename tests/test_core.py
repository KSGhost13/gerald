import asyncio
import json
import pytest
from gerald.core import Orchestrator
from gerald.models import AgentSpec
from gerald.storage import Storage

async def completed(job):
    async with asyncio.timeout(4):
        while job['pending']:
            await asyncio.sleep(.01)

@pytest.mark.asyncio
async def test_live_routing_changes_current_result_destination():
    entered, release = asyncio.Event(), asyncio.Event()
    async def generate(spec, prompt, emit, metrics, mode):
        if spec.name == 'Source':
            entered.set()
            await release.wait()
        await emit('answer')
        return 'answer'
    c = Orchestrator(Storage(':memory:'), generate)
    await c.start()
    try:
        a = await c.create(AgentSpec(name='Source'))
        b = await c.create(AgentSpec(name='Old'))
        d = await c.create(AgentSpec(name='New'))
        await c.route([{'source': a['id'], 'target': b['id']}])
        job = await c.submit(a['id'], 'goal')
        await entered.wait()
        await c.route([{'source': a['id'], 'target': d['id']}])
        release.set()
        await completed(job)
        assert c.agents[b['id']].output == ''
        assert c.agents[d['id']].output == 'answer'
        assert job['status'] == 'completed'
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_cycles_rejected_atomically():
    c = Orchestrator(Storage(':memory:'))
    try:
        a = await c.create(AgentSpec(name='A'))
        b = await c.create(AgentSpec(name='B'))
        before = list(c.edges)
        with pytest.raises(ValueError, match='Cycle'):
            await c.route([{'source':a['id'],'target':b['id']},{'source':b['id'],'target':a['id']}])
        assert c.edges == before
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_pause_resume_and_abort_cancels_current_and_queued_work():
    entered, cancelled = asyncio.Event(), asyncio.Event()
    async def generate(*args):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    c = Orchestrator(Storage(':memory:'), generate)
    await c.start()
    try:
        a = await c.create(AgentSpec(name='Slow'))
        await c.control(a['id'], 'pause')
        j1 = await c.submit(a['id'], 'one')
        await asyncio.sleep(.03)
        assert not entered.is_set()
        await c.control(a['id'], 'resume')
        await entered.wait()
        j2 = await c.submit(a['id'], 'two')
        await c.control(a['id'], 'abort')
        await completed(j1)
        await completed(j2)
        assert cancelled.is_set()
        assert j1['status'] == j2['status'] == 'failed'
        assert c.agents[a['id']].status == 'aborted'
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_orchestrator_dispatches_only_connected_worker():
    calls = []
    async def generate(spec,prompt,emit,metrics,mode):
        calls.append(spec.name)
        return json.dumps({'tasks':[{'agent_id': worker['id'], 'task':'write report'}]}) if spec.name=='G.E.R.A.L.D.' else 'report'
    c = Orchestrator(Storage(':memory:'), generate)
    await c.start()
    try:
        worker = await c.create(AgentSpec(name='Writer'))
        job = await c.submit('gerald', 'Make a report')
        await completed(job)
        assert calls == ['G.E.R.A.L.D.', 'Writer']
        assert c.agents[worker['id']].output == 'report'
        assert job['status'] == 'completed'
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_completed_mission_and_output_survive_restart(tmp_path):
    path=tmp_path / 'state.sqlite3'
    async def generate(*args):
        return 'persisted answer'
    first=Orchestrator(Storage(path),generate)
    await first.start()
    job=await first.submit('gerald','persist this mission')
    await completed(job)
    await first.close()
    second=Orchestrator(Storage(path),generate)
    try:
        assert second.agents['gerald'].output=='persisted answer'
        assert second.jobs[-1]['status']=='completed'
    finally:
        await second.close()

@pytest.mark.asyncio
async def test_cloud_failure_falls_back_to_local():
    calls=[]
    async def generate(spec,prompt,emit,metrics,mode):
        calls.append((spec.provider,mode))
        if spec.provider=='codex':
            raise RuntimeError('network unavailable')
        return 'local answer'
    c=Orchestrator(Storage(':memory:'),generate)
    c.mode='cloud'
    await c.start()
    try:
        a=await c.create(AgentSpec(name='Cloud',provider='codex'))
        job=await c.submit(a['id'],'hello')
        await completed(job)
        assert calls==[('codex','cloud'),('ollama','local')]
        assert job['status']=='completed'
    finally:
        await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['invalid_json', 'disconnected', 'duplicate', 'empty_task', 'wrong_type', 'too_many', 'paused', 'aborted', 'queue_full', 'summary'])
async def test_master_plans_fail_closed_without_partial_dispatch(kind):
    calls = []
    async def generate(spec, *args):
        calls.append(spec.name)
        if spec.name != 'G.E.R.A.L.D.':
            return 'unexpected'
        task = {'agent_id': worker['id'], 'task': 'prepare report'}
        plans = {
            'invalid_json': 'not json',
            'disconnected': {'tasks': [task, {'agent_id': 'unknown', 'task': 'bad'}]},
            'duplicate': {'tasks': [task, task]},
            'empty_task': {'tasks': [{**task, 'task': '   '}]},
            'wrong_type': {'tasks': [{**task, 'task': 42}]},
            'too_many': {'tasks': [task] * 9},
            'paused': {'tasks': [task, {'agent_id': blocked['id'], 'task': 'held'}]},
            'aborted': {'tasks': [task, {'agent_id': blocked['id'], 'task': 'held'}]},
            'queue_full': {'tasks': [task, {'agent_id': blocked['id'], 'task': 'held'}]},
            'summary': {'summary': 'Internal review complete; awaiting owner approval.', 'tasks': []},
        }
        result = plans[kind]
        return result if isinstance(result, str) else json.dumps(result)
    c = Orchestrator(Storage(':memory:'), generate)
    await c.start()
    try:
        worker = await c.create(AgentSpec(name='Writer'))
        blocked = await c.create(AgentSpec(name='Held'))
        if kind == 'paused':
            await c.control(blocked['id'], 'pause')
        if kind == 'aborted':
            await c.control(blocked['id'], 'abort')
        if kind == 'queue_full':
            # Keep the worker from consuming a synthetic full queue during preflight.
            c.agents[blocked['id']].task.cancel()
            await asyncio.gather(c.agents[blocked['id']].task, return_exceptions=True)
            for _ in range(16):
                c.agents[blocked['id']].queue.put_nowait({})
        job = await c.submit('gerald', 'Plan, not uncontrolled fan-out')
        await completed(job)
        assert calls == ['G.E.R.A.L.D.']
        assert c.agents[worker['id']].queue.empty()
        assert job['status'] == ('completed' if kind == 'summary' else 'failed')
    finally:
        await c.close()
