# Retrospective — Now sprint 4 (2026-10-02): TD-069 and TD-218

**Scope:** make an STPM student's SPM-prerequisite entry survive a logout/login and lift its
elective cap to `MAX_SPM_ELECTIVES` (TD-069); give each of the six `exam_type` readers the accessor
for the question it actually means, characterising before switching, and switching only where no
outcome moves except the Form Six explorer's (TD-218). Built by one agent; an adversarial reviewer
reads the diff before the lead commits. One additive migration (`courses/0076`), no data change, no
copy, no new i18n key, no ledger raised, VERDICT_ENGINE_VERSION unchanged.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-069 model | `spm_elective_subjects` (JSON list), `spm_stream` (char) on `api_student_profiles`; migration 0076, Postgres DDL in its docstring, defaults KEPT | `makemigrations --check` clean |
| TD-069 api | sync accepts both (shape-checked), GET serves both | `test_spm_prereq_selection.py` (10) |
| TD-069 web | profile sync sends prereq grades + electives + stream; `auth-context` hydrates them; `KEY_SPM_ALIRAN` / `KEY_SPM_ELEKTIF` in `lib/storage.ts`; aliran derived after login; caps → `MAX_SPM_ELECTIVES`; the elective dropdown keeps a slot's own pick | `stpm-grades/page.test.tsx` (7, mounts the real `AuthProvider`) |
| TD-218 accessors | `apps/courses/exam_questions.py`: `heading_for`, `results_held`, `ResultsHeldField`; `held_qualification` is now `results_held` | `test_exam_questions.py` (15) |
| TD-218 readers | income checks → `heading_for`; student payload → `results_held`; gate / band / parser HELD on `heading_for` (TD-324) | the characterisation table, the fence, a source guard over all six |
| TD-218 web | the review card's label reads the payload's `exam_type` | `ScholarshipReview.test.tsx` (+1) |
| Found on the way | the profile GET never served `results_exam_type` — served now | `test_spm_prereq_selection.py` |

Counts, measured at the first build: api **7,520 → 7,545** passed, 3 skipped; jest **3,273 → 3,281**, 197 suites;
`tsc`, `next lint` (17 warnings, unchanged), `check-i18n` (ALL PASSED) green;
`makemigrations --check` "No changes detected". Bundle: `/profile` 310 → **310** kB (page 23 kB →
23 kB), `/onboarding/stpm-grades` 208 → **209** kB, `/onboarding/profile` 267 → **267** kB, median
227 kB (2.0 kB under its budget, six routes may cross before it does) — unchanged. Register: open
130 → **130** (two closed, TD-324 and TD-325 raised), defined 322; `code_health.py` td_open 130.

Six bites, all red as intended, every restore SHA-equal: the payload switch reverted (5 red); the
sponsor band switched without the probe (10 red — the fence, the table and the explorer pin); the
elective key-shape check removed (the `DROP TABLE` case red); the elective cap back to 2 (red); the
login hydrate dropping the STPM electives (red); the review card's label back on the declaration
(red).

## The adversarial review — FIX-THEN-SHIP, fixed in place

**The measured blast radius (production, read-only, run by the lead on 2026-10-02):** TD-069 — 36
profiles declare STPM, **none** has SPM prerequisites on the server, 3 live applications belong to
them. TD-218 — 68 live applications where the two answers agree, **1** live Form Six explorer (in
a cohort with an academic floor, with a published anonymous profile and a current results slip),
**0** live applications in the other direction, 2 explorer-shaped across any status. So today the
held readers would move exactly one student, and only in the direction the defect names.

| Finding | Fix | Guard |
|---|---|---|
| F1 (med) the apply form's Results step lacked the Form Six rule and now disagreed with the review card; serving `results_exam_type` woke it | the profile GET serves `results_held`; `profileAcademicSummary` prefers it; the accessor module moved to `apps/courses/` so a courses view can serve it | `apply/page.results.test.tsx` (3, mounts the page), `test_spm_prereq_selection.py` |
| F2 (med) the login hydrate could replace a fresh STPM entry | the sign-in gate sends the three STPM fields (and v2.21's missing `elective_subjects`) before the hydrate runs; the hydrate drops the browser's aliran when it writes the server's grades | `AuthGateModal.sync.test.tsx` (2), `stpm-grades/page.test.tsx` (+1) |
| F3 (low) a 21–40 character stream label 400'd the sync | serializer field without `max_length`; the validator drops anything over 20 | 25-character test |
| F4 (low) no bound on the elective list, no check on prerequisite grades; reviewer-visible line undocumented | both bounded at 20; bad cells dropped (grades from the STPM engine's `SPM_GRADE_ORDER`); reviewer Guide + FAQ line | shape tests |
| F5 | answered by the production counts above (0 in the other direction) | — |
| F6 (low) the probe overstated two counts | shortlist and parser rows labelled UPPER BOUND; TIGHT rows added (submitted-not-scored in open cohorts; slips the gate actually skipped) | — |
| F7 (low) TD-218's old status line under its RESOLVED heading | marked "(historical)" | — |

After the fixes: api **7,552** passed, 3 skipped; jest **3,287**, 199 suites; `tsc` clean; lint 17
warnings (unchanged); `check-i18n` ALL PASSED; `makemigrations --check` clean. Bundle: `/profile`
**310 kB** (311,847 → 311,869 gz bytes for the aliran reset), `/onboarding/stpm-grades` 209 kB,
`/scholarship/apply` 271 kB, median 227 kB. *What the review taught:* the first pass fixed the
readers it was asked about and woke a dormant one by serving a field — a served field is a new
reader's input, so grep the other tree for what consumes it before serving it.

## The characterisation (written against the unchanged tree, then re-run)

Ten profile shapes, every reader called for real (the document helpers patched to "nothing on
file" so each income check reaches its exam branch; the cohort's floors set unreachable so the
gate's failure reason names the branch that ran). `head` = `heading_for`, `held` = `results_held`.
The only cells that changed in this sprint are the four marked ◆, all in the student payload.

| Shape | head | held | shortlist gate | sponsor band | leaving-cert ask | semester ask | SPM parser | student payload |
|---|---|---|---|---|---|---|---|---|
| declared spm, SPM grades | spm | spm | SPM test | SPM · 5 As | yes | no | runs | spm |
| declared stpm, STPM results | stpm | stpm | STPM test | STPM · PNGK 3.5 | no | yes | skipped | stpm |
| **Form Six explorer** (declared stpm, SPM only) | stpm | **spm** | STPM test ('STPM PNGK not provided') | STPM | no | yes | skipped | stpm → **spm** ◆ |
| declared stpm, both sets | stpm | stpm | STPM test | STPM · PNGK 3.5 | no | yes | skipped | stpm |
| explorer + recorded spm | stpm | spm | STPM test | STPM | no | yes | skipped | stpm → **spm** ◆ |
| declared spm, both, recorded stpm | spm | **stpm** | SPM test | SPM · 5 As | yes | no | runs | spm → **stpm** ◆ |
| declared stpm, both, recorded spm | stpm | spm | STPM test | STPM · PNGK 3.5 | no | yes | skipped | stpm → **spm** ◆ |
| #15 mirage (declared spm, STPM typed) | spm | spm | SPM test | SPM · 5 As | yes | no | runs | spm |
| declared stpm, nothing at all | stpm | stpm | STPM test | STPM | no | yes | skipped | stpm |
| blank everything | '' | '' | SPM test | SPM · 0 As | yes | no | runs | '' |

**Reading it per reader.**
- **Shortlist gate** — means results-held (a cohort floor tests what she holds). Switching moves
  the explorer rows (the defect) AND "declared spm, both, recorded stpm" (from the SPM test to the
  STPM floor) — not the defect. **Held** on `heading_for`; TD-324. The brief also reserved this
  one for the owner.
- **Sponsor band** — means results-held (it is a summary of results). Same two directions; the
  second turns 'SPM · 5 As' into 'STPM · PNGK 3.5' on a sponsor's card. **Held**; TD-324.
- **Leaving-certificate ask** and **semester-result ask** — mean heading-for: a student heading
  for STPM is in Form Six, still at school (no leaving certificate) and in semesters. Moved; every
  cell identical by construction.
- **SPM slip parser** — means results-held (a Form Six student uploads her SPM slip; BrightPath
  #12). Switching runs the parser for the explorer rows (the fix) and SKIPS it for "declared spm,
  recorded stpm" (not the defect; her slip would go to Gemini). **Held**; TD-324.
- **Student payload** — means results-held (it picks which grades the student's results card
  shows). Switched: the four ◆ cells. No shortlist, verdict, chip or sponsor surface reads it.

**A surprise the characterisation caught.** The first `ResultsHeldField` served `None` for an
application with no profile. The old `source='profile.exam_type'` OMITTED the key (DRF skips a
read-only field whose dotted source breaks on `None`). Pinned, and matched.

## What went well

- **Characterising first turned "switch five readers" into "switch one, move two, hold three".**
  The table made the second direction (declared SPM, recorded STPM) visible on day one; without it
  the obvious sweep would have changed a shortlist gate and a sponsor card for a population nobody
  had counted.
- **The rendered test found a bug the brief did not name.** The STPM page's elective pool excluded
  every elective pick, including each slot's own, so a chosen elective rendered blank. It surfaced
  the moment a test asked for the rebuilt values rather than the number of dropdowns.
- **Reading the web's own TD-218-era code found a dead reader.** `profileAcademicSummary` and the
  login hydrate both read `results_exam_type` from the profile GET, which never served it.

## What went wrong

1. **A `# noqa` and a semicolon went into `vision.py` for a moment** to keep the file line-neutral.
   Caught before any gate ran; replaced by a docstring compression. *Lesson (not new):* the rails
   are the first thing to re-read when a file is at its ceiling — the cheap trick is the one the
   rail forbids.
2. **Shell escapes ate a regex twice** (`\b` became a backspace through a heredoc). The test still
   passed with the corrupted pattern, which is the dangerous part: a guard whose pattern can never
   match is green for ever. Fixed by writing the bytes explicitly and checking the file for `\x08`.
   *Lesson:* after generating a regex through a shell, grep the file for control characters.

## Left, by decision

- **TD-324** (Owner-decision): the three held readers, with the probe that counts both directions.
- **TD-325** (Later): four readers outside the six (the sponsor-profile prompt, the Check-2 facts
  ledger, the apply form, the pathway picker) that also mean results-held.
- No backfill of `spm_elective_subjects`: nothing ever synced `spm_prereq_grades` from the web, so
  there is nothing to recover — STPM students repopulate on their next save, as after v2.21.0.
