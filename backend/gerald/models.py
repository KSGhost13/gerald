from typing import Literal
from pydantic import BaseModel, Field

Provider = Literal['ollama', 'ollama-cli', 'codex', 'codex-ollama', 'anthropic', 'codex-session']

class AgentSpec(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default='Worker', max_length=120)
    directive: str = Field(default='Complete the assigned task accurately. Provide a concise result.', max_length=16000)
    provider: Provider = 'ollama'
    model: str = Field(default='', max_length=160)
    server: str = ''
    tools: list[Literal['workspace_read', 'workspace_write', 'system_metrics']] = Field(default_factory=list, max_length=3)
    x: float = 450
    y: float = 200

class Edge(BaseModel):
    source: str
    target: str

class GraphUpdate(BaseModel):
    edges: list[Edge] = Field(max_length=256)

class Goal(BaseModel):
    prompt: str = Field(min_length=1, max_length=32000)
    agent_id: str = 'gerald'

class Mode(BaseModel):
    mode: Literal['local', 'cloud']

class Position(BaseModel):
    x: float
    y: float

class SessionBinding(BaseModel):
    thread_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    automation_id: str = Field(default='', max_length=160)
    poll_seconds: int = Field(default=60, ge=30, le=3600)

class SessionClaim(BaseModel):
    thread_id: str = Field(min_length=1, max_length=160)

class SessionProgress(SessionClaim):
    claim_token: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=4000)

class SessionAssignment(BaseModel):
    agent_id: str
    task: str = Field(min_length=1, max_length=32000)

class SessionResponse(SessionClaim):
    claim_token: str = Field(min_length=1, max_length=160)
    response: str = Field(default='', max_length=262144)
    tasks: list[SessionAssignment] = Field(default_factory=list, max_length=8)
    error: str = Field(default='', max_length=4000)
