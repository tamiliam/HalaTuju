# Code health

Readings taken by `Settings/_tools/code_health.py`; decisions recorded per
`Settings/_workflows/code-health-audit.md`. The tool writes **Trend** and **Latest run**; people
write **Reviews**. A WARN is an absolute threshold crossed (the triage list). A FAIL is a reading
that got WORSE than the last run by more than a tolerance — the only thing that blocks a close.

Run: `python Settings/_tools/code_health.py --project . --write` (add `--full` at sprint close).

**The plan that acts on these readings:** `docs/plans/2026-09-18-code-health-roadmap.md` (nineteen sprints, six phases, run back to back under a development freeze; awaiting the owner's word to start H1).

## Trend
| date | sha | days | fix% | hot#1 | big | long | dup | xapp | supp | skip | guard% | td_open | unused | tsc | i18n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-18 | 257fcd4 | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | 17 | 85 | 0 | - | - |
| 2026-09-18 | 1bef45b | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | 17 | 83 | 0 | 0 | ok |
| 2026-09-18 | 2e3cd2b | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 2 | 17 | 83 | 4 | 0 | ok |
| 2026-09-18 | b0c2687 | 90 | 41 | views_admin.py 285.4 | 25 | 16 | 10 | 132 | 139 | 2 | 17 | 84 | 4 | 24 | ok |

## Latest run (2026-09-18, 257fcd4, window 2026-06-20 onward)

### Hotspots (fixes x KLOC — where the next bug is most likely)
| file | fixes | lines | score |
|---|---|---|---|
| `halatuju_api/apps/scholarship/views_admin.py` | 34 | 8547 | 290.6 |
| `halatuju-web/src/lib/admin-api.ts` | 25 | 4099 | 102.5 |
| `halatuju_api/apps/scholarship/services.py` | 32 | 2931 | 93.8 |
| `halatuju_api/apps/scholarship/income_engine.py` | 29 | 3187 | 92.4 |
| `halatuju_api/apps/scholarship/emails.py` | 14 | 4242 | 59.4 |
| `halatuju-web/src/lib/officerCockpit.ts` | 28 | 1634 | 45.8 |
| `halatuju_api/apps/scholarship/vision.py` | 18 | 2321 | 41.8 |
| `halatuju_api/apps/scholarship/views.py` | 17 | 2421 | 41.2 |
| `halatuju-web/src/app/admin/scholarship/[id]/view.tsx` | 7 | 3587 | 25.1 |
| `halatuju_api/apps/scholarship/models.py` | 5 | 4756 | 23.8 |

### Fix ratio
- 301 fix / 430 feat commits since 2026-06-20

### Files over 1000 lines
- `8547  halatuju_api/apps/scholarship/views_admin.py`
- `4756  halatuju_api/apps/scholarship/models.py`
- `4242  halatuju_api/apps/scholarship/emails.py`
- `4099  halatuju-web/src/lib/admin-api.ts`
- `3587  halatuju-web/src/app/admin/scholarship/[id]/view.tsx`
- `3187  halatuju_api/apps/scholarship/income_engine.py`
- `2931  halatuju_api/apps/scholarship/services.py`
- `2468  halatuju-web/src/lib/api.ts`
- `2421  halatuju_api/apps/scholarship/views.py`
- `2377  halatuju_api/apps/courses/views.py`
- `2321  halatuju_api/apps/scholarship/vision.py`
- `1942  halatuju-web/src/components/ScholarshipDocuments.tsx`
- `1634  halatuju-web/src/lib/officerCockpit.ts`
- `1371  halatuju_api/apps/courses/stpm_quiz_data.py`
- `1371  halatuju-web/src/app/profile/page.tsx`
- `1368  halatuju_api/apps/courses/models.py`
- `1328  halatuju-web/src/lib/scholarship.ts`
- `1284  halatuju_api/apps/scholarship/verdict_engine.py`
- `1244  halatuju_api/apps/courses/views_admin.py`
- `1214  halatuju_api/apps/scholarship/serializers_admin.py`
- `1195  halatuju_api/apps/scholarship/serializers.py`
- `1155  halatuju_api/apps/scholarship/contracts.py`
- `1142  halatuju-web/src/app/scholarship/apply/page.tsx`
- `1061  halatuju_api/apps/scholarship/org_requests.py`
- `1023  halatuju_api/apps/scholarship/profile_engine.py`

### Python functions of 150+ lines
- `333  halatuju_api/apps/courses/ranking_engine.py:379 calculate_fit_score`
- `312  halatuju_api/apps/scholarship/views.py:1008 post`
- `306  halatuju_api/apps/scholarship/vision.py:2009 _run_field_extraction_impl`
- `293  halatuju_api/apps/courses/management/commands/backfill_spm_field_key.py:22 classify_course`
- `290  halatuju_api/apps/courses/engine.py:569 check_eligibility`
- `245  halatuju_api/apps/courses/views.py:118 get`
- `244  halatuju_api/apps/courses/management/commands/classify_stpm_fields.py:296 classify_stpm_course`
- `214  halatuju_api/apps/scholarship/verdict_engine.py:405 _verdict_income`
- `192  halatuju_api/apps/scholarship/services.py:1765 autofill_pathway_from_offer`
- `189  halatuju_api/apps/scholarship/verdict_engine.py:621 _verdict_income_salary`
- `183  halatuju_api/apps/courses/views_admin.py:641 post`
- `177  halatuju_api/apps/scholarship/resolution.py:235 doc_match_verdict`
- `169  halatuju_api/apps/courses/management/commands/sync_stpm_mohe.py:37 handle`
- `155  halatuju_api/apps/courses/views.py:1000 get`
- `152  halatuju_api/apps/scholarship/help_engine.py:334 verdict_for_document`
- `151  halatuju_api/apps/scholarship/bursary.py:129 render_agreement_html`

### Function names with 3+ homes in one app
- _money x7 (scholarship): doc_parse.py, invoice_parsers.py, invoicing.py, import_vircle_csv.py, payments.py, sponsor_comms.py, sponsorship.py
- _any x4 (scholarship): electricity_doc.py, salary_doc.py, school_leaving_doc.py, water_doc.py
- _ids x4 (scholarship): award_students_batch.py, send_award_offer_emails.py, send_sign_invitation_emails.py, send_vircle_install_emails.py
- _norm x4 (scholarship): academic_engine.py, bc_parse.py, funding_estimate.py, results_doc.py
- _digits x3 (scholarship): import_vircle_csv.py, offer_parse.py, vircle_airtable.py
- _gemini_generate x3 (scholarship): apply_copy_draft.py, contracts.py, sponsor_terms.py
- banned_phrases x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py
- render x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py
- score_markers x3 (scholarship): electricity_doc.py, school_leaving_doc.py, water_doc.py
- unknown_placeholders x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py

### Cross-app imports
- courses -> scholarship: 25
- reports -> courses: 2
- reports -> scholarship: 2
- scholarship -> courses: 104

### Suppressions
- # noqa: 80
- # type: ignore: 15
- : any: 2
- eslint-disable: 42

### Skipped tests
- none

### Source-text guard tests (web)
- 24 of 140 web test files read source text

### Debt register
- 148 entries have a defining line; 85 carry no resolution marker on it

### Debt register near-misses — read these by eye
- line 355: ### [TD-003] Zero frontend tests (LOW RISK) — PARTIALLY RESOLVED
- line 4013: ### [TD-252] An award nobody answers stays open for ever; a test/abandoned case cannot be closed — medium

### Unused npm dependencies
- none

## Reviews

_Decisions per run, newest first. Written by a person or the agent — never by the tool._

### 2026-09-18 (fourth reading) — H2 closed: the gate is live; nothing in the code moved

Plain run after sprint H2 (config and one test file — no source changed). No FAILs.
- **td_open 83 → 85** — *expected.* Two entries raised by the sprint: **TD-255** (production
  builds on Node 18, past end of life; the dev box runs 24) and **TD-256** (an api test reads a
  docs file the api trigger ignores). Near-miss list unchanged and read: TD-003, TD-252 open is right.
- Not a reading the tool takes, but the point of the sprint: **tests now run before every deploy**
  (6,714 pytest + 2,354 jest in the first gated builds). First row of the roadmap's targets: done.
- All other readings unchanged; decisions stand as in the baseline.

### 2026-09-18 (third reading) — H1 closed: `unused` 4 → 0, `skip` 2 → 0

After sprint H1 of the roadmap. `--full`. No FAILs; nothing else moved.
- **unused 4 → 0** — *done.* Four packages removed, each proven unimported; `next build` exits 0.
- **skip 2 → 0** — *done.* One dead skip branch deleted; the email golden's regenerate mode now
  fails the run rather than skipping it. Three *runtime* skips remain and are honest: "real corpus
  not present on this machine".
- **A flaky test surfaced in the clean-room run** and was fixed (a sentinel a timestamp could
  contain). Not a reading the tool takes; noted because from H2 a flaky test blocks a deploy.
- All other WARNs unchanged; decisions stand as in the baseline.

### 2026-09-18 (second reading) — the type check is a gate again: tsc 24 → 0

Taken after the first act on the baseline (TD-221 closed). No FAILs.
- **tsc 24 → 0** — *done.* No suppressions. Seven config, fourteen test-side, three a real app-type
  drift (`StrCheck.current_status`). Any tsc error is now a regression: tolerance is zero.
- **td_open 84 → 83** — TD-221 carries its marker.
- **hot#1 +5.2 and xapp +1** — *accept.* Both came from another sprint's commits (Overview phase 2
  Sprint A) landing between the two readings, not from this change. Inside tolerance.
- Everything else unchanged; decisions stand as in the baseline below.

### 2026-09-18 — baseline: the bugs land in eight files, and nothing was measuring that

First reading. Nothing can FAIL on a first run, so every line below is a WARN read for the first
time. **No app code was changed** — the owner's ruling was *measure only*.

**Where the next bug is most likely (fixes in 90 days x size).** This is not blame; it is where a
test, a split or a choke-point pays back first.
1. `apps/scholarship/views_admin.py` — fixed **34 times** in 90 days and **8,393 lines** long. Its
   score (285) is nearly three times the next file. No person or agent can hold it in one head.
2. `halatuju-web/src/lib/admin-api.ts` — 25 fixes, 4,008 lines, imported by ~109 files: a change
   here touches a quarter of the web app.
3. `apps/scholarship/services.py` — 32 fixes, 2,931 lines.
4. `apps/scholarship/income_engine.py` — 29 fixes, 3,187 lines. Same family as TD-235 (the income
   rule has four homes).
5. `apps/scholarship/emails.py` — 14 fixes, 4,242 lines.
6. `halatuju-web/src/lib/officerCockpit.ts` — 28 fixes in 1,634 lines: the **densest** fix rate on
   the web side. Request #24 (today) was one of them.
7. `apps/scholarship/vision.py` and `views.py` — 18 and 17 fixes.
8. `admin/scholarship/[id]/view.tsx` — 3,587 lines, the largest component, 7 fixes.

**Decisions on the readings**
- **fix% 41** (300 fixes to 430 features; `refactor:` is 20 commits since June) — *accept as the
  baseline.* Four fixes for every six features is the owner's observation, in a number. It is the
  reading to watch; the ratchet FAILs at 47.
- **big 25 / long 16** — *accept as baseline; do not split files for the sake of a number.* A split
  is promoted only when a hotspot above is next touched by a sprint. Ratchet holds the line.
- **dup 10** — *candidate TD, owner to pick.* `_money` has **seven** homes in `scholarship`
  (`doc_parse`, `invoice_parsers`, `invoicing`, `import_vircle_csv`, `payments`, `sponsor_comms`,
  `sponsorship`), and `render` / `banned_phrases` / `unknown_placeholders` are a whole template
  trio copied three times. A money-format fix made in one copy is not made in the other six. This
  is the cheapest real risk on the list and it touches money — so it is a sprint, not a small change.
- **xapp 132** — `scholarship -> courses` 103 and the back-edge `courses -> scholarship` 25. *Accept;*
  the back-edge is the one to watch.
- **supp 139** — 80 `# noqa` (mostly the deliberate "a mirror must never break the write" broad
  excepts), 42 `eslint-disable` (33 are `exhaustive-deps`). *Accept as baseline.*
- **skip 2** — both golden-master tests skip themselves on the run *after* their baseline is
  regenerated: the least-supervised moment passes green. *Candidate TD, low.*
- **guard% 17** — 24 of 138 web tests assert on source TEXT. Some are right (brand, i18n). But
  today's #24 guard cried wolf on a CRLF and an earlier one was decorative. *Accept; watch.*
- **unused 4** — `next-intl`, `react-hook-form`, `tailwind-merge`, `@supabase/ssr`. *Candidate, 15 min.*
- **tsc 24** — ⚠ **new fact: all 24 errors are in TEST files (9 of them); the app code has none.**
  TD-221 calls this gate a no-op. It is one jest-types fix away from being a real gate at zero.
  *Candidate, promoted to the top of the list below.*
- **td_open 84 of 146 defined.** The hand count on this date said 86 of 140. The tool finds six
  more definitions (headings shaped `### ✅ [TD-197 — RESOLVED …]`, which the hand rule skipped)
  and reads four `— RESOLVED` titles with no date as resolved (TD-002, -015, -017, -213). Near-misses
  read by eye: TD-003 (*partially* resolved — open is right) and TD-252 (open is right).

**Gate holes found by the survey — candidates for the owner, none done here**
1. `tsc` fails on 24 test-file errors, so nobody reads it (TD-221). Fix the 9 test files → a real gate.
2. `package.json` has no `test` or `typecheck` script; `scripts/check-i18n.js` is wired to nothing.
   The four web gates exist only as lines in `CLAUDE.md`.
3. Nothing runs tests before a deploy: the api image build runs `collectstatic`, the web build runs
   `next build`. A red suite can ship.
4. `requirements.txt` pins by range, has no lock file, and does not list `pytest` — two builds a week
   apart install different code, and a fresh clone cannot run the suite.
5. Four unused npm packages.
6. No coverage is configured on either side, so "is this file tested?" has no answer.
