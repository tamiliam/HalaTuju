# Higher results owed by a degree-bound student who declared SPM only (bug fix, 2026-11-07)

Executor: Opus agent. Branch `fix-higher-owed-spm` (from origin/main 778f8871). **Main is under audit:
push to the branch only, never to main.**

## The bug (owner, 2026-11-07, apps 158 / 168 / 247)

A university-bound student who declared SPM only is never asked for STPM / Matriculation / Asasi /
Diploma results. Owner rule: "STPM/etc. is a must for univ students" (missing higher results → amber).

Verified facts:
- `results_route.higher_need` already makes a degree-bound SPM-only holder upload higher results
  (`required_with_slip`, owner ruling 2026-10-26) — but only on the LIVE path, before submit.
- These applications were submitted 14–25 Oct, before S3a: their frozen `requirements_snapshot` has
  `results_slip: required` and no `higher_results` key.
- `higher_owed._owed` (the #388 catch-up for pre-S3a snapshots) returns '' at
  `kind = results_route.held_kind(application)` because the held results are SPM, not tertiary. So no
  Missing slot, no Academic cap, no Check-2 ask.
- Live population (read-only prod, 2026-11-07): 10 apps — 158, 162, 168, 207, 215, 217, 245, 247, 266,
  347. All submitted, degree course (`stpm_courses`), `exam_type='spm'`, no STPM grades / higher CGPA,
  no live higher_results doc (168 now HAS one: doc 5303, kind stpm, split off its SPM upload today,
  unread), every intake `min_stpm_pngk = 2` (asks higher). SPM years on the slips: 2021–2024.

## Owner-settled decisions

| # | Decision |
|---|---|
| 1 | Extend the catch-up: a SUBMITTED, degree-bound (`destination == DEGREE`) application whose held results are SPM only, on an intake that asks higher (`gift_asks_higher`), with a frozen snapshot that does not already require higher results and does not have results off, and no higher result sitting in the SPM card → higher results are OWED. |
| 2 | Same consequences as #388: Documents drawer shows the higher-results slot as Missing; Academic capped at **Unsure** (`recommend`, the current `cap()`), reason named; one Check-2 document request (`higher_results_requested`), raised and closed by the existing sync rules. |
| 3 | We don't know which qualification she holds, so the slot, the reason and the ask name all four generically ("STPM / Matriculation / Asasi / Diploma results"), not one kind. |
| 4 | Never a gate: no snapshot rewrite, no revert to the wizard, no blocker — display + verdict + ask only (as the #388 module docstring says). |
| 5 | Model principle: what she declared is checked against documents; a tick only on a match. A higher upload she never declared has nothing declared to match → never Certain/tick on it; it must not crash or read as verified. |
| 6 | (Widened 2026-11-07.) Every student bound for a university DEGREE, or already studying for one, must have STPM / Matriculation / Asasi / Diploma results on file. If not, Check 2 checks whether she DECLARED them and asks for documentary evidence. Exempt: a UA diploma and PISMP (SPM entry; "Ijazah Sarjana Muda Perguruan" is PISMP), and an intake that asks no higher results (D16c). |
| 7 | A student who declared SPM only gets ONE ask covering both: enter (declare) her higher results AND upload the document. A student who declared but has no upload keeps the existing upload ask. |
| 8 | "Already in university" with no catalogue course: assess whether a degree course name or a live offer letter whose programme reads as a degree should count as degree-bound for THIS check only (`destination()` unchanged). Built: the course name (the offer's own, autofilled); the offer read was not needed. |
| 9 | Legacy rows that DECLARED higher results (STPM grades / CGPA) but whose recorded completion still reads SPM (161, 205, 226, 243, 251, 276) are the same rule: owed with the declared kind. |
| 10 | Recommended or any later stage is too late: the new arms (owed slot, cap, ask) stop at `family.DECIDED_STATUSES` (187, 276 out). #388's own shape unchanged. |
| 11 | The Check-2 stage rule is NOT changed; report who would actually be asked. |

## What to build

1. `higher_owed._owed`: the SPM-only-degree arm (decision 1). Return a value that callers can tell
   from the four real kinds (e.g. a module constant for "unspecified"); check every caller
   (`owed_kind`, `late_anchor`, `answered`, `final_owed_kind`, `ask_codes`, `cap`, the serializer that
   serves the Missing slot, `upload_kind`, the Check-2 DOC_SPEC, cockpit copy) handles it. The upload
   for this ask must land in the higher-results card; its `results_kind` may stay blank or be chosen
   by the student — pick the smallest correct option and say why.
2. Copy (en/ms/ta) for the generic case: the Academic reason (today
   `higher_results_not_on_file`: "{held} results not on file…"), the drawer's Missing slot label, the
   student-facing Check-2 ask. British English; Tamil per the style guide (flag for language review).
3. Once a higher upload is on file for such a student (168 after its read): decide what Academic
   shows under decision 5 — the smallest honest behaviour (e.g. stays Unsure with a reason that the
   higher results are on file but were not declared, so the officer confirms at interview). Report
   exactly what 168 will show.
4. Bump `VERDICT_ENGINE_VERSION`. docs/decisions.md entry, CHANGELOG.
5. Tests: the 10-app shape (SPM-only, degree, pre-S3a snapshot) → owed + cap + ask; not owed for:
   post-SPM destination, intake not asking higher, snapshot already requiring higher, results off,
   unsubmitted, higher in the SPM card, tertiary holder (existing behaviour unchanged). Plus the
   on-file-but-undeclared case.

## Check before finishing

- The Check-2 ask is raised only in the stage the sync allows (`services.auto_queries_allowed`).
  Report which of the 10 (statuses: interviewing / profile_complete / interviewed) would actually get
  the ask; do NOT change the stage rule — flag it if most won't.
- Gates: full API suite, `npm run gates` (via `python Settings/_tools/test_queue.py -- …`), bundle
  ratchet. Commit, push to `origin/fix-higher-owed-spm`. Never push main, never touch prod data, no
  paid reads.
