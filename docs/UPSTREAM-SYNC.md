# Upstream Sync

This fork (`kewtyboi/whatsapp-mcp`) tracks `verygoodplugins/whatsapp-mcp` as its primary upstream. The full upstream-sync SOP — the 6-step procedure, conflict-resolution policy, and cadence guidelines — lives in [`UPSTREAM-SYNC-SOP.md`](./UPSTREAM-SYNC-SOP.md) (PointyTooling #604). This file holds the Sealjay watch log (PointyTooling #606).

## Sealjay Watch Log

**Purpose:** Track [`Sealjay/mcp-whatsapp`](https://github.com/Sealjay/mcp-whatsapp) — a
single-binary Go HTTP-transport rewrite of the WhatsApp MCP server — for maturity on behalf
of PointyTooling issue #606. When all four signal thresholds are met, the director will
decide whether to migrate the bridge to that implementation.

**Signal thresholds** (proxies for production-readiness; director may adjust per design doc
decision 5):

| Signal | Threshold |
|--------|-----------|
| Stars | >50 |
| Open issues (non-PR) | <10, none blocking |
| Last commit | within 30 days |
| Public production reports | any |

### 2026-05-30 — Watch set; baseline captured

| Signal | Threshold | 2026-05-30 baseline | Pass? |
|--------|-----------|---------------------|-------|
| Stars | >50 | 2 | ✗ |
| Open issues (non-PR) | <10, none blocking | 3 | ✓ |
| Last commit | within 30 days | 2026-05-11 (~19 days; `06ff149e` "feat(download): add output_path to download_media") | ✓ |
| Public production reports | any | none observed (README describes 41 MCP tools; MIT; not archived) | — |

**Status set 2026-05-30, assess 2026-07-01.**

At baseline the project is well below the star/maturity proxy (2 vs >50), so a "stay
another 4 weeks" outcome looks likely unless adoption accelerates. The formal decision is
deferred to the gate date. A calendar reminder for 2026-07-01 has been created separately.

### Next gate: 2026-07-01

The assessor will re-capture the four signals above and log one of:

- **Migrate** — all thresholds met; new EPIC #TBD filed to replace the current bridge.
- **Stay: next review 2026-07-29** — thresholds not met; watch extended by 4 weeks.

Outcome is logged in a new dated entry in this section, per #606 acceptance criteria.
