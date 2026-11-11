# HalaTuju audit fix roadmap

> **Status (checked 2026-11-05): In progress.** Approved by the owner; waves in progress.

- **Status:** APPROVED by the owner on 2026-11-05. Each deploy group still needs its own yes.
- **Date:** 2026-11-05
- **Audit commit:** v3.1.0 (`442b21f4`)
- **Audit report:** [docs/audits/2026-11-05-project-audit.md](../audits/2026-11-05-project-audit.md) (findings, Appendix A = the TD code check)
- **Workflows:** `Settings/_workflows/implementation-planning.md`, `project-audit.md` step 7, `credit-discipline.md`

## Freeze

From audit close until this roadmap ends:

- No new features, pages or models.
- Security fixes and live-defect hotfixes are allowed.
- Lane B org-request work (#54 to #64) is separate. It is not part of this roadmap and does not count against it.
- A push to main deploys. Every deploy is owner-gated and deploys are grouped (1 to 2 a day at most).
- Migrations are applied by hand before the push that needs them.
- `docs/**` and the root CHANGELOG deploy nothing.

## Owner's goal

> "I want a comprehensive plan that improves all readings -- ie if we do an audit again in the near future, there should be substantial improvements"

So every reading below has a number to reach, and every sprint says which readings it moves and by how much.

---

## 1. Targets

### 1.1 How each reading is measured

All readings come from `Settings/_tools/code_health.py`, except the four speed numbers and `wat_lint`. There are three kinds:

- **Current-state.** The tool reads the code as it is today. The reading moves on the day the sprint merges. These are big, long, dup, xapp, supp, skip, mirror, guard%, unused, tsc and i18n.
- **Windowed.** The tool counts commits in the last 90 days (`WINDOW_DAYS=90`, merges left out). The reading lags, and old commits only drop out slowly. These are fix% and hot#1.
- **Ratchet.** The tool compares with the last recorded run. These are std and the FAIL side of every reading.

| Reading | How it is computed (short) |
|---|---|
| fix% | Commits whose subject starts `fix` ÷ (`fix` + `feat`) in the window. `refactor:`, `test:`, `docs:` and `chore:` are not counted. |
| hot#1 | Highest (fixes in the window × current KLOC) for a source file that exists today. A renamed or split path leaves the count at once. |
| big | `.py` / `.ts` / `.tsx` source files (tests excluded) over 1000 lines. |
| long | Python functions of 150 lines or more (AST, any nesting). |
| dup | A module-level function name defined in 3 or more files of one app. |
| xapp | Distinct (from app → to app, imported name) edges from top-level `apps.X` absolute imports. `import apps.courses.public` as a module counts as 1 edge. |
| supp | Bare suppressions. Python: `# noqa` without a reason, plus all `# type: ignore`. Web: every `eslint-disable`, `: any`, `as any`, `@ts-ignore`, `@ts-expect-error`. A noqa written `# noqa: CODE — reason` is not counted. **An eslint-disable is counted even when it carries a reason.** |
| skip | skip, xfail and todo in tests. |
| mirror | `src/lib` comment blocks that claim to mirror the API but have no `drift-test:` marker. |
| guard% | Web test files that read source text (`readFileSync` / `apiSource`) ÷ all web test files. `*Drift.test.ts` files are left out of both. **Lower is better** (WARN above 15%). |
| td_open | Defining lines in `technical-debt.md` with no resolution marker. A merged entry must carry a marker, for example `CLOSED (merged into TD-383)`, to leave the count. Info only, never FAIL. |
| unused | npm dependencies with no import. |
| tsc | TypeScript errors. |
| i18n | Message-key parity across en / ms / ta. |
| std | The budgets in `code-standards.json` (api and web) compared with the last recorded run. A rise or a new ledger member is a FAIL. A tightening is fine. A split must write a `_moved` record (`{ledger, from, to}`) or it reads as a new member. |

### 1.2 Targets table

"Now" is the audit reading at v3.1.0. "Target" is what the next full audit must show.

| Reading | Now | Target at next audit | How fast it can move | Sprints that move it |
|---|---|---|---|---|
| fix% | 51% (333 fix / 321 feat), WARN 3rd time | ≤ 60%, plus the commit-type rule in force and TD-385 decided. See note A. | Windowed and lagging. In a freeze, feat ≈ 0, so the ratio rises by construction. | A0.2 (rule), A4.7 (TD-385), every sprint (prefix discipline) |
| hot#1 | 32.4 (`vision.py`, 14 fixes × 2.3 KLOC) | < 20. Every one of today's top 5 under 15. | Drops at once when the path is split (old path leaves the count). New files score only from new fixes. See note B. | A3.1, A3.2, A3.3, A3.4 |
| big | 13 files > 1000 lines | ≤ 6 (`stpm_quiz_data.py` may stay; it is data) | Current-state, moves on merge | A3.1 to A3.9 |
| long | 15 functions ≥ 150 lines | ≤ 5 | Current-state | A3.1, A3.2, A3.4 to A3.8, A3.10 |
| dup | 4 names | 0 | Current-state | A3.11 |
| xapp | 85 edges (scholarship→courses 54, courses→scholarship 19, reports→courses 8, reports→scholarship 2, rest) | ≤ 50. courses→scholarship ≤ 8. Budget `courses_to_scholarship_imports` tightened 17 → ≤ 8. | Current-state | A3.12, A3.13 (plus A3.11 org resolver) |
| supp | 92 bare (noqa 38, type: ignore 11, eslint-disable 40, `: any` 2) | ≤ 30, and every remaining Python suppression carries a reason. noqa budget 80 → ≤ 45, type_ignore 11 → ≤ 2. | Current-state | A3.14, A3.15 |
| skip | 0 | 0 (hold) | Current-state | all (guard) |
| mirror | 3 (all in `incomeWizard.ts`: lines 1, 98, 125) | 0, and the guard widened past `src/lib` (TD-362) | Current-state | A3.16 |
| guard% | 11.5% (44 / 383) | ≤ 8%. See note C. | Current-state | A3.16 |
| td_open | 219 (code check: 143 open, 47 owner, 12 fixed, 6 stale, 7 merge, 4 unsure) | ≤ 110 | Moves on every register edit | A0.2 (≈ −60), then every sprint closes its TDs |
| unused | 0 | 0 (hold) | Current-state | A1.1 (re-check after Next 15) |
| tsc | 0 | 0 (hold) | Current-state | A1.1 |
| i18n | ok (7693 / 7727 keys) | ok (hold). Every sprint that adds a key adds all three. | Current-state | A4.2 |
| std | FAIL (accepted): /profile 193→195, /scholarship/application 206→209, /scholarship/apply 187→189, median 145→146.5 kB | PASS, with every web line at or below its pre-patch value (/profile ≤ 193, /application ≤ 206, /apply ≤ 187, median ≤ 145). api ledgers shrink (oversize 28 → ≤ 18, long 15 → ≤ 5, duplicated_names 4 → 0). | Ratchet. Passes at the next reading if nothing loosens. Tightening is the real goal. | A1.1, A3.9, all Wave 3 (`_moved` records) |
| wat_lint | FAIL (20 code commits since 2026-10-28 neither sprint work nor logged) | PASS | Moves on the next run | A0.2 |
| Consolidation Review | Overdue (14 pending small changes) | Done, and the next one held on time | Moves on the next run | A0.2 |
| record-verdict p95 | ≈ 50 s (17 of 23 calls over 30 s, max 51.9 s) | < 5 s | Live logs, 7 days after deploy | A2.1 |
| reprocess-ic-vision runtime | p50 200 s, p95 232–260 s, max 300 s, 5 timeouts | p95 < 120 s, 0 timeouts in 14 days | Job logs, 14 days after deploy | A2.2 |
| upload p95 | 27.2 s (p50 11.6 s, max 57.4 s) | < 10 s (p50 < 3 s) | Live logs, 7 days after deploy | A2.3 |
| assign p95 | 39–49 s | < 8 s | Live logs | A2.3 |
| bundle headroom | median 0.4 kB, /profile 0.66, /apply 0.56, /application 1.18 | ≥ 3 kB on every ledgered line, with the lines tightened as in std | `next build`, moves on merge | A1.1, A3.9 |

**Note A (fix%: an honest target).** In a freeze almost nothing is `feat`, so this ratio can only rise, whatever the code quality. The reading measures the 90-day window, not the code. The target is therefore a ceiling plus two controls:

- **The commit-type rule**, written into the project CLAUDE.md in A0.2. Use `fix:` only for a real defect repair. Use `refactor:` for structure, `test:` for test-only work, `chore:` for tooling and `docs:` for docs.
- **TD-385**, a tool change so review-round fixes stop counting as field fixes. This is a workspace change and needs owner approval (A4.7).

The next audit's Review note must say how many of the window's `fix:` commits were roadmap repairs of old debt. Also, by the accept-three-times rule, fix% is now a TD (CH-03). That TD is TD-385 plus this rule.

**Note B (hot#1: what the drop means).** Splitting a hot file drops its score at once, because the old path leaves the count. That drop is partly bookkeeping. The real proof is that no new module from a split earns more than 3 fixes in the 60 days after it. The interim reading (section 6) checks this.

**Note C (guard%: direction).** The brief asked for "guard% 12 → ≥ 25". In `code_health.py` a higher guard% is worse: it is the share of tests that read source text rather than test behaviour, and the WARN is above 15%. The target here is the other way: ≤ 8%, by turning source-reading tests into behaviour tests. Drift tests (`*Drift.test.ts`) are left out of the reading, so adding more of them is still encouraged. **The owner should confirm this reading of the target.**

---

## 2. Sprints

### Rules for every sprint

- ≤ 40 files touched. When in doubt, split.
- One build phase per agent. Builders write tests. Targeted tests while building. The full suite runs once, through `test_queue.py`, before the push.
- A fresh Sonnet reviewer reads every sprint's diff.
- Money, eligibility, identity and permission work:
  - Opus builds it.
  - An Opus adversarial review runs before the push.
  - The owner does a phone check before it goes live.
- **Refactors keep behaviour.** Write the pinning tests first (they must pass before and after). Write `_moved` records in `code-standards.json` for every split file or function. No logic change rides on a refactor sprint.
- Every sprint closes its TDs in the register with a marker, and appends to the CHANGELOG.
- Commit prefixes follow note A.

Field key: **Model** = build model. **Gates** = reviews and checks before the push. **Deploy** = deploy group (section 7).

### Wave 0 — ship what is ready, clean the register

#### A0.1 Ship sec-a and money-a

- **Goal:** Deploy the two hotfix branches already built during the audit.
- **Scope:**
  - Branch sec-a: SEC-01 / TD-512 (document record path fence, using `scholar_money.own_path`), SEC-02 / TD-513 (code half: `supabase_auth.py:156-157`), and whatever else the branch hand-back lists (SEC-03 / TD-514, SEC-04 / TD-515).
  - Branch money-a: TD-465 part 1 (`b0bedd54`: unknown course-start year no longer auto-awards RM3,000; the `award.py:58-66` stop gets its caller).
  - Anything the hand-back shows is not on a branch moves to A1.9 (SEC-03, SEC-04) or A1.13 (TD-465 part 2).
  - Added 2026-11-05 (lead, recorded here so the plan matches the build): branch td066 (owner ruled "remove the box"; web only), the `is_clean_key` guard in `org_requests_ai.py` (same fence as SEC-01, one more caller), and the audit report + this roadmap (docs). TD-510, TD-511, TD-524 logged.
  - A0.2 and A0.3 are docs only. They are in Wave 0 but not in G0. G0 = A0.1 only.
- **Acceptance:**
  - Both suites are green on the merged tip.
  - A regression test exists for each fix: a foreign storage path is refused; an unverified metadata email is refused; an STPM accept with an unknown start year gets no amount and lands at the QC stop.
- **Readings moved:** td_open −2 to −4. Security top-4 closed. fix% +2 to 3 commits.
- **Complexity:** S (already built).
- **Model:** none (review only). An Opus adversarial review, if it has not already run on both branches.
- **Gates:** Adversarial review (money, identity). Owner phone check: an upload, then an STPM accept on a test case.
- **Deploy:** G0.

#### A0.2 Register clean-up and Consolidation Review (docs only)

- **Goal:** Make the debt register true. Clear the `wat_lint` FAIL. Hold the overdue Consolidation Review.
- **Scope:**
  - **Verdict check.** A fresh Sonnet agent, not anchored on the sweeps, re-checks every FIXED, STALE and MERGE verdict in Appendix A against the code. These are:
    - FIXED: 104, 252, 326, 382, 413, 440, 470, 471, 473, 479, 481, 482
    - STALE: 278, 394, 405, 427, 433, 468
    - The merge clusters listed in the report
  - **Close and merge.** Close the confirmed entries with markers. Write a `CLOSED (merged into TD-xxx)` marker on each merged child.
  - **Settle the conflicts:**
    - TD-471: FIXED or narrowed. Sweep 5 says the `/admin/organisation` surface is still missing.
    - TD-472: OPEN or OWNER.
    - TD-252: closed into TD-198.
  - **The 4 UNSURE entries** (127, 129, 395, 478): close with a reason, or keep with a clear trigger.
  - **Index.** Regenerate the Open Items Index (RD-02 / CH-11).
  - **Consolidation Review** (CH-02):
    - Promote the clusters it names: My activity, and the request 50 / 53 pairs.
    - Turn repeating fix classes into guardrails.
    - Log the 20 unlogged commits in `consolidation-log.md`, including `1a6f8cd1` flagged as sprint-sized and `bf79bea6` as a new module.
  - **Commit-type rule** (note A): add it to the project CLAUDE.md.
  - **TD numbering:** file TD-512 to TD-523 if the report appendix has not already done it (507 to 511 stay reserved for Lane B).
- **Acceptance:**
  - `python Settings/_tools/wat_lint.py --project …` PASSes.
  - ~~The `code_health.py` td_open reading is ≤ 165.~~ Corrected 2026-11-05: the start was 233, not 219 (the audit added 14). A0.2 closed 25 with evidence, giving 208. The rest needs owner decisions or fixes in later waves. The final target (≤ 110) is unchanged.
  - The index count equals the reading.
  - Every merged child carries a marker.
- **Readings moved:** td_open 219 → ≈ 160 (−60). wat_lint FAIL → PASS. Consolidation Review overdue → done.
- **Complexity:** M (≈ 3 files, many lines).
- **Model:** Sonnet (verdict re-check). Haiku runs `wat_lint` and `code_health`.
- **Gates:** Fresh Sonnet review of the register diff.
- **Deploy:** none (docs only).

#### A0.3 Documents that are out of date (docs only)

- **Goal:** The docs say what is true today.
- **Scope:**
  - TD-522 / RD-02 / CO-02 / CO-03:
    - Bring `docs/roadmap.md` up to v3.1.0.
    - Add a table of live flag values. Values are read off the running service (`gcloud run services describe`), never from settings defaults.
  - CO-11: add a Status line to the ~92 plan files, and archive the finished ones.
  - CO-17: old roadmap leftovers.
  - Project `halatuju_api/CLAUDE.md` is 30.5k characters. Bring it under 20k by moving detail to `docs/`.
- **Acceptance:**
  - Every plan file has a Status line.
  - The flag table lists every flag with its live value and the date it was read.
  - CLAUDE.md is under 20k characters, with the Next Sprint section kept.
- **Readings moved:** td_open −1 (TD-522). CO-02, CO-03, CO-11 and CO-17 closed.
- **Complexity:** M (≈ 40 docs files; split into two passes if over).
- **Model:** Sonnet. Haiku reads the live flags.
- **Gates:** Fresh review.
- **Deploy:** none.

### Wave 1 — security and money

#### A1.1 Next 15 upgrade (audit fix 1)

- **Goal:** Clear the Next.js advisories and win back bundle room.
- **Scope:**
  - TD-506 (web half), SEC-15, CO-15.
  - Next 14.2.35 → 15.x. Next 15's App Router needs React 19, so `react` and `react-dom` move too. Testing-library is already 16.
  - 3 files use `params` / `cookies()` / `headers()` and must go async. 97 of 102 pages are client pages.
  - Re-measure the bundle. Then tighten the four web lines in `code-standards.json` to the new size + 3 kB, never above today's lines.
  - TD-321 (`images.unoptimized`, no sharp) is noted for A2.5 but not done here.
- **Acceptance:**
  - `next build` is green.
  - jest suite and `npm run gates` pass, and `mobile-check` is clean.
  - The tsc and unused readings are 0.
  - `npm audit` shows no Next advisory.
  - The web budgets are tightened, each line ≤ its pre-patch value.
- **Readings moved:** std → PASS, and the budgets go back to pre-patch or below. Bundle headroom ≥ 3 kB (likely; Next 15 may shift sizes, and A3.9 finishes the job if not). td_open −1.
- **Complexity:** L.
- **Model:** Opus (major upgrade, wide blast radius).
- **Gates:**
  - **STOP item:** a major-version upgrade needs the owner's explicit yes (already given as "audit fix 1").
  - Fresh review.
  - Owner phone check: sign-in, apply, upload, and the console on a phone.
- **Deploy:** G1 (web).

#### A1.2 Python dependency advisories

- **Goal:** Clear the pip-audit findings.
- **Scope:**
  - SEC-10 / TD-516: DRF 3.18.2, pyjwt 2.15.0, and the rest of pip-audit. Skip whatever sec-a already did.
  - SEC-16 / TD-506 (Python half): Pillow 11.3.0, pypdf 5.9.0, pillow-heif 0.22.0.
  - `requirements.lock` regenerated.
- **Acceptance:**
  - Full pytest is green.
  - pip-audit is clean (or each residue is listed with a reason).
  - A HEIC, a multi-page PDF and a JPEG upload pass the doc-recognition smoke tests, mocked (no paid re-read).
- **Readings moved:** td_open −2. SEC-10 and SEC-16 closed.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review. pyjwt is in the auth path, so an Opus adversarial read of the auth tests' diff.
- **Deploy:** G1 (api).

#### A1.3 TD-501: staff invites name a gift

- **Goal:** A reviewer invite picks its gift. NULL no longer means "every gift".
- **Scope:**
  - TD-501 / SEC-17.
  - `courses/views_staff.py` AdminInviteView, and `staff_reinvite.py:292` (`row.programme = None`).
  - The web invite form.
  - A data check of existing NULL-programme rows: owner-visible list, no silent rewrite.
- **Acceptance:**
  - An invite without a gift is refused for gift-scoped roles.
  - A re-invite keeps the gift.
  - A test proves a reviewer invited to gift A cannot read gift B.
- **Readings moved:** td_open −1. One medium security finding closed.
- **Complexity:** M.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check: invite a test reviewer to one gift, and confirm they see only that gift.
- **Deploy:** G2.

#### A1.4 TD-383 part 1: money writers re-check status under a lock

- **Goal:** No money moves on a status read earlier.
- **Scope:**
  - TD-383 (choke-point helper, e.g. `lock_application_for(app, allowed_statuses)`).
  - First TD-367: `payments.complete` re-reads the status under `select_for_update` and refuses CLOSED.
  - TD-420: tranche release reads the hold on a locked row.
  - TD-365: `fund_student` versus close race.
- **Acceptance:**
  - Concurrency tests (two transactions) prove: a CLOSED student is not paid; fund and close cannot both win; a held tranche is not released.
  - The helper is used by every money writer named in TD-383.
- **Readings moved:** td_open −4 (383 stays open until A1.5). fix% +.
- **Complexity:** L.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check: a payment run on a test case.
- **Deploy:** G2.

#### A1.5 TD-383 part 2: lifecycle writers

- **Goal:** Finished cases cannot be booked or double-submitted.
- **Scope:**
  - TD-368: `propose_slots` and `book_slot` check the status.
  - TD-348: two rounds submitted at once.
  - TD-351: a same-round double submit gives a 500. Handle the IntegrityError and return 409.
  - TD-442: wrap QC reject and reopen in one atomic block.
  - Close TD-383.
- **Acceptance:**
  - Race tests for each case.
  - A double submit gives 409, not 500.
  - A failed QC reject leaves the case where it was.
- **Readings moved:** td_open −5.
- **Complexity:** M.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check.
- **Deploy:** G2.

#### A1.6 TD-347: re-arm the sign deadline on a parent call

- **Goal:** The accept deadline cannot lapse while signing waits on the parent call (owner ruling, decisions.md:3744).
- **Scope:**
  - TD-347: `parent_call.record_call` re-arms `arm_sign_deadline`.
  - CO-04 note: in-app signing stays dark. TD-140 and TD-152 remain owner blockers.
- **Acceptance:**
  - A test: a parent call recorded on day N re-arms the deadline from N.
  - With the flag off, nothing changes.
  - This must land before `BURSARY_AGREEMENT_ENABLED` is ever set.
- **Readings moved:** td_open −1. The high money TD is closed.
- **Complexity:** M.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check (flag off: confirm nothing changes).
- **Deploy:** G3.

#### A1.7 Storage: bucket limits and no overwrite

- **Goal:** Uploads cannot overwrite or smuggle files.
- **Scope:**
  - TD-467 / SEC-18 (SEC-07 folded in).
  - Set the private bucket's `allowed_mime_types` and `file_size_limit` (migration or Supabase setting, recorded in the repo).
  - `documents.ts:369` and `admin-api/requests.ts:391` stop sending `x-upsert: true`.
  - `views.py:846` and `requests_delivery.py:338` sign with `upsert=False`.
  - TD-173: HEIC request attachments are converted, using the same path as `storage.py:266`.
- **Acceptance:**
  - Tests: a second PUT to the same signed path is refused; a wrong-type or oversize file is refused server-side.
  - The live bucket settings are read back and recorded.
- **Readings moved:** td_open −2. Two medium security findings closed.
- **Complexity:** M.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check: upload a photo and a PDF from a phone.
- **Deploy:** G3.

#### A1.8 TD-115: database guard on the document slot

- **Goal:** Only one live document per (application, doc_type, household_member, request_code). Four columns, not three: since TD-134 each officer request is its own slot, so a 3-column key would refuse the request-keyed uploads TD-134 exists for. (Corrected 2026-11-06 from the live data.)
- **Scope:**
  - TD-115.
  - A read-only count of live duplicates first. The owner sees the list, and duplicates are resolved by rule, not deleted silently. (Counted 2026-11-06 on the 4-column key: 0 live duplicates in 3,272 rows, 2,519 live.)
  - Then a partial `UniqueConstraint` (live rows only), applied by hand. In-programme results slips (`request_code = 'in_programme'`) are left out: one per semester, never replaced, by design.
  - **Order: deploy FIRST, then the index** (not "before the push"). The old image's upload door puts a re-upload live first and supersedes after, so with the index in place it would 500. The new code supersedes first and is safe either way. Steps in migration `0203`'s docstring.
- **Acceptance:**
  - A test: a second live row for the same slot raises.
  - The migration is applied, and `list_migrations` shows it.
  - The duplicate count is 0.
- **Readings moved:** td_open −1.
- **Complexity:** L (data plus migration).
- **Model:** Opus.
- **Gates:** Adversarial review. Owner approves the duplicate list before the migration.
- **Deploy:** G3.

#### A1.9 PII and request hygiene

- **Goal:** No IC numbers or emails in logs. Signer IPs are real. The low security tidy-ups are done.
- **Scope:**
  - TD-421: admin search of applications and scholars moves out of the query string (POST body) or is redacted.
  - TD-429: signer IP uses the rightmost trusted XFF hop (shared helper with SEC-03 / TD-514 if not on sec-a).
  - TD-458: shared phone leftovers (pageshow handler, localStorage tagged by owner).
  - SEC-05: one CRON_SECRET for every job; split per job or per family.
  - SEC-06: Django admin login throttle.
  - TD-520: SEC-08 (claim-code race), SEC-09 (email in WARNING log), SEC-11 (`partner_organisations` read policy), SEC-12 (security headers).
  - SEC-13: decide if anonymous sign-ins need the NRIC gate (document why if not).
  - SEC-14: service_role policy on the 15 deny-all tables.
  - SEC-04 / TD-515 if not on sec-a.
- **Acceptance:**
  - A test that the search term is absent from the logged request line.
  - XFF tests.
  - A headers test against the live response.
  - Each SEC item is closed or documented.
- **Readings moved:** td_open −5. 9 low security findings closed.
- **Complexity:** M (may split into A1.9a api and A1.9b web/db if over 40 files).
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check: sign-in and a search.
- **Deploy:** G4.
- **Status (2026-11-07):** SPLIT. **A1.9a (API) built on branch a19, not pushed:** TD-514, TD-429, TD-515 fixed; SEC-05 (TD-546) and SEC-06 (TD-547) fixed; TD-520 SEC-08, SEC-09 and the API's HSTS done; SEC-13 documented, no gate (TD-548); TD-421 API half (the `X-Search-Term` header). **A1.9b (web + SQL) left:** TD-421 web half, TD-458, SEC-11 and SEC-14 (TD-549) hand-apply SQL files, SEC-12 web headers and the live-response headers test. Deploy order: the A1.9a API first (CORS must allow the header before the web sends it). **A1.9b (web + SQL) built on branch a19b, not pushed:** TD-421 web half (`X-Search-Term`, percent-encoded), TD-458 (owner-tagged localStorage, `pageshow` reload), SEC-12 web headers (config test; the live-response check waits for G4), SEC-11 and SEC-14 (TD-549) as hand-apply SQL files in `docs/security/`, NOT applied. Owner steps are TD-550.

#### A1.10 Permission doors

- **Goal:** Every door reads the one permission system.
- **Scope:**
  - RD-03 (two systems coexist). Retire the union doors:
    - TD-497: `may_do_admin_work` in `views_staff.py:421`, `mentor_invite.py:99`, `org_emails.py:338`, and `credits.py:59` (`may_read_org` on writes).
  - TD-475: wallet credits read the finance permission, not the role.
  - TD-498: reading doors ask the read key, not `.edit`.
  - TD-496: graduation list by permission, not role label.
  - TD-499: web editor drops the retired qc → see_all dependency.
  - TD-336: overview pools money for an org-less super.
  - TD-476: a reopened case strands an ex-reviewer.
  - TD-435: reviewer without review held on Profile.
  - TD-504: invitations card read key.
  - TD-064: retire `is_super_admin` beside role (bridge and readers).
- **Acceptance:**
  - A permission matrix test per door (allowed and refused).
  - A guard test that fails if a new door calls a union helper.
  - TD-064's field is removed by migration, applied by hand.
- **Readings moved:** td_open −10. xapp −1 to −2. RD-03 closed.
- **Complexity:** L (split: A1.10a api doors, A1.10b web plus TD-064 migration).
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check with a finance and a reviewer test account.
- **Deploy:** G4.
- **Progress (2026-11-07):** A1.10a (api doors) BUILT on branch a110a, not pushed, awaiting review. Closed:
  TD-497 (no door calls a union helper; guard test in `test_permission_catalogue_v2`), TD-475 (checker seat =
  `payments_approve`), TD-336, TD-476, TD-435, TD-504. TD-498 partly done (sponsor terms / sponsor emails left:
  their `.view` key would widen access). TD-496 left (owner/lead ruling: no key keeps its holders). A1.10b
  (TD-499, TD-064) BUILT on branch a110b, not pushed, awaiting review; migration courses 0093 STEP 1 is
  migrate-first (owner, before the push), STEP 2 (DROP COLUMN) after the deploy.

#### A1.11 QC separation and decision integrity

- **Goal:** The person who reviewed cannot QC. Declines follow the QC gate.
- **Scope:**
  - TD-484 (delete and re-invite escapes separation), TD-485 (failed activity write drops evidence), TD-443 (`staff_footprint` misses history).
  - TD-486 (super cancel-reopen lands a declined case at `recommended`).
  - TD-487 (`/reject/` before AWAITING QC; owner's call) and TD-488 (org admin closes AWAITING-QC; owner's call).
  - TD-441 (admin role on student/sponsor login side effects: compare-and-set the UID).
  - TD-483 (QC panel shows for a QC the server refuses).
  - TD-227 (unassigned rejection with no reason: require a comment, show who).
  - TD-216 (interviewer label stamped by first click).
  - SEC-19 and SEC-20.
- **Acceptance:**
  - Tests per gap.
  - Separation reads `AssignmentEvent` and review verbs, not only activity rows.
  - Each owner-ruled item is built to the ruling, or left blocked with a pinned test.
- **Readings moved:** td_open −10. Two medium security findings closed.
- **Complexity:** L (split: A1.11a separation evidence, A1.11b decline and close gates after the owner rules TD-487 / 488).
- **Status 2026-11-07:** A1.11b built on branch a111a, not deployed (owner rulings, decisions.md 2026-11-07). TD-487 / SEC-19 and TD-488 fixed. TD-216 left open: it needs a migration and a new box (Stitch), so it moves to its own sprint.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check: a decline and a QC on test cases.
- **Deploy:** G4.

#### A1.12 Metering and billing money

- **Goal:** What we bill and report matches what was used.
- **Scope:**
  - TD-459: Gemini thinking tokens metered (`usage.py:112-124`, `thoughts_token_count`).
  - TD-422: busy-meter guard per tenant.
  - TD-425: a skipped month strands a correction (readiness warning plus carry forward).
  - TD-428: the verification mail is metered (`courses/views.py:1369` bare `send_mail`).
  - TD-174: email UsageEvent org-NULL.
  - TD-245: "spent nothing" versus "wallet not in export".
  - TD-460: income wizard writes on open; a silent save failure becomes visible.
- **Acceptance:**
  - Meter tests with thinking tokens.
  - A per-tenant guard test with two orgs.
  - A test that a correction carries over a skipped month.
  - The income wizard shows a save failure.
  - Historic under-count: a one-off report of the gap (read-only), no back-billing without the owner.
- **Readings moved:** td_open −7. One medium money finding closed.
- **Complexity:** M.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check: the income wizard.
- **Deploy:** G5.

#### A1.13 Owner-ruled money items

- **Goal:** Build the money rulings once the owner gives them.
- **Scope:**
  - TD-198 / CO-09 (no route out of awarded: who may withdraw an award), with TD-252 closed into it.
  - TD-465 part 2 (QC and payments read `reporting_date` directly at `verdict.py:292`), plus the review of cases already given RM3,000 with an unknown start year (data, read-only list first).
  - TD-075 / TD-142 / CO-05 (sponsor money mock): status recorded only. This waits on the lawyer, the entity and TD-140.
- **Acceptance:**
  - Built to the rulings, with tests.
  - The case list is reviewed by the owner and actions logged.
  - Anything still unruled is left blocked, with the owner decision ID in the register.
- **Readings moved:** td_open −2 to −3.
- **Complexity:** M.
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check.
- **Deploy:** G5.
- **Blocked by:** owner decisions D2 and D3.

### Wave 2 — live harm and speed

#### A2.1 record-verdict off the request

- **Goal:** Recording a verdict answers in seconds.
- **Scope:**
  - SP-01 / TD-517.
  - Move `refine_sponsor_profile` (`verdict.py:174`) and `generate_anon_blurb` (`:202`) to the background (the existing job/queue pattern), with retry and an "in progress" state on the card.
- **Acceptance:**
  - The view makes no Gemini call (a mock asserts it).
  - A background retry test.
  - Live p95 < 5 s over 7 days after deploy (Haiku reads the logs).
- **Readings moved:** record-verdict p95 ≈ 50 s → < 5 s. td_open −1.
- **Complexity:** M.
- **Model:** Opus (decision path).
- **Gates:** Adversarial review. Owner phone check: record a verdict.
- **Deploy:** G6.

#### A2.2 reprocess-ic-vision inside its time

- **Goal:** The job never hits 300 s.
- **Scope:**
  - SP-02 / TD-518: `reprocess_unread_ic.py` (limit 200). Add a time budget, a smaller batch, and a resume cursor (and bounded concurrency if safe).
  - SP-14: give the job its own timeout, separate from the service-wide 300 s.
- **Acceptance:**
  - A test that the job stops cleanly at its time budget and resumes.
  - p95 < 120 s and 0 timeouts in 14 days.
- **Readings moved:** reprocess runtime p95 ≈ 250 s → < 120 s, timeouts 5 → 0. td_open −1.
- **Complexity:** M.
- **Model:** Sonnet. No paid re-read in tests; mocked Vision only.
- **Gates:** Fresh review.
- **Deploy:** G6.

#### A2.3 Upload and assign answer fast

- **Goal:** Upload and assign do the slow work after the reply.
- **Scope:**
  - SP-03 / SP-04 / TD-519.
  - Upload: Vision moves out of the request (`views.py:1132-1164`), with the doc shown as "reading".
  - Assign: the email goes to the background (`services/assignment.py:286-306`), and the reply uses a slim serializer.
- **Acceptance:**
  - A mock asserts no inline Vision or email.
  - The query budget for assign is set.
  - Live upload p95 < 10 s and assign p95 < 8 s.
  - `MODEL_VERSION` is bumped if any doc-recognition result path changes.
- **Readings moved:** upload p95 27 s → < 10 s. assign p95 ≈ 45 s → < 8 s. td_open −1.
- **Complexity:** L.
- **Model:** Opus (doc judging).
- **Gates:** Adversarial review. Owner phone check: upload a document from a phone.
- **Deploy:** G6.

#### A2.4 Other slow reads

- **Goal:** No common admin page over 3 s p95.
- **Scope:**
  - SP-05: interview submit, qc-decision, resolution-items.
  - SP-06: income coach GETs cached by input hash, with no model call on a repeat.
  - SP-07: applicant detail (round trips, not just query count).
  - SP-13: TD-500 (mentor alias per mentee) and TD-505 (overview id list).
  - TD-449: offer check query budget.
  - TD-190: sponsor tables paginated server-side.
- **Acceptance:**
  - Query-budget tests for each.
  - A cache hit test.
  - Applicant detail p95 < 2.5 s and interview submit p95 < 5 s.
- **Readings moved:** td_open −4.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G6.

#### A2.5 Platform cost: cold start, builds, jobs

- **Goal:** Fewer slow first hits and fewer build minutes, within the budget.
- **Scope:**
  - SP-08 / SP-12 / TD-523: minimum instances is the owner's cost call; build caching and skipping docs-only builds.
  - SP-11: merge the hourly email jobs (33 jobs, 13 at hourly or */15).
  - SP-10 / TD-304: the budget counts layouts, CSS and lazy chunks.
  - TD-321: images via sharp (after Next 15).
  - TD-389: release the admin message slice after leaving the console.
  - TD-238: merchant count alert.
- **Acceptance:**
  - A build-minutes baseline and after.
  - The job count is cut by at least 6.
  - TD-304 is measured into `code-standards.json` without loosening any line.
- **Readings moved:** td_open −5. Bundle headroom +.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review. Owner cost ruling D6.
- **Deploy:** G7.

#### A2.6 Decision emails and notices

- **Goal:** No student is told by silence.
- **Scope:**
  - TD-355 / 357 / 358 / 359: decision emails after the status is visible, retry cap, the no-email surface for officers, and the stamp saved outside the send.
  - TD-430: the weekly partner mail counts a cool-off decline as Rejected before the student is told.
  - TD-350: embargoed decline uploads.
  - TD-356: cancel_reopen.
  - TD-363: closed-from status lives only in a log line. Store it in an existing field if one fits; otherwise defer (freeze: no new models).
  - TD-370: query-reminder dry-run clock.
  - TD-406: "Not checked" hold never clears.
- **Acceptance:**
  - Tests: a failed send leaves a retriable state with a cap; an officer sees the no-email case; partner counts mask an embargoed decline.
- **Readings moved:** td_open −10.
- **Complexity:** M.
- **Model:** Sonnet. Opus adversarial review (student notice and privacy).
- **Gates:** Adversarial review. Owner phone check: decline a test case.
- **Deploy:** G7.

#### A2.7 Offer reader live gaps

- **Goal:** Offer letters are read whole and judged right.
- **Scope:**
  - TD-491 (scanned multi-page scored on page 1).
  - TD-492 / 493 / 494 / 495 (agency lift and closed-list cluster).
  - TD-474 (town line join).
  - TD-451 / 452 (campus type and town words).
  - TD-447 (hostel line on stale course).
  - TD-448 (Bumi realign).
- **Acceptance:**
  - Pinned-gap tests flipped to passing.
  - The offline eval does not regress.
  - `MODEL_VERSION` is bumped.
  - No local re-extraction (halatuju_never_reextract_locally).
- **Readings moved:** td_open −10.
- **Complexity:** L (split: A2.7a pages and lines, A2.7b agency rules).
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check on a test offer.
- **Deploy:** G7.

#### A2.8 Check 2 holds and doc-reading gaps

- **Goal:** No hold stays frozen. Outage uploads get judged.
- **Scope:**
  - TD-393 (outage re-upload never re-judged).
  - TD-397 (hold frozen after the sweep gives up).
  - TD-398 (one deferred letter delays another).
  - TD-396 (no reason line).
  - TD-400 (consent against a half-read parent IC).
  - TD-111 (anomaly flags routed, plus a coverage critic).
  - TD-119 (8 false positives).
  - TD-121 (eval ignores genuineness).
  - TD-378 (re-verify IC at QC).
  - CO-10 (corpus brief, S7 frozen; TD-114 / TD-399 stay owner).
- **Acceptance:**
  - Tests per item.
  - A coverage critic test that fails on an unrouted flag.
  - The eval scores genuineness.
  - `MODEL_VERSION` is bumped.
- **Readings moved:** td_open −9.
- **Complexity:** L (split: A2.8a holds, A2.8b eval and critic).
- **Model:** Opus.
- **Gates:** Adversarial review. Owner phone check.
- **Deploy:** G7.

### Wave 3 — structure (behaviour kept, tests first)

Each sprint here:

- writes pinning tests first;
- splits by moving code, not changing it;
- writes `_moved` records;
- removes the old ledger rows;
- runs `code_health.py` before and after, and reports the delta in the hand-back.

#### A3.1 Split vision.py

- **Goal:** Take today's hotspot apart.
- **Scope:**
  - `vision.py` (2316 lines, hot 32.4) becomes a `vision/` package (pdf, field extraction, judge, outage).
  - Break up `_run_field_extraction_impl` (303 lines).
  - TD-361 (part).
- **Acceptance:**
  - Pinning tests are green before and after.
  - No module is over 600 lines.
  - `MODEL_VERSION` is unchanged (no behaviour change).
- **Readings moved:** hot#1 32.4 → next file (28.2). big −1. long −1.
- **Complexity:** L.
- **Model:** Opus.
- **Gates:** Fresh review. An Opus adversarial read that behaviour is unchanged.
- **Deploy:** G8.

#### A3.2 Split scholarship/views.py

- **Goal:** No 2400-line view file.
- **Scope:**
  - `scholarship/views.py` (2441 lines, hot 22) becomes a `views/` package by area.
  - Break up the document-record `post` (320 lines).
  - TD-361 (part).
- **Acceptance:**
  - URL tests prove every route still resolves.
  - Pinning tests.
  - `_moved` records.
- **Readings moved:** big −1. long −1. hot#3 drops.
- **Complexity:** L.
- **Model:** Sonnet. An Opus read, because the document-record path is identity.
- **Gates:** Fresh review plus adversarial read.
- **Deploy:** G8.

#### A3.3 Split the officer cockpit (web)

- **Goal:** The two hot web files come apart.
- **Scope:**
  - `officerCockpit.ts` (1620 lines, hot 28.2) and `admin/scholarship/[id]/view.tsx` (1114 lines, hot 20.1) split by panel.
  - TD-477 (shared Prev/Next hook).
  - TD-480 (native confirms become the site dialog, plus the hover-only name).
- **Acceptance:**
  - Behaviour tests (not source reads) for the panels moved.
  - `mobile-check` is clean.
  - The bundle does not grow.
- **Readings moved:** big −2. hot#2 and hot#5 drop. dup −0 (web not counted). guard% −.
- **Complexity:** L.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G8.

#### A3.4 Verdict and resolution engines

- **Goal:** The decision engines are small enough to read.
- **Scope:**
  - `verdict_engine.py` (1004 lines, hot 21.1): split, and break up `_verdict_income` (215 lines).
  - `resolution.py` `doc_match_verdict` (186 lines).
  - `help_engine.py` `verdict_for_document` (162 lines).
  - RD-01 / TD-262 (income rule homes): consolidate only the copies the owner's rulings already fix. Option 4 waits on D7.
- **Acceptance:**
  - Golden-case tests (same verdict for every fixture before and after).
  - The income-rule drift test passes.
- **Readings moved:** big −1. long −3. hot#4 drops.
- **Complexity:** L.
- **Model:** Opus.
- **Gates:** Adversarial review (eligibility). Owner phone check is not needed (no behaviour change), but the golden cases are shown to the owner.
- **Deploy:** G9.

#### A3.5 Split courses/views.py

- **Goal:** The course views are split by page.
- **Scope:**
  - `courses/views.py` (≈ 2177 lines): split.
  - Break up `get` at :126 (253 lines) and `get` at :1017 (165 lines).
- **Acceptance:** URL and pinning tests. `_moved` records.
- **Readings moved:** big −1. long −2.
- **Complexity:** L.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G9.

#### A3.6 Eligibility and ranking engines

- **Goal:** The two longest functions are broken up.
- **Scope:**
  - `courses/engine.py` `check_eligibility` (294 lines).
  - `ranking_engine.py` `calculate_fit_score` (333 lines).
  - `profile_engine.py` (1043 lines): split.
  - TD-434 (TVET first-category-wins: a per-course drift test only, no rule change).
- **Acceptance:**
  - Golden eligibility and ranking fixtures are identical before and after (whole course set).
  - The parity test passes.
- **Readings moved:** big −1. long −2.
- **Complexity:** L.
- **Model:** Opus.
- **Gates:** Adversarial review (eligibility).
- **Deploy:** G9.

#### A3.7 Serializers and models

- **Goal:** No serializer file over 1000 lines.
- **Scope:**
  - `scholarship/serializers.py` (1215 lines) and `serializers_admin.py` (1026 lines; TD-283) become packages.
  - `courses/models.py` (1051 lines) becomes a models package (no migration change; app label kept).
  - `models/applications.py` margin (TD-283).
- **Acceptance:**
  - `makemigrations --check` shows no change.
  - API contract tests (response shapes) are unchanged.
- **Readings moved:** big −3. hot (serializers 12.3 and 10.9) drops. td_open −2.
- **Complexity:** L.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G10.

#### A3.8 Money modules

- **Goal:** Money code is small and readable.
- **Scope:**
  - `contracts.py` (1151 lines), `sponsorship.py` (1010 lines): split.
  - `bursary.py` `render_agreement_html` (153 lines).
  - `offer_sync.py` `autofill_pathway_from_offer` (191 lines).
  - `views_staff.py` `post` (153 lines).
- **Acceptance:**
  - Golden tests for agreement HTML and schedules (byte-equal), and for the autofill fixtures.
- **Readings moved:** big −2. long −3.
- **Complexity:** L.
- **Model:** Opus.
- **Gates:** Adversarial review (money).
- **Deploy:** G10.

#### A3.9 Profile page and bundle room

- **Goal:** `/profile` has room to grow, and all web lines are tightened.
- **Scope:**
  - `app/profile/page.tsx` (1274 lines): split into sections, with lazy loading where it is safe.
  - Tighten every web line to measured + 3 kB.
  - SP-09 / CH-01.
- **Acceptance:**
  - `next build` headroom ≥ 3 kB on every line.
  - Each line is ≤ its pre-patch value.
  - `mobile-check` is clean.
- **Readings moved:** big −1. std tightened. Bundle headroom ≥ 3 kB.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G10.

#### A3.10 Management commands and repair doors

- **Goal:** One-off commands are short, or retired.
- **Scope:**
  - `backfill_spm_field_key.classify_course` (293 lines), `classify_stpm_fields.classify_stpm_course` (244 lines), `sync_stpm_mohe.handle` (169 lines): split, or retire the backfills already run (with a note in docs).
  - TD-234: 13 repair commands get a door, or are retired.
  - RD-11: test-only and offline files in the API.
- **Acceptance:**
  - The `NO_DOOR` ledger is empty.
  - The retired commands are listed in docs.
- **Built 2026-11-10 (branch a310, not pushed):** the three functions split (pins first); retired `backfill_nric_locks`, `repair_interview_credit` and five offline files in `halatuju_api/scripts/`; `NO_DOOR` is empty, the other eleven repair commands are declared in `DOCUMENTED_ROUTE` (release-decisions job args override). TD-234 closed; RD-11 acted on. Suspects not retired: `backfill_reminder_anchors`, `backfill_pismp_tags`.
- **Readings moved:** long −3. td_open −2.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G11 (deploys only command code).

#### A3.11 One home for duplicated helpers

- **Goal:** dup reaches 0, and the hidden copies go too.
- **Scope:**
  - A shared `comms_render` module (`render`, `banned_phrases`, `unknown_placeholders` from email_templates, partner_comms and sponsor_comms).
  - One Gemini helper (`_gemini_generate` in apply_copy_draft, contracts and sponsor_terms).
  - RD-10 / TD-412: the org resolver in 5 copies.
  - RD-09: `names_match` in 3 copies.
  - RD-05: logic imported from the view layer (programme_overview).
- **Acceptance:**
  - The dup reading is 0.
  - `duplicated_names` budget 4 → 0.
  - A guard test that fails on a 6th resolver copy.
- **Readings moved:** dup 4 → 0. xapp −2. td_open −2.
- **Complexity:** M.
- **Model:** Sonnet. An Opus read, because `names_match` is identity.
- **Gates:** Fresh review plus adversarial read.
- **Deploy:** G11.

#### A3.12 Cross-app imports, part 1 (scholarship → courses)

- **Goal:** Scholarship talks to courses through one door.
- **Scope:**
  - Add `apps/courses/public.py`, a facade of public service functions, imported as a module.
  - TD-414: `results_rules` behind the facade, replacing 34 direct `exam_questions` imports.
  - TD-384: private `_staff_target_manageable`.
  - RD-04 (half).
  - Batch to ≤ 40 files. Split into A3.12a / A3.12b if the 54 edges spread wider.
- **Acceptance:**
  - scholarship → courses ≤ 15 edges.
  - A guard test that fails on a new private (`_name`) cross-app import.
- **Readings moved:** xapp 85 → ≈ 55.
- **Complexity:** L.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G11.

#### A3.13 Cross-app imports, part 2 (courses → scholarship, reports)

- **Goal:** The courses app no longer reaches back into scholarship.
- **Scope:**
  - courses → scholarship (19 edges) through a `scholarship/public.py` or signals.
  - reports → courses and reports → scholarship through the facades.
  - RD-04 (rest).
  - Tighten the `courses_to_scholarship_imports` budget 17 → ≤ 8.
- **Acceptance:**
  - xapp ≤ 50.
  - courses → scholarship ≤ 8.
- **Readings moved:** xapp ≈ 55 → ≤ 50.
- **Status:** built 2026-11-11 on branch a313 (not pushed). Partial: five courses files and reports views/prompts routed; views_admin (9 names) and report_engine (3) skipped, owned by other sessions. Real readings xapp 105 -> 107, courses -> scholarship 20 -> 21 edges, budget 17 -> 16. Targets (xapp <= 50, courses -> scholarship <= 8) NOT met; they need those two files.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G12.

#### A3.14 Suppressions (api)

- **Status (2026-11-11):** BUILT on branch a314, not pushed, not deployed. Source `# type: ignore` 11 -> 0 (budget 11 -> 0; 2 deliberate ones remain in tests, each with a reason). Bare `# noqa` 67 -> 7: every one outside the other sessions' files now names its code and a reason. The noqa budget stays 80 (the count includes reasoned ones; it only falls if a noqa is removed, which was not safe without a linter to check). Left for the owners of those files: 4 in courses views_admin.py, 1 in backfill_admin_seen.py, 2 in test_code_standards.py (its own prose). No linter or mypy is configured in this repo.

- **Goal:** Every Python suppression is fixed or explained.
- **Scope:**
  - The 11 `# type: ignore`: fix the types.
  - The 38 bare `# noqa`: remove by fixing, or write `# noqa: CODE — reason`.
  - Tighten the noqa budget 80 → ≤ 45 and type_ignore 11 → ≤ 2.
- **Acceptance:**
  - The bare Python count is 0 (noqa) and ≤ 2 (type: ignore).
  - Lint and mypy (where it runs) are green.
- **Readings moved:** supp 92 → ≈ 45.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G12.

#### A3.15 Suppressions (web)

- **Goal:** Most eslint-disables are gone, because the code no longer needs them.
- **Scope:**
  - The 40 `eslint-disable`: fix the cause (mostly hook dependencies and `img` rules). The tool counts them even with a reason.
  - The 2 `: any`.
  - Target ≤ 15 eslint-disables left, each with a reason.
- **Acceptance:**
  - The supp reading is ≤ 30.
  - jest and `npm run gates` are green.
  - No behaviour change in the hook-dependency fixes (a test per changed hook).
- **Readings moved:** supp ≈ 45 → ≤ 30.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G12.

#### A3.16 Tests that test behaviour; mirrors with drift guards

- **Goal:** mirror 0, and guard% down.
- **Scope:**
  - Add drift tests and markers for the 3 `incomeWizard.ts` mirrors (income engine, patronymic connectors, salary_member_blocks).
  - TD-362: the guard reads beyond `src/lib` and catches keyword-free comments.
  - RD-06: the 41 mirrors are all guarded.
  - TD-426: hoursAnalysisId.
  - TD-185: creditChain uses status.
  - Convert at least 15 source-reading tests to behaviour tests.
  - TD-415: cockpit test fixture.
  - TD-065: sponsor and admin component tests.
  - CO-01 / TD-521: a local role sandbox sign-in, so behaviour tests can drive roles.
- **Acceptance:**
  - mirror reading 0.
  - guard% ≤ 8%.
  - The widened guard finds no unguarded mirror.
- **Readings moved:** mirror 3 → 0. guard% 11.5 → ≤ 8. td_open −5.
- **Complexity:** L (split: A3.16a mirrors and guard, A3.16b test conversion and sandbox).
- **Model:** Sonnet.
- **Gates:** Fresh review. CO-01 sandbox: an Opus read (it signs in as roles; local only, never on the live site).
- **Deploy:** G12 (tests deploy nothing; the sandbox is local only).

#### A3.17 Dead code

- **Goal:** Shipped code is all used.
- **Scope:**
  - RD-07: `ScholarshipReferee.tsx`, `error-i18n.ts`.
  - RD-08: API routes with no web caller (remove, or document as scripted).
  - CO-16: BANK_DETAILS code.
  - TD-226: two cohort settings read by nothing (migration).
  - TD-084: orphaned income fields and dead i18n (migration).
- **Acceptance:**
  - `unused` is 0.
  - The migrations are applied by hand.
  - The route-caller test is updated.
- **Readings moved:** td_open −3. A small cut to big and xapp.
- **Complexity:** M.
- **Model:** Sonnet (TD-084 touches income: an Opus read).
- **Gates:** Fresh review plus adversarial read on TD-084.
- **Deploy:** G12.

### Interim reading (after Wave 3)

See section 6. This is a measurement step, not a sprint.

### Wave 4 — remaining open TDs, grouped by area

#### A4.1 Apply and student scholarship screens

- **Scope:**
  - TD-338 / 339 (two open cohorts: duplicate choice and 409; inactive programme).
  - TD-341 (banner reads `applications[0]`).
  - TD-342 (abandoned Google sign-in).
  - TD-343 (intake failure names no gift).
  - TD-354 ("See programmes" with none open).
  - TD-454 (Google user without NRIC sees the signed-out header).
  - TD-462 (bank statement early refusal).
- **Acceptance:** A test per item.
- **Readings moved:** td_open −8.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review. Owner phone check: apply.
- **Deploy:** G13.

#### A4.2 Language

- **Scope:**
  - TD-388 (hydration mismatch).
  - TD-455 (saved toasts).
  - TD-456 (course page labels).
  - TD-463 (award schedule locale).
  - TD-346 ("open" wording).
  - TD-077 (bare `#` in course names).
  - TD-469 (sponsor desktop language control: owner's call on placement).
  - TD-472 (console language control: owner's call, D10).
- **Acceptance:** i18n parity stays ok. A test per string. Tamil follows `tamil-style-guide.md`.
- **Readings moved:** td_open −6 to −8. i18n held.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G13.

#### A4.3 Phone layout leftovers

- **Scope:**
  - TD-461 (10 px tab bar).
  - TD-464 (36 px selects; mobile-check fixed bar).
  - TD-466 (sandbox gutter, grade picker).
  - TD-453 (hoverOnlyWhenSupported).
  - TD-457 (sticky row header height).
  - TD-489 (mentor cards; owner said later).
  - TD-490 (charts paint the desktop box first).
  - TD-450 cluster (overlay stack and guards).
  - TD-471 (organisation sandbox surface, if still open after A0.2).
  - TD-187 (sidebar scroll, only if the trigger is reached).
- **Acceptance:** `mobile-check` is clean. A test per item.
- **Readings moved:** td_open −9.
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review. Owner phone check.
- **Deploy:** G13.

#### A4.4 Cockpit and overview leftovers

- **Scope:**
  - TD-438 (header photo link expires).
  - TD-444 (invited_by never recorded).
  - TD-502 (overview cards without a filtered link).
  - TD-503 (card scope: owner D9).
  - TD-228 (ORGANISATION crumb, only on trigger).
  - TD-126 (wire the existing reviewer-guide PNGs).
- **Acceptance:** A test per item. The Guide and FAQ are updated in the same change (reviewer feature).
- **Readings moved:** td_open −5.
- **Complexity:** S.
- **Model:** Sonnet.
- **Gates:** Fresh review.
- **Deploy:** G14.

#### A4.5 Billing, sources and org requests

- **Scope:**
  - TD-247 (supplier bills by hand: a cron door).
  - TD-423 (receipt resend).
  - TD-424 (date formats: owner asked).
  - TD-387 (referral partner mark/unmark screen; it uses the existing API, but if it counts as a new page it is deferred).
  - TD-432 (source users' Guide and FAQ).
  - TD-431 (Sources edit lock: accepted risk, close with the reason or stamp "ever joined").
  - TD-243 (AI reliability per engine version).
  - TD-212 (PartnerEmailTemplate misnamed: rename only if no migration; otherwise defer).
- **Acceptance:** A test per item.
- **Readings moved:** td_open −6.
- **Complexity:** M.
- **Model:** Sonnet. Opus for TD-247 (money).
- **Gates:** Fresh review. Adversarial read on TD-247.
- **Deploy:** G14.

#### A4.6 Sponsor side and walks

- **Scope:**
  - Walks in a browser, by the owner or Playwright (CO-14):
    - TD-070 (sponsor sign-in and vetting)
    - TD-092 (sponsor landing in 3 languages)
    - TD-112 (income route switch)
    - TD-184 and TD-196 (owner walks, D-list)
  - TD-074 (pool detail keyed by raw id: opaque id).
  - TD-192 (sponsor vetting, HIGH: only if the owner un-parks it, D8. Then it becomes its own Opus sprint, A4.6b).
- **Acceptance:** A recorded walk per item (Playwright script kept in `e2e/`). The TD-074 test.
- **Readings moved:** td_open −4 to −6.
- **Complexity:** M.
- **Model:** Sonnet (walks: Haiku drives Playwright). Opus for TD-074 / TD-192.
- **Gates:** Adversarial review on TD-074.
- **Deploy:** G14.

#### A4.7 Tests, tooling and data

- **Scope:**
  - TD-345 (local signed-in student smoke path; pairs with A3.16 sandbox).
  - TD-478 (doc-snapshot flake: close on no second sighting).
  - TD-385 (`code_health.py` ignores review-round fixes: workspace tool, owner approval D11).
  - CO-12 (vocabularies that are not yet a gate: make each a gate or drop it).
  - TD-058 (prod lacks Django contenttypes/auth tables: decide "managed" as final, with a doc, or fix).
- **Acceptance:** The TD-385 change is tested in workspace tests. The CO-12 gates are added. TD-058 is decided.
- **Readings moved:** td_open −4. fix% is honest (TD-385).
- **Complexity:** M.
- **Model:** Sonnet.
- **Gates:** Fresh review. Owner approval for the workspace tool change.
- **Deploy:** none (workspace and tests) or G14.

---

## 3. Owner decisions

Each line names the sprint it blocks. Items marked (D-list) only need a yes, no or pick.

| # | Decision | Blocks |
|---|---|---|
| D1 | Supabase "Confirm email" setting on (the SEC-02 residue: the code half ships in sec-a; the dashboard setting closes it) | Closing TD-513 (A0.1 follow-up) |
| D2 | Cases already given RM3,000 with an unknown start year: review each, claw back, or leave | A1.13 |
| D3 | TD-198: who may withdraw an award, and when (TD-252 closes into it) | A1.13 |
| D4 | TD-487: may `/reject/` before AWAITING QC go straight through, or need a second check? Also TD-488 (org admin closes an AWAITING-QC case) | A1.11b — RULED 2026-11-07 (option A; close at submitted / recommended only), built in A1.11b |
| D5 | TD-501 existing NULL-gift staff rows: which gift each should have | A1.3 (data step) |
| D6 | TD-523 / SP-08: minimum instances (cost per month) and build-minute changes | A2.5 |
| D7 | TD-262: income rule option 4 (`income_support_doc`) yes or no | A3.4 (the consolidation part) |
| D8 | TD-192: un-park sponsor vetting (HIGH) or keep parked with a written risk acceptance | A4.6b |
| D9 | TD-503: who sees the wallet_credits and sponsors_to_vet cards | A4.4 |
| D10 | TD-472 and TD-469: where the language control sits in the console and on sponsor desktop | A4.2 |
| D11 | TD-385: approve the workspace `code_health.py` change | A4.7 |
| D12 | guard% direction (note C): confirm ≤ 8% is the target, not ≥ 25% | A3.16 |
| D13 | TD-115 duplicate list: approve how each duplicate is resolved | A1.8 |

**Other OWNER entries from the sweep.** None of these blocks a sprint. They stay open in the register with their owner action, and the next audit counts them as owner-waiting:

- Tamil and Malay copy passes: TD-091, 094, 097, 105, 108, 132, 170, 180, 183, 215.
- Legal and money: TD-140, 141, 142, 152, 075, 328, 417.
- Product rulings: TD-043 / CO-06 (WhatsApp OTP, ≈ RM12/month), 068, 096, 116, 117, 114, 128, 143, 166, 179, 211, 260, 265, 353, 366, 386, 399.
- Infra actions: TD-130 (Brevo List-Help), 156 (Google Admin), 208 (DMARC), 318 / CO-08 (Twilio webhook URL), 225 (logo artwork).
- Walks: TD-184, 196.
- TD-066 (the personal mobile in the TEMP help box: keep which number, or remove). **This one should be answered soon:** it is a personal number on the live site.

---

## 4. Coverage check

### 4.1 Findings (all 74, not only high and medium)

| Finding | Severity | Sprint |
|---|---|---|
| TD-465 (rank 1) | high | A0.1 (part 1), A1.13 (part 2) |
| SEC-01 / TD-512 | medium | A0.1 |
| SEC-02 / TD-513 | medium | A0.1, then D1 |
| SEC-03 / TD-514 | low | A0.1 or A1.9 |
| SEC-04 / TD-515 | medium | A0.1 or A1.9 |
| SEC-05, SEC-06 | low | A1.9 |
| SEC-07 | low | A1.7 (folded into SEC-18) |
| SEC-08, 09, 11, 12 / TD-520 | low | A1.9 |
| SEC-10 / TD-516 | medium | A1.2 |
| SEC-13, SEC-14 | low | A1.9 |
| SEC-15 / CO-15 / TD-506 | medium | A1.1, A1.2 |
| SEC-16 | medium | A1.2 |
| SEC-17 / TD-501 | medium | A1.3 |
| SEC-18 / TD-467 | medium | A1.7 |
| ~~SEC-19 / TD-487~~ | medium | A1.11b (D4) — fixed 2026-11-07 |
| SEC-20 | low | A1.10, A1.11, A4.4 |
| CO-01 / TD-521 | medium | A3.16b |
| CO-02, CO-03 / TD-522 | medium | A0.3 |
| CO-04 | medium | A1.6 (TD-347). TD-140 / TD-152 stay owner. |
| CO-05 | medium | A1.13 (status only; owner, legal) |
| CO-06 / TD-043 | medium | Deferred: owner (paid OTP) |
| CO-07 | low | Deferred: the "coming soon" screens are features (freeze). Recorded in A0.3 docs. |
| CO-08 / TD-318 | medium | Owner action (Twilio). No sprint. |
| CO-09 / TD-198 | medium | A1.13 (D3) |
| CO-10 | medium | A2.8 |
| CO-11 | medium | A0.3 |
| CO-12 | medium | A4.7 |
| CO-13 | medium | Section 3 (owner list) |
| CO-14 | low | A4.6 |
| CO-16 | low | A3.17 |
| CO-17 | low | A0.3 |
| RD-01 / TD-262 | medium | A3.4 (D7) |
| RD-02 | medium | A0.2 |
| RD-03 | medium | A1.10 |
| RD-04 | medium | A3.12, A3.13 |
| RD-05 | low | A3.11 |
| RD-06 / TD-362 | medium | A3.16a |
| RD-07, RD-08 | low | A3.17 |
| RD-09 | low | A3.11 |
| RD-10 / TD-412 | medium | A3.11 |
| RD-11 | low | A3.10 |
| SP-01 / TD-517 | medium | A2.1 |
| SP-02 / TD-518 | medium | A2.2 |
| SP-03, SP-04 / TD-519 | medium | A2.3 |
| SP-05, 06, 07 | medium | A2.4 |
| SP-08, SP-12 / TD-523 | medium | A2.5 (D6) |
| SP-09 / CH-01 | medium | A1.1, A3.9 |
| SP-10 / TD-304 | low | A2.5 |
| SP-11 | low | A2.5 |
| SP-13 (TD-500, 505) | low | A2.4 |
| SP-14 | low | A2.2 |
| CH-01 | accepted FAIL | A1.1, A3.9 |
| CH-02 | medium | A0.2 |
| CH-03 (fix% → TD) | medium | A0.2 (rule), A4.7 (TD-385) |
| CH-04 (hotspot) | medium | A3.1 to A3.4 |
| CH-05 (big) | low | A3.1 to A3.9 |
| CH-06 (long) | medium | A3.1, A3.2, A3.4 to A3.8, A3.10 |
| CH-07 (dup) | low | A3.11 |
| CH-08 (mirrors) | medium | A3.16a |
| CH-09 (xapp) | low | A3.12, A3.13 |
| CH-10 (supp) | low | A3.14, A3.15 |
| CH-11 (debt rise) | medium | A0.2 and every sprint |
| CH-12 (register near-misses) | low | A0.2 |

### 4.2 OPEN TDs (code check verdicts)

Every OPEN TD from sweeps 1 to 6 is placed below. ★ marks medium or high.

| Sprint | TDs |
|---|---|
| A0.1 | 465★ (part 1), 512, 513, 514?, 515? |
| A0.2 | Closes the FIXED / STALE / MERGE set. Settles 471, 472, 127, 129, 395, 478. |
| A0.3 | 522 |
| A1.1 | 506★ (web) |
| A1.2 | 506★ (Python), 516 |
| A1.3 | 501★ |
| A1.4 | 383★ (part), 367, 420, 365 |
| A1.5 | 383★, 368, 348, 351, 442★ |
| A1.6 | 347★ |
| A1.7 | 467★, 173 |
| A1.8 | 115★ |
| A1.9 | 421★, 429, 458★, 514, 515, 520 |
| A1.10 | 475★, 497★, 498, 496, 499, 336, 476, 435, 504, 064 |
| A1.11 | 484★, 485, 443★, 486★, 487★, 488, 441★, 483, 227★, 216★ |
| A1.12 | 459★, 422★, 425★, 428, 174, 245★, 460★ |
| A1.13 | 465★ (part 2), 198 (owner) |
| A2.1 | 517 |
| A2.2 | 518 |
| A2.3 | 519 |
| A2.4 | 500, 505, 449, 190 |
| A2.5 | 523, 304, 321, 389, 238 |
| A2.6 | 355★, 357, 358★, 359, 430★, 350, 356, 363, 370, 406 |
| A2.7 | 491★, 492★, 493★, 494★, 495, 474, 451, 452, 447, 448 |
| A2.8 | 393★, 397★, 398, 396, 400, 111★, 119★, 121, 378 |
| A3.1 to A3.9 | 361, 283 |
| A3.4 | 262 (owner part waits on D7) |
| A3.6 | 434 |
| A3.10 | 234★ |
| A3.11 | 412 |
| A3.12 | 414, 384 |
| A3.16 | 362, 426, 185, 415, 065, 521 |
| A3.17 | 226, 084 |
| A3.3 | 477, 480 |
| A4.1 | 338, 339, 341, 342, 343, 354, 454, 462 |
| A4.2 | 388, 455, 456, 463, 346, 077, 469 |
| A4.3 | 461, 464, 466, 453, 457, 489, 490, 450, 471 (if open), 187 |
| A4.4 | 438, 444, 502, 228, 126 |
| A4.5 | 247, 423, 424, 387, 432, 431, 243, 212 |
| A4.6 | 070★, 092, 112, 074, 192★ (D8) |
| A4.7 | 345, 385, 058 |

### 4.3 Deferred, with a reason

| TD / finding | Reason |
|---|---|
| TD-024 (course field named `course`) | A rename across the eligibility engine and the API contract. High blast radius, no user harm. Re-raise after the freeze. |
| TD-041 / TD-076 (settings account options) | A new feature (freeze). |
| TD-101 (donate more / withdraw offer) | A new feature, and it waits on TD-075 (mock money). |
| TD-103 (CGPA read off the slip) | A new doc-reading capability (freeze). |
| TD-124 (contact messages page) | A new page (freeze). |
| TD-155 (partner scholarship view) | A new page (freeze). |
| TD-437 (source website column) | A new model field (freeze). |
| TD-212 (model rename) | Deferred only if the rename needs a migration (see A4.5). |
| TD-353, TD-366 | The owner put them ON HOLD (second organisation, bursary signing). |
| CO-06 / TD-043, CO-07 | Owner and paid service, or feature work. |

Low TDs not named above: none. Every OPEN low TD from the six sweeps is in a sprint row in 4.2.

---

## 5. Re-measuring after deploys

The speed numbers are read from live logs by a Haiku agent 7 days after each speed deploy (14 days for the job). Each sprint's hand-back records "before / after" for the readings it claims to move, from a `code_health.py` run on the sprint branch.

## 6. Interim audit reading

- **When:** after Wave 3 closes (after G12). This is about two thirds of the way through, with all structure work done.
- **What:**
  - A full `code_health.py` run, recorded in the run log.
  - `wat_lint`.
  - The four speed numbers from live logs.
  - The bundle headroom from `next build`.
  - A register count.
- **Pass mark at the interim reading:**

  | Reading | Pass mark |
  |---|---|
  | hot#1 | < 20 |
  | big | ≤ 7 |
  | long | ≤ 6 |
  | dup | 0 |
  | xapp | ≤ 55 |
  | supp | ≤ 35 |
  | mirror | 0 |
  | guard% | ≤ 9% |
  | td_open | ≤ 140 |
  | std | PASS |
  | speed | all four targets met |

  Also check note B: no new split module has more than 3 fixes.
- **If a reading misses:** add a catch-up sprint to Wave 4 before the area work. Do not lower the target.
- **Final close** (`project-audit.md` step 8): a fresh full reading after Wave 4, a closing section in the audit report, and then lift the freeze.

## 7. Totals

- **Sprints:** 45 numbered (Wave 0: 3, Wave 1: 13, Wave 2: 8, Wave 3: 17, Wave 4: 7). About 52 with the planned splits (A1.9, A1.10, A1.11, A2.7, A2.8, A3.12, A3.16, A4.6b).
- **Order:**
  1. Wave 0 (ship, then clean the register).
  2. Wave 1, in the order the owner ruled: Next 15 → Python bumps → TD-501 → TD-383 → the rest.
  3. Wave 2.
  4. Wave 3.
  5. The interim reading.
  6. Wave 4.
  7. The final reading.
- Wave 4 sprints may run beside Wave 3 sprints when they touch different files (≤ 2 builders at once; worktrees per `parallel-work-isolation.md`).

**Deploy groups** (each one owner-gated, at most 1 to 2 a day):

| Group | Sprints | Notes |
|---|---|---|
| G0 | A0.1 | sec-a + money-a |
| G1 | A1.1 (web), A1.2 (api) | Major upgrade. Two pushes, one day. |
| G2 | A1.3, A1.4, A1.5 | Invites and the choke-point. Phone check. |
| G3 | A1.6, A1.7, A1.8 | Deadline, storage, slot guard. Migration first. |
| G4 | A1.9, A1.10, A1.11 | PII, doors, QC. Migration (TD-064). |
| G5 | A1.12, A1.13 | Metering. Owner rulings. |
| G6 | A2.1 to A2.4 | Speed. Logs 7 days after. |
| G7 | A2.5 to A2.8 | Platform, notices, document reading. `MODEL_VERSION` bump. |
| G8 | A3.1, A3.2, A3.3 | Hotspot splits. |
| G9 | A3.4, A3.5, A3.6 | Engines and course views. |
| G10 | A3.7, A3.8, A3.9 | Serializers, money modules, profile. |
| G11 | A3.10, A3.11, A3.12 | Commands, dup, xapp part 1. |
| G12 | A3.13 to A3.17 | xapp part 2, suppressions, tests, dead code. Migrations. |
| G13 | A4.1, A4.2, A4.3 | Student screens, language, phone layout. |
| G14 | A4.4, A4.5, A4.6 (+ A4.7 if it touches the repo) | Leftovers. |

Docs-only sprints (A0.2, A0.3) deploy nothing.

That makes 15 deploy groups, about 17 pushes counting G1's two.
