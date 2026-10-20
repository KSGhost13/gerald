"""Exercise installed providers with a tiny prompt; writes a reviewable verification report."""
import asyncio
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from gerald.models import AgentSpec
from gerald.providers import generate, discover

async def main():
    report = {'integrations': await discover(), 'providers': {}}
    report_path = root / 'VERIFICATION.json'
    if report_path.exists():
        report['providers'] = json.loads(report_path.read_text(encoding='utf-8')).get('providers', {})
    for provider in (sys.argv[1:] or ['ollama', 'ollama-cli', 'codex-ollama', 'codex']):
        print(f'Verifying {provider}...', flush=True)
        metrics = {}
        async def emit(text):
            return None
        try:
            async with asyncio.timeout(150):
                result = await generate(AgentSpec(name='Verification', provider=provider,
                    directive='Reply with only GERALD_READY. Do not use tools. /no_think'),
                    'Reply GERALD_READY.', emit, metrics, 'cloud' if provider == 'codex' else 'local')
            report['providers'][provider] = {'ok': 'GERALD_READY' in result, 'output': result[:500], 'metrics': metrics}
        except Exception as exc:
            report['providers'][provider] = {'ok': False, 'error': str(exc) or type(exc).__name__}
        (root / 'VERIFICATION.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report['providers'][provider]), flush=True)

asyncio.run(main())
