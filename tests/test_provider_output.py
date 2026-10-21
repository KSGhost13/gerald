import json
import httpx
import pytest
from gerald import providers
from gerald.models import AgentSpec, MasterPlan

@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['plain', 'qwen', 'qwen_writer', 'master', 'business'])
async def test_ollama_uses_structured_output_only_for_required_contracts(monkeypatch, kind):
    spec = AgentSpec(name='Example', provider='ollama', model='installed-test-model',
                     qwen_profile='researcher' if kind.startswith('qwen') else '',
                     tools=['qwen_canvas_write'] if kind == 'qwen_writer' else ['business_docs_read'] if kind == 'business' else [])
    if kind == 'business':
        from gerald import business
        monkeypatch.setattr(business, 'agent_document_context', lambda spec, prompt: '\nCanonical document excerpt test marker')
    if kind == 'master':
        spec._output_schema = MasterPlan.model_json_schema()
    requests = []
    def transport(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, text=json.dumps({'message': {'content': 'public answer'}, 'done': True, 'eval_count': 2, 'eval_duration': 1000000000})+'\n')
    original = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    monkeypatch.setattr(providers, 'OLLAMA_URLS', ['http://127.0.0.1:11434'])
    emitted = []
    async def emit(value):
        emitted.append(value)
    assert await providers.generate(spec, 'Test', emit, {}, 'local') == 'public answer'
    body = requests[0]
    assert ('Canonical document excerpt test marker' in body['messages'][0]['content']) == (kind == 'business')
    if kind == 'master':
        assert body['format'] == MasterPlan.model_json_schema()
    elif kind == 'qwen':
        assert body['format'] == providers.READ_ONLY_PROPOSAL
        assert body['format']['properties']['canvas']['additionalProperties'] is False
        assert body['format']['properties']['files']['maxItems'] == 0
    elif kind == 'qwen_writer':
        assert body['format'] == 'json'
    else:
        assert 'format' not in body
    assert emitted == ['public answer']
    assert '_output_schema' not in spec.model_dump()

def test_provider_hint_cannot_be_supplied_through_agent_json():
    spec = AgentSpec.model_validate({'name': 'Example', '_output_schema': {'malicious': 'ignored'}})
    assert spec._output_schema is None
