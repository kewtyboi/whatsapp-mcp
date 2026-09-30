# Upstream Sync Log

Every sync with `verygoodplugins/whatsapp-mcp` (VGP), newest first. Procedure: [UPSTREAM-SYNC-SOP.md](./UPSTREAM-SYNC-SOP.md).

## 2026-09-30

- **VGP range:** `76d332b..8954045` (merge base from 2025-03 to upstream `main`, release 0.7.0)
- **Commits merged:** 175
- **Method:** merge commit on `sync/upstream-2026-09-30` (not a rebase; see the SOP for why). Fork `main` was `7fc8e85`.
- **Conflicts:** `.env.example`, `.github/dependabot.yml`, `.github/workflows/{ci,release-please,release,security}.yml`, `.gitignore`, `.release-please-manifest.json`, `CHANGELOG.md`, `CLAUDE.md`, `LICENSE`, `README.md`, `server.json`, `whatsapp-bridge/{go.mod,go.sum,main.go,main_test.go,webhook.go}`, `whatsapp-mcp-server/{main.py,pyproject.toml,uv.lock,whatsapp.py}`, `whatsapp-mcp-server/tests/{test_get_contact,test_whatsapp}.py`
- **Resolution:** upstream content everywhere (release-please, CI, CHANGELOG, manifest, go.mod and go.sum, webhook.go, uv.lock, `.env.example`) with fork identity kept (`LICENSE` credits both, `server.json` and `pyproject.toml` name, author and URLs, `README.md` credits, `CLAUDE.md`). `main.go`, `whatsapp.py`, `main.py` and the test files started from upstream with the fork patches re-applied.
- **VGP issues now merged upstream:** equivalents of the fork's `include_last_message` fix, `get_message_context` serialisation (VGP #73 first half), contact-chat de-duplication (VGP #74), loopback bind, bearer auth, path confinement for media, sent-message persistence; `/api/mark-read`, `/api/react`, quoted replies, mentions, on-demand history and call capture also arrived.
- **Local patches re-applied:** sent-message persistence (upstream's own copy kept, fork's structured `level=ERROR` logging added), VGP #73 NULL-safe row parsing and `context_to_dict`, VGP #74 regression tests, structured `/api/health` (upstream's `connected` and `timestamp` kept), graceful HTTP shutdown, `bridgeCtx`-threaded media downloads, interruptible reconnect backoff, `/api/revoke-message` and `/api/delete-chat` (behind upstream's `withAuth`) and the `revoke_message` / `delete_chat` MCP tools, MCP startup health gate (now sends the bridge bearer token), `include_last_message` regression tests.
- **Dropped or superseded:** fork `authMiddleware` and `sanitiseChatJID` (upstream's `withAuth` with Host allow-list and `mediaDownloadStorePaths` cover them, and their unit tests were removed with them); `/api/health` is no longer exempt from auth (upstream authenticates every route); webhook is now sent even if the message store fails (upstream's deliberate behaviour); upstream's `.github/CODEOWNERS` and `dependabot-auto-merge.yml` (they name upstream maintainers and call another organisation's reusable workflow) were not adopted.
- **PR:** pending (branch `sync/upstream-2026-09-30`)
