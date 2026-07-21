# Plan — Sponsor portfolio: status taxonomy + card details (Sprint 1 of the labels rework)

Owner-approved 2026-07-21. Two more sprints follow (detail page; spending — deferred).

## Goal
Give the sponsor's **My Students** portfolio a clear, distinct status per student, and show the full
course + institution + key details on the card (was the bare field slug "perubatan").

## Sprint 1 scope (this plan)

### Backend
1. **`supported_semesters`** — nullable `IntegerField` on `ScholarshipApplication` (migration 0106).
   Owner fills it per-student over time; empty → heuristic `award_amount // 1000`
   (RM1,000 ≈ 1 semester: STPM 3, continuing-STPM 1, Matric/Asasi/others 2). Helper
   `pool.supported_semesters(app)` (explicit → heuristic → None).
2. **`pool.sponsor_portfolio_status(app)`** — one badge, priority-ordered from existing state:
   `discontinued` (status=withdrawn OR closed+withdrawn/lapsed/terminated) → `graduated`
   (closure graduated OR progress graduated) → `paused` (maintenance on_hold) → `semester_completed`
   (closure 'completed' OR results ≥ supported_semesters) → `needs_attention` (progress needs_attention
   OR maintenance probation) → `on_track`. Returns None for non-funded (e.g. a discovery-pool
   'recommended' card) — guarded before any query, so no N+1 on the grid. "Awaiting acceptance" stays
   FE-derived from the sponsorship `offered` status (unchanged).
3. Expose `portfolio_status` + `supported_semesters` on `SponsorPoolCardSerializer` (so both the
   My-students card and the future detail page get them; the discovery card ignores them).

### Frontend (My Students card, `sponsor/(portal)/page.tsx`)
4. Lead with **full course → institution**, then key details (region · your support · academic ·
   supported sems · enrolment). Render the single **portfolio_status** badge (colour per state).
   Journey tracker gains a **"Withdrew"** stop-dot for discontinued.

### i18n (en/ms/ta)
5. `sponsorPortal.myStudents.status.{on_track,semester_completed,needs_attention,paused,discontinued,graduated}`
   + `awaiting` (kept). Tamil first-draft (flagged for owner review).

### Tests
6. `sponsor_portfolio_status` per state; `supported_semesters` explicit + heuristic fallback; the card
   serializer surfaces both.

## Not in Sprint 1
- The new clickable **detail page** (Sprint 2, Stitch-gated).
- **Spending** panel/tab (Sprint 3, deferred — space reserved in the detail page then).
- Actually FUNDING the longer 5/6/10-sem pathways (award model unchanged; a separate owner decision).

## Risks / notes
- The heuristic under-counts supported semesters for UA/Poly (5–6) & PISMP (10), which are funded at
  the flat RM2,000 (= 2) today — acceptable; the explicit field is the override when the owner sets it.
- Migration 0106 is a nullable column (safe, no backfill). Migrate-first before deploy.
- Behind `SPONSOR_POOL_ENABLED` (whole sponsor surface is dark until go-live).
