from typing import Literal
from pydantic import BaseModel, Field, PrivateAttr, model_validator

Provider = Literal['ollama', 'ollama-cli', 'codex', 'codex-ollama', 'anthropic', 'codex-session']

class AgentSpec(BaseModel):
    # Execution-only provider hint, never accepted from API data or persisted.
    _output_schema: dict | None = PrivateAttr(default=None)
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default='Worker', max_length=120)
    directive: str = Field(default='Complete the assigned task accurately. Provide a concise result.', max_length=16000)
    provider: Provider = 'ollama'
    model: str = Field(default='', max_length=160)
    server: str = ''
    tools: list[Literal['workspace_read', 'workspace_write', 'system_metrics', 'business_docs_read', 'qwen_canvas_read', 'qwen_canvas_write', 'qwen_outreach_draft']] = Field(default_factory=list, max_length=6)
    qwen_profile: Literal['', 'client_acquisitions', 'coder', 'communicator', 'planner', 'researcher', 'ui_designer'] = ''
    x: float = 450
    y: float = 200

    @model_validator(mode='after')
    def qwen_permissions(self):
        if self.qwen_profile and self.qwen_profile != 'coder' and 'workspace_write' in self.tools:
            raise ValueError('Only the QwenW coder may write generated code; canvas writes use the scoped adapter')
        if self.qwen_profile != 'client_acquisitions' and 'qwen_outreach_draft' in self.tools:
            raise ValueError('Outreach draft capability is reserved for client acquisitions')
        return self

class CanvasEdit(BaseModel):
    expected_revision: int = Field(ge=0)
    section: Literal['sales_insights', 'research_metrics', 'architectural_blueprint', 'design_tokens', 'engineering_manifest']
    value: dict

class RevisionCheck(BaseModel):
    expected_revision: int = Field(ge=0)

class Edge(BaseModel):
    source: str
    target: str

class GraphUpdate(BaseModel):
    edges: list[Edge] = Field(max_length=256)

class Goal(BaseModel):
    prompt: str = Field(min_length=1, max_length=32000)
    agent_id: str = 'gerald'

class PlanAssignment(BaseModel):
    model_config = {'extra': 'forbid', 'strict': True}
    agent_id: str = Field(min_length=1, max_length=160)
    task: str = Field(min_length=1, max_length=32000)

class MasterPlan(BaseModel):
    model_config = {'extra': 'forbid', 'strict': True}
    tasks: list[PlanAssignment] = Field(max_length=8)
    summary: str = Field(default='', max_length=16000)

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
