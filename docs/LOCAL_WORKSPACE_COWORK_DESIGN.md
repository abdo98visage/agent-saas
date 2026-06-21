# Local Workspace Cowork Design

Date: 2026-06-20

Goal:

Make AgentSaaS behave closer to Codex / Claude-style coworking without sending the full project to the platform server.

Core rule:

- Project files stay on the employee machine.
- The platform receives only limited context plus explicit tool/file-operation requests.
- File changes are applied locally by the desktop app after explicit user approval.

## Implementation status (2026-06-21)

Implemented in the current codebase:

- employee profile picker in desktop
- `user_message` with selected profile + bounded workspace metadata
- FastAPI cowork WebSocket loop for Hermes profiles
- Hermes `tool_request` -> desktop `tool_result` roundtrip
- Hermes `apply_request` -> approval -> desktop `apply_result` roundtrip
- local read/search/list/multi-read tools
- local create/update/rename/delete apply workflow with approval
- persistence of cowork events in `agent_run_events`

Still intentionally not exposed:

- arbitrary local shell execution
- unrestricted terminal access

This matches the intended safe rollout direction in this design.

## 1. Target user experience

Desired flow:

1. Employee opens a local project folder in the desktop app.
2. Employee sends a prompt.
3. Desktop sends:
   - user prompt
   - selected profile
   - limited project context
   - optional open file contents
4. FastAPI forwards the request to the selected Hermes profile.
5. Hermes can do one or more of:
   - answer normally
   - ask to read a file
   - ask to search files
   - propose file edits
   - propose file creates/deletes/renames
6. Desktop shows the proposed changes as diff/preview.
7. User approves or rejects.
8. Desktop applies approved changes locally.
9. Desktop reports the result back to the platform/Hermes.

This matches the correct cowork model:

- reasoning is remote
- workspace stays local
- execution on local files is gated by the user

## 2. What is wrong with the current model

Current behavior:

- Desktop scans local files and builds a text `project_context`
- FastAPI sends the prompt + context to Hermes
- Hermes returns a text response
- file editing is a separate local desktop feature, not part of the agent protocol

Current gaps:

- no profile picker in employee desktop flow
- no structured tool protocol between Hermes and desktop
- no local file-operation approval workflow driven by Hermes
- no patch/diff roundtrip
- no “read more files” loop after first prompt

## 3. Correct architecture

### 3.1 Responsibility split

Desktop app:

- owns local filesystem access
- scans workspace
- reads files
- writes files
- previews diffs
- asks user approval
- applies approved changes

FastAPI platform:

- authenticates employee
- resolves allowed Hermes profile
- stores sessions/messages/runs/events
- brokers agent <-> desktop tool messages
- enforces quotas, policy, audit

Hermes:

- reasons over prompt/context
- requests additional local tools through structured actions
- returns file edit proposals
- never directly touches employee filesystem

### 3.2 Security rule

Hermes must never receive unrestricted filesystem access on the server for employee local projects.

Instead:

- Hermes emits intent
- desktop executes locally
- desktop returns bounded results

## 4. Required protocol

Introduce a structured cowork protocol over WebSocket.

### 4.1 Client -> server events

`user_message`

```json
{
  "type": "user_message",
  "conversation_id": "optional",
  "profile_name": "Marketing",
  "content": "Refactor the auth flow",
  "workspace": {
    "root_name": "my-project",
    "selected_files": ["app/auth.py", "tests/test_auth.py"]
  },
  "project_context": "bounded snippets"
}
```

`tool_result`

```json
{
  "type": "tool_result",
  "request_id": "uuid",
  "tool": "read_file",
  "ok": true,
  "result": {
    "path": "app/auth.py",
    "content": "..."
  }
}
```

`apply_result`

```json
{
  "type": "apply_result",
  "request_id": "uuid",
  "ok": true,
  "result": {
    "changed_files": ["app/auth.py"],
    "summary": "Applied 1 file update"
  }
}
```

### 4.2 Server/Hermes -> client events

`assistant_chunk`

```json
{
  "type": "assistant_chunk",
  "content": "I inspected the auth flow..."
}
```

`tool_request`

```json
{
  "type": "tool_request",
  "request_id": "uuid",
  "tool": "read_file",
  "args": {
    "path": "app/auth.py"
  }
}
```

`apply_request`

```json
{
  "type": "apply_request",
  "request_id": "uuid",
  "mode": "patch",
  "changes": [
    {
      "path": "app/auth.py",
      "patch": "*** Begin Patch\n..."
    }
  ],
  "summary": "Refactor duplicated token parsing"
}
```

`approval_required`

```json
{
  "type": "approval_required",
  "request_id": "uuid",
  "title": "Apply proposed changes?",
  "summary": "1 file update, 12 lines changed"
}
```

`done`

```json
{
  "type": "done",
  "conversation_id": "uuid",
  "profile_name": "Marketing"
}
```

## 5. Tool model

Start with a small, explicit local tool set.

### Phase 1 tools

- `list_files`
- `search_files`
- `read_file`
- `read_multiple_files`
- `propose_patch`

### Phase 2 tools

- `create_file`
- `rename_file`
- `delete_file`
- `run_tests_local`

### Phase 3 tools

- `run_command_local`
- `open_terminal_task`

Do not expose arbitrary shell at first.

## 6. Approval model

### Safe by default

- Read-only tools can auto-run:
  - `list_files`
  - `search_files`
  - `read_file`
- Write tools always require approval:
  - patch apply
  - create/delete/rename
  - local commands

### Approval UI

For every write action show:

- affected files
- diff preview
- summary
- approve / reject

Optional later:

- “approve this change only”
- “approve all in this turn”
- “always allow read-only tools”

## 7. File change format

Preferred format:

- unified diff or `apply_patch`-style patch

Why:

- compact
- auditable
- easy to preview
- easy to reject

Avoid raw full-file replacement except as fallback.

## 8. Required backend changes

### 8.1 WebSocket API

Extend `app/api/websocket_chat.py` to support:

- `tool_request`
- `tool_result`
- `apply_request`
- `apply_result`
- approval loop

Current WebSocket only supports:

- start
- chunk
- done
- error

### 8.2 Agent runtime loop

Update agent runtime/orchestrator flow so Hermes can emit structured actions, not only plain text.

Required model:

1. user message enters backend
2. backend sends to Hermes
3. Hermes may return:
   - assistant text chunk
   - tool call request
4. backend forwards tool request to desktop
5. desktop executes locally
6. desktop returns tool result
7. backend feeds tool result back into Hermes
8. repeat until final answer or apply request

### 8.3 Persistence

Store in DB:

- tool requests
- tool results
- approvals
- file apply attempts
- file apply result

This should live in `agent_run_events`.

## 9. Required desktop changes

### 9.1 Profile picker

Employee desktop must allow choosing the assigned profile explicitly.

Current gap:

- profile selection is not exposed in the employee desktop flow

Need:

- fetch assigned profiles from API
- display picker
- include `profile_name` in chat requests

### 9.2 Tool execution engine

Add a local tool executor layer in desktop:

- validate requested path stays inside selected workspace
- execute read/search operations
- build diff preview for writes
- hold proposed changes until approval

### 9.3 Apply workflow

Desktop receives `apply_request`:

1. preview diffs
2. ask user approval
3. if approved:
   - apply patch locally
   - return `apply_result`
4. if rejected:
   - return rejection to backend/Hermes

## 10. Safety constraints

- all file paths must stay within selected workspace
- hidden secret patterns stay excluded unless user explicitly opens the file
- no arbitrary command execution in phase 1
- local execution events must be logged server-side
- max file size / context size limits remain enforced

## 11. Recommended rollout plan

### Phase 1

- add profile picker
- add local read/search tool protocol
- Hermes can ask for more files
- no writes yet

Success criteria:

- agent can iteratively inspect local project safely

### Phase 2

- add `apply_request` with patch preview
- add approve/reject flow
- add local patch apply

Success criteria:

- agent can propose and user can apply local file changes from chat

### Phase 3

- add multi-file edits
- add create/rename/delete file flows
- add better diff UX

### Phase 4

- optional local test execution
- optional guarded command execution

## 12. Final verdict

For a Codex/Claude-like cowork product, the correct design is:

- keep project files on the employee machine
- let Hermes reason remotely
- exchange structured tool requests/results
- apply file changes locally with explicit approval

This is the design AgentSaaS should converge toward.
