# F1 — Slip-check rule table (draft for the owner, approve by Wed 18 Nov)

Written 2026-11-13 by tamiliam's build agent. **No code was changed.** This page says what the system does
**today** (live `origin/main` 70a51cdc7; the g15 branch holds the same slip-check code) when it compares a
student's results document with what she typed. Roadmap entry: `2026-11-05-audit-fix-roadmap.md`, F1.

## How to read this page

The officer sees two things for each results document:

- **Drawer chips** (Documents drawer). Green = checked and matches. Amber = please look. Red = does not
  match. Grey = not checked (nothing to compare).
- **The Academic tile.** One band: **Certain**, **Probable**, **Unsure** or **Fail**, with short lines under it.
  Each line has a wording key (shown in `code`) and its English text.

Two general rules sit behind every table:

1. **Red chips push the band down.** Each red chip moves the tile one step down (none = no change, 1 = at
   best Probable, 2 = at best Unsure, 3 = Fail). A "may not be genuine" document counts as one more step.
2. **A document nobody could check for genuineness** can reach Probable but not Certain (your 2026-06-13
   rule, TD-114). The live service has the genuineness check switched on (`halatuju_api/CLAUDE.md` line 61).

The seven slip states, in plain words:

| State | Meaning |
|---|---|
| Checked | Read in full; everything she typed matches. |
| Not final | The upload is a semester slip or an unfinished transcript, not the final result. |
| Suspect | The genuineness check thinks it may not be an original. |
| Short read | The read caught fewer subject rows than the slip prints. |
| Extra typed subject | She typed a subject that is **not** on the slip. |
| Subject missing | The slip shows a subject she did **not** type. |
| Undeclared higher results | A higher-results document is on file, but she said she holds SPM only. |

Each cell is marked **Filled** (today's behaviour), **QUESTION** (see Part 2) or **Unreachable** (cannot
happen today; Part 2, question 8).

---

## Part 1 — The tables

### Table A. SPM holder, going to a post-SPM course (diploma, Form Six, matriculation, PISMP …)

Her SPM slip is compared with **all** the SPM grades she typed.

| State | Drawer chips | Academic tile | Mark |
|---|---|---|---|
| Checked | Name, Subjects, Results all green. | **Certain**. `grades_verified`: "All {count} grades match the results slip." Plus `results_slip_name_ok`: "The results slip is in the student's name." | Filled |
| Not final | — | — | Unreachable (no "not final" test exists for SPM slips) |
| Suspect | Extra amber "Genuine" chip. Other chips unchanged. | At best **Probable** (one more step if any chip is red). `document_not_genuine`: "This document may not be a genuine official original — confirm it at interview." | Filled |
| Short read | Subjects and Results can both show **green**. | Can read **Certain**: "All N grades match", where N counts only the rows read. Subjects she typed that the read missed are never checked and never named. | **QUESTION 1** |
| Extra typed subject | Subjects **red**. | At best **Probable** (one red chip). `academic_extra_subjects`: "Entered by the student but not on the slip: {subjects}. Check by eye: a typing slip, or a row the read missed." Only on a full read (grades read, not short). | Filled |
| Subject missing | Subjects **red** (the same single chip as "extra"). | At best **Probable**. `academic_missing_subjects`: "Entered {entered} of {total} subjects on the slip — missing: {subjects}. Ask the student to add them." | Filled |
| Undeclared higher results | A higher-results upload in its own slot is not asked for on this route and does not touch the tile. If a higher result is put **in the SPM slot**: Name chip + red "Type" chip; no Subjects or Results chips. | **Probable**. `results_slip_is_higher`: "This is a higher result ({kind}), not an SPM slip. It was not compared with the SPM grades entered…" Plus `results_slip_missing` ("No results slip uploaded.") when the SPM slip is required. | Filled |

Grade differences (part of "Checked"): a clear wrong grade = Results **red**, `academic_grade_mismatch`
("{subject}: typed {typed}, but the slip reads {slip}. Check."); a ± difference the slip's letter and Malay
band both confirm = **red**, `academic_grade_band_mismatch` ("…The typed grade is wrong; ask the student to
correct it."); a ± difference the read cannot be sure of = **amber**, `academic_grade_uncertain` ("…an
A/A+ (±) read we can't be sure of. Check it by eye against the slip."). Amber adds no red step.

### Table B. STPM holder

The **STPM results** upload drives the tile. Her SPM slip is optional (see Table G).

| State | Drawer chips | Academic tile | Mark |
|---|---|---|---|
| Checked | Name, Type, CGPA (within 0.01), Results green; "Genuine" chip when scored. | **Certain** only if: name matches, Type matches, CGPA matches, every printed subject entered with the same grade, scored genuine, and the optional SPM slip (if on file) is clean or not compared. Lines: `higher_results_name_ok`, `higher_results_kind_ok` ("The document reads as {held} results, as on the results page."), `higher_results_cgpa_ok` ("The CGPA on the document ({cgpa}) matches the one entered."). | Filled |
| Not final | — | — | Unreachable (STPM semester results use a separate slot; no "not final" rule reads STPM pages) |
| Suspect | Amber "Genuine" chip. | At best **Probable**. `document_not_genuine`. | Filled |
| Short read | Results can show **green**. | No short-read guard. An STPM subject she typed that the read missed is never checked or named; the tile can read Certain. | **QUESTION 2** |
| Extra typed subject | Results can show **green**. | Never flagged. An STPM subject she typed that is not on the slip is ignored. | **QUESTION 3** |
| Subject missing | Results **red**. | At best **Probable**. `higher_results_subjects_missing`: "STPM subjects on the slip but not entered: {subjects}." | Filled |
| Undeclared higher results | — | — | Unreachable (an STPM holder has declared them) |

Also on this route: an STPM row the read cannot name → amber, `higher_results_subjects_unrecognised`
("A subject on the results could not be recognised, so the slip cannot be confirmed as matching: {subjects}."),
blocks Certain, never red. A wrong STPM grade → Results **red**, `higher_results_grade_mismatch`
("{subject}: typed {typed}, but the STPM slip reads {slip}. Check."), even for a ± difference (QUESTION 4).
CGPA different (with a "cumulative" label) → CGPA **red**, `higher_results_cgpa_mismatch`.

### Table C. Matriculation holder

Only the **CGPA** is compared (she enters no matriculation subjects).

| State | Drawer chips | Academic tile | Mark |
|---|---|---|---|
| Checked | Name, Type, CGPA (within 0.05) green. No Results chip. | **Certain** only when the final transcript is scored genuine. A slip, cropped page or anything not scored stays at best **Probable**, with `higher_results_not_checked`: "Genuineness of higher results is NOT checked yet (no pattern for these documents) — check the document by eye." | Filled |
| Not final | Grey "final owed" chip. | At best **Probable**. `higher_results_not_final`: "The {held} upload is not the final result (…) so it does not count: the final academic transcript is still owed … Academic cannot be Certain until it is on file." | Filled |
| Suspect | — | — | Unreachable (matriculation pages are stored "genuine" or "not checked", never "suspect": your ruling 4, 2026-10-29) |
| Short read | — | — | Unreachable (no subjects compared) |
| Extra typed subject | — | — | Unreachable (no subjects compared) |
| Subject missing | — | — | Unreachable (no subjects compared) |
| Undeclared higher results | — | — | Unreachable (she has declared them) |

A matriculation **offer letter** in this slot → red "wrong type" chip, `higher_results_not_results`
("The {held} upload is a Matriculation offer letter, not a results document…").

### Table D. Diploma holder

As Table C (CGPA only, within 0.05), with one difference: only a **polytechnic** diploma transcript can be
scored genuine. A UiTM, community-college, UA or private-college diploma is never scored.

| State | Drawer chips | Academic tile | Mark |
|---|---|---|---|
| Checked | Name, Type, CGPA green. | Polytechnic final transcript scored genuine: **Certain**. Any other diploma: at best **Probable**, `higher_results_not_checked`. | **QUESTION 5** |
| Not final | Grey "final owed" chip (polytechnic portal page, semester slip, or an in-progress transcript). | At best **Probable**. `higher_results_not_final`. | Filled |
| Suspect | — | — | Unreachable (never stored, as Table C) |
| Short read | — | — | Unreachable (no subjects compared) |
| Extra typed subject | — | — | Unreachable |
| Subject missing | — | — | Unreachable |
| Undeclared higher results | — | — | Unreachable |

### Table E. Asasi holder

As Table C, but **no** Asasi page is ever scored.

| State | Drawer chips | Academic tile | Mark |
|---|---|---|---|
| Checked | Name, Type, CGPA green. | At best **Probable**, always. `higher_results_not_checked`. | **QUESTION 5** |
| Not final | — | — | Unreachable (no "not final" rule reads Asasi pages) |
| Suspect | — | — | Unreachable |
| Short read | — | — | Unreachable |
| Extra typed subject | — | — | Unreachable |
| Subject missing | — | — | Unreachable |
| Undeclared higher results | — | — | Unreachable |

### Table F. SPM holder going to a university degree ("degree-bound")

She must have STPM / Matriculation / Asasi / Diploma results on file (your rule, 2026-11-07). Her SPM slip
is still required and still compared exactly as in Table A.

| State | Drawer chips | Academic tile | Mark |
|---|---|---|---|
| Checked (clean SPM slip) | SPM chips green. | Never Certain on this route. No higher upload: **Fail**, `higher_results_missing` ("No STPM / Matriculation / Asasi / Diploma results uploaded.") — or, for an application submitted before 26 Oct, **Unsure**, `higher_results_not_declared` ("…The student declared SPM results only but chose a university degree…"). | Filled |
| Not final | Grey "final owed" chip on the higher upload. | At best **Unsure**. `higher_results_not_final` plus `higher_results_undeclared`. | Filled |
| Suspect | Amber "Genuine" chip on the SPM slip. | `document_not_genuine`; band already capped at Unsure (or Fail). | Filled |
| Short read | As Table A. | As Table A, but the cap keeps the tile at Unsure or worse. The green SPM chips can still mislead. | **QUESTION 1** |
| Extra typed subject | As Table A. | As Table A, then capped. | Filled |
| Subject missing | As Table A. | As Table A, then capped. | Filled |
| Undeclared higher results | Name chip checked; Type grey (no tick, no "differs"); CGPA amber ("read, nothing to check"); Results grey. | At best **Unsure**. `higher_results_undeclared`: "Higher results are on file, but the student declared SPM results only, so there is nothing declared to check them against. Confirm the qualification and its results at interview." The student is asked to declare (`higher_results_declare_requested`). | Filled |

Not applied at **Recommended or later** (too late; your 2026-11-07 rule). QUESTION 7 is about who counts as
degree-bound.

### Table G. The optional SPM slip of an STPM, Matriculation, Asasi or Diploma holder

Compared **only** with the SPM subjects she typed in the "SPM prerequisites" box. It speaks on the higher
card only when the slip is on file. No prerequisites typed = grey, nothing shown, nothing held.

| State | Drawer chips | Academic tile | Mark |
|---|---|---|---|
| Checked | Subjects, Results green. | Adds "All {count} grades match the results slip." ({count} = subjects she typed). Does not hold the card back. | Filled |
| Not final | — | — | Unreachable (as Table A) |
| Suspect | Amber "Genuine" chip. | The higher card drops to at best **Probable**, with `document_not_genuine`. | Filled |
| Short read | If at least one typed subject was checked: Results **amber** ("pending"). If none was checked: grey, nothing shown. | First case: `academic_grades_unchecked` ("Entered by the student, but the read could not check the grade on the slip: {subjects}. Please check it by eye against the slip."), holds Certain. Second case: nothing (your ruling, 6 Nov review 3). | Filled |
| Extra typed subject | Subjects **red**. | `academic_extra_subjects`; holds the card at best **Probable**. | Filled |
| Subject missing | Nothing. | Nothing — a slip subject she did not type is never "missing" for her (your ruling, 6 Nov). | Filled |
| Undeclared higher results | — | — | Unreachable (she has declared them) |

---

## Part 2 — Questions for the owner

1. **SPM short read can show a full tick.** When the read catches fewer rows than the slip prints, the
   subjects it missed are never checked, yet the tile can say "All N grades match" and read Certain (Tables
   A and F). *Recommend:* treat it like Table G — name the unchecked subjects ("please check by eye"), no
   green Subjects chip, at best Probable.
2. **STPM short read.** Same gap for STPM: a typed STPM subject the read missed is never checked.
   *Recommend:* the same fix as question 1.
3. **STPM extra typed subject is never flagged.** An STPM subject she typed that is not on the slip passes
   silently. *Recommend:* flag it "please check", as SPM does since request #62, on a full read only.
4. **STPM ± grades are always red.** On SPM, a ± difference the read cannot confirm is amber ("check by
   eye"). On STPM every difference is a red "Check". *Recommend:* mirror SPM — amber unless the read is sure.
5. **Asasi and most Diplomas can never be Certain.** Only a matriculation or polytechnic final transcript
   can be scored genuine. Asasi, UiTM, community-college and private diplomas stop at Probable (your TD-114
   rule). *Recommend:* keep as is; the tile already says "not checked". Add patterns when samples exist.
6. **A higher result in the SPM slot holds a clean higher card.** For an STPM / Matriculation / Asasi /
   Diploma holder, the SPM slip is optional, yet a higher result filed there keeps her card at Probable even
   when her real higher-results upload is clean. *Recommend:* show the line but do not hold the card for
   her.
7. **Two tests for "going to a degree".** Before submit, the document list uses one test (course list, then
   pathway code). After submit, the "higher results owed" rule uses a wider test that also reads the course
   name. A student with an old Form Six pathway code and a degree course name is not asked before submit,
   then capped at Unsure after. *Recommend:* use the wider test in both places.
8. **21 unreachable cells.** "Not final" exists only for Matriculation and polytechnic pages; "Suspect" is
   never stored for Matriculation or Diploma and nothing scores Asasi; Matriculation, Asasi and Diploma
   compare the CGPA only, so subject states cannot happen. *Recommend:* confirm these as designed; the F1
   test matrix pins them as "cannot happen".

---

## Appendix — technical citations

All paths under `halatuju_api/apps/` unless shown. Live check: `git diff --stat origin/main HEAD` on g15
shows no change to any file below (only staff, cron and permission files differ).

**Cell counts.** 49 cells (7 tables × 7 states): 22 Filled, 6 QUESTION (A4, B4, B5, D1, E1, F4), 21
Unreachable. Questions 4, 6, 7 and 8 sit outside single cells.

### Citations by group

- **SPM compare** — `scholarship/academic_compare.py`: `_short_read` L40-47; `compare_academics` L78-172
  (missing L105, printed/raw lines L115, short L118, extra only on grades and not short L119-120, grade loop
  L122-152: band_confirmed L147-148, uncertain L149-150, mismatched L151-152; complete L160; accurate L161;
  typed_ungraded L170-171). `spm_slip_compare` L175-206 (SPM holder: full match, `unchecked` always [] L196
  — the source of Q1; tertiary: `missing` [] L201, not compared when nothing checked L200-205).
- **Drawer, SPM card** — `scholarship/academic_engine.py` `student_slip_check` L626-691 (wrong slip
  L635-637; no rows L661-670; subjects L675-676; results L677-684). `_slip_name_status` L569-585.
- **Tile, SPM card** — `scholarship/verdict_academic.py` L14-91 (no slip `results_slip_missing` L27; name
  L34-45; wrong slip L46-47; not comparable L49-50; no rows L51-55; not compared L59-60; missing L61-65;
  extra L66-67; mismatches L68-73; uncertain L76-78; unchecked L79-80; no grades L82-86; Certain L88-90).
- **Wrong slip (higher result in SPM slot)** — `scholarship/wrong_slip.py` `higher_kind` L93-107,
  `slip_check` L128-145, `academic_fact` L148-163 (Q6: always 'review').
- **Higher card** — `scholarship/higher_results.py`: `_compare_stpm` L248-258 (missing + mismatched only,
  no extra, no short-read guard, no uncertain: Q2-Q4); `student_higher_check` L272-353 (undeclared L296,
  kind L298-299, CGPA L302-313, STPM grades L314-324); `academic_fact` L385-393; `verdict_academic`
  L396-456 (not final L438-440, not checked L441-442, clean L443-444, SPM fold-in and "idle" L445-455);
  `final_owed` L459-466; `higher_doc` L469-477; `red_chips` L523-532.
- **Drawer, higher card** — `halatuju-web/src/lib/higherResultsFacts.ts` L15-29 (Name, Type, CGPA,
  Results only when `grades_status` set); `slipHigherFacts` L35-40. `halatuju-web/src/lib/cockpitDocFacts.ts`
  `factStatus` L31-49, `genuinenessFact` L145-152, results-slip chips L203-219.
- **Genuineness** — `scholarship/verdict_ladder.py`: `_academic_red_chips` L77-101; `_apply_genuineness_ladder`
  L213-247 (band = max(base, step + chips) L242; higher anchor docs L226-230); `_UNSCORED_FLOOR` and
  `_genuineness_unscored` L271-286 (Q5). `scholarship/genuineness/matric_poly_doc.py` L1-39 (never suspect;
  Asasi and non-polytechnic diplomas never scored), `matric_poly_higher_genuineness` L309-324, `_ruled_page`
  L276-284 (not final: matric and diploma only). `scholarship/genuineness/bands.py` L59-76 (`FINAL_OWED`).
- **Degree-bound and owed** — `scholarship/results_route.py`: `destination` L74-110, `degree_bound`
  L113-131 (Q7), `higher_need` L147-163, `map_documents` L166-183. `scholarship/higher_owed.py`:
  `declared_kind` L93-105, `_spm_only` L108-115, `_needs_higher` L118-133 (uses `degree_bound`, Q7),
  `_too_late` L136-141, `undeclared` L144-148, `_owed` L151-164, `owed_kind` L180-184, `late_anchor`
  L187-190, `cap` L289-303, `cap_undeclared` L306-318.
- **Routes** — `courses/exam_questions.py`: `is_tertiary` L95, `results_held` L121, `spm_grades_for`
  L297-315, `spm_slip_comparable` L329-338.
- **Decisions read** — `docs/decisions.md`: #62 (2026-11-06, L19266); three exclusive routes (L19316);
  cap at Unsure and SPM tick needs subjects (L19386); every degree student must have higher results
  (2026-11-07, L19393); undeclared compares nothing, typo-tolerant STPM names (L19471). Requests #54, #58
  and #59 are about income, My Profile and the parent IC: they do not touch the slip check.

### Duplicated rules (7) — the F1 build should leave one of each

1. **SPM red chips re-derived.** `verdict_ladder._academic_red_chips` L89-100 recomputes the Name, Subjects
   and Results chips from scratch, apart from the tile items (`verdict_academic` L35-80) and the drawer
   statuses (`academic_engine` L675-684).
2. **The SPM compare runs three times per verdict.** `verdict_academic` L58, `verdict_ladder` L96 and
   `higher_results` L453-454 (the "idle" test) each call `spm_slip_compare` on the same slip.
3. **Drawer and tile map the same compare result separately.** `student_slip_check` L661-684 and
   `_verdict_academic` L51-91 (for example, "unchecked" is drawer 'pending' but a tile item; no rows is
   drawer 'pending'/'unreadable' but tile `grades_unverified`).
4. **"Not comparable" asked three times.** `spm_slip_comparable` in `academic_engine` L665,
   `verdict_academic` L49 and inside `spm_slip_compare` L193.
5. **Higher card chips re-derived.** `higher_results.red_chips` L523-532 vs the tile items L406-437.
6. **Two compare engines with different rules.** SPM `compare_academics` (extra, short read, uncertain) vs
   STPM `_compare_stpm` (none of them) — the root of Q2-Q4.
7. **Two "degree-bound" tests.** `results_route.destination` (document list) vs `results_route.degree_bound`
   (owed rule, funding, award) — Q7.

### Small finding

`scholarship/higher_owed.py` module docstring (L17) still says the owed cap is "capped at Probable"; the
code (`cap` L289-303) caps at Unsure since 2026-11-06. Comment only; fix in the F1 build.
