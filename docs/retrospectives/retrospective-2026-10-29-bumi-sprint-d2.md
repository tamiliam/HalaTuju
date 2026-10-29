# Retrospective — Bumi coverage Sprint D2 (the other SPM courses, ATAU, Bumi matric tracks) — 2026-10-29

Live in `914d4a5b` (web-01018-27c; api-01187-shx, then the ingest re-revision api-01188-45h). No migration.
66 rows + institution `MARA-BPT` ingested. With D1, all 150 Sprint A SPM courses are live.

## What Was Built

- 47 Bumi-only non-UiTM rows (UIAM 20, MARA 15, UMS 4, UNIMAS 3, UM 3, UniSZA 2), 14 open Islamic-subject rows
  (UniSZA 9, USIM 4, UM 1), the 3 UiTM rows D1 held back, and 2 Bumi-only Matrikulasi tracks.
- `any_of` (ATAU) count-once groups, read only through a reviewed per-programme scope table
  (`spm_atau_scopes.py`) because the scraped text is flat; "A- in ONE AND B in THREE" as two groups over one list.
- Per-row parent institutions and a dry-run-first `--create-institutions`; MARA-BPT (IPTA, WP Kuala Lumpur).
- Search pick-lists refresh when the Bumi answer arrives, with the page's first jest harness.

## What Went Well

- **Nothing guessed, still nothing flagged.** The 5 ATAU rows were read from the five MOHE modals' layout (5 polite
  requests), recorded per programme, and every other ATAU stays flagged by default.
- **The golden master proved the open rows are open and the Bumi rows are not:** bumi=False delta 0 over the 50
  golden students, plus a dedicated student who holds the Islamic subjects and gains open rows only.
- **Deploy matched the runbook to the row:** dry run printed exactly 1 institution + 66 CREATE, 52 Bumi-only.
- **The live smoke covered both subject profiles** (science and Islamic) × three people; one apparent leak was
  traced to an old course with a similar code (UH4520001) in two minutes, not reported as a fault.

## What Went Wrong

1. **The course page would have crashed on every ATAU row, two of them open to everyone.** *What:* the engine and
   data gained an `any_of` group with no `subjects`; `RequirementsCard.tsx` read `group.subjects.length`. *Why:*
   the builder tested the engine and the data end to end but not the web renderer of the same JSON — the D1
   count-once construct had been added to the card in D1, so its consumers were known, and the brief did not say
   "every reader of `complex_requirements` must render the new shape". *Fix:* `GroupBody` renders `any_of`, a jest
   test renders all five real rows, and the reviewer grepped every other reader. Lesson below.
2. **A reading that made rules empty came back for MARA.** "C in any N subjects" without "belum diambil kira"
   was read as `min_credits`, which BM, Maths and English already meet. The D1 lesson ("a reading everyone meets
   is the wrong reading") caught it in review rather than in build. *Fix:* owner ruled strict for MARA's shape;
   8 rows re-parsed. The lesson stands; the builder brief now needs to name it explicitly.
3. **The MARA institution proposal used a state spelling and a type that prod does not use.** *Why:* the builder
   could not read prod. *Fix:* the lead's read-only SQL caught both before the ingest; the runbook already listed
   the check. No new lesson.

## Design Decisions (decisions.md, 2026-10-29)

- ATAU through a reviewed scope table, never inferred from flat text.
- "A- in ONE AND B in THREE" = four distinct subjects.
- MARA "any N" = strict; UM0221002 may share a subject across clauses (no "not yet counted" phrase).
- The 2 Bumi matric tracks are not offered in the scholarship pickers until they have a college list.
- MARA-BPT is type IPTA (a label only; no student filter reads it).

## Numbers

- 10,192 pytest / 3 skipped (`-n auto`) · 4,914 jest / 316 suites · tsc 0 · bundle median 146.4 / 148 kB.
- Golden masters: original 389 = 5,319 identical; full bumi=False 5,319 (+0); bumi=True 5,986; STPM 2,025.
- Prod: 516 courses, 136 Bumi-only.

## Follow-ups

- Sprint F: UP_TVET incl. ~544 MARA rows.
- The 2 prod rows the fixture lacks (UL0481001, FB0500001).
- College lists for the 2 Bumi matric tracks, then offer them in the pickers (Option A).
- Tamil for `courseDetail.oneOf` / `orAlternative` and the track names goes through Sol.
- `ranking_engine.TRACK_FIELD_MAP` has no entries for the new tracks (file at its budget).
