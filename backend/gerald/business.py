"""Read-only launch desk. No OAuth tokens, email transport or signup automation."""
import json
from pydantic import BaseModel, Field
from .config import DATA
from .qwenw import safe_path

BUSINESS_ROOT = DATA / 'workspace' / 'business-launch'
DOCUMENTS = ('START-HERE.md', 'LAUNCH-PLAN.md', 'SERVICE-PLAYBOOK.md',
             'EMAIL-SETUP.md', 'TEMPLATES.md', 'SOURCES.md', 'prospects.csv', 'TEAM-RESULTS.md')

class LaunchDesk(BaseModel):
    name: str = Field(max_length=120)
    markets: list[str] = Field(max_length=8)
    email: str = Field(pattern=r'^[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', max_length=254)
    phase: str = Field(max_length=160)
    budget: str = Field(max_length=160)
    next_actions: list[str] = Field(max_length=12)

def launch_snapshot():
    path = safe_path(BUSINESS_ROOT, 'desk.json')
    if not path.is_file():
        return {'configured': False, 'documents': []}
    if path.stat().st_size > 24000:
        raise ValueError('Launch desk configuration exceeds its size limit')
    desk = LaunchDesk.model_validate(json.loads(path.read_text(encoding='utf-8')))
    return {'configured': True, **desk.model_dump(),
            'mailbox_access': 'Browser-assisted only; agents cannot read or send Gmail.',
            'support_status': 'No staffed 24/7 service or automated monitoring is active.',
            'documents': [name for name in DOCUMENTS if safe_path(BUSINESS_ROOT, name).is_file()]}

def document_path(name):
    if name not in DOCUMENTS:
        raise ValueError('Document is not in the launch desk allowlist')
    path = safe_path(BUSINESS_ROOT, name)
    if not path.is_file() or path.stat().st_size > 1048576:
        raise ValueError('Launch document unavailable')
    return path
