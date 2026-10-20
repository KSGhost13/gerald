from typing import Literal
from pydantic import BaseModel, Field

Provider = Literal['ollama', 'ollama-cli', 'codex', 'codex-ollama', 'anthropic']

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
