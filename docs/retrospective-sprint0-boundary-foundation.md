# Retrospective — Sprint 0: Sponsor boundary foundation (widen the allowlist)

**Branch:** `feat/sponsor-boundary-foundation` (ring-fenced worktree; base `main@7cc1f1e`) · **2026-06-07** · **ships dark.**

## What shipped
Implements the owner **Boundary decision (2026-06-07)** in the sponsor-facing allowlist, fail-closed, with the
trusted-sponsor gate. The allowlist `Serializer` stays the hard boundary; one new field crosses, behind a gate.

- **`models.py`** — `Sponsor.is_trusted` (BooleanField, default `True`). Launch sponsors are trusted; flip to False
  per-sponsor when public onboarding opens.
- **`migrations/0043_sponsor_is_trusted.py`** — additive, backward-compatible (every existing sponsor → trusted).
- **`serializers.py`** — `SponsorPoolCardSerializer.institution` (`SerializerMethodField`): returns `profile.school`
  **only** when `context['is_trusted']` is True; absent otherwise (fail-closed). Docstring updated (parents' identifiers
  also never cross).
- **`profile_engine.py`** — coarsened the anonymous-blurb prompt with a quasi-identifier guard (keep family/community
  detail general; no employer/village/one-of-a-kind particulars).
- **`tests/test_sponsor_pool.py`** — added parent identifiers (in `guardians`) to the leak fixture + two tests:
  `institution` absent for non-trusted, present (= school) for trusted with all other identifiers (incl. parents') still
  blocked. Fixture switched from `**IDENTIFIERS` spread to explicit fields (lesson #55).

## Verification
- `pytest apps/scholarship/tests/test_sponsor_pool.py` → **26 passed**; `test_sponsor.py` → **15 passed**.
- `makemigrations scholarship --check --dry-run` → **no changes detected** (migration complete).

## Lessons applied
- **#107** — kept the plain `Serializer` + method-field allowlist; extended the planted-identifier leak test for the new
  blocked parent fields + institution-non-trusted.
- **#108** — `scan_anon_for_identifiers` untouched (still the backstop); institution crosses only as a structured
  trusted-gated field, the blurb still scrubs school tokens + is now coarser on locality.
- **#32 / #61 / #126** — migration numbered `0043` against the verified baseline `0042`; **not applied to prod**
  (reads only under `SPONSOR_POOL_ENABLED`, which is off) — will migrate-first via MCP at deploy.
- **#55** — explicit serializer test fixture (no `**` spread that hides omitted attributes).

## Deferred (intentional)
- **View-wiring** (`views_sponsor.py` passing `context={'is_trusted': sponsor.is_trusted}`) → done when the pool goes
  live / Sprint 7. Until then institution never actually reaches a sponsor (serializer is safe-by-default).
- **FE `SponsorPoolCard` interface** (`lib/api.ts`) → Sprint 1/7 (backend-only this sprint; lesson #81).
- **Shared-doc edits** (`CHANGELOG.md`, `CLAUDE.md` Next Sprint) → at **merge**, to avoid clobbering the other agent's
  concurrent Application-Form / Check-2 edits.

## Merge note
Rebase on `main` before merge; if the other agent's Check-2 migration claimed `0043`, **renumber** mine. Apply the
`is_trusted` migration migrate-first to prod only when the first deploy carrying it lands.
