import json
import pytest
from gerald import providers


@pytest.mark.asyncio
async def test_discovery_exposes_safe_cli_auth_status_and_visible_cached_models(tmp_path, monkeypatch):
    (tmp_path / 'models_cache.json').write_text(json.dumps({'fetched_at': 'test', 'models': [
        {'slug': 'available-model', 'display_name': 'Available Model', 'visibility': 'list'},
        {'slug': 'hidden-model', 'visibility': 'hide'}]}), encoding='utf-8')
    monkeypatch.setenv('CODEX_HOME', str(tmp_path))
    monkeypatch.setattr(providers, 'OLLAMA_URLS', [])
    monkeypatch.setattr(providers.shutil, 'which', lambda _: 'fake')
    monkeypatch.setattr(providers, 'executable', lambda _: ['fake'])
    class Process:
        returncode = 0
        async def communicate(self):
            return b'', b'Logged in using ChatGPT'
    async def spawn(*args, **kwargs):
        assert args == ('fake', 'login', 'status')
        return Process()
    monkeypatch.setattr(providers.asyncio, 'create_subprocess_exec', spawn)
    result = await providers.discover()
    assert result['codex_auth']['signed_in']
    assert result['codex_auth']['method'] == 'chatgpt'
    assert result['codex_models'] == [{'id': 'available-model', 'name': 'Available Model'}]
    assert 'auth.json' not in json.dumps(result)
