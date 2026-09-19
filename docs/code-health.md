# Code health

Readings taken by `Settings/_tools/code_health.py`; decisions recorded per
`Settings/_workflows/code-health-audit.md`. The tool writes **Trend** and **Latest run**; people
write **Reviews**. A WARN is an absolute threshold crossed (the triage list). A FAIL is a reading
that got WORSE than the last run by more than a tolerance — the only thing that blocks a close.

Run: `python Settings/_tools/code_health.py --project . --write` (add `--full` at sprint close).

**The plan that acts on these readings:** `docs/plans/2026-09-18-code-health-roadmap.md` (nineteen sprints, six phases, run back to back under a development freeze; awaiting the owner's word to start H1).

## Trend
| date | sha | days | fix% | hot#1 | big | long | dup | xapp | supp | skip | mirror | guard% | td_open | unused | tsc | i18n | std |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-19 | 9c5024a | 90 | 42 | views_admin.py 273.8 | 25 | 15 | 4 | 133 | 139 | 0 | 41 | 15 | 86 | 0 | - | - | ok |
| 2026-09-19 | b7a1350 | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 84 | 0 | - | - | ok |
| 2026-09-19 | 981ac18 | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 84 | 0 | - | - | ok |
| 2026-09-19 | 93761ad | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 83 | 0 | - | - | ok |
| 2026-09-19 | 7977547 | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 84 | 0 | - | - | ok |
| 2026-09-19 | 88c93f0 | 90 | 41 | views_admin.py 273.5 | 25 | 16 | 10 | 133 | 139 | 0 | - | 11 | 83 | 0 | 0 | ok | ok |
| 2026-09-19 | 13274d7 | 90 | 41 | views_admin.py 273.5 | 25 | 16 | 10 | 133 | 139 | 0 | - | 10 | 84 | 0 | 0 | ok | ok |
| 2026-09-19 | 5fbc6e1 | 90 | 41 | views_admin.py 273.5 | 25 | 16 | 10 | 133 | 139 | 0 | - | 18 | 83 | 0 | - | - | ok |
| 2026-09-19 | 1c24748 | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 18 | 83 | 0 | 0 | ok | ok |
| 2026-09-18 | 08ee0ce | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 83 | 0 | - | - | - |
| 2026-09-18 | cc4406f | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 84 | 0 | 0 | ok | - |
| 2026-09-18 | 257fcd4 | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 85 | 0 | - | - | - |
| 2026-09-18 | 1bef45b | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 83 | 0 | 0 | ok | - |
| 2026-09-18 | 2e3cd2b | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 2 | - | 17 | 83 | 4 | 0 | ok | - |
| 2026-09-18 | b0c2687 | 90 | 41 | views_admin.py 285.4 | 25 | 16 | 10 | 132 | 139 | 2 | - | 17 | 84 | 4 | 24 | ok | - |

## Latest run (2026-09-19, 9c5024a, window 2026-06-21 onward)

### Hotspots (fixes x KLOC — where the next bug is most likely)
| file | fixes | lines | score |
|---|---|---|---|
| `halatuju_api/apps/scholarship/views_admin.py` | 32 | 8556 | 273.8 |
| `halatuju-web/src/lib/admin-api.ts` | 26 | 4103 | 106.7 |
| `halatuju_api/apps/scholarship/income_engine.py` | 30 | 3201 | 96 |
| `halatuju_api/apps/scholarship/services.py` | 31 | 2946 | 91.3 |
| `halatuju_api/apps/scholarship/emails.py` | 14 | 4242 | 59.4 |
| `halatuju-web/src/lib/officerCockpit.ts` | 30 | 1622 | 48.7 |
| `halatuju_api/apps/scholarship/vision.py` | 18 | 2321 | 41.8 |
| `halatuju_api/apps/scholarship/views.py` | 17 | 2421 | 41.2 |
| `halatuju-web/src/app/admin/scholarship/[id]/view.tsx` | 9 | 3599 | 32.4 |
| `halatuju_api/apps/scholarship/models.py` | 5 | 4756 | 23.8 |

### Fix ratio
- 303 fix / 424 feat commits since 2026-06-21

### Files over 1000 lines
- `8556  halatuju_api/apps/scholarship/views_admin.py`
- `4756  halatuju_api/apps/scholarship/models.py`
- `4242  halatuju_api/apps/scholarship/emails.py`
- `4103  halatuju-web/src/lib/admin-api.ts`
- `3599  halatuju-web/src/app/admin/scholarship/[id]/view.tsx`
- `3201  halatuju_api/apps/scholarship/income_engine.py`
- `2946  halatuju_api/apps/scholarship/services.py`
- `2488  halatuju-web/src/lib/api.ts`
- `2421  halatuju_api/apps/scholarship/views.py`
- `2321  halatuju_api/apps/scholarship/vision.py`
- `2309  halatuju_api/apps/courses/views.py`
- `1957  halatuju-web/src/components/ScholarshipDocuments.tsx`
- `1622  halatuju-web/src/lib/officerCockpit.ts`
- `1375  halatuju_api/apps/courses/models.py`
- `1371  halatuju_api/apps/courses/stpm_quiz_data.py`
- `1371  halatuju-web/src/app/profile/page.tsx`
- `1332  halatuju-web/src/lib/scholarship.ts`
- `1246  halatuju_api/apps/courses/views_admin.py`
- `1229  halatuju_api/apps/scholarship/serializers_admin.py`
- `1195  halatuju_api/apps/scholarship/serializers.py`
- `1151  halatuju_api/apps/scholarship/verdict_engine.py`
- `1145  halatuju_api/apps/scholarship/contracts.py`
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
- `210  halatuju_api/apps/scholarship/verdict_engine.py:467 _verdict_income`
- `192  halatuju_api/apps/scholarship/services.py:1765 autofill_pathway_from_offer`
- `183  halatuju_api/apps/courses/views_admin.py:643 post`
- `177  halatuju_api/apps/scholarship/resolution.py:235 doc_match_verdict`
- `169  halatuju_api/apps/courses/management/commands/sync_stpm_mohe.py:37 handle`
- `155  halatuju_api/apps/courses/views.py:1000 get`
- `152  halatuju_api/apps/scholarship/help_engine.py:334 verdict_for_document`
- `151  halatuju_api/apps/scholarship/bursary.py:129 render_agreement_html`

### Function names with 3+ homes in one app
- _gemini_generate x3 (scholarship): apply_copy_draft.py, contracts.py, sponsor_terms.py
- banned_phrases x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py
- render x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py
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

### Front-end rules mirrored from the backend with no drift test
- 19 of 60 mirror claims in src/lib name a drift test
- halatuju-web/src/lib/admin-api.ts:887  Server-computed first-assign readiness (services.is_ready_for_assignment): all student tas
- halatuju-web/src/lib/admin-api.ts:1249  Admin-facing resolution item. Mirrors the student-facing ResolutionItem in src/lib/api.ts 
- halatuju-web/src/lib/admin-api.ts:2917  Advisory: has Vircle activated this eWallet (mirrored from the relay sheet)? A false value
- halatuju-web/src/lib/admin-api.ts:2962  One student's line in the Payments funding summary. Mirrors the backend's FundingSummaryRo
- halatuju-web/src/lib/api.ts:1692  The organisation's booking grid, SERVED (Org Config Sprint D). The student panel reads onl
- halatuju-web/src/lib/api.ts:2437  Accept or decline the award. A minor's guardian must accept (name + relationship + NRIC), 
- halatuju-web/src/lib/branding.ts:29  What a tenant may tint. Mirrors `TENANT_FAMILIES` in `apps/courses/theme_tokens.py`. */
- halatuju-web/src/lib/branding.ts:172  Substitute `{var}` placeholders in a message string. Mirrors the old `i18n.tsx` engine exa
- halatuju-web/src/lib/clauseNumbering.ts:1  Contract clause numbering — MIRROR of `contracts.clause_numbers` / `contracts.normalise_le
- halatuju-web/src/lib/contrast.ts:1   The contrast check, in the browser — Layer 1 A2.  ⚠ THIS IS NOT THE GATE. `apps/courses/c
- halatuju-web/src/lib/contrast.ts:27  The platform surfaces, per mode. `white` and `ground-0` are separate on purpose — `text-wh
- halatuju-web/src/lib/documentHelp.ts:53   Does this document have a soft problem worth a coach note? Mirrors the "non-good" states 
- halatuju-web/src/lib/familyRoster.ts:1  Structured family roster (the "About your family" redesign, 2026-06). Mirrors halatuju_api
- halatuju-web/src/lib/familyRoster.ts:44  Professions that do NOT earn income — mirror of family.NON_EARNING. Used to prefill the in
- halatuju-web/src/lib/familyRoster.ts:104  A person's NAME may contain letters, spaces, and the connectors that appear in Malaysian n
- halatuju-web/src/lib/incomeWizard.ts:1  Pure mirror of the backend income requirement engine (apps/scholarship/income_engine). Kep
- halatuju-web/src/lib/incomeWizard.ts:72  Malaysian patronymic connectors (A/L, A/P, S/O, D/O, bin, binti, @). A name that carries o
- halatuju-web/src/lib/incomeWizard.ts:99  Compulsory (mirrors income_engine.salary_member_blocks): IC → relationship doc. Income its
- halatuju-web/src/lib/invitations.ts:12  What an invitation is doing. Mirrors `invitations.status_of` — the server is the authority
- halatuju-web/src/lib/navigation.ts:255  The organisation's own settings, mirroring Programme → Configuration one level up (owner, 
- halatuju-web/src/lib/navigation.ts:479   Should the Programme group be hidden right now?  Owner, 2026-09-14: the Programme section
- halatuju-web/src/lib/officerCockpit.ts:308   Tone for a utility-bill ADDRESS check. Mirrors the backend's weighted matcher + officer-f
- halatuju-web/src/lib/officerCockpit.ts:479  IC No: an EPF statement always carries the member's number; a salary slip only sometimes (
- halatuju-web/src/lib/officerCockpit.ts:1127   A `shortlisted` application is PRE-SUBMISSION by definition — submitting Step 2 is exactl
- halatuju-web/src/lib/officerCockpit.ts:1183   Show the Interview Stage box?  The pre-submission half is `showsPostSubmissionCards` (no 
- halatuju-web/src/lib/partnerComms.ts:12   The emails, in the order the card lists them. Mirrors `partner_comms.KINDS`.  `student_as
- halatuju-web/src/lib/poolCard.ts:47   The single lifecycle badge on a sponsored-student card, as token classes.  ⚠ THIS USED TO
- halatuju-web/src/lib/requestStatus.ts:148   The Requests COMPONENT tree (Sprint 15.1) — the FE mirror of models.REQUEST_COMPONENT_TRE
- halatuju-web/src/lib/requestStatus.ts:182  Every valid component VALUE (parents + `${parent}_${sub}` children). Mirrors VALID_COMPONE
- halatuju-web/src/lib/reviewerDetail.ts:1   Reviewer detail — the pure decisions behind `/admin/organisation/reviewers[/id]` (#10, 20
- halatuju-web/src/lib/reviewerProfile.ts:3   Client mirror of the backend `reviewer_onboarding.reviewer_profile_complete` — which comp
- halatuju-web/src/lib/scholarship.ts:64  Mirrors the onboarding state list (onboarding/profile/page.tsx). Static — a fixed set of M
- halatuju-web/src/lib/scholarship.ts:205  ── Plans redesign: eligible-pathway dropdown (context-aware Plans step) ── Display order f
- halatuju-web/src/lib/scholarship.ts:376  A ranked course choice (rank derived from array order). Sourced from the student's saved c
- halatuju-web/src/lib/scholarship.ts:708   The caller's ONE live application, or null when that question has no single answer.  The 
- halatuju-web/src/lib/scholarship.ts:1154   How a document card presents the file(s) it holds: - `none` — nothing uploaded yet; the c
- halatuju-web/src/lib/sponsor-supabase.ts:10   Separate Supabase client for sponsor auth (mirrors the admin client pattern). Its own sto
- halatuju-web/src/lib/sponsorComms.ts:1   Sponsor comms — the pure decisions behind the Emails panel (S3, 2026-07-28).  The twin of
- halatuju-web/src/lib/sponsorDetail.ts:1   Sponsor detail — the pure decisions behind `/admin/sponsors/[id]` (2026-07-27).  The serv
- halatuju-web/src/lib/sponsorTerms.ts:25  A checkpoint is complete when it would survive the server's Q2 rule: three non-blank optio
- halatuju-web/src/lib/sponsorTerms.ts:111   Clearing the quiz flag WIPES the payloads, mirroring `replace_sections` on the server.  D

### Source-text guard tests (web)
- 22 of 150 web test files read source text (signals: readFileSync, apiSource)

### Debt register
- 156 entries have a defining line; 86 carry no resolution marker on it

### Debt register near-misses — read these by eye
- line 401: ### [TD-003] Zero frontend tests (LOW RISK) — PARTIALLY RESOLVED
- line 5007: ### [TD-252] An award nobody answers stays open for ever; a test/abandoned case cannot be closed — medium

### Unused npm dependencies
- none

### Standards budgets vs the last recorded run
- budgets no looser than at b7a1350

## Reviews

_Decisions per run, newest first. Written by a person or the agent — never by the tool._

### 2026-09-19 (ninth reading) — H9: the decision gates are drift-tested

`--full`, read-only (the reading itself is the lead's `--write`). **No FAILs.** No production code
changed — six drift test files, one shared test reader, seventeen comment blocks marked.
- **`mirror` — NEW READING, 41.** Front-end `src/lib` comments claiming a rule is mirrored, with no
  `drift-test:` marker. Added by this sprint at the roadmap's request, written to the same
  definition as `codeStandards.test.ts`, which is the authority; both read 41 on the day, so the
  tool's trend and the in-repo ledger are the same number. *Decision: promote* — H10's work list.
- **`unguarded_mirrors` 58 → 41** in `budget` (`baseline` untouched). The six rules H9 named were
  seventeen ledger entries; "rules" and "entries" are different units and the roadmap now says so.
- **`guard% 11 → 15` (+4, inside tolerance).** Two things, and only one of them is code.
  (a) Six new tests read the backend's source on purpose — that IS the H9 end state, and for a
  module-level constant it is the right instrument (a served constant could only fail at runtime;
  this fails in the deploy gate). *Accept, with the reason recorded in `docs/decisions.md`.*
  (b) The metric's definition was **widened** in the same sprint: it matched the literal
  `readFileSync`, so the six new tests — which delegate to `src/test/apiSource.ts` — were invisible
  to the reading that exists to watch them. `GUARD_SIGNALS` now counts a delegated read, dated in
  the source. Part of the step is the definition catching up, not the code getting worse.
  ⚠ **H10 adds ~15–20 more such tests. If `guard%` approaches the 15% WARN line, that is the
  signal to ask which of them could be a rendered or behavioural test instead** — the drift test is
  right for a constant and wrong for anything with a seam.
- **`td_open` +2** — TD-264 (medium, money path: the api and the web disagree on what a *digit* is
  on the payout account, and the api is the permissive side) and TD-263 (low). *Decision: TD-264 is
  the owner's — both candidate fixes change what the api accepts, and one of them needs a count of
  stored rows first.* Neither was found by a reading; both fell out of characterising before
  guarding, which is now three sprints running (H7's `_money`, H8's eleven homes, this).
- All other readings delta 0; `std` ok.

### 2026-09-19 (eighth reading) — TD-262 chunks 1–3 shipped

Plain run. No FAILs. Every reading delta 0 — the income work added small modules instead of growing
listed files (`docCategory.ts`, `incomeShown.ts`, `income_shown.py`).
- **Three files are at the edge of their allowance, and one function:** `src/lib/api.ts` (1 line
  left), `doc_parse.py` (1), `_verdict_income_salary` (1 of its +10), `view.tsx` (8). *Decision:
  promote* — H13 (api barrels) and H14 (cockpit panels) are the planned cures; `verdict_engine`'s
  salary branch wants splitting before TD-262 chunk R4 touches it.

### 2026-09-19 (seventh reading) — H8: Phase A delivered, Phase B stopped at its gate

Plain run. No FAILs. **No production code changed** — two characterisation test files.
- **td_open → +1** — **TD-262 (HIGH, eligibility):** the income rule has eleven homes, not four, and
  they disagree in sixteen places today. *Decision: owner's, step by step — every fix moves an
  eligibility answer.* This is the largest finding the arc has produced, and no reading could have
  found it: the numbers measure shape; only running the homes side by side measures agreement.
- **guard%** — one new web test reads source, to pin three module-private maps that have no seam.
  *Accept* — they are ledger pins, to be replaced by rendered tests once the owner rules.
- All other readings delta 0.

### 2026-09-19 (sixth reading) — TD-261 closed (on the owner's order)

Plain run. No FAILs. Not a roadmap sprint.
- **td_open 84 → 83** — TD-261 closed: five defects in money/figure helpers and three oddities,
  each fixed by EDITING its pinned characterisation row and seeing it red first.
- **`std` ok** — `doc_parse.py` 669 → 688 of 689 allowed: **one line of headroom left.** The next
  change to it splits the file first. Same standing as `src/lib/api.ts`.
- All other readings unchanged.

### 2026-09-19 (fifth reading) — H7 closed: `dup` 10 → 4

Plain run after sprint H7. No FAILs.
- **dup 10 → 4** — *done, and the four that remain are ACCEPTED, permanently.* `_gemini_generate` ×3
  are the metering seams tenancy rule 6 names; `render` / `banned_phrases` /
  `unknown_placeholders` ×3 are one engine and two thin per-audience adapters. The reading will
  keep WARNing at 4; that WARN is decided — do not chase it to zero by renaming adapters. The
  roadmap's target ("0 true duplicates") is met.
- **td_open 83 → 84** — **TD-261**: five defects in money/figure helpers found by characterising
  today's behaviour. *Decision: owner's — they change what money code returns.*
- **`std` ok** — six names left the budget; it tightened.
- All other WARNs unchanged; decisions stand as in the baseline.

### 2026-09-19 (fourth reading) — TD-254 + TD-259 closed (security, on the owner's order)

`--full`. No FAILs. Not a roadmap sprint; read because it touched the auth seam.
- **td_open 84 → 83** — TD-254 and TD-259 closed; **TD-260** raised (604 of 674 IC-holding students
  have no verified contact and support has no screen to help — two owner levers).
- **guard% 10 → 11** — *accept.* One new source-reading test, and it is a drift test between the
  api's refusal codes and the web's copy map — the kind the standards ask for.
- **`std` ok** — one budget moved and it tightened (`courses/views.py` 2,377 → 2,309).
- Flagged by the build, for the next sprint that touches it: `src/lib/api.ts` has **one line** of
  its +20 allowance left. H13 (the barrel split) is the planned cure; anything sooner splits first.

### 2026-09-19 (third reading) — H6 closed: Phase 2 complete; `guard%` 18 → 10

`--full` after sprint H6. No FAILs. **The first WARN to clear since the baseline.**
- **guard% 18 → 10** — *done; target was ≤ 12.* 25 source-reading web tests became 14 of 137. Four
  stopgap guards became mounts, eleven i18n guards became one. What remains reads source on
  purpose (brand, sandbox safety, IC padlock, ICU, the navigation and screenshot disk walks,
  soft-evidence drift, the standards test, theme) and is listed in `CLAUDE.md`.
- **td_open 83 → 84** — **TD-259** raised: eight i18n keys exist in no locale; four render raw on
  the IC-claim screen. **Decision: owner's, and to be fixed WITH TD-254 — the missing text is by
  accident hiding the holder's name.** Near-misses read: TD-003, TD-252 — open is right.
- Not a reading: the web suite fell 42 s → 21 s; the cockpit went from 0 rendered tests to 59.
- All other WARNs unchanged; decisions stand as in the baseline.

### 2026-09-19 (second reading) — H5 closed: the test factory; `std` holds

Plain run after sprint H5 (test code only). No FAILs.
- **`std` ok** — the api budget gained a whole new standard (`hand_built_application_fixtures`,
  154 files → 134). The tool first read that as a loosening; it is the opposite, and the tool was
  corrected the same day: a new top-level budget key is a new standard, a new ledger member is
  still a FAIL.
- **hot#1 290.6 → 273.5** — *no decision.* No source changed; the 90-day window moved a day and
  dropped old fixes from `views_admin.py`. The fall is time, not work. H11–H12 do the work.
- Not a reading: the suite fell from 174.6 s to 122.9 s, which is three-quarters of a build-minute
  back on every api deploy.
- All WARNs unchanged; decisions stand as in the baseline.

### 2026-09-19 — H4 closed: Phase 1 complete; a new reading, `std`

`--full` after sprint H4. No FAILs.
- **`std` — new reading, ok.** Compares each `code-standards.json` budget with the copy at the last
  recorded run's commit; FAILs if a limit rose or an exemption list gained a member. First reading
  of both files, so nothing to compare yet; from here on it holds the ratchet across history, which
  the in-repo tests (depth-1 deploy checkout) cannot.
- **guard% 17 → 18** — *accept.* The web standards test reads source by nature. H6 retires four
  text guards and pays it back.
- The tool's WARN list and the standards tests now agree by construction: the tests reuse this
  tool's definitions of source, test, long function, duplicated name and suppression. `big` reads 25
  here (over 1,000 lines) and 56 in the budgets (over 600) — a different threshold, on purpose.
- All other readings unchanged; decisions stand as in the baseline.

### 2026-09-18 (fifth reading) — H3 closed: three guards in, one real hole found

`--full` after sprint H3. No FAILs. No source reading moved — the sprint added guards, not code.
- **td_open 85 → 84** — three closed (TD-219, TD-240, TD-250), two raised: **TD-257** (22 endpoints
  no test drives) and **TD-258** (HIGH — the sponsor fund view sits outside the fence, and a mock
  donation endpoint is live). Near-misses read: TD-003, TD-252 — open is right.
- **TD-258 is the reading that matters and the tool cannot take it.** Numbers find growth; this
  was found by a guard scanning a file it had excused for two months. Decision: **promote, as a
  security fix ahead of H4** — the owner's call, and the freeze allows it.
- **TD-257 — promote to Phase 2** (after the H5 factory makes each endpoint test cheap).
- All WARNs unchanged; decisions stand as in the baseline.

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
