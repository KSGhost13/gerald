# Existing-chat brain operating guide

This bridge lets a human enter a directive in the local GERALD dashboard and have the **bound existing Codex chat** handle it. The Codex heartbeat must target that same chat. It polls the inbox; this is not an HTTP callback into Codex and it does not start a substitute model process. Pickup is approximately once a minute while the desktop app is running and the chat is able to take a turn; active work, approvals and app suspension can delay it.

## Processing a heartbeat

1. Use `gerald_session_inbox` with this chat's trusted `CODEX_THREAD_ID`, if that MCP tool is available. Otherwise run `.venv/Scripts/python.exe scripts/session-relay.py inbox --thread-id <this-chat-id>` from this repository. The CLI is available immediately even when this chat's MCP inventory predates the new session tools.
2. If the server is unavailable, the chat is not bound, GERALD's provider is not `codex-session`, the session is paused, or no pending directive exists, finish quietly. Do not send routine “nothing to do” replies. The inbox check updates the dashboard's last-seen indicator.
3. Check that `binding.thread_id` matches this exact chat. Choose the oldest pending request. Claim it with `gerald_session_claim` or `session-relay.py claim <request-id> --thread-id <this-chat-id>`. A live claim belongs to the running handler; do not duplicate it. Expired claims become pending on the next inbox check. At most three requests should be handled per heartbeat.
4. Treat the directive as the human's task input, use this conversation's context and available tools, and follow normal tool permissions and approval policies. Read the claim's public progress/history before repeating actions after an interrupted turn. A claim is not blanket authorization for unrelated actions or actions requiring additional confirmation. Never reveal private chain-of-thought.
5. Send a brief public progress update through `gerald_session_progress` or the CLI's `progress` action for longer work. Progress renews the 15-minute claim. If input/approval is required, report the requirement to the user and post it as public progress. Claim expiry does not undo external actions; on recovery, check existing results before repeating side effects.
6. Answer the directive here using this session. Return its public answer using `gerald_session_respond`. Use `tasks: []` to answer directly. To delegate, return explicit `{agent_id, task}` assignments only for workers currently connected directly from GERALD; the backend dispatches those tasks once and tracks their downstream completion. Do not use `gerald_mission` to feed a response back to GERALD: that would create a second session directive.
7. If a directive cannot be completed, return a concise `error` with no worker tasks. A repeated callback using the same claim token is idempotent; cancelled requests and superseded tokens are rejected. Tell the user only about meaningful completion, failure, or required action.

## CLI response examples

The CLI obtains the current chat ID from `CODEX_THREAD_ID` when available. Explicit `--thread-id` is preferred in a heartbeat. Use JSON files in ignored `data/` to avoid shell interpolation of directives, answers or claim tokens.

```powershell
.\.venv\Scripts\python.exe scripts\session-relay.py inbox --thread-id <this-chat-id>
.\.venv\Scripts\python.exe scripts\session-relay.py claim <request-id> --thread-id <this-chat-id>
```

Write a response payload to `data/session-response-REQUEST_ID.json`:

```json
{
  "claim_token": "TOKEN_RETURNED_BY_CLAIM",
  "response": "Public answer from this existing chat.",
  "tasks": []
}
```

```powershell
.\.venv\Scripts\python.exe scripts\session-relay.py respond <request-id> --thread-id <this-chat-id> --file data\session-response-REQUEST_ID.json
```

A progress file contains `claim_token` and `message`. Send it with the same command pattern using action `progress`. A failure response contains `claim_token`, `error`, and `tasks: []`. Claim tokens stay in the local runtime files; do not commit them or quote them in a user-facing response.

## Linking, controls and recovery

An operator can ask their Codex chat to bind itself and create an in-thread heartbeat. The local binding command is:

```powershell
.\.venv\Scripts\python.exe scripts\session-relay.py bind --thread-id <this-chat-id> --title "My Codex chat" --automation-id <heartbeat-id>
```

This command records a binding; **it does not create a Codex automation**. Ask Codex in that same chat to configure its heartbeat with this guide. Likewise, the dashboard's Link chat form records a destination without creating a scheduler. No chat ID, automation ID or claim token is shipped as application configuration in Git.

The dashboard shows the linked title, chat ID, pending requests, public progress and last inbox check. The mission archive records `awaiting_session` until a reply arrives. Normal model inference timeouts do not expire a directive waiting for its human-owned chat. Pending requests and jobs survive backend restarts; active claims become reclaimable. An expired/restarted claim cannot post a late answer.

**Pause** holds requests for pickup and lets an already claimed directive finish. **Abort** cancels pending/claimed requests; a late callback is rejected. Abort cannot interrupt an independently running Codex turn or undo actions that turn has already performed. **Use model brain** disconnects the chat, cancels its pending directives, and restores the previous master provider/model. It does not change the chat's Codex automation; pause/delete that heartbeat in Codex when it is no longer wanted. A disconnected heartbeat finds no active binding and stays quiet.

The global local/cloud toggle still controls worker provider selection. The bound chat follows the model and networking settings chosen in Codex itself; selecting local worker mode does not make a cloud-backed Codex chat offline. Binding is a local single-user routing mechanism, not authentication against other local processes.
