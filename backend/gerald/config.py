import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
OLLAMA_URLS = [u.rstrip('/') for u in os.getenv('GERALD_OLLAMA_URLS', 'http://127.0.0.1:11434').split(',') if u.strip()]
LOCAL_MODEL = os.getenv('GERALD_LOCAL_MODEL', 'ornith-1.5:9b')
CODEX_MODEL = os.getenv('GERALD_CODEX_MODEL', '')
CODEX_LOCAL_MODEL = os.getenv('GERALD_CODEX_LOCAL_MODEL', 'qwen2.5-coder:14b')
TIMEOUT = int(os.getenv('GERALD_TASK_TIMEOUT', '180'))
