# Upstream Sync SOP - kewtyboi/whatsapp-mcp

**Upstream:** `https://github.com/verygoodplugins/whatsapp-mcp` (VGP)
**Last reviewed:** 2026-09-30

---

## Why We Fork

This repo is a fork of VGP's whatsapp-mcp with the following local improvements:

- **Sent-message persistence** - outbound messages are stored so `is_from_me` is queryable
- **VGP #73 patch** - type-safe `get_message_context` (NULL-safe rows, `context_to_dict`)
- **VGP #74 patch** - `get_contact_chats` returns one row per chat
- **Bridge hardening (fork PRs #14, #15)** - loopback-only bind, graceful shutdown, shutdown-aware media downloads, interruptible reconnect backoff (bearer auth, path confinement and media integrity are covered by upstream's own implementation)
- **Account maintenance (fork PR #16)** - `/api/revoke-message`, `/api/delete-chat` and the `revoke_message` / `delete_chat` MCP tools
- **Structured `/api/health` and send-failure logging** - plus the MCP startup health gate
- **`list_chats` / `get_chat` `include_last_message` fix (fork PR #13)**

These patches are not all merged upstream. Every one must survive every sync (or be noted in the log as superseded by an upstream equivalent).

---

## Sync Cadence

| Trigger | Action |
|---|---|
| Monthly (1st of each month) | Review VGP commits since last sync; sync if meaningful changes |
| VGP #89 closes | Sync immediately (group members feature) |
| VGP #106 closes | Sync immediately (reactions support) |
| VGP #107 closes | Sync immediately (quoted replies) |
| Security advisory | Sync same day |

---

## Pre-Sync Checklist

Before starting a sync:

- [ ] Record the current fork HEAD SHA: `git rev-parse HEAD`
- [ ] Record the upstream SHA to sync to: `git fetch upstream && git rev-parse upstream/main`
- [ ] List commits between fork base and upstream: `git log <fork-base>..upstream/main --oneline`
- [ ] Confirm no in-flight PRs on this repo that would conflict
- [ ] Note any new local patches added since the last sync

---

## Sync Procedure

```bash
# 1. Ensure upstream remote exists
git remote get-url upstream 2>/dev/null || \
  git remote add upstream https://github.com/verygoodplugins/whatsapp-mcp.git

# 2. Fetch upstream changes
git fetch upstream

# 3. Create a sync branch from main
git checkout main && git pull origin main
git checkout -b sync/upstream-$(date +%Y-%m-%d)

# 4. Merge upstream/main into the sync branch (merge commit, not a rebase)
git merge upstream/main --no-commit

# 5. Resolve conflicts, see Conflict Resolution below, then commit the merge
git commit

# 6. Run tests
(cd whatsapp-bridge && go build ./... && go vet ./... && go test ./...)
(cd whatsapp-mcp-server && uv sync --extra dev && uv run --extra dev pytest -q)

# 7. Push and open a PR
git push origin sync/upstream-$(date +%Y-%m-%d)
gh pr create --title "chore: upstream sync $(date +%Y-%m-%d)" \
  --body "Syncs with VGP upstream. Preserves local patches for #73, #74, sent-persistence."
```

---

## Conflict Resolution

Conflicts will almost always be in these files:

| File | Likely conflict | Resolution |
|---|---|---|
| `whatsapp-bridge/main.go` | sent-persistence, health, revoke/delete endpoints, shutdown handling vs upstream changes | Start from upstream, re-apply the fork patches (auth wrappers come from upstream's `withAuth`) |
| `whatsapp-mcp-server/whatsapp.py` | VGP #73 NULL-safe rows, `context_to_dict`, revoke/delete clients | Start from upstream, re-apply; send bridge auth headers on every bridge call |
| `whatsapp-mcp-server/main.py` | `get_message_context` wrapper, health gate, `revoke_message` / `delete_chat` tools | Start from upstream, re-apply |
| `whatsapp-mcp-server/tests/` | fork regression tests | Keep upstream's tests and append the fork's (adjusting fixtures to upstream's schema) |

**Merge, not rebase (executed 2026-09-30):** the first sync was executed as a merge. The fork's
~70 commits sit on a 2025-03 merge base (upstream's `lharries` history), so a rebase onto
`upstream/main` would have replayed every fork commit through ~24 add/add and content conflicts
and, because `main` is shared, would have required force-pushing `main`. A merge commit resolves
each conflicted file once, keeps fork history intact and needs no force-push. Always merge; never
rebase the fork onto upstream and never force-push `main`. The merge base is now the synced
upstream SHA, so later syncs should conflict far less.

**Files where both sides diverged heavily** (`whatsapp-bridge/main.go`, `whatsapp-mcp-server/whatsapp.py`,
`whatsapp-mcp-server/main.py`): start from the upstream version and re-apply the fork patches onto it,
rather than hand-merging hunks. Upstream may already carry an equivalent of a fork patch (auth, loopback
bind, `include_last_message`, `get_message_context` serialisation, contact-chat de-duplication); when it
does, adopt upstream's form and keep the fork's regression tests. Fork CI and identity files
(`LICENSE`, `server.json`, `pyproject.toml` author and URLs, `README.md` credits, `CLAUDE.md`) keep the
fork's identity with upstream's content.

**Rule:** when in doubt, keep our local patch. Open a GitHub issue on VGP to track if they later merge an equivalent fix.

---

## Post-Sync Verification

After the merge and before merging the sync PR:

- [ ] `go build ./... && go vet ./... && go test ./...` and `uv run --extra dev pytest -q` all pass
- [ ] Smoke-test: start the server locally and send a test message
- [ ] Confirm `is_from_me` is still queryable on sent messages
- [ ] Confirm chat list does not return duplicate entries
- [ ] Confirm the server starts without a Pydantic crash on startup

---

## Rollback

If the sync causes a regression after merging:

```bash
# Revert to last known-good SHA (from Pre-Sync Checklist step 1)
git checkout -b revert/upstream-sync-<date> main
git revert -m 1 <sync-merge-commit-sha>
git push origin revert/upstream-sync-<date>   # open a PR; never force-push main
```

Document the regression in `docs/UPSTREAM-SYNC-LOG.md` with the VGP commit range that caused it.

---

## Tracking

Log every sync in `docs/UPSTREAM-SYNC-LOG.md`:

```markdown
## YYYY-MM-DD

- **VGP range:** <base-sha>..<target-sha>
- **Commits merged:** N
- **Conflicts:** list files
- **VGP issues now merged upstream:** list
- **Local patches re-applied:** list each patch kept, and note any dropped or superseded by upstream
- **PR:** kewtyboi/whatsapp-mcp#N
```

---

## Tracked Upstream Issues

| Issue | Title | Action on close |
|---|---|---|
| VGP #89 | Group member enumeration | Sync immediately; check if our chats.py dedupe interacts |
| VGP #106 | Reaction message support | Sync immediately; verify sent-persistence still captures reactions |
| VGP #107 | Quoted reply threading | Sync immediately; verify Pydantic model handles new fields |
