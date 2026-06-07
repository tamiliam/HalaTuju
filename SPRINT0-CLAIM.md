# 🚧 RING-FENCED WORKTREE — do not touch from the main checkout

**Owner:** Claude (this session) — **Sprint 0: sponsor boundary foundation** (widen the sponsor-facing allowlist).
**Branch:** `feat/sponsor-boundary-foundation`  ·  **Worktree:** `Production/HalaTuju-sprint0-boundary/`
**Base:** `main@7cc1f1e`  ·  **Started:** 2026-06-07

## Why this exists
Another agent is working **in the main checkout** (`Production/HalaTuju/`) on **Application Form + Check-2**. To avoid
collisions (lesson #102), this sprint is isolated in its own git worktree — separate working tree, index, and HEAD.

## My territory (only these)
- This worktree only: `Production/HalaTuju-sprint0-boundary/`
- Files this sprint touches: `apps/scholarship/serializers.py`, `apps/scholarship/models.py` (add `Sponsor.is_trusted`),
  a new migration, `apps/scholarship/profile_engine.py` (coarsen anon prompt), `apps/scholarship/tests/` (allowlist tests).

## What I will NOT do
- ❌ Touch the **main checkout** (`Production/HalaTuju/`) or the other agent's files
  (`resolution.py`, `services.py`, `verdict_engine.py`, Application-Form / Check-2 code).
- ❌ Apply the `is_trusted` migration to **prod** during the sprint — it only reads under `SPONSOR_POOL_ENABLED` (off),
  so it's held until this feature deploys (avoids prod-DB contention with the other agent's Check-2 migration).
- ❌ Commit/push to `main` — work stays on `feat/sponsor-boundary-foundation` until merge.

## Migration-number note (lesson #32)
Both branches fork from the same `main`, so my migration and the other agent's Check-2 migration may claim the same
number. I rebase on `main` before merge and renumber mine if theirs landed first. The migration is **not** applied to
prod until then.
