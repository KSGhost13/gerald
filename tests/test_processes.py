import asyncio
import sys
import psutil
import pytest
from gerald import providers
from gerald.models import AgentSpec

@pytest.mark.asyncio
async def test_abort_reaps_cli_and_its_child(tmp_path, monkeypatch):
    marker = tmp_path / 'child.txt'
    code = ('import subprocess,sys,time,pathlib; '
            'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(90)"]); '
            f'pathlib.Path({str(marker)!r}).write_text(str(child.pid)); time.sleep(90)')
    monkeypatch.setattr(providers, 'executable', lambda name: [sys.executable, '-c', code])
    metrics = {}
    async def emit(value):
        return None
    task = asyncio.create_task(providers.generate(AgentSpec(name='Process test', provider='ollama-cli'), 'test', emit, metrics, 'local'))
    async with asyncio.timeout(10):
        while not marker.exists():
            await asyncio.sleep(.02)
    parent, child = metrics['pid'], int(marker.read_text())
    task.cancel()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=10)
    assert not psutil.pid_exists(parent)
    assert not psutil.pid_exists(child)

@pytest.mark.asyncio
async def test_local_mode_rejects_remote_server(monkeypatch):
    monkeypatch.setattr(providers, 'OLLAMA_URLS', ['http://192.0.2.1:11434'])
    async def emit(value):
        return None
    with pytest.raises(ValueError, match='loopback'):
        await providers.generate(AgentSpec(name='Remote', server='http://192.0.2.1:11434'), 'test', emit, {}, 'local')
