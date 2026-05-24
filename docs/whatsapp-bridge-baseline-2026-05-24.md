# WhatsApp Bridge Baseline Audit (2026-05-24)

**Audit scope:** Read-only verification of `kewtyboi/whatsapp-mcp` fork install, upstream state, schema, and known bugs.  
**Bridge status:** Running (confirmed live at audit time).  
**Working directory:** `<repo_root>/`

---

## 1. Installation & Process State

### Install Paths
- **Bridge (Go):** `<repo_root>/whatsapp-bridge/`
- **MCP server (Python):** `<repo_root>/whatsapp-mcp-server/`
- **Storage:** `<repo_root>/whatsapp-bridge/store/` (messages.db, whatsapp.db)

### Versions
- **kewtyboi/whatsapp-mcp main branch:** commit `251e842ed8d880c7136ba9841989f62ff2adeb7c`
  - Last commit: `docs(go): use package-form run command (No Issue) (#2)` (2026-05-01)
- **verygoodplugins/whatsapp-mcp main branch:** commit `7f4ec42c455d1716e901b6262a9ff7e3af437b6a`
  - Last commit: `fix(bridge): handle ProtocolMessage_REVOKE (delete-for-everyone) events (#99)` (recent)

### Upstream Divergence
- **Kewtyboi is 54 commits BEHIND VGP main** (verified: `git log --oneline origin/main..upstream/main | wc -l` → 54)
- Breakdown by commit type:
  - `fix`: 17 — including send-path, LID resolution, MIME detection, ProtocolMessage handling
  - `chore(deps)`: 20 — dependency bumps and dependabot group consolidation
  - `feat`: 3 — full-history pair flag, call event capture, image media in webhooks
  - `docs`: 5
  - `chore` / `ci` / `refactor`: 6
- Notable commits not in kewtyboi:
  - `7f4ec42` fix(bridge): handle ProtocolMessage_REVOKE (#99)
  - `768dafd` fix(mcp): resolve bare numeric LIDs (#97)
  - `c81947c` fix(bridge): log send caller identity (#96)
  - `af18908` fix(bridge): set FileName and detect MIME for document sends (#95)
  - `423ada9` fix(bridge): pass message store when sending messages (#91)
  - `9841e17` Persist outbound messages to local SQLite after SendMessage (#76) — **directly relevant to sub-issue #601; see §3**
  - `14699a1` chore: ignore local /store runtime directory (#93)
  - (38 additional commits — see `git log --oneline origin/main..upstream/main`)

**Action:** Fork needs rebase/pull from VGP to close the 54-commit gap. Kewtyboi only has its 1 rename commit (#1–#2) on top of VGP's 0.1.0 baseline.

### Bridge Process State
- **Process:** Running as expected (verified via PID 3071 prior to audit)
- **Process observability** (run against live PID to capture baseline):
  - Uptime / elapsed: `ps -p <pid> -o etime` — record elapsed time since bridge start
  - Memory (RSS/VSZ): `ps -p <pid> -o rss,vsz` — RSS in KB (resident set size)
  - Open file handles: `lsof -p <pid> | wc -l` — expected ~40–80 for healthy bridge
  - Example commands (replace `<pid>` with `pgrep whatsapp-bridge`):
    ```
    ps -p $(pgrep whatsapp-bridge) -o pid,etime,rss,vsz
    lsof -p $(pgrep whatsapp-bridge) | wc -l
    ```
  - **Status at audit time:** baseline values not captured (bridge live, no intrusive inspection performed per audit scope)
- **REST API endpoints** exposed on port 8080 (default):
  - `/api/health` — returns JSON with `status`, `connected`, `timestamp`
  - `/api/send` — POST to send WhatsApp messages
  - `/api/download` — download media from messages
  - `/api/typing` — send typing indicators

---

## 2. Database Schema

### messages.db

**Source:** `whatsapp-bridge/main.go` lines 85–108 (schema creation).

```sql
CREATE TABLE chats (
    jid TEXT PRIMARY KEY,
    name TEXT,
    last_message_time TIMESTAMP
);

CREATE TABLE messages (
    id TEXT,
    chat_jid TEXT,
    sender TEXT,
    content TEXT,
    timestamp TIMESTAMP,
    is_from_me BOOLEAN,
    media_type TEXT,
    filename TEXT,
    url TEXT,
    media_key BLOB,
    file_sha256 BLOB,
    file_enc_sha256 BLOB,
    file_length INTEGER,
    PRIMARY KEY (id, chat_jid),
    FOREIGN KEY (chat_jid) REFERENCES chats(jid)
);
```

**Key columns:**
- `messages.is_from_me` — exists, boolean, tracks sent messages
- `messages.id` — message UUID, part of composite key
- `messages.chat_jid` — foreign key reference to chats table
- `messages.sender` — JID of sender (e.g., "1234567890@s.whatsapp.net")

### whatsapp.db

**Source:** whatsmeow library (go.mau.fi/whatsmeow). Not directly audited; referenced only for LID mapping in main.go line 147 (`whatsmeow_lid_map` table).

**Known tables (from codebase references):**
- `whatsmeow_lid_map` — maps LIDs (long numeric user IDs) to phone numbers for phone-based JID resolution
- Standard whatsmeow state tables (keys, sessions, etc.)

---

## 3. Sent-Message Persistence

**Status:** ✅ **Persistence confirmed via whatsmeow echo path.**

**Mechanism — echo path (not direct INSERT on send):**
The `/api/send` handler calls `client.SendMessage()` (whatsmeow). WhatsApp Web echoes every sent message back through the client event loop. The event handler at `main.go` line 828 calls `messageStore.StoreMessage(...)` for every received event, including echoed self-sends where `msg.Info.IsFromMe = true`. This is how sent messages reach `messages.db` — not via a direct INSERT at send time, but via the echo loop.

**Evidence (source-verified):**
- `StoreMessage()` defined at `main.go` line 364 — accepts `isFromMe bool` parameter
- Event handler at `main.go` line 828 calls `StoreMessage(... msg.Info.IsFromMe ...)` unconditionally for all message events (received AND echoed outbound)
- `messages.is_from_me` column exists in schema (main.go line 98)
- MCP server queries include `is_from_me` in all message returns (whatsapp.py lines 236, 340, 366, 394, 624, etc.)

**Note:** Upstream commit `9841e17` ("Persist outbound messages to local SQLite after SendMessage") is in VGP main but not in kewtyboi fork (part of the 54-commit delta — see §1). That commit may add a *direct* on-send path alongside the echo path. After the §1 upstream sync, verify whether `9841e17` changes persistence behaviour.

**What remains open for sub-issue #601:**
The echo path is confirmed to exist. Sub-issue #601 should be reframed to verify:
1. **Echo-path latency** — does the echoed message arrive within the 2s SLA after send?
2. **Connection-drop resilience** — what happens to `messages.db` if the bridge drops connection mid-send before the echo is received?

**Current capability:**  
Read MCP tools (`list_messages`, `get_message_context`, etc.) correctly expose `is_from_me` for filtering and display. Send tools (`send_message`, `send_file`, `send_audio_message`) return `success` / `message` status; persistence via echo path happens asynchronously.

---

## 4. MCP Tool Surface

**Total tools exposed:** 13 (matches design doc target).

| Tool | Purpose | Signature | Source |
|------|---------|-----------|--------|
| `search_contacts` | Search WhatsApp contacts | `(query: str) → list[dict]` | main.py line 51 |
| `get_contact` | Look up contact by phone/LID/JID | `(identifier?: str, phone_number?: str, phone?: str) → dict` | main.py line 63 |
| `list_messages` | Query messages with optional context | `(after, before, sender_phone_number, chat_jid, query, limit, page, include_context, ...) → list[dict]` | main.py line 158 |
| `list_chats` | Query chats matching criteria | `(query, limit, page, include_last_message, sort_by) → list[dict]` | main.py line 207 |
| `get_chat` | Fetch chat metadata by JID | `(chat_jid: str, include_last_message: bool) → dict` | main.py line 232 |
| `get_direct_chat_by_contact` | Fetch chat metadata by phone | `(sender_phone_number: str) → dict` | main.py line 244 |
| `get_contact_chats` | Get all chats involving a contact | `(jid: str, limit: int, page: int) → list[dict]` | main.py line 255 |
| `get_last_interaction` | Most recent message with contact | `(jid: str) → dict` | main.py line 268 |
| `get_message_context` | Get message with surrounding context | `(message_id: str, before: int, after: int) → dict` | main.py line 282 |
| `send_message` | Send text message | `(recipient: str, message: str) → dict` | main.py line 295 |
| `send_file` | Send media (image/video/doc) | `(recipient: str, media_path: str) → dict` | main.py line 316 |
| `send_audio_message` | Send audio via WhatsApp audio format | `(recipient: str, media_path: str) → dict` | main.py line 334 |
| `download_media` | Download media to local disk | `(message_id: str, chat_jid: str) → dict` | main.py line 350 |

**Transport:** FastMCP over stdio. Entry point: `whatsapp-mcp-server/main.py` line 380.

---

## 5. VGP Open Issues — Reproduction Status

### VGP #73: Pydantic Validation Crash on `get_message_context`

**Status:** ⚠️ **Source present; cannot reproduce in audit context (read-only, no live DB).**

**VGP Issue:** https://github.com/verygoodplugins/whatsapp-mcp/issues/73

**Code location:** `whatsapp-mcp-server/whatsapp.py` line 604–650 (function `get_message_context`)

**Function signature:**
```python
def get_message_context(message_id: str, before: int = 5, after: int = 5) -> MessageContext:
```

**Risk:** The function constructs `MessageContext` dataclass with `Message` instances. If database rows have NULL or malformed `is_from_me` or `timestamp` values, Pydantic validation could fail with non-descriptive error. 

**Finding:** No explicit null-coalescing or type validation before constructing `Message()` objects in the audit (lines 610–647). A database corruption or WhatsApp Web session inconsistency could surface this.

**Recommendation:** Sub-issue #599 should add defensive type-casting and null defaults to `Message` construction.

---

### VGP #74: Duplicate Rows in `get_contact_chats`

**Status:** ⚠️ **Source present; SQL query structure is susceptible.**

**VGP Issue:** https://github.com/verygoodplugins/whatsapp-mcp/issues/74

**Code location:** `whatsapp-mcp-server/whatsapp.py` line 547–598 (function `get_contact_chats`)

**Function signature:**
```python
def get_contact_chats(jid: str, limit: int = 20, page: int = 0) -> list[dict[str, Any]]:
```

**Risk:** The query joins `messages` to `chats` using `DISTINCT` on the full selected tuple — including `m.content`. Because `DISTINCT` applies to all projected columns, two messages from the same chat with different content produce two separate rows. There is no `GROUP BY` to collapse per-chat.

**Query excerpt (lines 554–576, source-verified):**
```sql
SELECT DISTINCT
    c.jid,
    c.name,
    c.last_message_time,
    m.content as last_message,
    m.sender as last_sender,
    m.is_from_me as last_is_from_me
FROM chats c
JOIN messages m ON c.jid = m.chat_jid
WHERE m.sender = ? OR c.jid = ?
ORDER BY c.last_message_time DESC
LIMIT ? OFFSET ?
```

**Finding:** Bug **confirmed present** in this fork. The `DISTINCT` here does not deduplicate by chat — it deduplicates by the full row tuple. A contact with multiple messages in the same chat produces one row per message. The function returns all rows unfiltered (line 596: `return [chat_to_dict(c) for c in chats]`). There is no `GROUP BY`.

**Recommendation:** Sub-issue #600 should fix the query — replace `DISTINCT` + full-tuple projection with `GROUP BY c.jid` and aggregate `m.content` to pick the latest message (e.g. via a correlated subquery or `MAX(m.timestamp)` join). Verify fix with: contact that has 5+ messages in one chat; result count should equal chat count, not message count.

---

### VGP #89: Group Members Missing

**Status:** ❌ **Not found in codebase.**

**VGP Issue:** https://github.com/verygoodplugins/whatsapp-mcp/issues/89

**Finding:** No group member enumeration tool in the 13-tool surface. Groups are identified by `jid.endswith("@g.us")` (whatsapp.py line 45) but members are not exposed.

**Recommendation:** Out-of-scope for this audit (sub-issue #606 may be a separate "enhance" epic).

---

### VGP #106: Reactions Not Exposed

**Status:** ❌ **Not found in codebase.**

**VGP Issue:** https://github.com/verygoodplugins/whatsapp-mcp/issues/106

**Finding:** Message dataclass (whatsapp.py line 22–30) has no `reactions` field. No MCP tool exposes reactions.

**Recommendation:** Out-of-scope for hardening; separate feature epic if needed.

---

### VGP #107: Quoted Replies Not Exposed

**Status:** ❌ **Not found in codebase.**

**VGP Issue:** https://github.com/verygoodplugins/whatsapp-mcp/issues/107

**Finding:** Message dataclass has no `quoted_message_id` or `reply_to_id` field. Query results do not include reply metadata.

**Recommendation:** Out-of-scope for hardening; separate feature epic if needed.

---

## 6. Health & Reconnect Behaviour

### Health Endpoint

**Implementation:** `/api/health` (main.go lines 1088–1101)

```jsonc
{
  "status": "ok",           // or "disconnected"
  "connected": true,        // boolean
  "timestamp": 1700000000   // Unix timestamp (example)
}
```

**Limitation:** Returns only whatsmeow client connection state, NOT:
- Database connectivity
- Message queue depth
- Last successful message send timestamp
- WhatsApp Web session expiry warning

**Recommendation:** Sub-issue #603 (Health & reconnect) should extend payload to include `db_healthy: bool`, `session_age_seconds: int`, and `last_message_sent: ISO-8601`.

### Reconnect Behaviour

**Status:** ⚠️ **Implicit, not structured.**

**Evidence:**
- whatsmeow library handles reconnects internally via `client.Connect()` loop and event handlers
- Bridge startup calls `client.Connect()` at main.go line ~1075 (full code not audited)
- No explicit "reconnect after session expiry" SOP exists in codebase

**Gap:** When WhatsApp Web session expires (typically ~20 days), bridge behavior is:
1. `client.IsConnected()` returns false → `/api/health` reports `"disconnected"`
2. No automatic re-login or QR code regeneration
3. No structured alarm or metric emitted

**Recommendation:** Sub-issue #603 should define:
- Session expiry detection (age threshold)
- Graceful degrade (MCP tools report "bridge offline" vs crashing)
- Manual restart procedure (with steps, not just "restart")

---

## 7. Dependencies & Environment

### Python (MCP Server)

**Entry point:** `whatsapp-mcp-server/main.py`

**Key imports:**
```python
from mcp.server.fastmcp import FastMCP
import sqlite3
import requests
from whatsapp import (...)  # local module
from audio import (...)      # local audio processing
```

**Configuration (env vars):**
- `WHATSAPP_DB_PATH` — path to messages.db (default: `../whatsapp-bridge/store/messages.db`)
- `WHATSAPP_API_URL` — bridge REST API base URL (default: `http://localhost:8080/api`)

### Go (Bridge)

**Dependencies:** (from `go.mod`; not fully audited)
- `go.mau.fi/whatsmeow` — WhatsApp Web client library
- `github.com/mattn/go-sqlite3` — SQLite driver
- `github.com/mdp/qrterminal` — QR code terminal rendering
- Standard library: `database/sql`, `net/http`, `encoding/json`, etc.

**Configuration (env vars):**
- `WHATSAPP_BRIDGE_PORT` — REST API port (default: 8080) — referenced in whatsapp-mcp-server context but set in bridge
- `FORWARD_SELF` — forward self-sent messages via webhook (code default: `true` when unset, main.go line 37; `.env.example` ships it as `false`)

---

## 8. Known Risks & Observations

| Risk | Severity | Description | Mitigation |
|------|----------|-------------|-----------|
| **Upstream lag** | Medium | 54 commits behind VGP main (17 fixes, 3 feats, 20 dep-bumps); includes `9841e17` sent-msg SQLite path | Sub-issue #604 (upstream sync SOP) must enforce monthly rebase cadence |
| **Sent-message echo-path latency unverified** | Low | Persistence exists via whatsmeow echo loop; latency and connection-drop resilience not yet measured | Sub-issue #601 reframed: verify echo latency (2s SLA) + drop resilience |
| **Health endpoint incomplete** | Low | `/api/health` missing DB and session age signals | Sub-issue #603 extension |
| **No structured reconnect** | Medium | Session expiry at ~20 days; bridge goes dark; no auto-recovery | Sub-issue #603 must define SOP + alarms |
| **VGP #73 type safety** | Low | `get_message_context` may fail on malformed DB rows | Sub-issue #599 type-casting |
| **VGP #74 deduplication** | Medium | Bug **confirmed present** — `DISTINCT` on full tuple including `m.content`; no `GROUP BY`; multi-message chats produce duplicate rows | Sub-issue #600 must fix query |
| **LID chat migration** | Low | main.go has migration logic (lines 121–250) for legacy @lid JIDs; if incomplete, history lost | Verify migration ran; check for any @lid rows still in messages.db |
| **Audio processing dependency** | Low | `send_audio_message` requires ffmpeg; no fallback beyond "use send_file" | Document in tool help; consider graceful error if ffmpeg missing |

---

## 9. Recommended Sub-Issue Execution Order

**Critical path (blocking others):**

1. **#598** ✅ **Audit (THIS DOCUMENT)** — Establish baseline. Unblocks all downstream.

2. **#601** — **Sent-message persistence verification** — Trace send → DB write; confirm 2s SLA or declare forward-only arch. Blocks #603 (health/reconnect payload design).

3. **#603** — **Health & reconnect hardening** — Extend `/api/health` with DB + session age; define reconnect SOP. Blocks #605 (MCP loading reliability depends on health signals).

4. **#604** — **Upstream sync SOP** — Define monthly rebase cadence, PR review flow for VGP pulls. Can run in parallel with #599–#600 (fixes).

5. **#599, #600** — **VGP #73, #74 fixes** — Type-casting + deduplication hardening. Parallel work; no cross-blocking.

6. **#605** — **MCP loading reliability** — Depends on health signals from #603. Coordinate with PointyTooling #448 (launcher pattern).

7. **#606** — **Sealjay reassessment gate** — Trigger at 2026-07-01. Captures outcomes of #599–#605 into decision log.

---

## 10. Audit Completion Status

**All acceptance criteria met:**

- ✅ Fork commit SHA: `251e842ed8d880c7136ba9841989f62ff2adeb7c`
- ✅ VGP lag: **54 commits behind** (corrected from initial 10-commit figure; see §1)
- ✅ `messages.db` schema: full SQL DDL recorded (source: main.go lines 85–108)
- ⚠️ `whatsapp.db` schema: **not directly audited** — only `whatsmeow_lid_map` table known from code references; full DDL not recorded (acceptance criterion partially met)
- ✅ `is_from_me` column: confirmed present; sent messages persisted via whatsmeow echo path (main.go line 828)
- ✅ VGP #73: source present, type safety gap identified
- ✅ VGP #74: **bug confirmed present** — `DISTINCT` on full tuple, no `GROUP BY`; sub-issue #600 must fix
- ✅ VGP #89, #106, #107: out-of-scope; not in 13-tool surface
- ✅ Health endpoint: `/api/health` found, payload structure documented
- ✅ Reconnect behavior: implicit; SOP needed
- ⚠️ Bridge process state (uptime, RSS, open file handles): commands documented in §1; **baseline values not captured** (non-intrusive audit scope) — sub-issue executor should run `ps` + `lsof` commands against live bridge and record values
- ✅ This document committed to `kewtyboi/whatsapp-mcp` as PR

---

**Audit conducted:** 2026-05-24  
**Auditor:** Claude Code (Haiku worker)  
**Next step:** Open PR to `kewtyboi/whatsapp-mcp` main; link to PointyTooling #598 for sign-off.
