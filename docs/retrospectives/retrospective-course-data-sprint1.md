# Retrospective — Course-Data Pipeline Sprint 1 (2026-06-13)

Roadmap: `docs/roadmap-course-data-pipeline.md`. One-command STPM/UPU refresh + dated archive + annual reminder.

## What Was Built
- **`refresh_stpm`** management command — orchestrates `scrape_mohe_stpm` (sanity-checked) → optional
  `validate_stpm_urls` → `sync_stpm_mohe` (dry-run by default) → `audit_data`, with a single step summary, and
  **halts loudly** if a safety guard trips (scrape shortfall, or the sync mass-deactivation guard). Local operator
  tool (scrape needs Playwright). Pure helpers `dated_archive_name` + `prune_archive`.
- **Dated CSV archive** — `data/stpm/archive/mohe_<date>.csv`, keeps newest `--keep` (default 12) for diff/rollback.
- **`send_refresh_reminder`** — `CronRunView` job `refresh-reminder`; annual email nudge. Setting
  `COURSE_REFRESH_REMINDER_EMAIL` (falls back to `DEFAULT_FROM_EMAIL`, clean no-op without a recipient).
- **Annual Cloud Scheduler job** `halatuju-refresh-reminder` (`0 9 1 12 *`, Asia/KL) mirroring `vision-outage`.
- Decision logged: no in-app notification system yet — email/Cloud-Scheduler until ~5+ operational reminders or >1 admin.

## What Went Well
- **Worktree isolation worked.** Built the whole sprint in `.worktrees/refresh-stpm` off the shared primary checkout —
  no collision with the other agent's `main` activity (the exact failure flagged twice before). Clean merge.
- **Reused the existing safety guards for free.** The wrapper inherits the scrape-shortfall + mass-deactivation guards
  from the P0 work, so "one command" didn't weaken any protection.
- **Orchestration tested without the heavy deps.** Mocking the module-level `call_command` let 12 tests assert step
  order + dry-run/apply pass-through + abort-before-sync, with no Playwright/Selenium/DB.

## What Went Wrong
- **Assumed the reminder fallback recipient was the admin's inbox; it wasn't.** I told the owner the recipient would
  "fall back to `DEFAULT_FROM_EMAIL` → your tamiliam@gmail.com". The smoke test revealed prod `DEFAULT_FROM_EMAIL` is
  **`noreply@halatuju.xyz`** (a no-reply *sender* address), so the reminder would have gone to an unread mailbox.
  *Root cause:* stated a prod config value from assumption instead of checking the deployed service env.
  *Fix:* set `COURSE_REFRESH_REMINDER_EMAIL=tamiliam@gmail.com` explicitly (rev `00369`); and the smoke test (curling
  the cron endpoint per the L137 pattern) is what caught it — keep smoke-testing any new cron/email wiring end-to-end
  rather than trusting a fallback. Lesson added.

## Design Decisions
- **Link validation is opt-in (`--validate-urls`), off by default** — it's a slow (~50 min Selenium) step; the common
  refresh run stays fast, and a full link pass is a deliberate periodic action.
- **Operational reminders stay email/Cloud-Scheduler, no notification system** (logged in `decisions.md`).

## Numbers
| Metric | Value |
|--------|-------|
| New tests | 12 (archive helpers, orchestration order, dry-run/apply, scrape+guard abort, reminder recipient/fallback/no-op) |
| Suite | 1040 (courses + cron), 0 failures |
| Deploys | 1 API build (commands) + 1 env-var revision (recipient) — within budget |
| Files | 8 (2 new commands, 1 test, settings, CronRunView, CHANGELOG, roadmap, decisions) |
| Golden masters | untouched |
