# Retrospective — Now sprint 3 (2026-10-02): TD-322, TD-114 and TD-151

**Scope:** move the admin onboarding flag out of the browser's reach (TD-322, security, kept
separable); stop a never-scored document from carrying a fact to Certain and give the old uploads a
re-score path (TD-114); build the bounded items of the misread-document hardening pass (TD-151).
Built by one agent; an adversarial reviewer reads the diff before the lead commits. No migration,
no data change, no copy, no ledger raised (one LOWERED).

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-322 api | `apps/courses/password_change_flag.py`; invite / Resend / expiry cron / set-password write and read `app_metadata`; one-release fallback on the server's own Invitation row | `test_admin_auth.py` (+8: browser flag refused, app wins, fallback honoured, fallback expires with the TTL, unissued/revoked refused, removal date, cron in app_metadata, cron app-outranks-user) |
| TD-322 web | `lib/invitations.pendingPasswordChange`; the admin login reads it | `invitations.test.ts` (+3) |
| TD-114 verdict | ladder moved verbatim to `verdict_ladder.py`; never-scored anchor → floor at Probable | `test_verdict_unscored_floor.py` (8) |
| TD-114 re-score | `rescore_unscored_documents` (dry-run by default) | `test_rescore_unscored_documents.py` (5) |
| TD-151 (1) | `eval/labels.json` → `regressions`; hand-run `eval/regression_check.py` | `test_regression_corpus.py` (8, synthetic twins) |
| TD-151 (2) | RM100–20,000 window in `salary_figures._salary_monthly_amount` | `test_salary_plausibility.py` (6) |
| TD-151 (3) | self-heal sweep widened past ICs; `--dry-run` | `test_reprocess_ic.py` (+4) |

Counts: api 7,478 → **7,517** passed (3 skipped); jest 3,266 → **3,269** / 195 suites.
`manage.py check` clean, `makemigrations --check` clean, `npm run gates` and `bundle-budget` green
(`/admin/login` 229 kB). Register: open 131 → **130**, defined 320; `code_health.py` td_open 130.
Eight bites, all as expected, every restore SHA-equal: user_metadata believed again → red; the
fallback without the TTL → red; the web reading user_metadata first → red (jest); not-scored back
to genuine → red; the plausibility bound removed → red; the retry back to ICs only → red; two
comment-only edits → green.

## Decisions (decisions.md 2026-10-02)

- **The fallback leans on the server's Invitation row, not on `temp_password_issued_at`.** The
  brief said "within the TTL"; the TTL clock in `user_metadata` is written by the attacker in the
  same call as the flag, so it proves nothing. `Invitation.expires_at` is the server's copy of the
  same clock (invite and Resend move both).
- **Not-scored is a floor, not a step** — the approved 2026-06-13 design says "Probable at most",
  and an unscored document has no score to step by.
- **The re-score could not be free.** Read from the code: the IC scorer is a Gemini read, the
  slip's adds a Gemini visual read, and no OCR text is stored for these types. So the command
  counts, and the paid re-read is the owner's question (TD-114 → Owner-decision).

## What went well

- `verdict_engine.py` was AT its allowance; moving the whole ladder out first (189 lines, verified
  byte-identical after line-ending normalisation) let TD-114 land in the smaller module and lowered
  the ledger 1146 → 984 rather than raising anything.
- The plausibility bounds were measured, not chosen: 88 readable payslips in the local corpus
  (RM357.22 – RM9,900.04) against #66's RM32,600 misread.

## What bit

- **`sed` in Git Bash strips the `\r`.** The first moves-only comparison said "differ" at the end of
  line 1; it was the extraction tool, not the move. Compared in Python with line endings normalised.
- **A test assumption about `'0'`.** `_salary_monthly_amount({'gross_income': '0'})` was already
  None (gross 0 falls through to a missing net), so a "zero keeps its meaning" test was wrong and
  was dropped rather than bent.
- **INCIDENT after the deploy: the widened sweep OOM-looped the api.** At 06:00, 07:00 and 08:00
  UTC the hourly `reprocess-ic-vision` run killed the instance (2140 MiB against 2048) on one 2 MB
  scan-to-PDF salary slip: an unbounded 200 DPI raster of page 1, and no stamp written before the
  kill, so the same row was re-picked every hour. Neither the build nor the review could see it —
  no fixture had a large page box, and the loop guard was an `except` a process kill never reaches.
  Job paused; fixed by a pixel budget on the raster and a stamp written before each read
  (CHANGELOG 2026-10-02, lessons.md).

## Review round (2026-10-02): no HIGH/MEDIUM, four LOW, all fixed

- **F1:** the sweep's "stamp-less" fixture carried a stamp, so it proved nothing; a live row with
  stored fields and both stamps NULL would have been re-read and overwritten. The predicate now also
  requires `vision_fields` empty, and the fixture is truly stamp-less with fields.
- **F2:** the cron's `user_metadata` branch had no end date, so a stolen session could forge an old
  clock and lock the owner out for ever. It now ends on the same 2026-11-01 date.
- **F3:** Income's exemption from the not-scored floor is now stated as a choice, with its owner
  question; the gating plan's status says what is true.
- **F4:** (a) the Check-2 facts ledger will read "reported" instead of "verified" for name /
  qualification / pathway on the affected applications (the review counted 37) — officer-facing
  wording, no copy change; (b) the payslip window is pinned as applying BEFORE the SGD conversion;
  (c) `rescore_unscored_documents` counts the latest document per application and type, as the
  verdict reads them, beside every live row; (d) a jest test for the admin login's `app_metadata`-
  first read.

## Left, and why

- TD-114: re-reading the old unscored uploads (paid) and an officer "not checked" line (copy) —
  owner questions.
- TD-323: the cockpit's Amount chip still reads green on a figure the engine refuses (net > gross
  too, since #66), and the EPF-implied salary has no window (five statements are too few to set one).
- #140 and #73 are named in the corpus but not in the local snapshots; #73's IC-digit misread has no
  bounded fix.
