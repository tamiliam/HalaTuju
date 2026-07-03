# Verification-Model Hardening Roadmap (Check 1 / Check 2 / Check 3) — handover plan

## Context

The 2026-07-03 audit of HalaTuju's document-verification and verdict model
(`docs/plans/2026-07-03-check-model-audit.md` — findings #1–#17, sections E and F1–F3)
found the architecture sound but identified: two document types that are dead verification
limbs, a leaking query lifecycle, a three-way strictness inconsistency at the salary/STR
route seam, a systematic slotting hole for model-raised doc requests (the root of the
"Mother's IC shows as Earner's IC" complaint), Gopal being half-wired in the Action Centre,
and live-prod evidence that human reviewers hand-raise ~60 items vs the model's ~47 because
nine recurring ask-themes have no model template. This roadmap turns those findings into
six sprints, sized for the WAT sprint discipline, to be executed by a fresh agent.

**The audit document is the finding source of truth** — every sprint below cites its
finding numbers; the implementing agent MUST read the audit doc's cited entries (they carry
file:line evidence and concrete failure scenarios) before coding each sprint.

**Owner decisions already taken (2026-07-03 — embed, do not re-ask):**
1. **QC soft floor**: QC-Accept is blocked while any verdict fact is red/`gap`; a `super`
   may override with a recorded reason (audit #5).
2. **Promote all nine human-ask themes** into Check 2 (audit §E).
3. **Motivation stays human**: structure it for Check 3 (standing interview-agenda section
   + reviewer-guide entry, seeded when the statement of intent is thin) — no student query.
4. **Over-the-line income stays interview-only**: never a student message; hard-seed it
   into the interview agenda (with sprint V3's agenda work).

## Operating rules for the implementing agent (non-negotiable)

- Read `C:\Users\tamil\Python\CLAUDE.md` (workspace) + `halatuju_api/CLAUDE.md` (project)
  first; follow `Settings/_workflows/sprint-start.md` and `sprint-close.md` for EVERY
  sprint. Read `docs/lessons.md` at each sprint start.
- Repo: `C:\Users\tamil\Python\Production\HalaTuju` (branch per sprint off `main`; merge
  --no-ff; push at close = production deploy via Cloud Build; verify build SUCCESS with
  `gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`).
- **Migrate-first**: deploys never run `manage.py migrate`. Any new column/table is applied
  to prod FIRST via the Supabase MCP (project `pbrrlyoyyiftckqvzvvo`), hand-written
  Postgres DDL + `INSERT INTO django_migrations`, sentinel-column check before ALTER,
  verify after, RLS on new tables. `scholarship_applications` / `applicant_documents` are
  the live table names (check `Meta.db_table`, never assume).
- Tests: backend `cd halatuju_api && python -m pytest apps/scholarship` (2,019) and
  `apps/courses/tests/ apps/reports/tests/` (1,199); web `cd halatuju-web &&
  node node_modules/jest/bin/jest.js` (412). Full suites green before every close; a
  regression test per fixed finding. Don't run full pytest + `next build` back-to-back
  (8 GB box) — type-check with `npx tsc --noEmit --target es2018 --downlevelIteration
  --skipLibCheck` (17 pre-existing errors in old test files / stale .next are NOT yours).
- i18n: every student/officer string in en + ms + ta (Tamil per
  `~/.claude/.../memory/tamil-style-guide.md`, mark first-drafts for owner refine). Keys
  live in `halatuju-web/src/messages/*.json`; parity is jest-enforced.
- Never re-run document extraction locally (no Storage access); prod re-extraction only
  via cockpit Re-run / live service. The vision clobber guards (2026-07-03) protect, but
  don't rely on them.
- Check 1 persona = warm coach, diagnose→action→stop, no cheerleading, "you/your mother's";
  Check 2 persona = firm steward, every line a lean + an action, "the student/the earner".
  Action Centre = neutral-helpful third register (V6 documents this).
- Update `CHANGELOG.md`, retro, `docs/decisions.md`, `docs/lessons.md`, roadmap prune,
  memory files + `Settings/_shared/projects.json` (backup first), and run
  `python Settings/_tools/wat_lint.py` at every close, exactly as sprint-close.md says.

## Sprint V1 — Slot & document integrity (complexity: HIGH; do first)

> **✅ SHIPPED (code) 2026-07-03** — worktree `.worktrees/verify-model`, branch `feat/verify-v1`;
> NO migration; retro `docs/retrospective-2026-07-03-verify-v1.md`. All four findings closed in
> code + tested (2025 pytest + 412 jest). **V1.4 backfill DONE** (claude.ai Supabase MCP): 24/29
> blank-tagged income docs attributed (19→mother, 5→father; request-keyed docs resolved from their
> officer item); final tags 145 mother / 76 father / 2 brother / 5 blank. **CARRY:** 5 ambiguous
> rows left for the owner — app 88 (×4, no earner/members) + app 16 (×1, guardian-vs-brother; test
> account). NB much of V1 was already scaffolded: guardianship's verdict/resolution/chip existed —
> only the extraction TRIGGER was missing; `income_support_doc` needed the schema + a read-requirement.

Fixes the "boxes that tick themselves" + the slotting/labelling root cause.
**Findings: audit #1, #2, F2, F3.**

Scope:
1. **Wire `guardianship_letter` into the pipeline** (#1): add it to
   `SUPPORTING_NAME_CHECK_TYPES` (`halatuju_api/apps/scholarship/views.py:566-571`) so
   upload + `reextract.py` process it (schema already exists in `vision.py`
   `_FIELD_SCHEMAS`/`GEMINI_EXTRACT_DOC_TYPES`). Verify the downstream now lights up:
   `income_engine.student_guardianship_check`, guardian branch in
   `verdict_engine._verdict_income` (:335 reads `vision_name` — confirm the extraction
   populates what it reads, adjust to `vision_fields` fields if needed), cockpit chips
   (`officerCockpit.ts:394-401`), cluster coach `income_rel_doc_unreadable` path,
   `resolution.doc_match_verdict` mismatch branch (add one, mirroring birth_certificate).
2. **Give `income_support_doc` a read + verdict** (#2): add to
   `GEMINI_EXTRACT_DOC_TYPES` + `_FIELD_SCHEMAS` (fields: name, nric, amount, period,
   issuer/kind — employer letter / bank statement / community letter), a
   `doc_student_verdict` branch (person-match against the declared member), a
   `doc_match_verdict` branch, and make `declared_income_gaps` require a doc that READS
   (not mere presence). Officer chip in `officerCockpit.documentFacts`.
3. **Member-tag model doc requests** (F2): in `check2_queries.py` DOC_SPECS creation
   (~:176-181), write `params={'household_member': <member>}` (the member is derivable
   from the code, e.g. `father_income_proof_missing` → father — store it explicitly in
   DOC_SPECS). The FE (`ActionCentre.tsx` onFile) already forwards `item.params.household_member`.
4. **Backfill the ~29 blank-tagged income docs on prod** (F3): via Supabase MCP, attribute
   blank `household_member` on `applicant_documents` (doc_type in parent_ic/str/
   salary_slip/epf) from context: STR route → `income_earner`; salary route → only where
   unambiguous (single working member) — leave genuinely ambiguous rows and list them for
   the owner. Dry-run SELECT first; record counts in the retro.
5. **Label honesty** (F3): rename `admin.scholarship.docsDrawer.type.parent_ic` from
   "Earner's IC" to "Family member's IC" (en/ms/ta) and always render the derived member
   when available (`earnerMemberFor`, `officerCockpit.ts:528` + the two label call sites in
   `admin/scholarship/[id]/page.tsx:1641-1713`).

Acceptance: a selfie uploaded as a guardianship letter is held 'mismatch' with a Gopal
coach; a blank image as income_support_doc does NOT clear `declared_income_gaps`; a
salary-route Action-Centre upload against "father's salary slip" lands tagged `father` and
counts in `_cluster_docs`; prod blank-tag count reduced to the ambiguous remainder; no
"Earner's IC" label without a member qualifier. Regression tests for each.

## Sprint V2 — Resolution correctness (complexity: MEDIUM)

> **✅ SHIPPED (code) 2026-07-03** — branch `feat/verify-v2`; NO migration; retro
> `docs/retrospective-2026-07-03-verify-v2.md`. All three findings closed + tested (2040 pytest +
> 412 jest). Built directly on V1's seam (member-aware resolve uses V1.3's `params.household_member`;
> the pending/unreadable holds reuse V1's `student_verdict` pattern).

The re-upload/resolve path must verify what it resolves. **Findings: #3, #4, #16.**

Scope (all in `halatuju_api/apps/scholarship/resolution.py` + tests):
1. `doc_match_verdict` offer branch (:270-277): also fail (`'mismatch'`) when
   `pathway_engine.offer_official_status` says not-official — a non-official offer must not
   resolve an official-offer request (#3).
2. Add pending/unreadable handling for salary_slip/epf/birth_certificate (:291-303),
   mirroring the results_slip branch: an errored/unread extraction holds the task open
   (#4). The 2026-07-03 clobber guards make 'pending' reliable.
3. Make `resolve_doc_items_for_upload` (:355-365) member-aware (only resolve items whose
   `params.household_member` matches the upload's tag — V1.3 provides the params) and
   criterion-aware for `income_doc_stale` (re-check recency via the same helper
   `income_engine` uses (~:1617) before resolving).
4. Make `income_doc_stale` + the `*_income_proof_missing` codes re-raisable in
   `sync_check2_queries` when the gap re-fires after a resolve (drop the "never re-asked"
   guard for doc-kind items ONLY; clarifies stay once-ever).
5. Finish the S4 #13 unification (#16): `help_engine.verdict_for_document` (:432) uses
   `income_engine.STR_COACH_STATES`; FE `documentHelp.ts` `shouldShowCoach` (:96-98)
   mirrors (add the two missing states to its condition).

Acceptance: concrete scenarios from audit #3/#4 fail before, pass after; a wrong_type STR
re-upload in the Action Centre shows a Gopal coach.

## Sprint V3 — Query lifecycle & the Check-3 handoff (complexity: MEDIUM/HIGH)

> **✅ SHIPPED (code) 2026-07-03** — branch `feat/verify-v3`; NO migration; retro
> `docs/retrospective-2026-07-03-verify-v3.md`. All four findings closed + tested (2046 pytest +
> 413 jest). Two design forks were taken to the OWNER mid-sprint: (a) locked apps SHOW pre-existing
> items but create none; (b) per-item SLA with a submit-window `is_ready` floor. **⚠ OWNER
> CHECKPOINT is due here** — owner reviews the new reviewer-facing copy (agenda ambers + Motivation
> + overflow note, Tamil first-draft) before the owner-visible V4.

Check 2 stops asking the unanswerable and stops losing the asked. **Findings: #6-#9 +
owner decisions 3 & 4.**

Scope:
1. Gate `sync_check2_queries` + `sync_resolution_items` creation on NOT
   `services.querying_locked(app)` (`check2_queries.py:120`, `resolution.py:132`); remove
   `interviewed` from `QUERY_SLA_ACTIVE_STATUSES` (`services.py:400`) so no notify email
   invites an answer the API refuses (#6). Decide-and-document (decisions.md): doc
   requests remain answerable post-lock (uploads stay open) — only clarifies close.
2. Clarify cap redesign (#7): cap = 3 CONCURRENTLY OPEN clarifies (waived/resolved free a
   slot); when a higher-priority gap is crowded out, surface a cockpit note
   ("2 more queries waiting") so capped-out gaps are visible. Keep `reporting_date_unknown`
   effectively uncapped by ordering or a priority carve-out (it's a sponsor-profile input).
3. Per-item SLA (#8): base the reminder/lapse clock on `ResolutionItem.created_at`
   (5 days), not `profile_completed_at` (`services.py:412-426`); `is_ready_for_assignment`
   keeps a floor so late items don't block review forever — mirror the current grace logic.
4. **Interview agenda folding** (#9 + decisions 3/4): `_interview_agenda`
   (`views_admin.py:611`) additionally includes (a) OPEN resolution items (any source),
   (b) the "needs interview" verdict ambers (`income_unverified_needs_interview`,
   `income_above_b40_line`, `academic_grade_uncertain`, `ic_service_down`) — over-the-line
   phrased for the interviewer only, and (c) a standing **Motivation & grit** section
   (seeded rich when `submission_review` flags `motivation_missing` / thin statement of
   intent). Update the reviewer Guide + FAQ in the same change (standing feedback rule:
   reviewer-section changes update the Guide/FAQ together).

Acceptance: no item/email can be created for a locked app; open queries + the four ambers
appear on the interview agenda; motivation section always present; SLA tests on late items.

## Sprint V4 — Check-2 growth: promote the nine human asks (complexity: HIGH; owner-visible)

> **✅ SHIPPED (code) 2026-07-03** — branch `feat/verify-v4`; migration `0091` (choices-only, owner
> records via MCP at deploy); retro `docs/retrospective-2026-07-03-verify-v4.md`. All nine items +
> two doc types built + tested (2055 pytest + 413 jest). Raise-conditions taken to the OWNER and set
> CONSERVATIVE (under-ask, tune post-deploy) since they land on live students. **CARRY:** post-deploy
> cohort verification + margin tuning (esp. `utility_bill_missing`, `household_roster_undercount`).

**Findings: §E; owner decision 2 (all nine).** This is a feature sprint (new model
surface): follow the full sprint rails; NO Stitch needed (no new pages — new items render
in the existing Action Centre cards).

Scope:
1. **Two new doc types** on `ApplicantDocument.DOC_TYPES` (migration, choices-only +
   migrate-first no-op DDL): `school_leaving_cert`, `semester_result` (current-CGPA slip
   for continuing students). Extraction schemas (semester_result: institution, programme,
   semester, cgpa; leaving cert: name, school, year), officer chips, upload labels,
   `READABLE_DOC` labels, Gopal fallbacks.
2. **New auto-raised items** in `check2_queries.py` (firm-steward copy, en/ms/ta, template
   from the officers' own best phrasings quoted in audit §E — fix their typos):
   - doc requests: `school_leaving_cert_missing` (post-SPM applicants),
     `semester_result_missing` (continuing STPM/college students — detect from
     pathway/track), `epf_statement_missing` (EMPLOYED parents as corroboration — OPTIONAL
     like `unemployment_epf_missing`), `utility_bill_missing` (when neither bill uploaded).
   - clarifies: `deceased_parent_detail` (roster non-earning status 'deceased'),
     `informal_work_detail` (declared/informal occupation — own-account vs employer,
     average monthly wage), `household_roster_undercount` (stated size > described members
     — the missing direction of 2C), `other_scholarships_followup` (other scholarships
     listed at apply), `high_utility_expense` (promote `utility_reasonable`'s officer
     signal to a clarify).
   Mind the V3 cap semantics; these enter the same priority order (income-story items
   above comfort items). Wire each into `sync` gap-detectors in `income_engine`/
   `check2_queries` (reuse `household_status_gaps` patterns) + auto-resolve conditions +
   `actionCentre.ts` KNOWN_CODES + i18n cards.
3. Verify against the prod cohort: after deploy, run the sync for one Complete-stage app
   (via cockpit refresh) and eyeball that the new items raise only where the human items
   showed the theme.

Acceptance: each new code has raise-condition + auto-resolve + i18n(3) + KNOWN_CODES +
regression tests; existing officer-raised duplicates are NOT re-raised on apps that
already answered them (dedupe by satisfied gap, not by code existence alone).

## Sprint V5 — Verdict evenness + QC floor (complexity: MEDIUM; changes live verdicts)

**Findings: #5, #10-#14; owner decision 1.**

Scope:
1. **Route-seam reconciliation** (#10): FIRST write the single truth table into
   `docs/scholarship/str-proof-spec.md` (supersede the bands-doc paragraph; cross-link):
   over-the-line = RED on both routes; thin-headroom = the documented S4 exception (green
   on the fully-confirmed salary route) — annotate the spec with that exception;
   `str_recipient_mismatch` → `recommend` (amber) per spec §8. Then align
   `verdict_engine._verdict_income` (:374-375, :417-418, and the salary `over` branch
   :570-572 → `gap`) and update tests. Reviewer-visible re-banding on deploy — say so in
   the changelog.
2. **QC soft floor** (#5, decision 1): `AdminQcDecisionView.accept` refuses
   (`400 verdict_gap_floor`) while `build_verdict` has any fact at `gap`, unless the
   caller is `super` AND provides an override reason (recorded — reuse the
   `DecisionReopen`-style audit pattern or a field on the QC decision). Cockpit: disable
   the Accept button with the reason listed; super sees an override affordance. i18n ×3.
3. **SOFT_EVIDENCE refresh + guard** (#11): add `unemployment_epf_corroborated`,
   `household_size_confirm` (officerCockpit.ts:33-38); add a jest guard test that fails
   when a verdict-engine evidence code whose comment says soft is absent from the denylist
   (mechanical mirror-test like `test_subject_drift.py` — parse verdict_engine.py for a
   `# SOFT` marker convention and pin).
4. **Wrong-person offer decision** (#12): band `offer_name_mismatch` amber WITH a
   documented rationale in decisions.md + fix the bands-doc mislabel; no submission-block
   change (owner has not asked for one).
5. **Doc-rot fixes** (#14): verdict_engine.py:33-36 colour map; `_verdict_pathway`
   docstring; bands-doc "only fact using all four bands"; check2_queries i18n-namespace
   pointer; note #13's genuineness-skew as a recorded limitation (no code).

Acceptance: spec table is the single source; engine matches it; QC floor enforced with
super override; SOFT_EVIDENCE guard test in place; all cited docstrings corrected.

## Sprint V6 — Gopal in the Action Centre + persona polish (complexity: MEDIUM)

**Findings: F1, #15, #17.**

Scope:
1. **Persistent coach** (#15/F1): derive `coachDoc` from the FETCHED documents on
   Action-Centre load (the API already returns docs + verdicts) instead of only in-session
   upload state (`ActionCentre.tsx:139` + state init) — a reload keeps Gopal's advice on a
   held task.
2. **Cluster coach in the Action Centre** (F1): mount `IncomeClusterCoach` (from
   `ScholarshipDocuments.tsx`) for open income doc-tasks whose member cluster has advice
   (`IncomeClusterHelpView` already exists) — kills the null-render dead end for
   wrong-person slips/EPF/BC.
3. **Telemetry** (F1): one log line in `DocumentHelpView`/`IncomeClusterHelpView`
   (`served source=ai|fallback|none verdict=<v> app=<id>`) so Gopal's performance becomes
   measurable in Cloud Run logs; note the query in the retro.
4. **Persona strings** (#17): rewrite the Action-Centre Gopal greeting to lean coach
   register (name the next action, no cheerleading); replace "the earner" with the
   member-specific possessive in the three fallback strings + `str_recipient_mismatch.desc`
   (params carry the member — reuse `scholarship.docs.income.wizard.member.*`); fix ta
   "சிக்கு கோபால்" → keep "Cikgu Gopal" in Latin script (flag for owner) and the
   "எனத் உறுதிசெய்யவும்" grammar slip; polish `grades_unverified` officer line.
5. **Document the third register**: one paragraph in
   `docs/scholarship/str-proof-spec.md` §personas (or decisions.md) naming the Action
   Centre's neutral-helpful register alongside the two personas.

Acceptance: reload keeps the coach; wrong-person payslip re-upload shows cluster advice in
the Action Centre; log lines visible; persona strings pass the register rules; Tamil
changes marked first-draft for owner.

## Execution & handover mechanics

- Order: V1 → V2 → V3 → V4 → V5 → V6 (integrity → correctness → lifecycle → growth →
  evenness → polish). Re-plan the remainder at each close if reality shifts.
- At implementation start: save this roadmap into the repo as
  `docs/plans/2026-07-03-verification-model-roadmap.md` (commit with the first sprint) and
  add a "Next Sprint" pointer in `halatuju_api/CLAUDE.md`.
- Owner checkpoints: after V3 (before the owner-visible V4 growth sprint) and at the end
  (final report must include: all new/changed student+officer copy for review — especially
  Tamil first-drafts — and the verdict re-banding summary from V5).
- Deferred/parked (do NOT implement without asking): payslip genuineness scoring (#13),
  any student-facing over-the-line message (decision 4), changes to the two-persona split.

## Verification (end-to-end, per sprint and final)

- Full backend + jest suites green at every close; regression test per finding fixed.
- Prod smokes after deploy: V1 — blank-tag count query on `applicant_documents` +
  one cockpit Re-run of a guardianship letter; V3 — confirm no new items on a locked app;
  V4 — sync one Complete-stage app and review raised items; V5 — QC-Accept refusal on a
  gap-fact test case in cockpit; V6 — Gopal log lines appear in
  `gcloud logging read ... "/help/"`.
- The audit doc's concrete scenarios (each finding has one) are the acceptance oracle:
  before = reproduces, after = fixed.
