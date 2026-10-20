import asyncio
import json
import time
import uuid
from collections import deque
from .config import LOCAL_MODEL, TIMEOUT
from .models import AgentSpec
from .storage import Storage
from .providers import generate
from .session import SessionBrain

class BaseAgent:
    def __init__(self, ident, spec):
        self.id, self.spec = ident, spec
        self.status = 'idle'
        self.queue = asyncio.Queue(maxsize=16)
        self.gate = asyncio.Event()
        self.gate.set()
        self.task = None
        self.current = None
        self.metrics = {'tokens': 0, 'tps': 0, 'pid': None}
        self.output = ''

    def view(self):
        return {'id': self.id, **self.spec.model_dump(), 'status': self.status,
                'queued': self.queue.qsize(), 'metrics': self.metrics, 'output': self.output[-16000:]}

class Orchestrator:
    def __init__(self, storage=None, generator=generate):
        self.storage = storage or Storage()
        self.generate = generator
        self.mode = self.storage.get('mode', 'local')
        self.events = deque(self.storage.recent(), maxlen=300)
        self.clients = set()
        saved = self.storage.get('agents', {})
        if not saved:
            saved = {'gerald': AgentSpec(name='G.E.R.A.L.D.', role='Orchestrator', model=LOCAL_MODEL,
                directive='You are GERALD, a workflow orchestrator. Return only JSON with a tasks array. Each task has agent_id and task. Assign only to connected workers listed in the input. Split the goal into useful independent tasks. Maximum 8 tasks. Do not explain private reasoning.', x=80, y=170).model_dump()}
        self.agents = {k: BaseAgent(k, AgentSpec(**v)) for k, v in saved.items()}
        outputs = self.storage.get('outputs', {})
        for ident, agent in self.agents.items():
            agent.output = outputs.get(ident, '')
        self.edges = self.storage.get('edges', [])
        self.jobs = deque(self.storage.get('jobs', []), maxlen=100)
        for job in self.jobs:
            if job['status'] == 'running':
                job.update(status='interrupted', pending=0)
        self.watchdog = None
        self.session = SessionBrain(self)

    def persist(self):
        self.storage.set('agents', {k: a.spec.model_dump() for k, a in self.agents.items()})
        self.storage.set('edges', self.edges)
        self.storage.set('mode', self.mode)

    async def event(self, kind, message, agent_id='gerald', **extra):
        event = {'type': kind, 'message': message, 'agent_id': agent_id, 'time': time.time(), **extra}
        self.events.append(event)
        if kind != 'delta':
            self.storage.event(event)
        for queue in tuple(self.clients):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    def snapshot(self):
        agents = [a.view() for a in self.agents.values()]
        if self.session.binding and self.agents['gerald'].spec.provider == 'codex-session' and self.agents['gerald'].gate.is_set():
            master = next(a for a in agents if a['id'] == 'gerald')
            pending = self.session.snapshot()['pending']
            master['status'] = 'session_working' if any(r['status'] == 'claimed' for r in pending) else 'awaiting_session' if pending else 'idle'
            master['queued'] = len(pending)
            master['metrics']['effective_provider'] = 'codex-session'
        return {'mode': self.mode, 'agents': agents, 'edges': self.edges,
                'events': list(self.events)[-100:], 'jobs': list(self.jobs), 'session': self.session.snapshot()}

    async def start(self):
        for agent in self.agents.values():
            agent.task = asyncio.create_task(self.loop(agent))
        await self.event('system', 'Control plane online. Awaiting mission.')
        self.watchdog = asyncio.create_task(self.expire_queues())

    async def expire_queues(self):
        while True:
            await asyncio.sleep(1)
            for agent in list(self.agents.values()):
                for _ in range(agent.queue.qsize()):
                    item = agent.queue.get_nowait()
                    if time.time() - item['time'] > TIMEOUT:
                        item['job']['pending'] -= 1
                        item['job']['errors'] += 1
                        self.finish(item['job'])
                        await self.event('timeout', 'Queued task expired', agent.id)
                    else:
                        agent.queue.put_nowait(item)
                    agent.queue.task_done()

    async def close(self):
        if self.watchdog:
            self.watchdog.cancel()
            await asyncio.gather(self.watchdog, return_exceptions=True)
        for agent in self.agents.values():
            if agent.task:
                agent.task.cancel()
            if agent.current:
                agent.current.cancel()
        await asyncio.gather(*(a.task for a in self.agents.values() if a.task), return_exceptions=True)
        await asyncio.gather(*(a.current for a in self.agents.values() if a.current), return_exceptions=True)
        self.storage.set('jobs', list(self.jobs))
        self.storage.db.close()

    async def create(self, spec):
        if spec.provider == 'codex-session':
            raise ValueError('The current Codex session is reserved for the master GERALD agent')
        if len(self.agents) >= 24:
            raise ValueError('Maximum 24 agents')
        ident = uuid.uuid4().hex[:12]
        agent = self.agents[ident] = BaseAgent(ident, spec)
        agent.task = asyncio.create_task(self.loop(agent))
        self.edges.append({'source': 'gerald', 'target': ident})
        self.persist()
        await self.event('agent', f'Forged {spec.name}', ident)
        return agent.view()

    async def route(self, edges):
        pairs = {(e['source'], e['target']) for e in edges}
        for source, target in pairs:
            if source not in self.agents or target not in self.agents or source == target or target == 'gerald':
                raise ValueError('Routes require valid distinct agents and cannot target the orchestrator')
        visiting, done = set(), set()
        def visit(node):
            if node in visiting:
                raise ValueError('Cycle rejected: workflow routes must form a DAG')
            if node in done:
                return
            visiting.add(node)
            for source, target in pairs:
                if source == node:
                    visit(target)
            visiting.remove(node)
            done.add(node)
        for node in self.agents:
            visit(node)
        self.edges = [{'source': s, 'target': t} for s, t in sorted(pairs)]
        self.persist()
        await self.event('routing', f'Routing committed: {len(pairs)} connections')

    async def control(self, ident, action):
        agent = self.agents[ident]
        if action == 'pause':
            agent.gate.clear()
            agent.status = 'pausing' if agent.current else 'paused'
        elif action == 'resume':
            agent.gate.set()
            agent.status = 'running' if agent.current else 'idle'
        elif action == 'abort':
            agent.gate.clear()
            if ident == 'gerald':
                await self.session.cancel_all('Directive aborted from the dashboard')
            if agent.current:
                agent.current.cancel()
                await asyncio.gather(agent.current, return_exceptions=True)
            while not agent.queue.empty():
                item = agent.queue.get_nowait()
                item['job']['pending'] -= 1
                item['job']['errors'] += 1
                self.finish(item['job'])
                agent.queue.task_done()
            agent.status = 'aborted'
        elif action == 'delete':
            if ident == 'gerald':
                raise ValueError('The orchestrator cannot be deleted')
            await self.control(ident, 'abort')
            agent.task.cancel()
            await asyncio.gather(agent.task, return_exceptions=True)
            del self.agents[ident]
            self.edges = [e for e in self.edges if ident not in (e['source'], e['target'])]
        else:
            raise ValueError('Unknown control action')
        self.persist()
        await self.event('control', action.upper(), ident)

    def finish(self, job):
        if job['pending'] <= 0:
            job['status'] = 'failed' if job['errors'] else 'completed'
        self.storage.set('jobs', list(self.jobs))

    async def enqueue(self, ident, prompt, job, visited=()):
        agent = self.agents[ident]
        if agent.status == 'aborted':
            raise ValueError(f'{agent.spec.name} is aborted; resume it before submitting')
        if agent.queue.full():
            raise ValueError(f'{agent.spec.name} queue is full')
        agent.queue.put_nowait({'prompt': prompt, 'job': job, 'visited': visited, 'time': time.time()})
        job['pending'] += 1

    async def submit(self, ident, prompt):
        if ident not in self.agents:
            raise ValueError('Agent not found')
        job = {'id': uuid.uuid4().hex[:12], 'goal': prompt, 'status': 'running', 'pending': 0, 'errors': 0, 'time': time.time()}
        if ident == 'gerald' and self.agents[ident].spec.provider == 'codex-session':
            if self.agents[ident].status == 'aborted':
                raise ValueError('GERALD is aborted; resume before submitting a directive')
            self.session.add(prompt, job)
        else:
            await self.enqueue(ident, prompt, job)
        self.jobs.append(job)
        self.storage.set('jobs', list(self.jobs))
        await self.event('mission', prompt, ident, job_id=job['id'])
        if job['status'] == 'awaiting_session':
            await self.event('session', 'Directive queued for the linked Codex chat; awaiting heartbeat pickup', job_id=job['id'])
        return job

    async def loop(self, agent):
        while True:
            await agent.gate.wait()
            try:
                item = await asyncio.wait_for(agent.queue.get(), timeout=1)
            except TimeoutError:
                continue
            if not agent.gate.is_set():
                agent.queue.put_nowait(item)
                agent.queue.task_done()
                continue
            job = item['job']
            try:
                if time.time() - item['time'] > TIMEOUT:
                    raise TimeoutError('Queued task expired')
                agent.status, agent.output = 'running', ''
                agent.current = asyncio.create_task(self.execute(agent, item))
                await asyncio.wait_for(asyncio.shield(agent.current), timeout=TIMEOUT)
            except asyncio.CancelledError:
                job['errors'] += 1
                if asyncio.current_task().cancelling():
                    raise
                await self.event('cancelled', 'Execution cancelled', agent.id)
            except Exception as exc:
                if agent.current and not agent.current.done():
                    agent.current.cancel()
                    await asyncio.gather(agent.current, return_exceptions=True)
                job['errors'] += 1
                agent.status = 'error'
                await self.event('error', str(exc)[:1000] or 'Execution timed out', agent.id)
            finally:
                agent.current = None
                if agent.status not in ('error', 'aborted'):
                    agent.status = 'idle' if agent.gate.is_set() else 'paused'
                job['pending'] -= 1
                self.finish(job)
                agent.queue.task_done()

    async def execute(self, agent, item):
        job, prompt = item['job'], item['prompt']
        targets = [e['target'] for e in self.edges if e['source'] == agent.id]
        if agent.id == 'gerald' and targets:
            prompt += '\nAvailable directly connected workers:\n' + json.dumps([
                {'agent_id': t, 'name': self.agents[t].spec.name, 'role': self.agents[t].spec.role} for t in targets])
        async def emit(text):
            agent.output = (agent.output + text)[-262144:]
            await self.event('delta', text, agent.id, job_id=job['id'])
        await self.event('execution', f'{agent.spec.name} started', agent.id, job_id=job['id'])
        try:
            result = await self.generate(agent.spec, prompt, emit, agent.metrics, self.mode)
        except (asyncio.CancelledError, TimeoutError):
            raise
        except Exception:
            if self.mode != 'cloud' or agent.spec.provider not in ('codex', 'anthropic'):
                raise
            await self.event('fallback', 'Cloud unavailable; switching this task to local Ollama', agent.id)
            local = agent.spec.model_copy(update={'provider': 'ollama', 'model': LOCAL_MODEL})
            agent.output = ''
            result = await self.generate(local, prompt, emit, agent.metrics, 'local')
        # Resolve destinations at completion so live edge changes affect in-flight work.
        targets = [e['target'] for e in self.edges if e['source'] == agent.id]
        assignments = [(target, result) for target in targets]
        if agent.id == 'gerald' and targets:
            try:
                plan = json.loads(result.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip())
                assignments = [(task['agent_id'], task['task']) for task in plan['tasks'][:8]
                               if task['agent_id'] in targets and isinstance(task['task'], str)]
                if not assignments:
                    raise ValueError('No valid assignments')
            except (ValueError, KeyError, TypeError):
                assignments = [(target, item['prompt']) for target in targets]
                await self.event('planning', 'Structured plan unavailable; dispatching goal to connected workers', agent.id)
        for target, task in assignments:
            if target in item['visited']:
                continue
            await self.enqueue(target, task, job, (*item['visited'], agent.id))
            await self.event('packet', f'Routed to {self.agents[target].spec.name}', agent.id, target=target, job_id=job['id'])
        await self.event('result', result, agent.id, job_id=job['id'])
        agent.output = result
        self.storage.set('outputs', {ident: unit.output for ident, unit in self.agents.items()})
