from fastapi.testclient import TestClient
from gerald.main import app

def test_api_graph_worker_controls_and_websocket(tmp_path, monkeypatch):
    from gerald import storage
    monkeypatch.setattr(storage, 'DATA', tmp_path)
    with TestClient(app) as client:
        assert client.get('/api/health').status_code==200
        a=client.post('/api/agents',json={'name':'Test worker'}).json()
        assert client.put('/api/graph',json={'edges':[{'source':a['id'],'target':a['id']}]}).status_code==400
        for action in ['pause','resume','abort','resume']:
            assert client.post(f'/api/agents/{a["id"]}/{action}').status_code==200
        assert client.put('/api/mode',json={'mode':'cloud'}).json()['mode']=='cloud'
        assert client.patch(f'/api/agents/{a["id"]}/position',json={'x':12,'y':34}).status_code==200
        assert client.post('/api/goals',json={'prompt':'','agent_id':'gerald'}).status_code==422
        assert client.get('/api/state',headers={'Origin':'https://evil.example'}).status_code==403
        assert client.get('/api/state',headers={'Host':'evil.example'}).status_code==403
        with client.websocket_connect('/ws',headers={'Origin':'http://127.0.0.1:8765'}) as ws:
            assert ws.receive_json()['type']=='snapshot'
        assert client.post(f'/api/agents/{a["id"]}/delete').status_code==200
