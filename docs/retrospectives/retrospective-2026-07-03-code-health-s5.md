# Retrospective — Code-health Sprint 5 (final): infra & guardrails (2026-07-03)

## What Was Built

The last sprint of the code-health roadmap (findings #21/#23 + P3 quick wins):

1. **#21 Shared cache backend.** `production.py` now uses Django's DatabaseCache
   (`django_cache` table, created migrate-first via the Supabase MCP with deny-by-default
   RLS). Every rate limit that was per-worker in-memory — upload 40/hour (billable Vision),
   anon 1000/min, 3 AI reports/day — is now shared across instances and survives cold
   starts. Dev/test deliberately keep LocMemCache (no table needed, no test overhead).
2. **HSTS** (30 days; conservative — no preload, no subdomain pinning).
3. **#23 URL validator.** A 5xx is a retryable server-side `error`, never `dead` (a portal
   in maintenance can no longer get its URL permanently cleared); `--fix` refuses a sweep
   of >5 dead AND >10% of checked without `--force`. Tests updated + guard tests added.
4. **Quick wins:** applications-queue `interviewed` label → "Awaiting QC" (the list page
   missed the QC-gate relabel); dead `accepted` banner branch removed; resolution-items
   fetch gains its trailing slash (no more 301 per Action Centre load).

## What Went Well

- The DatabaseCache choice satisfied the finding at zero incremental cost (no Redis) —
  aligned with the <RM10/month constraint; the table was live on prod before the code push.

## What Went Wrong

- **A python-heredoc escape turned `\n` into a literal newline inside a string, writing a
  SyntaxError into `validate_course_urls.py`** — caught immediately by the test run's
  collection error. Root cause: multi-layer quoting (bash heredoc → python string) is
  error-prone for content containing escapes; the earlier S3 quiz rewrite had already hit
  a variant of this. System change: for multi-line content edits, write the edit script to
  a file first (as done for the quiz) rather than inline heredocs.
- **The mass-change guard's first test asserted global counts** and collided with seeded
  fixture institutions — scoped to the test's own rows. (Known trap; cheap fix.)

## Design Decisions

- DatabaseCache over Redis/Memorystore (free, one table, adequate for this traffic;
  revisit if request volume makes per-request cache queries measurable).
- HSTS without preload/subdomains — reversible posture first.
- The banner stays shortlisted-only by design: awarded students are reached by email and
  the (flag-embargoed) award panel, per the award-comms decisions of 2026-06-29.

## Numbers

- 3,218 backend tests + 412 jest, 0 failures (+4 net new backend).
- 1 prod DDL (django_cache, migrate-first, RLS). No Django migration file (cache table is
  not a model). No i18n change.

## Roadmap complete

All five sprints of `docs/plans/2026-07-03-code-health-review.md` are shipped. Remaining
open items live in the roadmap's Backlog section (P3 leftovers → small-change lane) and
the owner-decision list (WhatsApp opt-in default; quiz copy review before
`BURSARY_AGREEMENT_ENABLED`; optional GitHub-support scrub of the purged PII objects).
