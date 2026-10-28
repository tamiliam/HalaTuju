# STPM CGPA worked out from the grades + full STPM subject list — roadmap (draft 2026-10-28, awaiting owner approval)

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
