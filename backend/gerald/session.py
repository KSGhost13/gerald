"""Durable inbox for an existing Codex chat, independent from model subprocesses."""
import secrets
import time
import uuid

class SessionBrain:
    def __init__(self, core):
        self.core = core
        self.binding = core.storage.get('session_binding', None)
        self.requests = core.storage.get('session_requests', [])
        # A process restart cannot preserve an in-flight claim. Make it reclaimable.
        for request in self.requests:
            if request['status'] == 'claimed':
                request.update(status='pending', claim_token='', lease_until=0)
        self.save()

    def save(self):
        self.core.storage.set('session_binding', self.binding)
        self.core.storage.set('session_requests', self.requests)

    def view(self, request):
        return {key: value for key, value in request.items() if key != 'claim_token'}

    def snapshot(self):
        return {'binding': self.binding, 'pending': [self.view(r) for r in self.requests if r['status'] in ('pending', 'claimed')],
                'recent': [self.view(r) for r in self.requests[-10:]],
                'paused': not self.core.agents['gerald'].gate.is_set()}

    def job(self, request):
        return next((job for job in self.core.jobs if job['id'] == request['job_id']), None)

    async def bind(self, body):
        if self.binding and self.binding['thread_id'] != body.thread_id and self.snapshot()['pending']:
            raise ValueError('Finish or abort pending directives before binding another chat')
        previous = self.binding.get('previous') if self.binding else None
        agent = self.core.agents['gerald']
        if agent.current or not agent.queue.empty():
            raise ValueError('Finish or abort current model work before binding a Codex chat')
        if not previous:
            previous = {'provider': agent.spec.provider, 'model': agent.spec.model}
        previous.setdefault('directive', agent.spec.directive)
        self.binding = {**body.model_dump(), 'previous': previous, 'bound_at': time.time(), 'last_seen': None}
        agent.spec = agent.spec.model_copy(update={'provider': 'codex-session', 'model': '',
            'directive': 'Act as GERALD\'s main brain using this existing Codex chat and its context. Answer the human directive directly, or return explicit tasks for connected workers when useful. Publish only public answers and concise progress summaries.'})
        self.core.persist()
        self.save()
        await self.core.event('session', f"Main brain bound to Codex chat: {body.title}")
        return self.snapshot()

    async def disconnect(self):
        await self.cancel_all('Session disconnected')
        agent = self.core.agents['gerald']
        if self.binding:
            agent.spec = agent.spec.model_copy(update=self.binding['previous'])
        agent.metrics.pop('effective_provider', None)
        self.binding = None
        self.core.persist()
        self.save()
        await self.core.event('session', 'Session brain disconnected; previous model brain restored')
        return self.snapshot()

    def add(self, prompt, job):
        if not self.binding:
            raise ValueError('Bind a Codex chat before submitting session directives')
        if len(self.snapshot()['pending']) >= 16:
            raise ValueError('Session inbox is full (16 directives); finish or abort pending work')
        request = {'id': uuid.uuid4().hex[:16], 'job_id': job['id'], 'thread_id': self.binding['thread_id'],
                   'prompt': prompt, 'status': 'pending', 'created_at': time.time(), 'updated_at': time.time(),
                   'claim_token': '', 'lease_until': 0, 'progress': '', 'response': '', 'tasks': [], 'error': ''}
        # Keep all pending requests and at most 100 settled records.
        settled = [r for r in self.requests if r['status'] not in ('pending', 'claimed')][-99:]
        pending = [r for r in self.requests if r['status'] in ('pending', 'claimed')]
        self.requests = settled + pending + [request]
        job.update(status='awaiting_session', pending=1, session_request_id=request['id'])
        self.save()
        return request

    def get(self, ident):
        request = next((r for r in self.requests if r['id'] == ident), None)
        if request is None:
            raise KeyError(ident)
        return request

    def check_thread(self, thread_id):
        if not self.binding or self.binding['thread_id'] != thread_id:
            raise ValueError('This directive belongs to a different Codex chat')

    def inbox(self, thread_id):
        self.check_thread(thread_id)
        self.binding['last_seen'] = time.time()
        for request in self.requests:
            if request['status'] == 'claimed' and request['lease_until'] < time.time():
                request.update(status='pending', claim_token='', progress='Previous claim expired; ready for pickup')
        self.save()
        return self.snapshot()

    async def claim(self, ident, body):
        self.check_thread(body.thread_id)
        if not self.core.agents['gerald'].gate.is_set():
            raise ValueError('GERALD is paused; resume before processing directives')
        request = self.get(ident)
        if request['status'] == 'claimed' and request['lease_until'] >= time.time():
            raise ValueError('Directive already claimed; finish it or wait for its claim to expire')
        if request['status'] not in ('pending', 'claimed'):
            raise ValueError('Directive is no longer pending')
        request.update(status='claimed', claim_token=secrets.token_urlsafe(24), lease_until=time.time() + 900,
                       updated_at=time.time(), progress='Current Codex chat is processing this directive')
        self.binding['last_seen'] = time.time()
        self.save()
        await self.core.event('session', request['progress'], job_id=request['job_id'])
        workers = [{'id': a.id, **a.spec.model_dump(), 'status': a.status}
                   for a in self.core.agents.values() if a.id != 'gerald']
        return {**request, 'workers': workers, 'edges': self.core.edges,
                'directive': self.core.agents['gerald'].spec.directive}

    def owned(self, ident, body, allow_settled=False):
        self.check_thread(body.thread_id)
        request = self.get(ident)
        if not secrets.compare_digest(request['claim_token'], body.claim_token):
            raise ValueError('Claim token mismatch; a cancelled or expired claim cannot respond')
        if request['status'] != 'claimed' and not (allow_settled and request['status'] in ('responded', 'failed')):
            raise ValueError('Directive is not actively claimed')
        if request['status'] == 'claimed' and request['lease_until'] < time.time():
            raise ValueError('Claim expired; reclaim the directive before responding')
        return request

    async def progress(self, ident, body):
        request = self.owned(ident, body)
        request.update(progress=body.message, updated_at=time.time(), lease_until=time.time() + 900)
        self.save()
        self.core.agents['gerald'].output = body.message
        await self.core.event('session_progress', body.message, job_id=request['job_id'])
        return self.view(request)

    async def respond(self, ident, body):
        request = self.owned(ident, body, allow_settled=True)
        if request['status'] in ('responded', 'failed'):
            return self.view(request)  # Idempotent delivery: never dispatch assignments twice.
        if not body.error and not body.response.strip():
            raise ValueError('A public response is required')
        if body.error and body.tasks:
            raise ValueError('An error response cannot dispatch worker tasks')
        targets = {edge['target'] for edge in self.core.edges if edge['source'] == 'gerald'}
        counts = {}
        for task in body.tasks:
            if task.agent_id not in targets:
                raise ValueError('Assignments must target currently connected GERALD workers')
            agent = self.core.agents[task.agent_id]
            counts[task.agent_id] = counts.get(task.agent_id, 0) + 1
            if agent.status == 'aborted' or agent.queue.qsize() + counts[task.agent_id] > agent.queue.maxsize:
                raise ValueError('An assigned worker is aborted or its queue is full')
        job = self.job(request)
        if not job or job['status'] != 'awaiting_session':
            raise ValueError('Mission is no longer waiting for this session')
        # No await between validation and enqueue: other control requests cannot interleave.
        for task in body.tasks:
            await self.core.enqueue(task.agent_id, task.task, job, ('gerald',))
        request.update(status='failed' if body.error else 'responded', response=body.response,
                       tasks=[task.model_dump() for task in body.tasks], error=body.error, updated_at=time.time())
        job['pending'] -= 1
        job['errors'] += bool(body.error)
        job['status'] = 'running'
        self.core.finish(job)
        agent = self.core.agents['gerald']
        agent.output = body.error or body.response
        self.core.storage.set('outputs', {i: a.output for i, a in self.core.agents.items()})
        self.save()
        await self.core.event('error' if body.error else 'result', body.error or body.response, job_id=job['id'])
        for task in body.tasks:
            await self.core.event('packet', f'Codex session assigned {self.core.agents[task.agent_id].spec.name}',
                                  target=task.agent_id, job_id=job['id'])
        return self.view(request)

    async def cancel_all(self, reason):
        for request in self.requests:
            if request['status'] in ('pending', 'claimed'):
                request.update(status='cancelled', error=reason, claim_token='', updated_at=time.time())
                job = self.job(request)
                if job:
                    job['pending'] -= 1
                    job['errors'] += 1
                    self.core.finish(job)
        self.save()
