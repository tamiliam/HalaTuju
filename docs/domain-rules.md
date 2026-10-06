# HalaTuju — domain rules the code depends on

Current-state reference, moved out of `halatuju_api/CLAUDE.md` word for word at the v3.0.0 release cut
(2026-10-06) to keep that file short. These are LIVE rules: read the matching section before you
change the code it names. `halatuju_api/CLAUDE.md` keeps a one-paragraph summary of each and links here.

- Profile claim (IC already registered)
- The apply link, the intake answer and the two application pages
- Course data: annual refreshes and the dashboard
- The document snapshot
- Income evidence and the income verdict

## Profile claim (IC already registered) — TD-254, 2026-09-19
A student who lost access to their sign-in email re-registers and finds their IC already taken.
That path is legitimate and it survives — but it used to be an **account takeover**: the endpoint
answered somebody else's IC with **that person's name**, and a second call carrying
`confirm: true` moved the profile's primary key in raw SQL. `confirm: true` is GONE; a client
still posting it gets a refusal.

**⚠ NEVER RETURN THE HOLDER'S NAME.** `POST /api/v1/profile/claim-nric/` answers
`{status: 'exists', channels: [...]}` — bare channel TYPES (`'phone'` / `'email'` / neither),
never a name, never a masked address, never digits. The real owner knows their own phone. If you
are adding a field to that response, this is the line to argue with first.

**A claim is a LINK, not a move.** Proving control of a contact that is already on the target
profile and already verified (`ProfileLoginAlias`, `profile_login_aliases`) writes ONE row
meaning *"the login `alias_uid` acts as this profile"*. Nothing is moved, renumbered or deleted —
the caller's own empty profile stays exactly where it is, merely unreachable.

**The auth seam resolves it, once, for everything.** `SupabaseAuthMiddleware` sets
`request.auth_sub` = the REAL JWT subject and `request.user_id` = the profile that login acts as
(`resolve_login_alias`). One indexed primary-key look-up per authenticated request; deliberately
NOT cached, because a stale cache would keep a revoked alias working. ⚠ **Staff and sponsor
identity must resolve on `auth_sub`** (`PartnerAdminMixin.get_admin`, `SponsorMixin.get_sponsor`
and the two account-creation sites already do) — an alias may never redirect one, and the seam
re-checks in case a staff row was created after the alias.

**Everything is audited** in `ProfileClaimEvent` (`profile_claim_events`), append-only: the
plain look-up (`exists_shown`), each `code_sent` / `code_failed` / `claimed` /
`refused_<reason>` / `alias_revoked`, with the real caller sub, the target profile id as a PLAIN
value (so the line outlives the profile), the IC and the bare channel. Before this table, *"has
a profile ever been taken over?"* had no answer. ⚠ The IC belongs in the TABLE and **never in an
application log**.

**To revoke a claim:** `profile_claim.revoke_alias(alias_uid, by='<who>')` — it deletes the row
and writes the `alias_revoked` line, and the login is back on its own profile from its very next
request. There is no UI for it yet.

**The conservative policy, and where to widen it.** Only an ALREADY-VERIFIED contact may be
challenged. Two owner rulings are still open (does an unverified contact count? does the phone
count when the email is what was lost?) and both are one edit to
**`apps/courses/profile_claim.claim_channels()`** — the only function that decides. Measured
2026-09-18: of 674 profiles carrying an IC, 70 have a verified contact, so this returns `[]` for
nine accounts in ten and the honest answer is `channels: []` and a route to a human.

## The apply link, the intake answer and the student's two application pages — 2026-10-05
The current state of PF-1 (the apply link) and M1 (the application screen); the history is in the
superseded Next Sprint sections below and in `docs/decisions.md` (2026-07-28, 2026-10-05).

* **`GET /api/v1/scholarship/intake/?programme=<code>`** (public, `ScholarshipIntakeView`) answers
  `{open, cohort_name, programme_code, choices, apply_copy}`. `programme_code` is the CANONICAL code of
  the round `cohort_name` names (an alias resolves to the live code); `''` when ambiguous, closed,
  unknown, or the programme is inactive. `choices` is filled only when several rounds are open and
  nothing named one. Tests: `apps/scholarship/tests/test_open_cohort_scope.py`.
* **The apply form submits the SERVED code** (`halatuju-web/src/lib/useApplyGift.ts`), so the code
  sent is the one the shown name came from: a round that closes mid-form is refused at submit, never
  re-routed. A 409 `programme_required` re-asks which gift.
* **A bare `/scholarship/apply` asks afresh.** `enterApplyPage` (`src/lib/applyProgramme.ts`) forgets a
  stored code when the URL has no `?p=`; the My Results detour and the sign-in gate come back through
  `applyPagePath()` (`src/lib/applyPagePath.ts`), which puts `?p=` back in the URL.
* **One application in play (owner's ruling on TD-337, 2026-10-05: one per organisation; as BUILT,
  one ANYWHERE until M2) — ONE rule, on the server:** `apps/scholarship/services/apply_gate.py` — an
  application in play (not rejected / withdrawn / closed / expired) in ANY organisation →
  `application_in_progress`; a non-expired one in the same round → `already_applied`; otherwise
  allowed. ⚠ Deliberately stricter than the ruling across organisations: the student side cannot carry
  two live applications (`_current_application` 409s, positional picks) — relax it WITH M2, never
  before (TD-353). Judged on the STUDENT-FACING status (`apps/scholarship/student_status.py`, shared
  with `ApplicationReadSerializer.get_status`), so an embargoed decline still blocks. The submit
  refuses with 409 `{error, code}` (`apply_verdict`, always with a round);
  **`GET /api/v1/scholarship/apply-gate/?programme=<code>`** (`views_apply_gate.py`, signed in, →
  `apply_gate.verdict_for_visit`) serves `{allowed, reason, application_id}` before the form: in play
  → in progress on EVERY visit (any code, unknown or closed, bare, nothing open); otherwise an unknown
  and a closed code both → allowed. `apply_gate.in_play_application(user_id)` is her CURRENT
  application — `BursaryAgreementView` answers for it. Tests: `test_apply_gate.py`.
* **The web keeps no copy of the rule.** `src/lib/useApplyGate.ts` asks the gate (never signed out),
  re-asks when the gift changes, and obeys: in progress → `/scholarship/application`; already applied
  → `components/scholarship/AlreadyApplied.tsx`; a failed ask → the form. ONE function,
  `applyPageExit`, decides every redirect off the apply page (in progress first; then, once intake
  and gate have both answered, bare + nothing open → `/scholarship`); `useApplyGift` never redirects. `src/lib/applicationScreen.ts`
  decides only what the application page shows (one live → it; several → "more than one"; none live →
  the single submitted one, or the "closed" card, which now links back to the apply page).
  `studentScreenDrift.test.ts` reads the gate's `IN_PLAY_STATUSES` / `FINISHED_STATUSES` and asserts
  that, for every list the rule can produce, a student the gate calls in progress lands on THE
  application it named (`kind: 'one'`, same id). Open: TD-348 (no database lock; fix = a short locked
  transaction with the acknowledgement email on `on_commit`), TD-349 to TD-354.

## Course data: annual refreshes and the dashboard

### Annual STPM Data Refresh (before UPU application season)

```bash
# 1. Scrape latest data from MOHE ePanduan
python manage.py scrape_mohe_stpm --output data/stpm/mohe_2027.csv

# 2. Review diff report (dry run — no changes applied)
python manage.py sync_stpm_mohe --csv data/stpm/mohe_2027.csv

# 3. Apply URL updates
python manage.py sync_stpm_mohe --csv data/stpm/mohe_2027.csv --apply

# 4. Validate URLs (uses Selenium — checks rendered page, not HTTP status)
python manage.py validate_stpm_urls
# --fix flag clears dead URLs; --limit N checks first N only

# 5. For new programmes: parse requirements manually, add to DB
# 6. For removed programmes: consider marking inactive
# 7. Run golden master
python -m pytest apps/courses/tests/test_stpm_golden_master.py -v
```

Requires: `pip install selenium` (URL validation) + `pip install playwright && playwright install chromium` (scraper). Local admin tools, not deployed.

### UP_TVET Coverage Inventory (TVET gap analysis — no DB writes)

```bash
# 1. Scrape the public UP_TVET Perdana catalogue (~1000 programmes, ~50 pages)
python manage.py scrape_uptvet --output data/tvet/uptvet_latest.csv
#    (--max-pages N for a quick parser-validation spike)

# 2. Coverage report: total, Awam/Swasta split, by-institution, new-vs-already-held (ILJTM+ILKBS)
python manage.py audit_uptvet --csv data/tvet/uptvet_latest.csv
```

UP_TVET covers ~12 ministries / 685 institutions; we hold only ILJTM (ADTEC/JTM) + ILKBS (IKBN/IKTBN), ~83
courses. **No DB writes** — this is the decision-data step before a (golden-master-adjacent) TVET INGEST sprint.
Codes (`TVET/QP…`) don't match our synthetic `IJTM-*`/`IKBN-*` IDs, and the portal mixes Awam/Swasta — see
`docs/roadmap-course-data-pipeline.md` (UP_TVET track) + `docs/decisions.md`.
### Annual SPM Data Refresh (post-SPM `Course` catalogue — MOHE-coded subset only)

```bash
# 1. Scrape the SPM track (current year). Same scraper, --jenprog spm.
python manage.py scrape_mohe_stpm --jenprog spm --category A --output data/spm/mohe_2027.csv
#    (--max-pages N for a quick parser-validation spike; do NOT sync a --max-pages CSV)

# 2. Dry-run diff (report only — restricted to MOHE-coded UA/Asasi courses; synthetic-ID Poly/KK/TVET/PISMP excluded)
python manage.py sync_spm_mohe --csv data/spm/mohe_2027.csv

# 3. Apply (deactivate removed / reactivate returned / update merit; mass-deactivation guard; --force to override)
python manage.py sync_spm_mohe --csv data/spm/mohe_2027.csv --apply
```

**Scope:** `sync_spm_mohe` only touches courses whose `course_id` is a MOHE KOD PROGRAM (`^[A-Z]{2}[0-9]{7}$`, ~89
UA/Asasi). The ~300 synthetic-ID courses (`POLY-*`/`KKOM-*`/`TVET-*`/`50PD…`) are excluded (they need a name crosswalk —
roadmap Sprint 3b). New MOHE-coded courses are **reported, not auto-added** (requirements parsing = Sprint 3c). `is_active`
is set by the sync but **not yet read-filtered** anywhere. See `docs/roadmap-course-data-pipeline.md` + `docs/decisions.md`.

### Course Data dashboard (`/admin/course-data`, read-only reporting + health monitoring)

A read-only admin status surface: per-source **freshness** (e-Panduan STPM/SPM, UP_TVET, eMASCO), **coverage**
(have/available/gap, live from the DB), **link-health** + **audit** (last recorded run). Endpoint
`GET /api/v1/admin/course-data/` (`AdminCourseDataView`, any admin role). Freshness comes from `CourseDataStatus`
(`course_data_status` table) which the tools upsert on completion via `course_data_status.record_status(...)`:
`refresh_stpm`→`epanduan_stpm`, `validate_course_urls`→`link_health`, `audit_data`→`audit`. (The SPM `sync_spm_mohe` +
UP_TVET `scrape_uptvet`/`audit_uptvet` tools do NOT yet call `record_status` — until they do, the SPM/UP_TVET cards read
"never run"; wiring that is a one-line add per tool.)

**Health monitoring (READ-ONLY — no catalogue writes).** The dashboard's Link-health + Audit + freshness are kept
current by `course_data_check` = `audit_data` + `validate_course_urls --workers 40 --timeout 20 --retries 0`
(**no `--fix`/`--apply`/scrape**). It runs IN-REQUEST (cron + button), so it must fit the api's Cloud Run request
timeout — **raised 120s → 300s** for this (`gcloud run services update halatuju-api --timeout=300`). The bulk run uses
40 workers + `retries=0` so the slow MY-gov tail (20s/URL) stays well inside that budget; a per-URL retry would double
it. (The `--retries` default is 1 for manual/targeted runs.) Two ways to run it, both read-only:
- **Weekly cron** — `CronRunView` job `course-data-check` ← Cloud Scheduler `halatuju-course-data-check` (Mon 03:00 Asia/KL,
  `X-Cron-Secret`). POST needs a body (`-d '{}'`) or the LB returns 411.
- **Manual button** — `POST /api/v1/admin/course-data/check/` (`AdminCourseDataCheckView`, **super/admin only**) runs it
  synchronously and returns the refreshed payload; "Run health check now" on the page (~2 min).

`validate_course_urls` stores a `failures` list in its status (`{url, kind, institutions, refs}`) and splits results
into THREE severities so the dashboard doesn't cry wolf: **Broken** (`gone`/`dns`/`badurl` — actionable, the headline
count) · **Access-blocked** (`gated` = 401/403 — server up but refused this page: login wall OR wrong/old path like
Politeknik Port Dickson; eyeball) · **Couldn't verify** (`timeout`/`conn` — slow/blocked from Cloud Run, almost
certainly alive). SSL-cert-rejected-but-reachable sites are `insecure` (counted as alive). FIXING links (writes) is NOT
built into the check — owner inspects + corrects at source (done via audited MCP `UPDATE`s).

The browser catalogue scrapes (`refresh_stpm`, `scrape_uptvet`) stay manual/local (need Chromium) and only dry-run.
**UI-driven *updating* (apply-a-refresh) is deliberately NOT built** — owner wants reporting only.
Migration `0054_coursedatastatus` is the only schema for this surface (already on prod); the health-monitoring sprint
added NO migration.

## THE DOCUMENT SNAPSHOT (TD-282, 2026-09-21) — what it is and how to widen it
**What it is.** `apps/scholarship/document_snapshot.py`. It reads ONE application's documents
once and holds that list for the length of ONE read-only computation. About thirty helpers across
seventeen modules — `verdict_engine._latest_doc`, `income_engine`'s `_cluster_docs` and
`_latest_doc`, `anomaly_engine`, `income_shown`, `submission_review`, `services/blockers` and the
rest — now call one of its five readers (`latest_doc`, `live_docs`, `has_live_doc`,
`present_doc_types`, `tagged_members`) instead of each building its own queryset.

**How a reader decides.** If a snapshot is open **for that very application — same MODEL and
same pk** (the first version keyed on pk alone, and the adversarial review proved any object
sharing the number was served the applicant's documents) — it filters the loaded list in Python. If not, it runs exactly the query the helper ran before — same single
`.filter(**kwargs)`, same `ORDER BY`, same laziness. So nothing outside a snapshot changed.

**Ordering.** Every document read in this codebase is `ORDER BY uploaded_at DESC` — some helpers
say `.order_by('-uploaded_at')`, the rest inherit the identical clause from
`ApplicantDocument.Meta.ordering`. The snapshot loads with that same clause once and the readers
filter **without re-sorting**, so a subset keeps the order the database gave and an in-memory
answer matches the query's by construction **when timestamps are distinct**. ⚠ **Not one of those
reads has a tie-breaker**, so "the latest" is undefined when two documents share a timestamp.
That is pre-existing — but it is NOT "made no worse", and the first draft of this note said so:
the snapshot's order comes from a different, unfiltered query than each helper's own, and on
PostgreSQL the two can emit tied rows differently, so on a tie the snapshot can pick a different
document than the old code did. SQLite cannot show it. What makes it safe is a measurement:
**0 tied pairs in 1,356 production documents on 2026-09-21** (`uploaded_at` is `auto_now_add`,
nothing bulk-creates). TD-292 holds the `, '-id'` fix and why it needs a version bump.

**THE ONE PLACE IT IS OPENED.** `views_admin/applications.py`,
`AdminApplicationDetailView.get`, around the serializer build. That is the whole scope today.

⚠ **NO WRITE PATH MAY OPEN OR READ ONE.** The rows are a photograph taken when the block opened.
A function that writes a document and reads one back must see its own write, and inside a
snapshot it would not. This is why the scope is an explicit `with` around one handler and NOT a
request-wide middleware, and why `check2_queries` (which sits inside a write) was deliberately
left on its own query. (TD-308, 2026-10-04: inside that write path the ONE thing shared is the STR
reading — `str_check_memo.one_str_reading` wraps the side-effect-free `_gap_sets`, so
`student_str_check` reads each STR once per pass. Same rule: never widen it around a write.) ⚠ **"Read-only" here means ONLY "never writes `applicant_documents`".**
The detail GET is not read-only in the ordinary sense: building the payload runs
`sync_resolution_items`, which creates and resolves ResolutionItem rows off verdict facts and can
email the student. So a wrong row under the snapshot would be persisted and sent, not merely
drawn — which is why the matrix also compares what the FIRST, cold open leaves behind (items and
mail) on twin applications, not only the bytes of a warmed one. (TD-079, 2026-10-04: a SECOND, steady-state open writes nothing and sends nothing — `test_td079_resolution_reads_and_deletes.py`; the writes happen only when the verdict moved.) `test_document_snapshot.py` holds the test that a write is
visible to a read taken OUTSIDE the block — and the test that the detail GET writes no document
at all, which is the precondition for opening one there.

**It lives in a `contextvars.ContextVar`**, not a module global and not an attribute on the model
instance. A global would be shared between two officers opening two applicants at the same
instant; an attribute on the instance would survive into a later write in the same request. The
variable is reset from its token in a `finally`, so nesting and exceptions are both safe.

**To widen it — the four steps, in this order:**
1. Satisfy yourself the computation is **read-only with respect to `applicant_documents`**.
2. Wrap at the **outermost** point of that computation, so everything underneath shares one
   snapshot instead of opening several.
3. **Add the surface to the ON==OFF matrix in `test_document_snapshot.py` BEFORE you ship it.**
   That test asserts the response BYTES are identical with the snapshot on and off across 238
   fixtures (every stage × both income routes × seven document sets). A widening that is not in
   the matrix is not proven, and the matrix is the only reason anyone can change this module
   safely.
4. Lower the affected query budget afterwards. The budget is what notices if the saving is undone.

⚠ **The student's own read is a LIST** (`many=True`), so a snapshot there has to be opened per
application inside the loop, not once around it. See TD-291 for what it would save (20 → ~7 for a
two-earner family; break-even for an STR family).

## Income evidence and the income verdict

### Income evidence — one per-earner answer

**`apps/scholarship/income_shown.py` → `income_shown(application, member)`** answers *has this
earner's income been SHOWN?* — `{shown, way, documents, unusable}`. It is the owner's three
PER-EARNER ways and nothing else (a usable payslip · a readable EPF · a declared amount + a
supporting letter that READ), and `unusable` names a document that was sent and cannot carry the
income, in a stable code (`not_salary` · `no_value` · `letter_unread` · `no_declared_amount`).

**⚠ AN STR IS NEVER A PER-EARNER WAY.** An STR is evidence about the HOUSEHOLD: it clears the
submission gate and settles the verdict by precedence, and a working adult's income proof is
ADDITIONAL to it (owner 2026-09-19, `docs/decisions.md`). This function has NO STR arm, and that
absence is the ruling — adding one silences the salary-picture asks the owner asked for (F3) and
turns a per-earner cue green on a fact about somebody else.

**Who reads it.** `income_engine.member_income_evidenced` (the gate — literally `shown or
str_not_breached(app)`, which is where the household arm lives and the ONLY place it lives) ·
`income_engine._member_income_documented` (the officer's chase list, and through it the pension /
informal / formal-slip asks and the household-size tick) ·
`verdict_income_salary._salary_member_scan` (`any_financial`, the verdict's financial-evidence
line) · **`verdict_income_salary.salary_evidence_stands_without_the_str`** (the second half of the
rule-4 fall-through's gate — audit 2026-09-21; it is the right question there precisely BECAUSE
this module has no STR arm) · **`income_declared_gaps` (the Check-2 declared-wage ask — TD-262
F2)** · and **BOTH screens**, which read it **SERVED** — the officer on the applicant-detail
payload, the student on her own `ApplicationReadSerializer` payload — through
`halatuju-web/src/lib/incomeShown.ts`. Served, never mirrored, with an absent field falling back to
each screen's old presence reading so a half-deployed pair cannot paint a screen of red.

**⚠ IT COSTS THREE QUERIES PER MEMBER, SO THE MEMBER LIST IS A CONTRACT *AND* A BILL (audit
2026-09-21).** The student's `ApplicationReadSerializer` served all five of `_MEMBER_ORDER` on
every read AND on the LIST — which is the call that actually feeds her Documents tab
(`getMyScholarshipApplications` → `ScholarshipNextSteps` → `ScholarshipDocuments`). It now serves
`income_shown.student_income_members`: her working members plus any earner carrying a declared
amount, read off the row at no query cost. 22 → 7 queries on the STR route, 25 → 13 with one
earner. **The answer for a member that IS served is byte-identical**; an absent key lands on the
fallback `incomeShown.answerFor` already implements by design. The OFFICER payload
(`serializers_admin.py`) still serves all five, deliberately — the cockpit reads members the
student's own screen never asks about. Pinned in `tests/test_query_budgets.py`.

### The declared-wage ask (TD-262 F2) — `apps/scholarship/income_declared_gaps.py`

`declared_income_gaps(application)` is the ONLY reader of "who still owes us evidence for a wage
they declared", and `check2_queries._gap_sets` is its only caller → the soft, uncapped
`declared_income_evidence_missing` request. **Salary route only; a valid STR accepts every
declared amount at once.** It raises no gap for a member whose income is already **SHOWN** another
way (`income_shown`).

**⛔ THE FOURTH WAY IS FOR HOUSEHOLDS WITH NEITHER A CURRENT STR NOR A PAYSLIP** — owner ruling
2026-09-20: *"If STR has been fulfilled, there is no need for the student to complete the cash
door."* So **the cash door is never added to the STR route, and the two early returns above
(off-salary-route, and a valid STR) are RULINGS, not unfinished edges.** Each has a pinned row in
`tests/test_income_declared_gaps.py`. Do not "complete" them.

**⚠ SHOWN, NOT PRESENT — and the `has_income_support_doc` test is SUBSUMED, not kept beside it.**
Once a declared amount exists, `income_shown`'s third arm *is* that predicate, so testing both
would put one rule in two places in the very function TD-262 came to un-duplicate. A `not_salary`
photo or a blank EPF still leaves the ask standing, which is the F4 / F5 rule.

**⚠ IT LIVES IN ITS OWN MODULE AND HAS NO RE-EXPORT.** `income_engine.py` is on the oversize
ledger, so the function moved out rather than growing it (the Phase-4 standing rule). A re-export
back into `income_engine` would have needed a `# noqa` and given the name two homes — the first
cut did exactly that and the noqa ratchet caught it. **Import it from `income_declared_gaps`.**

**⚠ NO ELIGIBILITY ANSWER IS IN REACH OF IT.** No gate, no blocker code and no verdict fact reads
this function. A change here can never move a band, so `VERDICT_ENGINE_VERSION` is not bumped for
it.

### The income verdict has two routes, and they live in two files

`verdict_engine._verdict_income` owns the STR route and the order of precedence; the SALARY route
is `apps/scholarship/verdict_income_salary.py` (`verdict_income_salary`, split into
`_salary_relationship_docs` / `_salary_member_scan` / `_salary_unresolved` /
`_salary_place_verdict`, plus `_failed_str_headroom_fact`). It is a separate module because
`verdict_engine.py` is on the oversize ledger — the same reason `income_shown.py` is one — and the
edge is one-way: the salary module imports `verdict_engine`'s `_fact` / `_item` primitives at
module level, `verdict_engine` imports it lazily inside the function.

**⚠ "THE STRONGER PROOF IS PREFERRED" (owner rule 4, `docs/decisions.md` 2026-09-19).** When the
STR is stale, unreadable or in a stranger's name (item 1), **or when the cluster around it is
unfinished — a missing earner IC, a missing birth certificate (item 1b)** — `_stronger_income_fact`
assesses the salary evidence too and answers with whichever reading is stronger. **It can only ever
RAISE a band** — the weaker reading is discarded, so the salary route's own `income_above_b40_line`
RED is never taken over an amber STR answer — and the cluster's unresolved items are carried onto
the raised fact, so nothing the officer or the student was told disappears. Under item 1b that
carry is load-bearing: `earner_ic_missing` / `birth_cert_missing` are rows in
`resolution.CODE_TO_TICKET`, so dropping it would stop asking a raised household for documents it
still owes.

**⚠ ITEM 1b RUNS ONLY WHERE AN STR DOCUMENT EXISTS (`str_doc is not None`), AND THAT IS NOT
FUSSINESS.** With NO STR at all, **§6 rule 2 has already decided the household** one branch up, on
`salary_income_satisfied` — a deliberately STRICTER gate that holds §8's red row for a family with
nothing to fall through to. Offering item 1b's looser reading from the same `gap` overruled it and
lifted an unlinked earner off the fraud floor; an existing test
(`test_verdict_engine.…test_unrelated_earner_ic_does_not_open_the_fall_through`) caught it, and it
was restored by narrowing the code, never by editing the expectation. A pinned row on each side of
the line records it. **Do not widen the branch without re-opening rule 2's gate with the owner.**

**⚠ THE §6 FAILED-STR HEADROOM BLOCK LIVES IN `verdict_income_salary._failed_str_headroom_fact`.**
An STR-route branch in the salary module, and consistent rather than contradictory: `verdict_engine`
keeps the ORDER OF PRECEDENCE that decides a failed STR falls through at all; what it falls through
TO is a salary reading. It moved there verbatim for item 1b because `_verdict_income` sat one line
over its allowance and the standard's answer to that is to extract into the smaller module, never
to raise the number.

**⚠ `salary_income_satisfied` IS NOT "is there salary evidence?" AND MUST NOT BE USED AS THAT
GATE.** It is the submission gate's "one complete cluster", and a cluster is complete on ANY of the
owner's four ways — the fourth being a non-breached household STR. A stale / unreadable /
recipient-mismatched STR is **not breached**, so that predicate is satisfied by the very STR a
fall-through exists to look past. The honest test is the salary reading's own
`income_proof_present` marker. Pinned by name in `tests/test_income_evidence_homes.py` §8.

**⚠ AND `income_proof_present` IS NOT THE WHOLE GATE EITHER — THE FALL-THROUGH NEEDS *TWO*
CONDITIONS (audit 2026-09-21).** That marker follows `found['any_financial']`, one arm of which is
`earner_monthly_income` answering **`declared_str`**: a figure the family TYPED, accepted because
`income_engine.has_valid_str` sees an approved, in-cycle STR. **`has_valid_str` tests the STR's
CURRENCY and never asks whose STR it is.** So the salary reading offered to out-argue a failed STR
could rest ENTIRELY on that STR — a stranger's current Lulus letter plus a declared amount, with no
payslip, no EPF and no supporting letter — and raise the verdict the STR had just failed to settle.
Both new arms were reachable. It broke R5 (*"only the family's own STR count"*) and the 2026-09-20
ruling that the cash/declared door is not for the STR route.

`_stronger_income_fact` therefore now asks **`verdict_income_salary.salary_evidence_stands_without_the_str`
FIRST** — `income_shown`'s three per-earner ways, which have no STR arm by that same ruling — and
`income_proof_present` second. Two questions, not one: *does any earner's income stand on its own?*
and *does the salary route's own reading say so?* A declared amount backed by a READ letter still
raises; one leaning on the failed STR raises nothing. Order matters for cost only (42 → 27 queries
on the discarded case, 39 → 39 on the taken one), never for the answer. §11 of
`tests/test_income_evidence_homes.py` pins the rows, including the two that moved back to their
pre-2c6dbe68 bands.

**`has_valid_str` NOW ASKS WHOSE STR IT IS (TD-285, owner ruling 2026-09-29: *"close it now, the
F8 way"*).** It is `currency in (current, unconfirmed) AND NOT
income_str_ownership.str_check_names_a_stranger(sc)` — F8's rule, applied to the SAME
`student_str_check` reading the predicate already took, so it costs **no extra query** (the naive
`not str_recipient_is_stranger(application)` re-reads every household IC and DOUBLES the cost,
8 → 16; `test_query_budgets.TestHasValidStrQueryBudget` refuses it). **A POSITIVE mismatch refuses
ONLY when it is COMPLETE on a field the STR offers** (owner's F1 ruling, 2026-09-29: *"we cannot
judge" is NOT "stranger"*): every member of `income_str_ownership.str_roster` — a recorded
father/mother not `deceased`/`no_contact`, a guardian, the declared earner, every working member —
compared on that field, "read" counted PER FIELD (`student_str_check`'s `ic_read_members` =
`{on_file, name, nric}`, collected in the one matching loop). Otherwise the STR still vouches, does
NOT block submission (the lead's reading — decisions.md; TD-309), and the IC is ASKED after
submission as `<member>_ic_for_str_missing` or `_unreadable` (on file, field unread). A recipient
that did not read, or no household IC at all (`no_ref`), still vouches as before. The four callers move together: the Check-2 declared-wage ask (a
salary-route household on a stranger's STR is now asked for the letter — consistent with the
2026-09-20 cash-door ruling, which is about an STR that FULFILS something), per-capita on both
routes + `profile_engine` + the reconciliation tick, `on_str`, and the
`income_declared_accepted_str` / `_evidenced` code. The whole 336-row matrix — 80 rows moved fully
(true strangers), 48 freed at the gate — is `tests/test_income_whose_str_vouches.py`;
`VERDICT_ENGINE_VERSION` 2026-09-29.1. ⚠ The audit's fall-through gate is load-bearing for every
cannot-judge STR (it vouches, so the salary reading can rest on it) — never delete it.

**⚠ `on_str` IS STUDENT-FACING.** `check2_queries._gap_sets` uses it to pick the STUDENT's
high-utility clarify (`high_utility_expense_str` vs `high_utility_expense`, the latter quoting the
reported household income). Anything that moves `has_valid_str` therefore closes an open `_str`
clarify, raises the other variant (capped, lowest priority) and, via the re-armed notice, sends
`send_query_raised_email` from the hourly sweep. Pinned end to end in sections 5–6 of that test
file. Grep the consumers of a return value before calling a caller "officer-facing".

**⚠ THE AUDIT'S FALL-THROUGH GATE STAYS.** After TD-285 its two original rows are held by the
predicate too, but an STR whose recipient did NOT read still vouches, so on the incomplete-cluster
arm the salary reading can still carry `income_proof_present` off the STR alone.
`salary_evidence_stands_without_the_str` is what stops that raising a red — pinned by
`test_the_gate_still_bites_where_absence_keeps_the_str_vouching` (§11). Do not delete it as
redundant.

**⚠ A RAISED FACT CARRIES THE STR ROUTE'S EVIDENCE AS WELL AS ITS ASKS**
(`verdict_income_salary.raised_income_fact`). Item 1 was explicit that the cluster's unresolved
items survive; its greens were taken wholesale from the salary reading, so `str_verified` and the
STR earner's own `earner_ic_present` left the officer's card with the band. In the ordinary shape
of this case those are about a DIFFERENT PERSON from the one the salary reading named — the STR is
the mother's, the payslip the father's. Winning reading first, then the STR route's lines in order,
minus anything already stated **VERBATIM**; exact items, never codes, because deciding two items
are "the same claim" is a new matching rule. Band, status and unresolved list are untouched, which
is why this half alone does not bump `VERDICT_ENGINE_VERSION`. Pinned in §12.

**⚠ A CURRENT GENUINE STR IS SETTLED UPSTREAM AND PAYSLIPS NEVER TOUCH IT** (rules 1 and 2):
`_str_precedence_verdict` returns before the route split is reached. Removing it reddens five
tests; do not "simplify" the fall-through past it.

### Only the family's own STR opens the submission gate

**`apps/scholarship/income_str_ownership.py`** (TD-262 F8, owner 2026-09-19) holds
`str_recipient_is_stranger` and `stranger_str_blocks_submission`. `services.income_doc_blockers`
reads the second, guards BOTH of its `salary_income_satisfied` early returns with it, and emits
the blocker code `str_not_household` (student + officer copy in en / ms / ta).

**⚠ `str_not_breached` IS DELIBERATELY LEFT RECIPIENT-AGNOSTIC AND MUST STAY SO.** It is the
obvious place to put the ownership test and the wrong one: it feeds `member_income_evidenced` →
`member_cluster_complete` → `salary_income_satisfied`, which `verdict_engine._verdict_income` reads
at str-proof-spec §6 rule 2, so tightening it moves a verdict BAND as well as the gate. It also has
a web mirror (`officerCockpit.strNotBreached`) that stays honest only while the api does not move
under it. F8 is a GATE ruling, applied at the gate.

**⚠ TWO LINES BOUND THE TEST.** *Absence is not a mismatch* — `no_ref` (the STR read nothing, or no
household IC is on file to compare against) never blocks; only a positive `mismatch` with no match
anywhere does. And *matching is exhausted first* — name OR nric, independently, against every
parent/guardian, which `income_engine._str_recipient_household_match` already does; this module
only reads its verdict, so a second matching rule can never appear. The block also fires ONLY where
no working member's income is shown on its own (`income_shown`), so it can never newly block a
household that documented an earner properly.

**⚠ THE FROZEN GATE IS NOT TO BE TIDIED.** `services.application_completeness` keeps its legacy
document-type arm OR-ed with `any_member_income_evidenced`; it is MORE permissive in four cases and
replacing it un-submits students and nulls their `requirements_snapshot` (TD-262 F9). Any change to
an income home answers to `tests/test_income_evidence_homes.py`, `tests/test_income_shown.py` and
`halatuju-web/src/lib/__tests__/incomeEvidenceHomes.test.ts`.
