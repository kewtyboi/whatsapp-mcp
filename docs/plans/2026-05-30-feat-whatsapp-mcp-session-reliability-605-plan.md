# WhatsApp MCP Session Reliability — Implementation Plan

**Issue:** kewtyboi/whatsapp-mcp #605 (feeds into PointyTooling #448)
**Date:** 2026-05-30
**Scope:** STANDARD
**Branch:** `feat/mcp-session-reliability-605`

---

## Zero-Context Summary

The WhatsApp MCP server (`uv run main.py` in `whatsapp-mcp-server/`) is registered in
`~/.claude/settings.json` under `"whatsapp"`. Every Claude session spawns this process
via stdio. The bridge (`com.liam.whatsapp-bridge` launchd plist) runs the Go whatsmeow
binary at `localhost:8080`. When the bridge is down or not yet healthy at the moment
`main.py` starts, the MCP process starts anyway, registers all 13 tools, but every tool
call silently fails because `whatsapp.py` cannot reach `localhost:8080`. There is no
startup guard in `main.py`.

**Confirmed failure mode (b):** The bridge is not guaranteed to be running and healthy
when the MCP server starts. `main.py` has no bridge health check at startup.

The fix is a lightweight startup health-gate added to `main.py` (preferred, no
`settings.json` changes) that polls `GET localhost:8080/api/health` before accepting
tool calls, and exits with a clear error if the bridge is down.

---

## Sensitivity Notice

`~/.claude/settings.json` is global PROD config. A bad edit breaks MCP loading for
every session. **This plan avoids any `settings.json` change.** If a `settings.json`
edit ever becomes necessary, Task 6 is a DIRECTOR CHECKPOINT — do not execute
autonomously.

---

## Pre-conditions (verify before starting)

- Working directory: `/Users/liam/dev/whatsapp-mcp-605` (worktree of `feat/mcp-session-reliability-605`)
- Bridge source: `/Users/liam/dev/whatsapp-mcp/whatsapp-bridge/`
- MCP server source: `/Users/liam/dev/whatsapp-mcp-605/whatsapp-mcp-server/`
- Python venv: `/Users/liam/dev/whatsapp-mcp-605/whatsapp-mcp-server/.venv/`
- Bridge health endpoint: `GET localhost:8080/api/health`
- Reference doc: `~/.claude/docs/whatsapp-bridge.md`

---

## Team Structure

3+ tasks with inter-dependencies; single-agent sequential execution is appropriate.
No parallel swarm needed — tasks form a strict linear chain (diagnose → fix → verify).

| Role | Scope |
|------|-------|
| Implementation agent | Tasks 1–7 (full sequential execution) |
| DA reviewer | Challenger gate (after Task 7 draft) |

---

## Task Breakdown

### Task 1 — Diagnose and document the confirmed failure mode; post findings to PointyTooling #448

**Action:** Conduct a read-only audit of `main.py`, `settings.json`, the bridge launchd
plist, and the running process state. Confirm which of the four hypotheses (a–d) is the
real failure mode. Write the findings as a comment on PointyTooling #448
(`kewtyboi/PointyTooling`).

**What to check:**
- `~/.claude/settings.json` `"whatsapp"` block — confirm `command`, `args`, `type`
- `whatsapp-mcp-server/main.py` — confirm no startup bridge health check exists
- `launchctl list | grep whatsapp` — confirm `com.liam.whatsapp-bridge` launchd plist state
- `ps aux | grep -E 'whatsapp|main.py'` — process state at time of audit
- `python3 -c "import urllib.request; resp=urllib.request.urlopen('http://localhost:8080/api/health', timeout=5); print(resp.status)"` — bridge reachability
- `pyproject.toml` in `whatsapp-mcp-server/` — confirm dependency pin state

**Finding to record:**
Failure mode (b) confirmed: `main.py` has no startup bridge guard. The MCP process starts
and registers tools regardless of bridge state. Tools silently fail when the bridge is
unreachable. The `settings.json` config, `uv` resolver, and launchd plist are all
correctly configured.

**Acceptance criterion:** A comment is posted on PointyTooling #448 with: (1) the
confirmed failure mode letter + one-sentence description, (2) the evidence (process/plist
state), (3) the proposed fix (startup health gate in `main.py`).

**Validation command:**
```bash
gh issue view 448 --repo kewtyboi/PointyTooling --comments | tail -30
# Must show a new comment dated 2026-05-30 with the failure-mode finding.
```

**Dependencies:** None. First task.

---

### Task 2 — Add bridge startup health gate to `main.py`

**Action:** Edit `whatsapp-mcp-server/main.py` to add a startup bridge reachability
check that runs before `mcp.run()`. The check must:

1. Poll `GET localhost:8080/api/health` up to 3 times with a 5-second timeout per attempt,
   with 2-second waits between retries (total max 21s — acceptable for MCP startup).
2. Accept HTTP 200 as healthy.
3. On failure after all retries: print a human-readable error to stderr
   (`[whatsapp-mcp] ERROR: bridge not reachable at localhost:8080/api/health after 3 attempts — is com.liam.whatsapp-bridge running?`)
   and call `sys.exit(1)`.
4. On success: print a single info line to stderr
   (`[whatsapp-mcp] bridge healthy — starting MCP server`).
5. The health-check function must use only stdlib (`urllib.request`) — no new dependencies.
6. Insert the call in the `if __name__ == "__main__":` block, immediately before
   `mcp.run(transport="stdio")`.

**Do NOT touch `settings.json`.** Do NOT change the FastMCP tool registrations.

**Acceptance criterion:** After the edit, running:
```bash
cd /Users/liam/dev/whatsapp-mcp-605/whatsapp-mcp-server && \
  .venv/bin/python3 main.py 2>&1 &
PID=$!; sleep 2; kill $PID 2>/dev/null
# Must print "[whatsapp-mcp] bridge healthy — starting MCP server" (bridge is up)
# OR "[whatsapp-mcp] ERROR: bridge not reachable ..." (bridge is down)
# Must NOT hang indefinitely.
```

**Validation command:**
```bash
grep -n "bridge.*health\|localhost:8080\|sys.exit" \
  /Users/liam/dev/whatsapp-mcp-605/whatsapp-mcp-server/main.py
# Must show the health-check logic in the file.
```

**Dependencies:** Task 1 (confirms failure mode and scope).

---

### Task 3 — Audit and pin Python dependencies in `pyproject.toml`

**Action:** Read `whatsapp-mcp-server/pyproject.toml`. Check whether runtime dependencies
(`mcp`, `whatsapp-mcp-server` dependencies) have pinned versions (e.g. `mcp>=1.0,<2.0`)
or are unpinned (e.g. `mcp`). If any runtime dependency lacks a version constraint, pin
it to `>=<current-installed-version>,<next-major`. Use:
```bash
cd /Users/liam/dev/whatsapp-mcp-605/whatsapp-mcp-server && \
  .venv/bin/pip list --format=freeze | grep -E 'mcp|fastmcp|whatsapp'
```
to get current installed versions.

**Do not add new dependencies.** Only add version constraints to existing entries.

**Acceptance criterion:** Every runtime dependency in `pyproject.toml` has at minimum a
lower bound version constraint. `uv sync` or `uv run main.py` must still resolve cleanly
after the edit.

**Validation command:**
```bash
cd /Users/liam/dev/whatsapp-mcp-605/whatsapp-mcp-server && \
  uv run python3 -c "print('deps ok')" 2>&1
# Must print "deps ok" with no resolver errors.
```

**Dependencies:** Task 1 (establishes baseline; pin audit is independent of Task 2 but
must run in the same branch).

---

### Task 4 — Update `~/.claude/docs/whatsapp-bridge.md` to reflect the fixed reliable path

**Action:** Edit `~/.claude/docs/whatsapp-bridge.md` to:
1. Remove or update the line *"Direct SQLite query is the reliable path."* — once the
   startup health gate is in place, the MCP path is reliable.
2. Add a note under the MCP server section explaining the startup health check:
   *"The MCP server polls `GET localhost:8080/api/health` on startup (3 retries × 5s
   timeout). If the bridge is not reachable the process exits with an error rather than
   registering unresponsive tools."*
3. Add a troubleshooting note: *"If the MCP server exits at startup, check:
   `launchctl list | grep com.liam.whatsapp-bridge` — the bridge must be running and
   healthy before Claude Code starts."*

**SENSITIVITY:** `~/.claude/docs/whatsapp-bridge.md` is a global reference doc loaded by
all sessions. Only update what is listed above. Do not restructure the doc.

**Acceptance criterion:** The updated file no longer says "Direct SQLite query is the
reliable path" without qualification; the startup health-check behaviour is documented.

**Validation command:**
```bash
grep -n "reliable path\|health\|startup\|launchctl" \
  /Users/liam/.claude/docs/whatsapp-bridge.md
# Must show the new health-check note and the updated reliable-path statement.
```

**Dependencies:** Task 2 (the doc update must describe the actual implemented behaviour).

---

### Task 5 — Commit changes, push branch, open draft PR

**Action:** In the `feat/mcp-session-reliability-605` worktree:
1. Stage all changed files: `main.py`, `pyproject.toml` (if changed), this plan file.
2. Commit: `feat(mcp): add bridge startup health gate to prevent silent MCP failures (#605)`
3. Push: `git push -u origin feat/mcp-session-reliability-605`
4. Open a draft PR against `main` using:
   ```bash
   gh pr create \
     --repo kewtyboi/whatsapp-mcp \
     --title "feat(mcp): bridge startup health gate for session reliability (#605)" \
     --body "..." \
     --draft
   ```
   PR body must reference issue #605, describe the confirmed failure mode (b), list the
   three changed files, and include the validation commands from Tasks 2–3.

**Note:** `~/.claude/docs/whatsapp-bridge.md` is NOT committed to the whatsapp-mcp repo —
it is a global reference doc edited in place on the Mac. The doc update in Task 4 does
not belong in this PR.

**Acceptance criterion:** `git log origin/feat/mcp-session-reliability-605` shows the
commit; `gh pr view --repo kewtyboi/whatsapp-mcp` shows the draft PR.

**Validation command:**
```bash
gh pr list --repo kewtyboi/whatsapp-mcp --state open | grep mcp-session-reliability
# Must show the draft PR.
```

**Dependencies:** Tasks 2, 3 (all code changes must be committed before push).

---

### Task 6 — DIRECTOR CHECKPOINT: `settings.json` change decision

**STOP — this task requires director approval before execution.**

**Context:** The current `settings.json` `"whatsapp"` block launches `main.py` directly.
The startup health gate (Task 2) means that if the bridge is down, `main.py` exits with
code 1 and Claude Code will show a MCP server startup error. This is desirable (fail
visible > fail silent), but the director should confirm the behaviour is acceptable.

**Decision required:**
- Option A (default, recommended): Accept the new behaviour — `main.py` exits with a
  clear error if bridge is down. No `settings.json` change needed.
- Option B: Wrap `main.py` in a shell script that catches exit code 1 and logs rather
  than propagating the error, so Claude Code session start is not blocked by bridge
  state. Would require a `settings.json` change to point to the wrapper script.

**Do not make any `settings.json` change without explicit director approval.**

**Acceptance criterion:** Director responds with "A" or "B" (or equivalent).

**Dependencies:** Task 5 (director reviews the PR before this decision).

---

### Task 7 — Smoke test: verify 5/5 consecutive fresh session availability

**Action:** With the branch code deployed locally (copy `main.py` to the live MCP server
location or test from the worktree venv), perform 5 consecutive fresh Claude Code session
starts and call `list_chats` via the `whatsapp` MCP in each. Record the result. This test
requires a human operator (Liam) to start/restart Claude Code sessions — document the
procedure and expected output so Liam can perform it.

**Test procedure (for Liam to execute):**
1. Ensure bridge is running: `launchctl list | grep com.liam.whatsapp-bridge` — must show PID.
2. Restart Claude Code (quit + reopen).
3. In the new session, ask: "Using the whatsapp MCP tool, call list_chats and return the first chat name."
4. Record: PASS (tool returned data) or FAIL (error / no data).
5. Repeat steps 2–4 five times.

**Acceptance criterion:** 5/5 PASS. If any FAIL, record the error message and open a
follow-up issue before closing #605.

**Validation command:**
```bash
# After all 5 runs, record results in a comment on #605:
gh issue comment 605 --repo kewtyboi/whatsapp-mcp \
  --body "Smoke test results: 5/5 PASS — list_chats returned data in all 5 fresh sessions."
# (or document failures)
```

**Dependencies:** Task 6 (deployment decision confirmed), Task 4 (reference doc updated).

---

## Acceptance Criteria (issue-level)

| # | Criterion | Task |
|---|-----------|------|
| 1 | Root cause documented as comment on PointyTooling #448 | 1 |
| 2 | `main.py` polls `localhost:8080/api/health` on startup; exits with clear error if bridge down | 2 |
| 3 | No `settings.json` change made without director approval | 6 |
| 4 | Python dependencies have lower-bound version constraints in `pyproject.toml` | 3 |
| 5 | `~/.claude/docs/whatsapp-bridge.md` no longer directs agents to bypass MCP | 4 |
| 6 | Branch pushed and draft PR open on `kewtyboi/whatsapp-mcp` | 5 |
| 7 | `list_chats` returns results in 5/5 consecutive fresh Claude session starts | 7 |

---

## References

- Issue: `gh issue view 605 --repo kewtyboi/whatsapp-mcp`
- Feeds into: `gh issue view 448 --repo kewtyboi/PointyTooling`
- Design doc: `/Users/liam/dev/PointyTooling/.planning/2026-05-23-whatsapp-bridge-hardening-design.md` (sub-issue 7)
- Reference doc: `/Users/liam/.claude/docs/whatsapp-bridge.md`
- MCP server: `/Users/liam/dev/whatsapp-mcp/whatsapp-mcp-server/main.py`
- Bridge health: `GET localhost:8080/api/health`
- Settings: `/Users/liam/.claude/settings.json` (`"whatsapp"` key)
- Worktree: `/Users/liam/dev/whatsapp-mcp-605` (branch `feat/mcp-session-reliability-605`)
