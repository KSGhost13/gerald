import asyncio
import pytest
from fastapi.testclient import TestClient
from gerald.core import Orchestrator
from gerald.main import app
from gerald.models import AgentSpec, SessionBinding, SessionClaim, SessionProgress, SessionResponse
from gerald.storage import Storage

THREAD = 'test-current-chat'

async def bind(core):
    await core.session.bind(SessionBinding(thread_id=THREAD, title='Current session', automation_id='test-heartbeat'))

async def settle(job):
    async with asyncio.timeout(3):
        while job['pending']:
            await asyncio.sleep(.01)

@pytest.mark.asyncio
async def test_ui_goal_waits_for_this_session_without_model_generation():
    calls=[]
    async def generator(*args):
        calls.append(args)
        return 'must not generate'
    c=Orchestrator(Storage(':memory:'),generator)
    await c.start()
    try:
        await bind(c)
        job=await c.submit('gerald','Use our existing conversation context')
        await asyncio.sleep(.03)
        assert not calls
        assert job['status']=='awaiting_session'
        assert c.snapshot()['agents'][0]['status']=='awaiting_session'
        pending=c.session.inbox(THREAD)['pending'][0]
        assert 'claim_token' not in pending
        claim=await c.session.claim(pending['id'],SessionClaim(thread_id=THREAD))
        await c.session.progress(claim['id'],SessionProgress(thread_id=THREAD,claim_token=claim['claim_token'],message='Using this chat to compose the answer'))
        assert c.snapshot()['agents'][0]['status']=='session_working'
        await c.session.respond(claim['id'],SessionResponse(thread_id=THREAD,claim_token=claim['claim_token'],response='Answer from this existing chat.'))
        assert job['status']=='completed'
        assert job['pending']==0
        assert c.agents['gerald'].output=='Answer from this existing chat.'
        assert not calls
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_session_reply_routes_once_only_to_current_connected_workers():
    calls=[]
    async def generator(spec,prompt,*args):
        calls.append((spec.name,prompt))
        return 'worker result'
    c=Orchestrator(Storage(':memory:'),generator)
    await c.start()
    try:
        worker=await c.create(AgentSpec(name='ATLAS'))
        await bind(c)
        job=await c.submit('gerald','Plan this')
        claim=await c.session.claim(job['session_request_id'],SessionClaim(thread_id=THREAD))
        reply=SessionResponse(thread_id=THREAD,claim_token=claim['claim_token'],response='Delegating the analysis.',tasks=[{'agent_id':worker['id'],'task':'Analyze this goal'}])
        await c.session.respond(claim['id'],reply)
        await c.session.respond(claim['id'],reply)
        await settle(job)
        assert calls==[('ATLAS','Analyze this goal')]
        assert job['status']=='completed'
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_wrong_chat_stale_claim_and_invalid_graph_cannot_deliver():
    c=Orchestrator(Storage(':memory:'))
    await c.start()
    try:
        await bind(c)
        job=await c.submit('gerald','goal')
        ident=job['session_request_id']
        with pytest.raises(ValueError,match='different'):
            await c.session.claim(ident,SessionClaim(thread_id='some-other-chat'))
        claim=await c.session.claim(ident,SessionClaim(thread_id=THREAD))
        with pytest.raises(ValueError,match='already claimed'):
            await c.session.claim(ident,SessionClaim(thread_id=THREAD))
        with pytest.raises(ValueError,match='token mismatch'):
            await c.session.respond(ident,SessionResponse(thread_id=THREAD,claim_token='wrong',response='bad'))
        with pytest.raises(ValueError,match='currently connected'):
            await c.session.respond(ident,SessionResponse(thread_id=THREAD,claim_token=claim['claim_token'],response='bad',tasks=[{'agent_id':'missing','task':'bad'}]))
        assert job['pending']==1
        await c.control('gerald','abort')
        assert job['status']=='failed'
        assert c.session.get(ident)['status']=='cancelled'
        with pytest.raises(ValueError):
            await c.session.respond(ident,SessionResponse(thread_id=THREAD,claim_token=claim['claim_token'],response='late'))
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_pause_holds_inbox_and_disconnect_restores_model():
    c=Orchestrator(Storage(':memory:'))
    await c.start()
    original=c.agents['gerald'].spec.model_dump()
    try:
        await bind(c)
        await c.control('gerald','pause')
        job=await c.submit('gerald','wait for me')
        with pytest.raises(ValueError,match='paused'):
            await c.session.claim(job['session_request_id'],SessionClaim(thread_id=THREAD))
        await c.session.disconnect()
        assert c.agents['gerald'].spec.provider==original['provider']
        assert c.agents['gerald'].spec.model==original['model']
        assert job['status']=='failed'
        assert not c.session.binding
    finally:
        await c.close()

@pytest.mark.asyncio
async def test_restart_keeps_session_directive_and_invalidates_old_claim(tmp_path):
    path=tmp_path/'session.sqlite3'
    first=Orchestrator(Storage(path))
    await first.start()
    await bind(first)
    job=await first.submit('gerald','durable directive')
    old=await first.session.claim(job['session_request_id'],SessionClaim(thread_id=THREAD))
    await first.close()
    second=Orchestrator(Storage(path))
    await second.start()
    try:
        assert second.jobs[-1]['status']=='awaiting_session'
        assert second.session.get(old['id'])['status']=='pending'
        fresh=await second.session.claim(old['id'],SessionClaim(thread_id=THREAD))
        assert fresh['claim_token']!=old['claim_token']
        with pytest.raises(ValueError,match='mismatch'):
            await second.session.respond(old['id'],SessionResponse(thread_id=THREAD,claim_token=old['claim_token'],response='late'))
        await second.session.respond(fresh['id'],SessionResponse(thread_id=THREAD,claim_token=fresh['claim_token'],response='recovered'))
        assert second.jobs[-1]['status']=='completed'
    finally:
        await second.close()

def test_session_api_round_trip(tmp_path,monkeypatch):
    from gerald import storage
    monkeypatch.setattr(storage,'DATA',tmp_path)
    with TestClient(app) as client:
        assert client.put('/api/session',json={'thread_id':THREAD,'title':'Current chat'}).status_code==200
        mission=client.post('/api/goals',json={'prompt':'Say hello'}).json()
        claim=client.post(f'/api/session/requests/{mission["session_request_id"]}/claim',json={'thread_id':THREAD}).json()
        assert client.get('/api/state').json()['session']['binding']['thread_id']==THREAD
        result=client.post(f'/api/session/requests/{claim["id"]}/respond',json={'thread_id':THREAD,'claim_token':claim['claim_token'],'response':'Hello from this chat.'})
        assert result.status_code==200
        assert client.get('/api/state').json()['jobs'][-1]['status']=='completed'
        assert client.delete('/api/session').status_code==200
