# Retrospective — Sponsor portfolio: status taxonomy + card details (Sprint 1) — 2026-07-21

## What Was Built

The sponsor's My-students card now shows **one clear lifecycle badge** per student and leads with the
**full course → institution** (was the bare field slug "perubatan"). A new nullable
`supported_semesters` field drives the redefined "Semester completed" state.

- `supported_semesters` (migration 0106, applied migrate-first) — owner-set, else `award_amount // 1000`.
- `pool.sponsor_portfolio_status` — a single priority-ordered badge (discontinued > graduated > paused >
  semester_completed > needs_attention > on_track), derived entirely from existing state; None for a
  discovery card. "Awaiting acceptance" stays FE-derived from the sponsorship `offered` status.
- My-students card: full course + institution + key details, `PortfolioBadge`, a "Withdrew" journey stop.

## What Went Well

- **Investigation before invention.** The "how many semesters does support cover?" question had no clean
  field. Reading the award/disbursement code surfaced the RM1,000-per-semester pattern hiding in
  `award_amount`, so the badge ships correct today on a heuristic, with a nullable field as the owner's
  100% override — exactly the "fill it in over time" model the owner wanted.
- **Everything derived from existing state.** Discontinued/paused/graduated/needs-attention all map to
  fields that already exist (`closure_reason`, `maintenance_substate`, `SemesterResult`). No new lifecycle
  machinery — just one read-only resolver + a serializer field.
- **Migrate-first done cleanly via MCP.** DATABASE_URL is a Cloud Run secret (unreadable via describe), so
  the column + its `django_migrations` row went in atomically through the Supabase MCP after a read-only
  pre-check (column absent, 0106 unrecorded, prod at 0105) — no local DB connectivity needed.

## What Went Wrong

- Nothing broke; full suite green (2925). One judgement recorded (a single priority-ordered `portfolio_status`
  vs the old separate progress/support badges) so it isn't re-litigated — see decisions.md.

## Design Decisions

- **`supported_semesters` nullable + heuristic fallback**, and **one priority-ordered `portfolio_status`**
  instead of composing separate progress + support badges — see `docs/decisions.md`.

## Numbers

- Files touched: 11 (5 backend incl. migration + test, 5 web incl. 3 i18n, 1 plan). Commit `1a9b7b89`.
- Tests: full suite 2925 pass (12 new). Migration 0106 (nullable smallint), applied migrate-first.
- Deploy: api + web. Behind `SPONSOR_POOL_ENABLED`.

## Next (Sprint 2 / 3)

- **Sprint 2:** the new clickable sponsored-student **detail page** (Stitch mock → sign-off → build) —
  full anon profile, journey, commitment, thank-yous; **reserve the spending space**.
- **Sprint 3 (deferred):** the Vircle **spending** panel/tab.
- Owner: Tamil review of the new `myStudents.status.*` + `journey.withdrew` first-drafts.
