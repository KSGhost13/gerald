import asyncio
import contextlib
import time
import os
from contextlib import asynccontextmanager
from pathlib import Path
import psutil
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from .config import ROOT
from .core import Orchestrator
from .models import AgentSpec, GraphUpdate, Goal, Mode, Position
from .providers import discover

@asynccontextmanager
async def lifespan(app):
    app.state.core = Orchestrator()
    await app.state.core.start()
    yield
    await app.state.core.close()

app = FastAPI(title='G.E.R.A.L.D.', lifespan=lifespan)

def allowed_origin(origin):
    port = os.getenv('GERALD_PORT', '8765')
    return origin in (f'http://127.0.0.1:{port}', f'http://localhost:{port}', 'http://localhost:5173', 'http://127.0.0.1:5173')

@app.middleware('http')
async def local_only(request: Request, call_next):
    from fastapi.responses import JSONResponse
    host = request.url.hostname
    if host not in ('127.0.0.1', 'localhost', 'testserver', '::1'):
        return JSONResponse({'detail': 'Invalid Host'}, status_code=403)
    origin = request.headers.get('origin')
    if origin and not allowed_origin(origin):
        return JSONResponse({'detail': 'Origin rejected'}, status_code=403)
    return await call_next(request)

def core():
    return app.state.core

@app.exception_handler(ValueError)
async def invalid(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail': str(exc)}, status_code=400)

@app.exception_handler(KeyError)
async def missing(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail': 'Agent not found'}, status_code=404)

@app.get('/api/health')
async def health():
    return {'status': 'online', 'name': 'G.E.R.A.L.D.'}

@app.get('/api/state')
async def state():
    return core().snapshot()

@app.get('/api/integrations')
async def integrations():
    return await discover()

@app.post('/api/agents')
async def create(spec: AgentSpec):
    return await core().create(spec)

@app.put('/api/agents/{ident}')
async def edit(ident: str, spec: AgentSpec):
    core().agents[ident].spec = spec
    core().persist()
    return core().agents[ident].view()

@app.patch('/api/agents/{ident}/position')
async def position(ident: str, pos: Position):
    core().agents[ident].spec.x, core().agents[ident].spec.y = pos.x, pos.y
    core().persist()
    return {'ok': True}

@app.post('/api/agents/{ident}/{action}')
async def control(ident: str, action: str):
    await core().control(ident, action)
    return {'ok': True}

@app.put('/api/graph')
async def graph(update: GraphUpdate):
    await core().route([e.model_dump() for e in update.edges])
    return {'edges': core().edges}

@app.post('/api/goals')
async def goal(body: Goal):
    return await core().submit(body.agent_id, body.prompt)

@app.put('/api/mode')
async def mode(body: Mode):
    core().mode = body.mode
    core().persist()
    await core().event('mode', f'{body.mode.upper()} execution enabled; applies to the next task')
    return {'mode': core().mode}

def telemetry():
    units = {}
    for ident, agent in core().agents.items():
        pid = agent.metrics.get('pid')
        if pid:
            try:
                p = psutil.Process(pid)
                units[ident] = {'pid': pid, 'ram_mb': round(p.memory_info().rss / 1048576, 1), 'cpu_seconds': sum(p.cpu_times()[:2])}
            except psutil.NoSuchProcess:
                continue
    return {'cpu': psutil.cpu_percent(), 'memory': psutil.virtual_memory().percent,
            'ram_gb': round(psutil.virtual_memory().used / 1073741824, 2), 'units': units, 'time': time.time()}

@app.websocket('/ws')
async def socket(ws: WebSocket):
    if not allowed_origin(ws.headers.get('origin', '')):
        await ws.close(code=1008)
        return
    await ws.accept()
    queue = asyncio.Queue(maxsize=256)
    core().clients.add(queue)
    last_snapshot = 0
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1)
                await ws.send_json(event)
            except TimeoutError:
                event = None
            if time.monotonic() - last_snapshot >= 1:
                await ws.send_json({'type': 'snapshot', 'state': core().snapshot(), 'telemetry': telemetry()})
                last_snapshot = time.monotonic()
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        core().clients.discard(queue)

dist = ROOT / 'frontend/dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='dashboard')
