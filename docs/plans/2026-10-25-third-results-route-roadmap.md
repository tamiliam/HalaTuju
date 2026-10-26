# Third results route (Matriculation / Asasi / Diploma) — roadmap (2026-10-25)

**Status:** PLAN ONLY, awaiting owner approval (as the engineer analysis on org request #38, covering
#37 and #43). Nothing built. Planned per `Settings/_workflows/implementation-planning.md`.
**Closes when built:** TD-326 (results held = the HIGHEST completed qualification; Matric / Asasi /
Diploma as held results), org requests #37, #38, #43.
**Out of scope / related work:** the genuineness corpus (STPM results family, UiTM wording, the
"not checked" safety net, TVET families, `MODEL_VERSION` bumps, rescoring; #47) is a separate piece
of work — `docs/plans/2026-10-25-document-corpus-gaps-brief.md`. This roadmap keeps only plain TYPE
DETECTION (is this document an STPM / Matriculation / Asasi / Diploma result?) for routing.

## 0. Owner-approved product decisions (2026-10-25), verbatim in substance

1. SPM and STPM routes stay as they are.
2. Third card "Matriculation, Asasi or Diploma" (subtitle "STPM-equivalent qualifications"). Pick
   Matriculation / Asasi (Foundation) / Diploma; CGPA 0.00–4.00; co-curriculum 0–10 (HIDDEN for
   Diploma); MUET band; then SPM results, required, as the STPM page's SPM block. No subjects/stream.
   Overall CGPA = 0.9×CGPA + 0.1×(koko/10×4); Diploma = CGPA as is. Approved mock (artifact
   UFp2EFsJmfQweFqWr7eu2m).
3. STPM-equivalent everywhere: `min_stpm_pngk` applies; merit on one 0–100 scale as the course side
   does (`cgpa/4×100`); the applicant list's raw-CGPA STPM merit is fixed (characterise first).
4. Uploads: SPM holders — SPM slip compulsory. Tertiary (STPM or third route) — ONE compulsory
   "higher results" upload with a student-chosen type; the system also detects the type and flags a
   disagreement to student + reviewer; SPM slip optional at apply, requestable later.
5. Check 2: reviewers request "STPM / Matriculation / Asasi / Diploma results" and "SPM results" by
   name (#37); SPM can be asked for later.
6. Wrong slip (#43): a higher result where SPM is expected is recognised; no false SPM comparison;
   plain note to reviewer and student; never advise changing grades.

## 1. What the org requests actually say (DB, read 2026-10-25)

- **#37** "I can ask for the student to upload their SPM results but not … STPM or metrikulasi or
  assasi results."
- **#38** "how to upload both STPM and SPM docs? now can only upload one not both" (Additional
  documents offers only School-leaving certificate and Statement of intent).
- **#43** app #153: "student has entered both SPM and STPM results but only uploaded SPM results
  slip". **Measured: the document in #153's slot is an STPM slip** (`exam` = "Malaysia Higher School
  Certificate 2025"). The profile's `results_exam_type` is `'spm'` (her last completed form) with
  `stpm_cgpa` 3.92 on file, so `results_held` reads SPM and the STPM slip is compared against SPM
  grades. That is the "highest" rule (TD-326) and the wrong-slip case together.
- **#47** (ILKBN graduate, "no action required") — corpus brief, not here.

## 2. Current-state map

### 2.1 Exam choice and onboarding (web)
- `halatuju-web/src/app/onboarding/exam-type/page.tsx:14-22` — two cards; writes only localStorage
  `KEY_EXAM_TYPE` (`spm`/`stpm`) and routes to `/onboarding/grades` or `/onboarding/stpm-grades`.
- `onboarding/stpm-grades/page.tsx` (658 lines) — stream, PA + 3–4 subjects, MUET, koko, SPM block.
  CGPA from the server (`calculateCgpa` → `/api/v1/calculate/cgpa/`, page 195-216;
  `apps/courses/views.py:2101-2131`: `overall = academic×0.9 + min(koko,10)×0.04`,
  `merit_percent = overall/4×100`). Completion gate 219-222 = PA + ≥3 graded + MUET + stream —
  **the SPM block is NOT required today** (see open decision D4). Continue (224-241) stores
  `KEY_STPM_CGPA` = the OVERALL CGPA, `KEY_KOKO_SCORE`, `KEY_SPM_PREREQ`, `KEY_RESULTS_EXAM_TYPE='stpm'`.
- Saved to the API only at `onboarding/profile/page.tsx:105-185` → `POST /api/v1/profile/sync/`.
  The STPM koko is NOT sent as its own field (175-181 sends `coq_score` from the SPM
  `KEY_PROFILE.coqScore`); it lives only inside the overall `stpm_cgpa`.
- Route resolution on the web: `lib/resultsCache.ts:105-129` (`stpm` / `spm` / `stpm_pending` /
  `none`), `lib/scholarship.ts:21` (`Qualification = 'spm' | 'stpm'`), `profileAcademicSummary`
  `lib/scholarship.ts:480-505` (served `results_held` wins). ~65 route checks across 20 files
  (dashboard 11, ApplicantCards 10, saved 6, lib/scholarship 5, search/resultsCache/exam-type/
  scholarship apply 3 each, plus auth-context, AuthGateModal, PathwayPicker, onboarding grades/
  profile, storage, ScholarshipReview, admin students, pathway/stpm, ScheduleEditor).
- Scholarship apply: `app/scholarship/apply/page.tsx:194-211` — an STPM student's degree picker is
  fed by `/stpm/eligibility/check/` (needs STPM subject grades); 608-610 shows the CGPA; 655-700
  branches `examType === 'stpm'`.

### 2.2 Profile fields (`apps/courses/models.py`)
- `exam_type` 796-800 (max_length 10, choices spm/stpm, default spm) — "heading for".
- `results_exam_type` 816-820 (same choices, blank = never recorded) — last COMPLETED form.
- `stpm_grades` 821, `stpm_cgpa` 825 (stores the OVERALL CGPA), `muet_band` 826, `coq_score` 827
  (SPM koko, feeds SPM merit), `spm_prereq_grades` 831.
- Sync serializer drops an unbacked `results_exam_type` (`apps/courses/serializers.py:302-329`;
  STPM is backed by `stpm_grades` or `stpm_cgpa`).
- **Live finding:** of 64 STPM-held applications, SPM grades sit in `grades` for 42 and in
  `spm_prereq_grades` for 54 — the SPM comparison (`academic_engine.compare_academics`) reads only
  `grades`. A tertiary applicant's SPM grades need ONE reader.

### 2.3 The route decision
- `apps/courses/exam_questions.py`: `heading_for` 45-53, `has_stpm_results` 56-62, `results_held`
  65-88 (recorded completion wins; Form Six correction). Docstring 38-40 + decisions.md 2026-10-02
  TD-324 §5: when Matric/Asasi/Poly join, `results_held` is to be written as **"highest" outright**
  (a ranking over completed qualifications, not "last form completed").
- `serializers_admin.held_qualification = results_held` (213) — **a gate since TD-324**.
- Readers of `results_held`: `courses/views.py:1154` (profile payload), `shortlisting.py:146`,
  `pool.py:42`, `profile_engine.py:733`, `submission_review.py:99`, `vision.py:1980` (SPM slip
  parser gate), `serializers_admin.py:229,296`.
- Readers of `heading_for` (where she is studying): `income_engine/occupation.py:146-160`
  (school-leaving cert gap: only when heading for SPM), `income_engine/epf_evidence.py:22-50`
  (semester-result gap: heading for STPM). A third-route value must keep both quiet — pin it.

### 2.4 Academic test, merit, pool
- `shortlisting._academic_ok` 126-189: `exam == 'stpm'` → `stpm_cgpa >= min_stpm_pngk`
  (None = not applied); else SPM A-/B+/credit/merit floors. `spm_merit` 95-123 (SPM only).
  `min_merit_score` is SPM-only by design (docstring 40-41).
- Doors that run it: submit `views.py:323` → `services/intake.score_application` 204-220; rescore
  `intake.py:297` (`rescore_pending_decisions`, cron door `rescore-pending`). Nothing else calls
  `evaluate` (QC, reopen, revert, pool do not re-run the gate).
- Merit: `serializers_admin._application_merit_score` 216-243 returns **`p.stpm_cgpa` raw** for
  STPM; consumers: list + detail serializers (257/299, 347/665), merit sort
  `views_admin/applications.py:150-153` (`or 0`, in Python), `profile_engine._merit` 479-483 (AI
  anonymous profile input, "PNGK for STPM"), web `admin/scholarship/page.tsx:383,485`,
  `[id]/view/ApplicantCards.tsx:191-200`.
- Sponsor academic line: `pool.academic_band` 32-46 ('STPM · PNGK x' / 'SPM · N As');
  `emails/sponsor_cards.py:156` parses that string.
- Course side: `apps/courses/views.py:2124-2125`; web `app/dashboard/page.tsx:575`
  (`studentMerit = cgpa/4×100`).

### 2.5 Cockpit, coach, documents
- Academic tile: `verdict_engine._verdict_academic` 285-351 — reads `results_slip` only; name, then
  `read_slip` + `compare_academics(profile.grades, …)` (missing / mismatched / uncertain);
  fact→doc map 988; genuineness ladder `_apply_genuineness_ladder` 959. `VERDICT_ENGINE_VERSION`
  99 (`'2026-10-25.1'`) bumps whenever a band can move.
- `academic_engine.py`: `_BAND_TO_GRADE` 103-109 (`'lulus'→'E'` — why an STPM "Lulus Penuh" reads
  as E), `_is_spm_exam` 356-362, `read_slip` 531, `compare_academics` 576, `spm_exam_year_unknown`
  659 (already skips a non-SPM doc, #77), `student_slip_check` 697-757.
- Help coach: `help_engine.py:383-409` (results slip → `slip_subjects_missing` /
  `slip_grade_mismatch` …, from `student_slip_check`).
- Extraction: `vision.py:2030-2060` — SPM cert parse, then SPM positional parse (skipped unless
  `results_held == 'spm'`), then Gemini with the **SPM** schema/hint (`vision.py:1329-1332, 1407`).
  Genuineness for the slot 2141-2157 scores against SPM families only.
- **Live (results_slip slot):** 184 SPM docs; **34 STPM docs across 25 applications** (18 with no
  SPM doc, 7 with both); 0 genuine, ~31 suspect/fake among them; 1 matriculation offer (#77,
  `not_results_slip`). Other non-SPM titles ("Academic transcript", "Examination result slip
  semester II") also land in this slot.
- Document types: `models/documents.py:17-55` (`results_slip`, `semester_result`,
  `school_leaving_cert`, `other`; no higher-results type). `doc_type` max_length 30.
- Required documents: `requirements.required_documents` 197 via `resolve` 89 — **per programme**,
  frozen in `requirements_snapshot` at submit (108-120); `results_slip` is a core item (forced
  required, 160-170; seed `seed_application_catalogue.py:50`); platform floor 58.
- Gates: `services/consent_blockers.py:44-48` (`results_slip_missing`), `services/completeness.py:
  84-106` and the grandfathered hard-coded `{'ic','results_slip','parent_ic'}` at 121,
  `services/blockers.py:317, 368-371, 430-432`; codes in `resolution.py:43-45`.
- Upload UI: `components/ScholarshipDocuments.tsx:200-221` (`section('academic','results_slip')`,
  other docs 214), `ScholarshipDocuments/cards.tsx`, `checklists.tsx:421` (`ResultsSlipChecklist`),
  admin `view/DocumentsDrawer.tsx:56,99,179`, `lib/docCategory.ts:57`, `lib/officerCockpit.ts`,
  `lib/actionCentre.ts:122`.
- Reviewer requests: `admin/scholarship/[id]/view/shared.tsx:47-70` (`REQUEST_CATEGORIES`; results
  "which?" = `spm`→`results_slip`, `cgpa`→`semester_result`), `resolveReq` 74,
  `OutstandingPanel.tsx:233` → `views_admin/resolution.py:37-67` → `resolution.add_officer_item`
  247; uploads resolve the item (`resolution.py:451-468`, `views.py:712-760`). System asks:
  `check2_queries.py` `DOC_SPECS` 132-133, triggers 394-397.
- i18n: `halatuju-web/src/messages/{en,ms,ta}.json` — `scholarship.docs.type.results_slip`
  ("SPM/STPM results slip", en 1280), help 1300, done 1490, `admin.scholarship.requestWhich.*`
  3978-3979, `docsDrawer.type.results_slip` ("SPM results slip", 4741). Reviewer Guide/FAQ:
  `app/admin/guide/page.tsx`, `app/admin/faq/page.tsx`.

### 2.6 Course finder — does it need a third route?
- STPM degree eligibility (`StpmEligibilityCheckView` `courses/views.py:1662-1694` →
  `stpm_engine.check_stpm_eligibility` 362-444) needs STPM subject grades (400 without them) and
  checks STPM subject requirements (`StpmRequirement`, `models_stpm.py:92-152`).
- **There is no entry-requirement data for Matric / Asasi / Diploma holders** (scraper knows only
  `stpm` and `spm` tracks, `scrape_mohe_stpm.py:54-60`). A third-route CGPA cannot be matched
  honestly against STPM `min_cgpa` / `merit_score`.
- **Proposed scope (D2):** no eligibility verdict for this route. (a) Scholarship apply: the degree
  picker lists all degree programmes (the existing search list, `StpmSearchView`) unfiltered, so
  they can name the degree they hold an offer for — required, or they cannot apply at all. (b) Course
  finder dashboard: a plain "browse degrees" view with a note that entry rules for Matriculation /
  Asasi / Diploma holders are not yet in HalaTuju; no High/Fair/Low merit. (c) Later, separate:
  scrape the lepasan Matrikulasi/Asasi/Diploma tracks if ePanduan exposes them.

## 3. Data model

- **Profile (`api_student_profiles`)** — migrations applied via MCP before the code deploys:
  - `exam_type` / `results_exam_type` choices gain `matric`, `asasi`, `diploma` (fit max_length 10;
    choices only — Django state migration, no DDL).
  - New `higher_cgpa` float NULL (the raw CGPA as entered), `higher_koko` float NULL (NULL for
    Diploma). Do NOT reuse `stpm_cgpa`: `has_stpm_results` reads it, so a third-route CGPA there
    would make `results_held` say STPM. Do NOT reuse `coq_score` (SPM merit input).
  - New `completed_qualifications` JSON list (e.g. `["spm","matric"]`) written by each results form
    on completion, so "highest" ranks over COMPLETED forms (presence of data never promotes — #15).
    Blank for every legacy row → today's rule (D1 covers the 27 legacy rows it leaves).
  - Overall CGPA computed, never stored: ONE function (`exam_questions.overall_cgpa(profile)`), and
    ONE `merit_100(profile)` for every route (lessons 2026-09-07: one conversion, every reader routed
    through it).
  - `muet_band` reused; SPM grades for the third route written to `grades` (the field the SPM
    comparison reads); a single `spm_grades_for(profile)` reader merges `grades` / `spm_prereq_grades`
    for STPM holders.
- **Documents (`applicant_documents`)**: new `doc_type` `higher_results`; new column `results_kind`
  CharField(10) blank (student's chosen type: stpm/matric/asasi/diploma). Detected type stored in
  `vision_fields['results_kind_detected']` at extraction. Legacy STPM docs in the `results_slip`
  slot are NOT moved; they are classified at read time from the stored `fields.exam` (free, no
  re-OCR).
- **Catalogue**: the programme's core "results" item becomes per-applicant at resolve time: SPM
  holder → `results_slip` required; tertiary → `higher_results` required + `results_slip` optional.
  `requirements_snapshot` stays frozen; the per-applicant mapping applies on top (like
  `_offer_blocks`).
- `exam_questions.is_tertiary(held)` = held in {stpm, matric, asasi, diploma} — the one
  "STPM-equivalent" test every reader uses.

## 4. Doors into / out of the guarded states (sprint-start step 3b)

Guarded states: shortlisted vs rejected-on-merit; merit rank; required-documents complete (submit /
consent); academic fact band (cockpit verdict); sponsor academic line.

| Door | Where | Sprint covering it |
|---|---|---|
| Submit → score | `views.py:323` → `intake.score_application` | S2a |
| Rescore pending | `intake.py:297`, `rescore_pending_decisions`, cron `rescore-pending` | S2a |
| Cohort requirement edit (`min_stpm_pngk`) | `views_admin/intake_years.py:52,187` (read live at submit/rescore) | S2a |
| Profile edit after submit (results form re-completed, sync) | `courses/serializers.py:302-329`, `services/profile_sync.py:146` | S2a/S2b |
| Form Six explorer / declared-vs-held both directions | `exam_questions.results_held` + `test_exam_questions.TABLE` | S2a |
| Merit list + sort | `serializers_admin` 216, `views_admin/applications.py:150` | S1 |
| AI anonymous profile input | `profile_engine._merit` 479, qualification 733 (PROMPT_VERSION bump) | S1, S2a |
| Sponsor card / pool line | `pool.academic_band`, `emails/sponsor_cards.py:156` | S2a |
| Submission review claims | `submission_review.py:99` | S2a |
| QC accept/reject, reopen and its cancel, revert to pool, award, award revert | read `results_held`/merit as display only; gate not re-run — pin that they stay so | S2a (pins) |
| Consent / completeness / blockers | `consent_blockers.py:44`, `completeness.py:84-121`, `blockers.py:317,368,430` | S3 |
| Requirements resolve + submit snapshot | `requirements.resolve` 89-170 | S3 |
| Upload → extraction → detection | `vision.py:2030-2060, 2141` | S3 |
| Academic verdict + genuineness ladder | `verdict_engine` 285-351, 959 | S3, S4 |
| Reviewer request + upload resolves it | `resolution.add_officer_item` 247, 451-468 | S4 |
| System Check-2 asks | `check2_queries.DOC_SPECS` | S4 |
| Help coach / Action Centre | `help_engine.py:383`, `lib/actionCentre.ts:122` | S3, S4 |
| Doc promotion (which slip is "current") | `promotion.py:48,95` | S3 |
| School-leaving / semester gaps (heading_for) | `occupation.py:146`, `epf_evidence.py:22` | S2a (pins) |
| Reports (AI counsellor) | `apps/reports/views.py:106,131`, `report_engine.py:270-303` | S2b |

## 5. Sprints

Every sprint: Opus-family builder to a written brief; lead verifies diff and re-runs gates; red-first
tests; CHANGELOG + decisions.md; en/ms/ta; reviewer Guide/FAQ in the same change where a reviewer
surface moves; no re-extraction from a local checkout. A HalaTuju push deploys — push only when the
sprint is whole.

### S1 — Merit on one 0–100 scale (characterise first)
- **Goal:** every route ranks on one 0–100 merit; STPM = overall CGPA/4×100.
- **Scope:** `apps/courses/exam_questions.py` (new `merit_100`), `serializers_admin.py` 216-243,
  `views_admin/applications.py:150`, `profile_engine.py:479` + `PROMPT_VERSION`, web
  `admin/scholarship/page.tsx`, `ApplicantCards.tsx:191` (label "merit /100"), i18n, tests
  (`test_exam_questions`, admin list sort), a read-only before/after report (lead, MCP).
- **Characterisation (measured 2026-10-25):** 65 STPM-held applications (2026-bpb-s 55,
  b40-2026 8, GSS Ipoh 1, plus 1 awarded with no CGPA) show merit 1.28–4.00 and sort BELOW every SPM
  applicant on "merit ↓". After: 32–100, interleaved with SPM. The builder produces the per-cohort
  before/after rank list (ids only) for the owner before push.
- **Acceptance:** list and detail show the same 0–100 figure; sort interleaves routes; SPM merits
  byte-identical; null stays absent, not 0 (#106).
- **Complexity:** low–medium. **~8 h.** Adversarial review: YES (ranking). No migration. No
  MODEL_VERSION. VERDICT_ENGINE_VERSION: no (not read by `build_verdict`).

### S2a — The third route, server side ("highest" held results)
- **Goal:** a profile can hold Matric / Asasi / Diploma results; `results_held` = highest completed;
  the gate, merit, pool, profile engine and review claims treat it as STPM-equivalent.
- **Scope:** migration (profile columns/choices, §3); `courses/models.py`, `courses/serializers.py`
  (sync + backing check), `courses/views.py:1154` (serve `higher_*`, `results_held`) and the CGPA
  calculator (accept a raw CGPA + koko, Diploma = as is), `exam_questions.py` (highest,
  `is_tertiary`, `overall_cgpa`, `spm_grades_for`), `shortlisting.py:146-157` (tertiary →
  `min_stpm_pngk` on overall CGPA; reason text names the qualification), `pool.py:32-46` +
  `emails/sponsor_cards.py:156`, `profile_engine.py:733-736` (+ PROMPT_VERSION),
  `submission_review.py:99`, `serializers_admin.py` (qualification label), `services/profile_sync.py`,
  `apps/reports/views.py`, tests (TABLE rows both directions, every door in §4 marked S2a).
- **Acceptance:** Matric CGPA 3.50 + koko 8 → overall 3.47, merit 86.75, passes both the 2.0 and the
  2.9 floor; Diploma 2.80 vs flagship 2.9 → rejected on merit with a plain reason; legacy
  rows answer exactly as today (TABLE unchanged except new rows); `heading_for` gaps stay quiet for
  the new values.
- **Complexity:** high (a gate). **~14 h.** Adversarial review: YES. **Migration first via MCP.**
  No MODEL_VERSION. VERDICT_ENGINE_VERSION: no.

### S2b — The third route, student side (onboarding page per mock + apply + course finder)
- **Goal:** a student can choose the third card, enter results per the mock, and apply.
- **Scope:** `onboarding/exam-type/page.tsx` (third card), new `onboarding/higher-grades/page.tsx`
  (type, CGPA, koko hidden for Diploma, MUET, the STPM page's SPM block — shared component extracted,
  STPM page behaviour unchanged), `lib/storage.ts`, `onboarding/profile/page.tsx` (sync),
  `lib/scholarship.ts` (`Qualification`, `profileAcademicSummary`), `lib/resultsCache.ts`,
  `scholarship/apply/page.tsx` (summary + unfiltered degree picker), `dashboard/page.tsx` (browse
  degrees, no merit band), `profile/page.tsx` (edit link), `saved`, `search`, `AuthGateModal`,
  `auth-context`, `PathwayPicker`, `ApplicantCards.tsx`, `admin/students`, i18n ×3, jest tests.
- **Acceptance:** mock reproduced (Stitch/visual approval = the approved mock, D10); Continue
  disabled until type + CGPA + MUET + SPM block complete; Diploma shows no koko; the apply page
  reaches submit; SPM and STPM pages render byte-identical; `next build` green.
- **Complexity:** medium–high (~25 files). **~20 h.** Adversarial review: YES (async states, real
  browser). No migration. No MODEL_VERSION.

### S3 — Uploads redesign: "higher results" upload with type + detection
- **Goal:** tertiary applicants upload ONE higher-results document (type chosen); the system detects
  the type; SPM slip optional for them; SPM holders unchanged. (#38)
- **Scope:** migration (`results_kind` column); `models/documents.py` (`higher_results`),
  `requirements.py` (per-applicant mapping), `services/completeness.py` (incl. the hard-coded set at
  121), `consent_blockers.py`, `blockers.py`, `resolution.py` codes, new `results_kind.py`
  (detection by fixed markers: "SIJIL TINGGI PERSEKOLAHAN MALAYSIA"/"MALAYSIA HIGHER SCHOOL
  CERTIFICATE"/"MAJLIS PEPERIKSAAN MALAYSIA"/STPM; "PROGRAM MATRIKULASI"; "ASASI"/"FOUNDATION";
  "DIPLOMA"; + PNGK/CGPA label), `vision.py` (higher-results Gemini hint: name, kind, CGPA; no
  SPM-family genuineness for this type — shown "not checked" until the corpus work lands),
  `verdict_engine._verdict_academic` (tertiary: higher-results name + CGPA vs profile; SPM slip
  compared only if present) + `VERDICT_ENGINE_VERSION`, `academic_engine.py`, `help_engine.py`,
  `promotion.py`, web `ScholarshipDocuments.tsx`, `cards.tsx`, `checklists.tsx`, `DocumentsDrawer.tsx`,
  `docCategory.ts`, `officerCockpit.ts`, `actionCentre.ts`, `lib/scholarship.ts`, i18n ×3, Guide/FAQ,
  tests.
- **Acceptance:** an STPM applicant can submit with a higher-results doc and no SPM slip; an SPM
  applicant still cannot submit without the SPM slip; chosen ≠ detected → one plain note to student
  and reviewer, never a block; submitted applications keep their frozen requirements.
- **Detection and the house rule:** detection lives in a new module outside
  `genuineness/results_doc.py` and scores nothing, so **no `MODEL_VERSION` bump** under the rule as
  written ("anything in results_doc.py"). If the builder instead reuses `misfiled_as` /
  `_MISFILE_FAMILIES` in that file, it IS a bump. The academic fact can move a band →
  **`VERDICT_ENGINE_VERSION` bump**.
- **Complexity:** high (~40 files; split S3/S3b at the brief if it exceeds). **~24 h.**
  Adversarial review: YES. **Migration first via MCP.**

### S4 — Reviewer requests by name (#37) + wrong-slip handling (#43)
- **Goal:** reviewers ask for "STPM / Matriculation / Asasi / Diploma results" or "SPM results" by
  name; a higher result in the SPM slot is recognised with no false comparison.
- **Scope:** `view/shared.tsx:47-70` (+ `resolveReq`), `OutstandingPanel.tsx`, `resolution.py`
  (request carries the kind), upload resolves into `higher_results` with that kind; a system Check-2
  ask "SPM results" for a tertiary applicant when a programme needs it (`check2_queries.DOC_SPECS`);
  `academic_engine` / `verdict_engine` / `help_engine`: a detected non-SPM doc in the `results_slip`
  slot (stored `fields.exam`, free; the 34 live docs / 25 apps incl. #153) skips the SPM comparison
  and the SPM-family genuineness step, shows "This is an STPM result, not an SPM slip" to the
  reviewer and "Please upload it under Higher results" to the student — never "change your grades";
  `VERDICT_ENGINE_VERSION` bump; Guide/FAQ; i18n ×3; tests including #153's and #77's shapes.
- **Acceptance:** #153's shape shows no missing-subject / grade-mismatch chips; "Lulus Penuh" is never
  read as E on a detected STPM doc; a reviewer request for "Matriculation results" lands in the right
  slot and closes the request; an SPM request after a higher-results-only submission works.
- **Complexity:** medium. **~16 h.** Adversarial review: YES. No migration (S3's columns). No
  MODEL_VERSION (detection reused from S3).

**Total: S1 8 + S2a 14 + S2b 20 + S3 24 + S4 16 = 82 h** (includes tests, docs, review rounds, close).
Order: S1 (independent, smallest, exposes the ranking change early) → S2a (riskiest: a gate) → S2b →
S3 → S4. S1 can run in parallel with S2a in a worktree.

## 5a. Sprint path as approved by the owner (2026-10-25)

Six sprints, ~84 h. S3 is split for reviewability; the rulings in §7a are folded in.

| # | Sprint | Hours | Migration | Gate before it starts |
|---|---|---|---|---|
| S1 | Merit on one 0-100 scale | 8 | no | none |
| S2a | Third route, server side | 14 | yes | owner answers D5 (which diplomas count) |
| S2b | Third route, student side (+ SPM block required on the STPM page too, D4) | 20 | no | S2a live |
| S3a | Higher-results upload: model, requirements, submit (SPM optional, never a blocker, D9; one upload each, D6) | 14 | yes | S2b live; upload-card mock approved (D10) |
| S3b | Detection (`results_kind.py`, routing only) + academic tile + coaching; VERDICT_ENGINE_VERSION | 12 | no | S3a live |
| S4 | Reviewer requests by name (#37) + wrong-slip handling (#43); no automatic SPM ask (D9) | 16 | no | S3b live |

Every sprint: adversarial review before push; migrations via MCP before push; owner sees the
before/after list before anything that moves applicants.

## 6. Risks
- **"Highest" moves live records.** 27 applications are recorded/declared SPM with STPM data on file
  (15 shortlisted, 8 profile complete, 2 rejected, 1 interviewed, 1 awarded; 0 below their cohort's
  STPM floor). Writing "highest" from data presence would move them all; #15 says presence never
  promotes. Hence `completed_qualifications` and D1.
- **Ranking reorders for orgs** (S1): BrightPath's list shows 55 STPM-held applicants moving up.
  Tell them before deploy.
- **The STPM page's SPM block is not enforced** — the brief says "required"; decision 1 says unchanged.
- **Degree picker without eligibility** (S2b) could let a student name a degree they are not
  eligible for; the offer letter check still governs the pathway fact.
- **Genuineness gap stays open** for higher results until the corpus work lands — shown as "not
  checked", never as suspect.
- **Extraction is live-only**: any re-read of the 34 legacy STPM docs runs on the live cockpit, paid,
  owner-approved. The plan needs none (read-time classification).
- Web route checks are spread over 20 files — a missed branch silently falls to `stpm_pending` /
  `spm`; the S2b reviewer gets the full list.

## 7a. Owner rulings (2026-10-25)
- **D1:** (b)+(c) — promote to the higher route only when a detected STPM document is on file, and list
  the affected applications for reviewers (show the count first).
- **D2:** browse-only degree list for the third route; the apply page's degree picker unfiltered.
- **D3:** `min_merit_score` stays SPM-only. Context from the owner: BrightPath flagship sets no
  minimum merit (offering institutions set merit); it asks only for 5 A's, an SPM rule. STPM and
  STPM-equivalent applicants are tested on the CGPA floor (`min_stpm_pngk`) only — as `_academic_ok`
  already does for STPM today.
- **D4:** the SPM results block is required on BOTH the STPM route and the third route.
- **D6:** one upload each (SPM slip and higher results).
- **D9:** the system does NOT ask for SPM automatically; a reviewer may ask. A tertiary student MAY
  upload their SPM slip at any time, but it is optional and never a blocker for STPM/equivalent
  applicants.
- **D7:** the organisation-facing plan (request #38) already tells BrightPath the new order is shown to
  them before S1 goes live.
- **D5 (2026-10-25):** only PUBLIC diplomas count (polytechnic, UiTM, public university, other public
  institutions). A private-college diploma is not accepted by UA, so it does not qualify for this
  route. S2a/S2b: the Diploma choice asks where the diploma is from; "private college" is not accepted
  (plain message on the form; the gate refuses it with a clear reason if it reaches submit).
- **D11 (2026-10-26):** the S2b guard keeps a student held as STPM while STPM results are on file. Owner
  chose a STUDENT action, "I don't have STPM results", that clears the STPM data (so a Form Six explorer
  with made-up grades can drop them, e.g. when asked for documentation they cannot supply — STPM is
  needed for public universities but not for every course). Build in S3a (uploads), with: an audit line;
  a note to the reviewer when it happens after submit; the gate is not re-run (it runs at submit only),
  so the reviewer judges any post-submit change; it never touches SPM data.
- **D12 (2026-10-26) — which results upload is REQUIRED follows where the student is going:** a
  chosen university degree → the higher-results card (STPM / Matriculation / Asasi / Diploma) is
  required and the SPM slip optional; a chosen post-SPM pathway (Matriculation, Form 6, Polytechnic,
  ILKBS, etc.) → only the SPM slip is required and the higher-results card is not shown, even if
  higher results were entered. No course chosen yet ("not sure") → by the results held (owner chose A);
  it switches once a course is chosen. Supersedes "tertiary → higher results required" in S3a.
- **D11 revised (2026-10-26):** not a button and not only "remove STPM": one small, unobtrusive text
  link under the results cards, "My results are different", opening a short choice — "I took
  Matriculation, Asasi or Diploma instead" (→ third-route results page), "I took STPM instead"
  (→ STPM results page), "I only have SPM results" (→ clears the higher results entered, confirm box;
  audit line; reviewer told if after submit). Only the options that apply are shown; shown only where
  higher results matter (a university degree chosen, or no course chosen and higher results held).
  Safeguards: ONE higher qualification at a time (completing the Diploma form clears earlier STPM
  entries and vice versa); the upload card's type must agree with the results page, otherwise a note
  with a link to the results page.
- **D13 (2026-10-26) — supersedes D11 revised:** NO standing "My results are different" link and NO
  type dropdown. The higher-results card shows the type read-only from the results page — "Type of
  results: STPM · Change" — where "Change" opens that results page; the upload's kind always equals
  results held. Every redirect comes from detection (S3b), shown only when a problem is found:
  (B) entered STPM, uploaded a Matriculation slip → note + link to the third-route results page;
  (C) entered STPM, subjects/grades do not match → note + link to the STPM results page (like today's
  missing-subject note); (D) entered STPM but uploaded an SPM slip while a university degree is chosen →
  note "This is an SPM results slip. A degree course needs STPM, Matriculation, Asasi or Diploma
  results. If you only have SPM results, please choose a post-SPM pathway instead." with ONE action
  (after a confirm box) that clears the higher results AND takes the student to change the chosen
  course; audit line; reviewer told if after submit. **PISMP** counts as a post-SPM pathway for D12
  (SPM slip required, no higher-results card). Because the escape routes live in detection, **S3a and
  S3b are built together and released together.**
- **D13a (2026-10-26):** case (D) assumes a MISFILE first: "This appears to be your SPM results slip.
  Please upload it under \"SPM results slip\" below, and upload your STPM results here." with a primary
  "Move it to SPM results slip" (re-files the document into the SPM slot in one tap) and, in small text,
  "Don't have STPM, Matriculation, Asasi or Diploma results?" leading to the SPM-only confirm box.
- **D14 (2026-10-26):** for a NOT-yet-submitted application bound for a university degree (PISMP
  aside), a post-SPM results slip is a MUST — the higher-results card is required even when the student
  entered only SPM results (the SPM slip stays required for them too). Their card adds: "Required for
  degree courses. Enter your STPM, Matriculation, Asasi or Diploma results, or choose a post-SPM pathway
  if you only have SPM results." with links to the results choice and the course choice. Submitted
  applications keep their frozen requirement; check 2 or the reviewer can ask (S4).
- Still open: **D8** (default: classify at read time only), **D10**
  (default: the approved mock covers S2b; the S3 upload card gets a quick mock first).

## 7. Open decisions for the owner (as raised)
- **D1** Legacy "highest": for the 27 applications recorded SPM with STPM data on file (#153 is one),
  (a) leave until the student re-completes a results form, (b) promote when a detected STPM document
  is on file, or (c) list them for reviewers. Recommended (b)+(c), shown first as a count.
- **D2** Course finder for the third route: browse-only degree list with a note (recommended) or hide
  it; and the apply page's degree picker unfiltered.
- **D3** Does `min_merit_score` (today SPM-only) stay SPM-only now that every route has a 0–100 merit?
  Recommended: yes (the CGPA floor is the tertiary bar).
- **D4** The STPM page does not require the SPM block today. Keep STPM unchanged (decision 1) and
  require it only on the third route, or require it on both?
- **D5** Which diplomas count — any diploma (polytechnic, UiTM, private), or public only?
- **D6** For SPM holders who ALSO hold a higher result (rare): one upload each, or higher only?
- **D7** BrightPath notice of the merit reorder (S1) — who tells them, and when.
- **D8** The 34 legacy STPM documents in the SPM slot: classify at read time only (recommended,
  free) or also move them to the new slot (a production write).
- **D9** System Check-2 ask for SPM results for tertiary applicants: automatic, or reviewer-only?
- **D10** Visual approval: is the approved mock enough for S2b, and does the S3 upload card need a
  Stitch screen first?
