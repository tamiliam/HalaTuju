# Retrospective — Bumi coverage Sprint F1 (public UP_TVET, non-MARA; two new pathways) — 2026-10-30

Live in `a60662cc` (web-01023-hb6; api-01194-hhv, then the ingest re-revision api-01195-7wf). No migration.
35 courses (39 campus offerings), 33 new campus links to 20 held courses, 4 institutions (IKBN-022,
ILKA-001..003). Prod now holds 551 courses.

## What Was Built

- A fresh UP_TVET catalogue (1,006 programmes; Awam 943) and every public course page saved (943, MARA too,
  for F2), with `scrape_uptvet` / `audit_uptvet` writing the dashboard's UP_TVET status row.
- A page reader and requirement parser (`tvet_pages.py`, `tvet_syarat.py`, `tvet_subjects.py`): "no formal
  education" = open; the SPM option is the only academic rule; citizenship, Bumi and colour vision are flags;
  age, health and the qualified disability line are text; gender, religion, unknown wording and no SPM route are
  flagged. Review round 1 added a gate scan over EVERY line of an academic card.
- `ingest_tvet_courses` (dry run first; `--create-institutions`; refuses an existing or non `TVET-` id and a
  "new" link that already exists), with the shared ingest code moved out of `ingest_spm_courses` first.
- Pathways `mara` and `tvet_other` ("Other skills training") from the institution category, through every door.

## What Went Well

- **The golden master proved the exact gain.** A non-Bumi student gains exactly the F1 rows she meets (1,494,
  digest-pinned); the original 389 courses stayed 5,319 identical; the Bumi gain is now digest-pinned too.
- **The deploy matched the runbook to the row:** dry run 4 / 35 / 0 UPDATE / 33 LINK / 116 held / 90 flagged;
  `--apply` "Applied 35 courses, 33 held-course links; created 4 institutions".
- **The live smoke agreed with the rules:** non-Bumi 33, Bumi 35 (the 2 KEMAS rows), foreigner 0.
- **Four sessions shared one deploy lane without a collision**: Maintenance S4a and S4b and Billing each went
  first, F1 rebased onto each, and the full gates ran again on the final tree.

## What Went Wrong

1. **The review file believed 22 prod links were new, and the rollback would have deleted them.** *What:* the
   builder matched held offerings by the June `id_kursus` in the prod hyperlink; October's numbers differ, so 22
   (course, campus) pairs prod already holds were marked new, and the runbook rollback deleted "every link marked
   new". IKBN-DIP-002, a course only the repo fixture holds, would have made `--apply` refuse. *Why:* the builder
   reads repo fixtures, not prod; the prod export it was given was matched on the wrong key; no gate compared
   the file's picture of prod with prod. The pattern recurred from D2 (MARA-BPT state and type). *Fix:* links
   match on the (course, campus) pair; `--apply` refuses a "new" link that exists, so the rollback list is exact;
   the lead's read-only SQL on the review file's own pairs ran before the push. Lesson below.
2. **The parser could drop a gate hidden inside an academic option.** *What:* text before the first item,
   non-SPM options and open options were not scanned, so "Lelaki sahaja" there would have been ingested with no
   gate. No F1 page had one; MARA pages may. *Why:* the parser walked the requirement shape it expected, not
   every line. *Fix:* `academic_gate_hits` scans every line of an academic card; a hit not matched by a condition
   card is unparsed. Covered by the D1 lesson ("never guess"); no new lesson.
3. **One jest test failed once while pytest ran beside it, and passed alone (5,018 / 5,018).** *Why:* a timing
   test under a loaded machine. *Fix:* none yet; noted. Run jest and pytest one after the other before a push.

## Design Decisions (decisions.md, 2026-10-29)

- Today's catalogue only; the June-only Kraf, PERDA-TECH, MARDI, Peladang and tenun rows are not ingested.
- The qualified "ketidakupayaan ... menyukarkan kerja amali" line is text, never `no_disability`.
- Held rows are never written by F1; their flag mismatches (`req_malaysian` on 150 rows, `no_colorblind` on 59,
  `no_disability` on the qualified line) are a separate small change after F1 (owner, 2026-10-29).
- A Tahfiz certificate offered BESIDE an SPM route is allowed; the SPM route decides.
- New institution ids: `IKBN-NNN` for KBS campuses, `ILKA-NNN` (category TVET) for other public bodies,
  `MARA-NNN` (category MARA) for F2.

## Numbers

- 10,442 pytest / 3 skipped (`-n auto`) · 5,018 jest / 321 suites · tsc 0 · bundle median 146.574 / 148 kB.
- Golden masters: original 389 = 5,319 identical; full bumi=False 6,813 (+1,494 F1); bumi=True 7,578; STPM 2,025.
- Prod: 551 courses; 35 `TVET-` rows (all `req_malaysian`, 2 `req_bumiputera`).

## Follow-ups

- The held-row flag fix (small change, owner-approved).
- Sprint F2: MARA (665 pages saved; the parser reads 21 cleanly, so more condition wording first).
- The 90 flagged rows (75 post-SKM with no SPM route are expected to stay out).
- Fixture drift: UL0481001, FB0500001 (prod only), IKBN-DIP-002 (fixture only).
- The new subcategories have no ranking weight; the new pathways have no colour swatch.
