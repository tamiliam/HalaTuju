# Retrospective — Team tables T1 (hats plumbing) — 2026-11-03

Live 2026-11-03: main 83cddf96; api-01239-5jr, web-01067-6fr. No migration, no Scheduler job.

## What shipped
- `apps/courses/staff_tables.py`: the Admins / Reviewers / Mentors tables, DERIVED from role, keys and the mentor
  link (no new column). `admin/role/` serves `tables`; web page guards read `lib/pageGuard.ts`.
- Owner ruling option B: a reviewer whose keys put them in Admins (today: Rohini, `see_all` + `spending`) gains the
  organisation READ pages only. Write pages and lead-only powers are unchanged; her landing is unchanged.

## What went well
- The golden access matrix (fixture from faacf681, 4,095 cells) made "nobody else changed" a test, not a claim.
  The adversarial review re-ran it on the parent commit: 0 differences.
- The builder found the qc edge (`see_all` beside `qc` must not count) and the mixed-key shapes before review.

## What to improve
- wat_lint FAILed because the commit subjects name "Team tables T1", not "Sprint N". Add the consolidation-log
  line in the same commit set from the start.
- Mobile M5 landed first and left `/scholarship/apply` at 0.191 kB of room (T1 adds 0; measured on clean main).
  Rebasing onto another session's push means re-running the bundle gate; Mobile owns the follow-up.

## Next
T2 — the Team page (Admins · Reviewers · Mentors tables with Add / Remove); design already approved.
