# Upstream Sync SOP — kewtyboi/whatsapp-mcp

**Upstream:** `https://github.com/verygoodplugins/whatsapp-mcp` (VGP)
**Last reviewed:** 2026-05-24

---

## Why We Fork

This repo is a fork of VGP's whatsapp-mcp with the following local improvements:

- **Sent-message persistence** — outbound messages are stored so `is_from_me` is queryable
- **VGP #73 patch** — fixes a Pydantic crash on certain message types
- **VGP #74 patch** — deduplicates chat entries returned by list operations

These patches are not yet merged upstream. All three must survive every sync.

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

# 4. Rebase onto upstream/main
git rebase upstream/main

# 5. Resolve conflicts — see Conflict Resolution below

# 6. Run tests
cd whatsapp-mcp-server && python -m pytest -q

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
| `whatsapp-mcp-server/server.py` | sent-persistence code vs upstream changes | Keep both: apply upstream change first, then re-apply local block |
| `whatsapp-mcp-server/models.py` | VGP #73 Pydantic fix | Always keep our version; check if upstream merged an equivalent fix |
| `whatsapp-mcp-server/chats.py` | VGP #74 dedupe logic | Always keep our version unless upstream has a superior fix |

**Rule:** when in doubt, keep our local patch. Open a GitHub issue on VGP to track if they later merge an equivalent fix.

---

## Post-Sync Verification

After the rebase and before merging:

- [ ] `python -m pytest -q` — all tests pass
- [ ] Smoke-test: start the server locally and send a test message
- [ ] Confirm `is_from_me` is still queryable on sent messages
- [ ] Confirm chat list does not return duplicate entries
- [ ] Confirm the server starts without a Pydantic crash on startup

---

## Rollback

If the sync causes a regression after merging:

```bash
# Revert to last known-good SHA (from Pre-Sync Checklist step 1)
git checkout main
git reset --hard <fork-base-sha>
git push origin main --force-with-lease
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
- **Local patches re-applied:** #73, #74, sent-persistence (or note if any were dropped)
- **PR:** kewtyboi/whatsapp-mcp#N
```

---

## Tracked Upstream Issues

| Issue | Title | Action on close |
|---|---|---|
| VGP #89 | Group member enumeration | Sync immediately; check if our chats.py dedupe interacts |
| VGP #106 | Reaction message support | Sync immediately; verify sent-persistence still captures reactions |
| VGP #107 | Quoted reply threading | Sync immediately; verify Pydantic model handles new fields |
