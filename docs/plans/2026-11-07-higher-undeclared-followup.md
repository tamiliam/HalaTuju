# Follow-up: undeclared higher results + typo-tolerant STPM subject names (bug fix, 2026-11-07)

Executor: Opus agent. Branch `fix-higher-undeclared-followup` (from origin/main c8650ffb, which carries
the higher-owed fix 5d945a7d + c7f8af4e). **Main is under audit: push to the branch only, never to
main, never deploy.** No charge (follow-up to the same bug). Predecessor brief:
`docs/plans/2026-11-07-higher-owed-spm-only.md`.

## Live case: app 278 (owner screenshots, 2026-11-07)

Status interviewing, interview session submitted (querying locked). Declared SPM only — no STPM grades.
On file: STPM certificate (doc 4105, `results_kind` 'stpm' from a team split, AI read, CGPA 3.67 read
right, "PENGAJIAN AM" read as "PENGJIAN AM"), SPM slip (doc 4106, Exact, all 8 match). The new ask
`higher_results_declare_requested` was raised 04:46 today. The cockpit shows:
- Academic: "STPM subjects on the slip but not entered: BAHASA MELAYU, SEJARAH, GEOGRAFI" — and PA
  is missing from that list; the Results chip is RED; CGPA amber.
- "✓ The document reads as STPM results, as on the results page" — false: her results page says SPM;
  the kind 'matched' the team's split label, not anything she declared.
- Check 2 card: "Upload: Enter and upload your STPM… results" — but the document is already on file.
- Check 2 panel banner: "Querying closed — the interview is concluded. This is now a read-only
  record." directly above the ask raised today.

## Owner principle

Everything shown is what the student DECLARED; a tick only when documentary evidence matches it.
Nothing declared → nothing to compare → no tick, no mismatch claim (grey, "not checked").

## Fixes (all six)

1. **Undeclared: no comparison.** When the student declared no higher results
   (`higher_owed.undeclared` / the on-file-undeclared state), the higher-results card must not compare
   subjects or grades against an empty entry: no "subjects on the slip but not entered" item, no red
   Results / Subjects chips (grey/unknown instead), no grade mismatch notes. Only the undeclared note
   (`higher_results_undeclared`) speaks. CGPA stays as now (amber "read, nothing to check").
2. **No false kind tick.** For an undeclared student, the "reads as <kind> results, as on the results
   page" tick must not appear (the kind came from the slot/team label, not her declaration). Show the
   detected kind neutrally (no tick) or not at all — smallest honest option.
3. **Ask copy when the document is on file.** `higher_results_declare_requested` with a live higher
   upload already on file: the student-facing card (and the cockpit's Check-2 line) says only "enter
   your results on your results page — we already have your document", not "enter and upload". Pick
   the smallest mechanism (params flag at raise/refresh, or a second copy keyed at render) — the copy
   must also be right if the upload arrives AFTER the ask was raised. en/ms/ta.
4. **Banner.** The cockpit's "Querying closed" banner must not contradict an open late ask
   (`higher_owed.LATE_ASK_STATUSES` exception). E.g. add one line: "The higher-results request is still
   open — the student can still answer it." Smallest change; en/ms/ta.
5. **Verify (test, then report):** can a SUBMITTED student who declared SPM only move up to STPM /
   Matriculation / Asasi / Diploma on the onboarding results pages (`/onboarding/exam-type`,
   `/onboarding/stpm-grades`, `/onboarding/higher-grades`) after submit, and after the interview was
   submitted? (`courses.serializers.ProfileUpdateSerializer._never_demote_held_results` guards
   DOWNWARD moves only — confirm upward is allowed end to end, and the declare ask then closes once a
   clean upload is on file.) If it is blocked, report — do not open a new door without the owner.
6. **Typo-tolerant STPM subject names** (`higher_results._STPM_NAMES` / `_STPM_BY_NAME`, used by the
   comparison, `entered_lookup`, `stpm_marks`, the Exact reader if it shares it). Live: "PENGJIAN AM"
   on apps 196, 278, 279, 341, 418 (AI reads; the certificates print PENGAJIAN AM) and "PENGJIAN
   PERNIAGAAN" on 196. Rule: a printed name within a small edit distance (1, or 2 for long names —
   your call, justify) of exactly ONE known name maps to that subject; ambiguous → unrecognised.
   Never map onto a subject already matched exactly on the same document.
   **No silent drop:** a printed STPM subject still unrecognised is named in Academic (a new
   item, e.g. "A subject on the results could not be recognised: …") and blocks the all-subjects
   tick (`stpm_marks.all_subjects` must not be 'match'). Live impact to report: 196 (entered PA B+,
   certificate B — a REAL mismatch currently hidden) must now show the PA mismatch; 279/341/418 PA
   matches and their set can tick if all else matches. Do NOT apply this to a doc that is not an STPM
   result (see out of scope).

## Out of scope — raise TD entries (next free ids) instead

- App 343: an STPM document listing papers by term ("PENGAJIAN AM 1 … 4", "GEOGRAFI 1 … 4") — a
  per-paper/term layout the subject comparison does not model.
- Apps 306, 340: Matriculation transcripts read / detected as STPM (subject rows "MATHEMATICS 1",
  "MATRICULATION GENERAL STUDIES").

## Gates and rules

- Bump `VERDICT_ENGINE_VERSION`. decisions.md entry, CHANGELOG, tests for every point (rendered web
  tests for the chips/banner/copy).
- Full API suite, `npm run gates`, bundle ratchet, and `npm run mobile-check` for the UI changes — heavy
  runs through `python /Users/elanjelian/Python/Settings/_tools/test_queue.py -- …` (no `|` in args).
- Never push main, never deploy, never write prod data, no paid reads. Read-only prod SELECTs only if
  needed; no names/ICs in output, files or commits.
