# B40 Redesign — Sprint 12b Retrospective (2026-05-25)

The gated production deploy. `feature/b40-redesign` (S7–S12a, 11 commits) merged to `main` and deployed; both
Cloud Run services live; the B40 redesign is in production (dormant — site not promoted).

## What Was Done
- Added an idempotent `seed_b40_2026_cohort` management command (+ 3 tests; 1100 → 1103).
- **Migrate-first deploy:** applied courses `0048` + scholarship `0007/0008/0009` to prod **before** pushing `main`
  (additive migrations → live old code unaffected). Verified via `showmigrations` + an information_schema column check.
- Merged to `main` (release `55c2c36`), pushed → both Cloud Build triggers deployed; health checks 200; the live
  course-guide stayed healthy (the migration's whole purpose).
- Seeded/verified cohort `b40-2026`; corrected its stale thresholds; ran post-deploy security advisors (0 errors).
- Deferred the Cloud Scheduler (no applicants while unpromoted) and Vision OCR (S13) — both flagged as pre-promote /
  post-launch.

## What Went Well
- **Investigating the deploy mechanism before trusting it.** The Dockerfile CMD is just gunicorn and the Cloud Build
  triggers are the auto-generated build→push→deploy (no migrate step) — so a naive "push and hope" would have shipped
  code that 500s for *every logged-in user* (new StudentProfile columns). Catching this and going migrate-first gave
  a zero-downtime deploy.
- **Verifying prod state at each step** (migration plan, showmigrations, information_schema columns, health curls,
  security advisors) rather than assuming.

## What Went Wrong
- **The deploy does not auto-apply migrations.** *Symptom:* container start = gunicorn only; triggers = 3 steps, no
  migrate. *Root cause:* the project uses Cloud Run's auto-generated deploy triggers, which never had a migrate step;
  prior deploys migrated manually (undocumented). *Fix → lessons.md + CLAUDE.md:* documented that migrations are
  manual and must be applied migrate-first before pushing `main`.
- **The live cohort had stale thresholds.** *Symptom:* `b40-2026` showed `min_spm_a_count=5`, `min_stpm_pngk=3.0` (the
  advertised bar) instead of the settled engine values 4 / 2.9. *Root cause:* migration `0008` changed those columns'
  *defaults* via `AlterField`, but `AlterField` does not rewrite existing rows — the Phase-1 row kept its old values
  (newer fields added in `0008` correctly picked up their new defaults; pre-existing columns didn't). *Fix:* corrected
  the row; lesson recorded — after a default change, explicitly sync existing config rows.
- **My side couldn't run the prod migration in auto mode.** *Symptom:* the auto-permission classifier (rightly)
  blocked pulling prod DB creds + connecting directly. *Resolution:* surfaced it to the user; they switched to
  "ask before edits" so the command prompted for approval. Honest stop beats working around a safety gate.
- **A near-deletion of real data.** The one prod application carried a real person's name; I asked before deleting
  rather than treating "reset test data" literally. The user confirmed it's real — kept. (Operating rule held:
  inspect the target + surface before deleting something you didn't create.)

## Numbers
- Backend **1103** (+3 seed-cohort tests), golden masters intact. Prod migrations verified. Deploy: 1 push, both
  services SUCCESS, 0 advisor errors. No frontend change.
