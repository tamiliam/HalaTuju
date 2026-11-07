# Degree students get a degree funding estimate, not a UA-diploma one (bug fix, 2026-11-07)

Executor: Opus agent. Branch `fix-degree-estimate` (from origin/main c8650ffb). **Main is under audit:
push to the branch only, never to main.**

## The bug (owner, 2026-11-07, app 278)

The cockpit's "Estimated need & proposed bursary" card shows a post-STPM **degree** student
the UA-**diploma** estimate: "≈ RM 6,600, ~RM 220/month × 30 months, Public-university diploma — after
the PTPTN loan". #278 is `chosen_pathway='university'`, programme `UH6145006` *Ijazah Sarjana Muda
Pendidikan (Sejarah)* at UMS, a 4-year degree.

Classification: **bug**. `funding_estimate.py` and `docs/scholarship/funding-estimate-basis.md` assume
post-SPM only ("'university' means a UA DIPLOMA"). The Sabah / Ipoh gifts admit STPM-level students
(D16), and the offer realignment (decisions.md, 2026-10-31) deliberately stores an STPM degree as
`university`. The estimator was never brought in line with that.

Verified facts (read-only prod + origin/main, 2026-11-07):
- `estimate_funding` is **display only**: one reader, `serializers_admin.get_funding_estimate`. No
  award is sized from it. `classify_pathway` has one other reader:
  `submission_review.completeness_gaps` (the STPM transport-cost gap).
- 547 applications, 325 past `shortlisted` (the card shows from `submitted` onward). 106 of those are
  degree-bound; **80 are live** (submitted → recommended): 42 show the UA-diploma RM6,600, 35 show
  "no estimate" (blank pathway, degree name matches no keyword), 3 show the Form-6 RM9,000
  (#133, #239, #251). 0 awarded students are on a degree. Almost all are in cohort 3 (Sabah).
- 20 of the 80 live degree students started before 2026 (continuing).
- **Money bug, same root:** #251 (Sabah, profile_complete) has a stale `chosen_pathway='stpm'` on a
  degree (*Sarjana Muda Sains Gunaan*). `award.proposed_award_amount` reads the code alone, so at
  verdict it commits RM3,000 (or None and a QC reporting-date stop) instead of RM2,000. It is the
  only live case.
- Degree detection already exists: `higher_owed._degree_bound` (`results_route.destination == DEGREE`
  via `stpm_courses`, else the programme NAME via `offer_pathway.detect_pathway_type`; a UA diploma
  and PISMP read as non-degree). It handles #251 and the 35 no-`course_id` rows.
- `stpm_courses.stream` is `arts` / `science` (#278: `arts`), which is PTPTN's Sastera / Sains
  split. `stpm_courses` has **no duration column**.
- Start year: `pathway_engine.course_start_year(application)` (offer intake year, then
  `reporting_date`); cohort year: `application.cohort.year`.

Source for the degree figures: owner's `SLS Model.xlsx` (Assumptions, Course Fees, PTPTN sheets):
living RM1,200/month × 10 study months; UM IPTA bachelor fees RM2,100–3,400/yr (mean ≈ RM2,900);
PTPTN IPTA bachelor max RM6,180/yr (Sastera) / RM6,650/yr (Sains). B40 → the maximum loan.
The workbook holds UM only (no USM rows).

## Owner-settled decisions (1-8 confirmed by the owner, 2026-11-07; 9-12 added by the owner during the build, the same day)

| # | Decision |
|---|---|
| 1 | **Post-SPM figures stay exactly as they are** (stpm, matric, asasi, poly, UA diploma, pismp: ≈RM600/month living basis, owner-validated 2026-06-15). No figure, duration or flag of theirs changes. |
| 2 | **University degree studies** (post-STPM / matric / asasi / diploma holders, i.e. every degree-bound student) use living costs of **RM1,200 × 10 study months a year**. |
| 3 | Tuition: one flat **RM2,900/yr** (SLS UM mean), with the `variable` caveat. |
| 4 | PTPTN: the IPTA bachelor maximum by `stpm_courses.stream`: arts → **6,180**, science → **6,650**; stream unknown (no catalogue id) → arts (the smaller loan, the larger need). |
| 5 | Length from the SLS durations: arts **3** yrs, science **4**, and by name: Pendidikan (education) **4**, Perubatan / Pergigian (medicine / dentistry) **5**; unknown → **4**. |
| 6 | A continuing degree student is estimated for the years LEFT: `years − (cohort.year − course_start_year)`, at least 1. Start year unknown → the full length. Degree only (decision 1). |
| 7 | `award.py`: a degree-bound student never gets the STPM amount and never trips the STPM start-year stop (`course_start_unknown`). They get the standard RM2,000, whatever the stored code says. Fixes #251. **Why (owner, 2026-11-07):** the bursary is sized by the FUNDED PERIOD. STPM's RM3,000 exists only because Form 6 is 18 months; every other pathway is funded for 12 months at RM2,000; the continuing STPM RM1,000 is the remaining stretch. A degree-bound student is on the 12-month RM2,000 basis whatever the code says. No amount changes. |
| 8 | The STPM transport-cost gap is not raised for a degree-bound student. |
| 9 | **MARA / UiTM diplomas** (owner, 2026-11-07, added during the build): UiTM `UE4…` stays `university`. A Kolej Profesional MARA diploma (`OP4…`, MARA-BPT division) gets its own key `mara_diploma` with the same numbers as `university`; label "MARA diploma, after the MARA education loan. Covers meals, hostel & fees." A MARA-family TVET course at catalogue level Diploma → `mara_diploma`; `chosen_pathway='mara'` with no course id and a Diploma name → `mara_diploma`. A MARA degree follows the degree rule. |
| 10 | **ILKBS (IKBN / IKTBN)** (owner, 2026-11-07): ~**RM350/month** (the lead's derivation: Matrikulasi's ~RM450 living − the ~RM100 allowance; the owner may adjust), `variable` / `practical` false. Length = the catalogue's `courses.semesters` × 6; no course or no semesters → 24. All levels, via `chosen_pathway='ilkbs'`, `ikbn` / `iktbn` / `ilkbs` id prefixes, or a TVET id in the ILKBS family. Label "IKBN / IKTBN: free tuition & hostel, after the ~RM100 monthly allowance. Mostly meals + small costs." |
| 11 | **ILJTM and Kolej Komuniti** (owner, 2026-11-07): ~**RM450/month** (no allowance), flags false, the same length rule; own keys `iljtm` and `kkom`. Labels "ILJTM: free tuition & hostel, no allowance. Covers meals + small costs." / "Kolej Komuniti: free tuition & hostel, no allowance. Covers meals + small costs." |
| 12 | **MARA certificates and every other TVET course** (owner, 2026-11-07): a MARA-family TVET course that is not a Diploma (e.g. #450 `TVET-30721`), and every TVET course or family not covered by 9-11 (bare `tvet`, `tvet_other`, a `mara` code whose programme is not a diploma), are treated like ILJTM: RM450/month, flags false, semesters × 6 (else 24). One shared spec; keys `mara_cert` and `tvet` only so the labels can differ: "MARA skills certificate: free tuition & hostel, no allowance assumed. Covers meals + small costs." / "TVET institute: free tuition & hostel, no allowance assumed. Covers meals + small costs." "No estimate" is left only for a genuinely unknown / undecided pathway. |

Resulting annual shortfall: arts 12,000 + 2,900 − 6,180 = **RM8,720** (≈RM872 per study month);
science 12,000 + 2,900 − 6,650 = **RM8,250** (≈RM825). #278 (arts, education, 4 yrs, fresh entrant)
→ 8,720 × 4 = **≈RM34,900**, "~RM872/month × 40 study months".

## What to build

1. **Promote** `higher_owed._degree_bound` to a public `results_route.degree_bound(application)`
   (moves only); `higher_owed` calls it. No behaviour change there.
2. `funding_estimate.py`:
   - `classify_pathway`: `degree_bound` is checked **first**, before the sure `chosen_pathway`,
     and returns `'degree'`. Everything after it is unchanged. Keep the module pure: no new DB reads
     beyond what `destination` already does (it is memoised on the instance).
   - A `DEGREE` spec built from decisions 2–5 as named constants (living, months/yr, fee, PTPTN by
     stream, years by stream / name keyword). `estimate_funding` for `'degree'`: monthly = round
     (annual / 10), months = 10 × years left (decision 6), total = `_round100(annual × years left)`,
     `variable=True`, `practical=False`. Return two extra keys the card can use: `study_months=True`
     and `continuing` (bool). Post-SPM results are byte-identical to today.
   - The stream is read from `stpm_courses` by `course_id` (one query; None if no id).
   - Update the module docstring: post-SPM scope + degree.
3. `submission_review.completeness_gaps`: decision 8 (falls out of step 2, since a degree classifies as
   `degree`; add a test).
4. `award.py`: decision 7, in `proposed_award_amount` and `course_start_unknown` (call
   `results_route.degree_bound`). Docstrings name the 2026-11-07 decision.
5. Web: `RateAndEstimate.tsx`: for `fe.study_months` render "study months"; a `continuing`
   line ("Continuing student: estimated for the years left."). `messages/{en,ms,ta}.json`:
   `estimate.pathway.degree` ("Public-university degree: after the PTPTN loan. Covers living
   costs (RM1,200 × 10 months a year) & fees."), `estimate.studyMonths`, `estimate.continuingNote`.
   Update the `none` copy only if needed. British English; Tamil per the style guide (flag for
   language review). Type `funding_estimate` in `admin-api.ts`.
6. Docs: `docs/scholarship/funding-estimate-basis.md`: a "Degree (post-STPM) scope" section, the
   degree row with the SLS sources, the classification order; `docs/decisions.md` entry; CHANGELOG.
7. Tests:
   - `test_funding_estimate.py`: #278 shape (catalogue degree, arts, education) → degree, 34,900;
     science catalogue degree; no-id degree name under `stpm` (#251) and under blank (#133) → degree;
     PISMP "Ijazah Sarjana Muda Perguruan" stays `pismp`; UA diploma (`UH4…`) stays `university`;
     continuing (start one year before cohort) → years − 1; start unknown → full; floor at 1;
     **every post-SPM pathway's output unchanged** (pin the current dicts).
   - `test_award_rule.py`: degree-bound with `chosen_pathway='stpm'` → RM2,000, not None, not 3,000;
     a real Form-6 STPM student unchanged (fresh 3,000 / continuing 1,000 / unknown None).
   - transport gap not raised for a degree-bound student.
8. Report: re-run the classifier over prod (read-only) and list the 80 live degree apps' before/after
   figures, plus #251's proposed award before/after.

## Not in scope (follow-ups, owner to schedule)

- Continuing **post-SPM** students (7 live UA-diploma students started before 2026) still get the
  full programme length (decision 1).
- Per-university or per-field tuition (only UM is in the SLS workbook).

## Risks

- `destination` hits the DB (`StpmCourse` exists check) and the stream adds one more. The card
  serializer runs per detail view only; keep it out of list serializers.
- `classify_pathway` order change: a degree-bound student whose stored code is `stpm` / `matric`
  moves category. Intended, but check every `classify_pathway` reader (two today).
- The award change touches money: verdicts already recorded keep their stored `award_amount`
  (no backfill). Only a re-recorded or new verdict uses the new rule.
