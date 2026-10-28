# STPM CGPA worked out from the grades + full STPM subject list — roadmap (APPROVED by the owner 2026-10-28)

## Why
- The cockpit, the merit score (0–100) and the minimum STPM CGPA check all use the CGPA the student TYPED
  (`StudentProfile.stpm_cgpa`). Live check (2026-10-28): of 98 STPM students with grades entered, 54 typed a
  CGPA that does not match their own grades (45 open applications). Examples: #173 typed 3.90 for all-A
  grades (certificate 4.00); #232 typed 2.42, certificate 3.17; #252 typed 3.21 = the plain average of five
  subjects. Every certificate read Exact agrees with PNGK = (Pengajian Am + best three other subjects) / 4.
- The onboarding STPM subject list (`halatuju-web/src/lib/subjects.ts` STPM_SUBJECTS, 20 entries) misses
  official MPM subjects, e.g. **Sains Sukan** — so #184 could enter only 3 subjects. Official list:
  https://www.mpm.edu.my/en/stpm/stpm-syllabus?id=96 (also: Bahasa Arab, Literature in English,
  Kesusasteraan Melayu Komunikatif, Tahfiz Al-Quran, Muzik, Matematik (M)/(T) naming, etc. — verify).

## Owner rulings (2026-10-28)
- Subjects, grades and CGPA in the cockpit all come from onboarding; the **CGPA is worked out from the
  subjects and grades**, never typed (STPM). They are then **counter-checked against the uploaded
  document**; a match gets a check mark — as SPM already works.
- Include **all** official STPM subjects for students to select.

## Proposed rules (for the owner to confirm in the plan review)
- PNGK = round((PA + best three others) / 4, 2), on the fixed scale A 4.00 … F 0.00. Needs PA + ≥3 others.
- Fewer than PA + 3 subjects entered → no calculated CGPA; keep the old typed value, labelled "not
  calculated", and ask the student to complete their grades (Action Centre / Check 2 wording to agree).
- Matriculation / Asasi / Diploma keep a typed CGPA (they enter no subject grades) — unchanged.
- Merit (`exam_questions.merit_100`) and the gate (`shortlisting._academic_ok`, `min_stpm_pngk`) read the
  calculated CGPA. Existing students are recalculated (backfill) — **owner sees the before/after list
  (merit + gate) before release**.

## Sprints
### C1 — full STPM subject list (web + API keys) · low–medium
- Add every official MPM STPM subject to STPM_SUBJECTS + STPM_SUBJECT_TO_API_KEY + backend keys
  (`apps/courses/stpm_engine.py`, `higher_results._STPM_NAMES`, report_engine) without breaking course
  eligibility (stpm_requirements fixtures), en/ms/ta names. Done when every subject on the MPM page can be
  selected and round-trips; existing keys unchanged.
### C2 — CGPA from grades (onboarding + server) · high (ranking/eligibility)
- Onboarding: remove the typed STPM CGPA box; show the calculated CGPA live (Stitch mock first).
- Server: one function computes PNGK from `stpm_grades`; `stpm_cgpa` is written from it (or replaced by a
  read-through); merit, gate, cockpit, reports, sponsor profile read it. Door list in the plan.
- Backfill command (preview default) → owner before/after list → apply. VERDICT/MODEL versions as needed.
- Adversarial review before push.
### C3 — cockpit check marks · medium
- STPM grades + CGPA chips show a check mark when the document (Exact or AI read) matches, a difference
  marker when not — reuse the SPM pattern and `higher_results` comparison.

## Ground rules
Opus builder per sprint; adversarial review before every push (C2 is eligibility); a push DEPLOYS — never
push to main without checking the other local session ("BrightPath Sabah processing"), which also pushes;
local Python must match requirements.lock (pypdf 5.9.0 / pypdfium2 4.30.0); no PII in tracked files.

## Cloud-session handoff (owner's weekly limit is near)
A claude.ai/code cloud session can do C1 and C2's code + tests from this file. It has NO access to:
the local gitignored corpus, Supabase MCP / production DB, gcloud, the local .env. So in the cloud:
- work on a **branch** (e.g. `stpm-cgpa-from-grades`), never push to main; open a PR;
- the before/after list, the backfill apply, the push to main and deploy checks happen back on the local
  machine (or by the owner) after review.

## Cloud-session package (paste as the cloud session's first message)
Read `docs/plans/2026-10-28-stpm-cgpa-from-grades-roadmap.md` and `CLAUDE.md` / `halatuju_api/CLAUDE.md` first.
Work on a NEW branch `stpm-cgpa-from-grades` from main. NEVER push to main (a push to main deploys); open a
PR at the end. Do sprint C1, then sprint C2's code and tests:
1. C1: add every official MPM STPM subject (https://www.mpm.edu.my/en/stpm/stpm-syllabus?id=96) to
   `halatuju-web/src/lib/subjects.ts` (STPM_SUBJECTS + STPM_SUBJECT_TO_API_KEY) and every backend place that
   names STPM subjects (`apps/courses/stpm_engine.py`, `apps/scholarship/higher_results.py` `_STPM_NAMES`,
   `apps/reports/report_engine.py`, fixtures) — existing keys unchanged; en/ms/ta labels; tests.
2. C2 server: one function computes PNGK = round((PA + best three others)/4, 2) from `stpm_grades`
   (A 4.00, A- 3.67, B+ 3.33, B 3.00, B- 2.67, C+ 2.33, C 2.00, C- 1.67, D+ 1.33, D 1.00, F 0.00); fewer than
   PA + 3 → None ("not calculated", keep the typed value). Merit (`exam_questions.merit_100`), the gate
   (`shortlisting._academic_ok`), the cockpit, reports and the sponsor profile read it. Write the DOOR LIST
   (every reader of `stpm_cgpa`) into the PR and test each door. Matric/Asasi/Diploma unchanged.
3. C2 backfill: a management command, PREVIEW by default, that lists per application old vs new CGPA, merit
   and gate result; `--apply` writes. Do NOT run it (no production access in the cloud).
4. C2 onboarding UI: do NOT build it yet — add a static HTML mock (docs/plans/stpm-cgpa-onboarding-mock.html)
   showing the typed CGPA box replaced by a live calculated CGPA, for owner approval.
Gates: from halatuju_api `python -m pytest -q -n auto -p no:cacheprovider` + test_code_standards +
`python manage.py makemigrations --check`; from halatuju-web jest, `npx tsc --noEmit`, `npm run check-i18n`,
`npm run bundle-budget -- --gate` (median headroom is ~0.4 kB — keep new strings in the admin/onboarding
slices). Use pypdf 5.9.0 / pypdfium2 4.30.0 (requirements.lock). No real student data in tests or files.
CHANGELOG + docs/decisions.md entries. Finish with a PR and a short summary: files, door list, test results,
what is left for the local session (backfill preview on production, owner before/after list, merge, deploy).
