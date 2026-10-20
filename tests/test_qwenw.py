import asyncio
import hashlib
import json
import pytest
from fastapi.testclient import TestClient

from gerald import qwenw
from gerald.core import Orchestrator
from gerald.models import AgentSpec
from gerald.storage import Storage


@pytest.fixture
def pack_files(tmp_path, monkeypatch):
    pack = tmp_path / 'import'
    source = pack / 'source'
    (source / 'agents').mkdir(parents=True)
    records = []
    for profile in qwenw.PROFILES:
        path = source / 'agents' / (profile + '.md')
        path.write_text(f'# {profile}\nUse the shared canvas.', encoding='utf-8')
        records.append({'path': f'agents/{profile}.md', 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    # An engine that would fail if executed; import must treat it only as archived bytes.
    engine = source / 'main.py'
    engine.write_text('raise RuntimeError("NEVER EXECUTE THE PROTOTYPE")', encoding='utf-8')
    records.append({'path': 'main.py', 'bytes': engine.stat().st_size, 'sha256': hashlib.sha256(engine.read_bytes()).hexdigest()})
    (pack / 'manifest.json').write_text(json.dumps({'files': records}), encoding='utf-8')
    monkeypatch.setattr(qwenw, 'PACK', pack)
    monkeypatch.setattr(qwenw, 'BUNDLED', tmp_path / 'unavailable-bundle')
    monkeypatch.setattr(qwenw, 'WORKSPACE', tmp_path / 'workspace')
    return pack


async def wait_job(job):
    async with asyncio.timeout(3):
        while job['pending']:
            await asyncio.sleep(.01)


@pytest.mark.asyncio
async def test_import_idempotent_preserves_graph_and_never_executes_legacy(pack_files):
    c = Orchestrator(Storage(':memory:'))
    try:
        old = await c.create(AgentSpec(name='Existing'))
        existing = list(c.edges)
        first = await c.qwenw.install()
        assert first['created'] == 6
        assert c.agents[old['id']].spec.name == 'Existing'
        assert all(edge in c.edges for edge in existing)
        assert (await c.qwenw.install())['created'] == 0
        assert len(c.agents) == 8
        assert len(c.qwenw.state['files']) == 7
        planner = c.agents[first['profiles']['planner']]
        assert 'workspace_write' not in planner.spec.tools
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_import_rejects_changed_hash_before_creating_any_agents(pack_files):
    (pack_files / 'source/agents/coder.md').write_text('changed')
    c = Orchestrator(Storage(':memory:'))
    try:
        with pytest.raises(ValueError, match='snapshot changed'):
            await c.qwenw.install()
        assert len(c.agents) == 1
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_bundled_profiles_install_on_clean_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(qwenw, 'PACK', tmp_path / 'no-local-snapshot')
    monkeypatch.setattr(qwenw, 'WORKSPACE', tmp_path / 'workspace')
    c = Orchestrator(Storage(':memory:'))
    try:
        result = await c.qwenw.install()
        assert result['created'] == 6
        assert len(result['files']) == 6
        assert all('Desktop' not in a.spec.directive for a in c.agents.values())
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_profile_writes_scoped_canvas_and_coder_gate_enforced_before_generation(pack_files):
    calls = []
    async def generate(spec, prompt, emit, metrics, mode):
        calls.append(spec.qwen_profile)
        assert 'GERALD QwenW adapter contract' in spec.directive
        return json.dumps({'answer': 'Plan ready', 'canvas': {'architectural_blueprint': {'summary': 'Reviewed plan', 'verified': True}}})
    c = Orchestrator(Storage(':memory:'), generate)
    await c.start()
    try:
        pack = await c.qwenw.install()
        job = await c.submit(pack['profiles']['coder'], 'implement')
        await wait_job(job)
        assert job['status'] == 'failed' and not calls
        job = await c.submit(pack['profiles']['planner'], 'plan')
        await wait_job(job)
        assert job['status'] == 'completed'
        assert c.qwenw.state['canvas']['architectural_blueprint']['summary'] == 'Reviewed plan'
        assert not c.qwenw.snapshot()['verified']  # Models cannot self-verify.
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_human_review_coder_artifacts_and_revision_invalidation(pack_files):
    c = Orchestrator(Storage(':memory:'))
    try:
        pack = await c.qwenw.install()
        await c.qwenw.edit('architectural_blueprint', {'plan': 'safe'}, 0)
        await c.qwenw.verify(1)
        coder = c.agents[pack['profiles']['coder']]
        _, digest = c.qwenw.prepare(coder, 'code')
        result = json.dumps({'answer': 'done', 'canvas': {'engineering_manifest': {'files': ['src/main.ts']}}, 'files': [{'path': 'src/main.ts', 'content': 'export const result = 1;'}]})
        assert 'Saved artifacts' in c.qwenw.accept(coder, result, 'job-123', digest)
        assert (qwenw.WORKSPACE / 'generated/job-123/src/main.ts').is_file()
        await c.qwenw.edit('design_tokens', {'color': 'teal'}, c.qwenw.state['revision'])
        assert not c.qwenw.snapshot()['verified']
        with pytest.raises(ValueError, match='changed during coding'):
            c.qwenw.accept(coder, result, 'job-456', digest)
        assert not (qwenw.WORKSPACE / 'generated/job-456').exists()
        with pytest.raises(ValueError, match='Canvas changed'):
            await c.qwenw.verify(0)
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_outreach_pending_approval_backup_and_no_send(pack_files):
    c = Orchestrator(Storage(':memory:'))
    try:
        pack = await c.qwenw.install()
        agent = c.agents[pack['profiles']['client_acquisitions']]
        result = json.dumps({'answer': 'Draft prepared', 'draft': {'to': 'example@example.test', 'subject': 'Hello', 'body': 'A review-only test draft.'}})
        assert 'No email sent' in c.qwenw.accept(agent, result, 'outreach', None)
        draft = c.qwenw.state['drafts'][0]
        assert draft['status'] == 'PENDING_HUMAN_APPROVAL'
        assert len(list((qwenw.WORKSPACE / 'outreach').glob('*.txt'))) == 1
        await c.qwenw.approve(draft['id'], 1)
        assert draft['status'] == 'APPROVED_FOR_MANUAL_USE'
        assert c.qwenw.state['canvas']['email_pipeline']['status'] == 'APPROVED_FOR_MANUAL_USE'
        with pytest.raises(ValueError, match='Potential secret'):
            c.qwenw.accept(agent, result.replace('A review-only test draft.', 'password=unshared-secret'), 'secret', None)
        assert len(c.qwenw.state['drafts']) == 1
    finally:
        await c.close()


@pytest.mark.parametrize('path', ['../escape.py', '/absolute.py', r'C:\escape.py', 'file:stream', 'NUL.txt', 'a/../../escape', ''])
def test_artifact_path_restrictions(tmp_path, path):
    with pytest.raises(ValueError):
        qwenw.safe_path(tmp_path, path)


@pytest.mark.asyncio
async def test_scope_and_malformed_proposals_never_modify_canvas(pack_files):
    c = Orchestrator(Storage(':memory:'))
    try:
        p = await c.qwenw.install()
        agent = c.agents[p['profiles']['researcher']]
        before = c.qwenw.snapshot()
        for value in ['plain text', '[]', json.dumps({'answer': 'bad', 'canvas': {'design_tokens': {}}}), json.dumps({'answer': 'bad', 'files': [{'path': 'a', 'content': 'b'}]})]:
            with pytest.raises(ValueError):
                c.qwenw.accept(agent, value, 'bad', None)
        assert c.qwenw.snapshot() == before
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_stale_model_write_cannot_overwrite_operator_canvas_edit(pack_files):
    c = Orchestrator(Storage(':memory:'))
    try:
        p = await c.qwenw.install()
        agent = c.agents[p['profiles']['planner']]
        _, token = c.qwenw.prepare(agent, 'plan')
        await c.qwenw.edit('architectural_blueprint', {'plan': 'operator revision'}, 0)
        proposal = json.dumps({'answer': 'stale', 'canvas': {'architectural_blueprint': {'plan': 'old model result'}}})
        with pytest.raises(ValueError, match='stale proposal'):
            c.qwenw.accept(agent, proposal, 'old', token)
        assert c.qwenw.state['canvas']['architectural_blueprint']['plan'] == 'operator revision'
    finally:
        await c.close()


def test_qwen_api_round_trip_and_profile_identity(tmp_path, monkeypatch, pack_files):
    from gerald import storage
    from gerald.main import app
    monkeypatch.setattr(storage, 'DATA', tmp_path)
    with TestClient(app) as client:
        installed = client.post('/api/packs/qwenw/install').json()
        assert len(installed['profiles']) == 6
        response = client.put('/api/packs/qwenw/canvas', json={'section': 'architectural_blueprint', 'value': {'plan': 'operator test'}, 'expected_revision': 0})
        assert response.status_code == 200
        assert client.post('/api/packs/qwenw/verify', json={'expected_revision': 1}).json()['verified']
        ident = installed['profiles']['planner']
        assert client.put(f'/api/agents/{ident}', json={'name': 'Cannot clear profile'}).status_code == 400
        assert client.get('/api/packs/qwenw', headers={'Origin': 'https://evil.test'}).status_code == 403


@pytest.mark.asyncio
async def test_pack_canvas_survives_restart(tmp_path, pack_files):
    db = tmp_path / 'pack.sqlite3'
    c = Orchestrator(Storage(db))
    await c.qwenw.install()
    await c.qwenw.edit('sales_insights', {'niche': 'local bakery'}, 0)
    await c.close()
    second = Orchestrator(Storage(db))
    try:
        assert second.qwenw.snapshot()['canvas']['sales_insights']['niche'] == 'local bakery'
        assert (await second.qwenw.install())['created'] == 0
    finally:
        await second.close()
