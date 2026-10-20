"""Interact with this chat's GERALD inbox without restarting its MCP tool inventory."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote
import httpx

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'bind', 'disconnect', 'inbox', 'claim', 'progress', 'respond'])
    parser.add_argument('request_id', nargs='?')
    parser.add_argument('--thread-id', default=os.getenv('CODEX_THREAD_ID', ''))
    parser.add_argument('--title', default='Current Codex chat')
    parser.add_argument('--automation-id', default='')
    parser.add_argument('--file', help='JSON payload file for progress/respond, or - for stdin')
    parser.add_argument('--url', default='http://127.0.0.1:' + os.getenv('GERALD_PORT', '8765'))
    args = parser.parse_args()
    body = None
    method, path = 'GET', '/session'
    if args.action == 'bind':
        if not args.thread_id:
            parser.error('--thread-id is required outside a Codex chat environment')
        method, body = 'PUT', {'thread_id': args.thread_id, 'title': args.title, 'automation_id': args.automation_id}
    elif args.action == 'disconnect':
        method = 'DELETE'
    elif args.action == 'inbox':
        if not args.thread_id:
            parser.error('--thread-id is required')
        path += '/inbox?thread_id=' + quote(args.thread_id, safe='')
    elif args.action in ('claim', 'progress', 'respond'):
        if not args.request_id or not args.thread_id:
            parser.error('request_id and --thread-id are required')
        method, path = 'POST', f'/session/requests/{quote(args.request_id, safe="")}/{args.action}'
        body = {'thread_id': args.thread_id}
        if args.action != 'claim':
            if not args.file:
                parser.error('--file is required for progress/respond; supply claim_token and the public message/response')
            raw = sys.stdin.read() if args.file == '-' else Path(args.file).read_text(encoding='utf-8-sig')
            body.update(json.loads(raw))
            body['thread_id'] = args.thread_id
    try:
        with httpx.Client(timeout=15, trust_env=False) as client:
            response = client.request(method, args.url + '/api' + path, json=body)
            data = response.json()
            print(json.dumps(data, ensure_ascii=True, indent=2))
            return 0 if response.is_success else 1
    except httpx.HTTPError as exc:
        print(json.dumps({'unavailable': True, 'message': str(exc)}))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
