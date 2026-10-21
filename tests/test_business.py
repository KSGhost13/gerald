import json
import pytest
from fastapi.testclient import TestClient
from gerald import business, storage
from gerald.main import app

@pytest.fixture
def desk(tmp_path, monkeypatch):
    (tmp_path / 'db').mkdir()
    monkeypatch.setattr(storage, 'DATA', tmp_path / 'db')
    root = tmp_path / 'business'
    root.mkdir()
    monkeypatch.setattr(business, 'BUSINESS_ROOT', root)
    return root

def configure(root, **extra):
    value = dict(name='Example Studio', markets=['Example region'], email='owner@example.com',
                 phase='Internal preparation', budget='$0 new spending', next_actions=['Review scope'])
    (root / 'desk.json').write_text(json.dumps({**value, **extra}), encoding='utf-8')

def test_unconfigured_and_private_field_filtering(desk):
    assert not business.launch_snapshot()['configured']
    configure(desk, password='must-not-be-returned')
    state = business.launch_snapshot()
    assert state['configured'] and state['email'] == 'owner@example.com'
    assert 'password' not in state
    assert 'cannot read or send' in state['mailbox_access']

@pytest.mark.parametrize('email', ['javascript:alert(1)', 'owner@example.com\r\nBcc:victim@example.com', 'not-an-email'])
def test_contact_rejects_unsafe_identity(desk, email):
    configure(desk, email=email)
    with pytest.raises(ValueError):
        business.launch_snapshot()

def test_document_allowlist_and_api_security(desk):
    configure(desk)
    (desk / 'START-HERE.md').write_text('Internal launch brief', encoding='utf-8')
    (desk / 'before-launch.json').write_text('private snapshot', encoding='utf-8')
    with TestClient(app) as client:
        state = client.get('/api/business').json()
        assert state['documents'] == ['START-HERE.md']
        response = client.get('/api/business/documents/START-HERE.md')
        assert response.text == 'Internal launch brief'
        assert response.headers['content-type'].startswith('text/plain')
        assert 'attachment' in response.headers['content-disposition']
        assert client.get('/api/business/documents/before-launch.json').status_code == 400
        assert client.post('/api/business', json={}).status_code == 405
        assert client.get('/api/business', headers={'Origin':'https://evil.example'}).status_code == 403
        assert client.get('/api/business', headers={'Host':'evil.example'}).status_code == 403

def test_oversized_configuration_is_rejected(desk):
    (desk / 'desk.json').write_text('x' * 24001, encoding='utf-8')
    with pytest.raises(ValueError, match='size limit'):
        business.launch_snapshot()
