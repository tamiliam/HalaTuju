# Retrospective — Bumi coverage Sprint F2 (MARA UP_TVET) — 2026-10-30

Live in `2127fda6` (api-01205-sgc / web-01030-cv7; ingest re-revision api-01206-r7r). No migration.
`ingest_tvet_courses --file data/tvet/tvet_new_courses_F2.json --create-institutions --apply`: 181 courses,
606 campus offerings, 233 institutions (MARA-001..233: GIATMARA 209, IKM 13, KKTM 10, MJII 1); 59 rows flagged
and not ingested.

## What Was Built

- The F1 parser now reads MARA's condition wording: 606 of 665 public MARA pages (21 before). New line rules
  for the bare "Warganegara" / "Bumiputera" / "Calon Bumiputera" headings, "Tidak Buta / Rabun Warna", MARA's
  blanket OKU wording (with its "sebaran" typo), the card summary line, a second gate on one line, "Tidak Tamat
  Sekolah" (= no formal education), and SPM options whose heading names the vocational groups.
- 177 courses are Bumi-only (all also citizen-only); 4 GIATMARA courses are open because their pages are silent
  on Bumiputera (owner: follow the page).
- Colour vision no longer splits a programme: it hides if ANY campus page excludes it (F1b ruling).
- `--sql` / `--rollback-sql` print the read-only pre-check and the one-transaction rollback, refusing any id
  outside the expected shapes.

## What Went Well

- **The dry run on prod printed the runbook's numbers** (233 / 181 / 606 / 59) and the apply matched them.
- **The live smoke agreed with the golden master:** non-Bumi citizen 4 F2 courses, Bumi citizen 181
  (177 Bumi-only), foreigner who says Bumi 3, Bumi-only 0.
- **The review found no wrong gate.** It checked every Bumi, citizen, colour and OKU flag on all 665 pages
  against the page and proved F1 and F1b still rebuild byte for byte.
- **The builder's own survey caught four silent errors before review** (experience/Form 3 headings read as
  "open", OKU only in the card summary, two gates on one line, heading credits above the table).

## What Went Wrong

1. **A printed "Atau" between two subject rules was read as "and" without a flag (48245).** *Why:* the item
   splitter treated a bare "Atau" line as one more body line. *Fix:* it is now a problem, so the row is
   flagged for a person (review round 1). Covered by the standing rule "unknown wording flags, never guess";
   no new lesson.
2. **Two latent gaps in the card-summary reader** (a recognised line hid an unrecognised gate word; an ATAU
   card could get a dropped gate back from its summary). No page triggered them; fixed and tested.

## Design Decisions (decisions.md, 2026-10-30, Sprint F2)

- The 4 GIATMARA pages silent on Bumiputera stay open (owner).
- "Bumiputera / Bumiputera Sabah atau Sarawak" = Bumi-only; KKTM heading credits vs table: the table wins,
  heading in the remarks.
- Form 3 / PT3 / experience routes never decide; only the SPM route does.
- Count-once on "Mana-mana satu (1) mata pelajaran lain" follows the strict ruling of 2026-10-29 (45 courses).

## Numbers

- 10,607 pytest / 3 skipped (`-n auto`, alone); tsc 0; jest 5,265.
- Golden: original 5,293 identical; full bumi=False 6,986 (F2 non-Bumi gain 199); bumi=True 12,621
  (F2 Bumi gain 5,069); STPM 2,025.

## Follow-ups

- The 59 flagged F2 rows (54 with no SPM route, 2 wide tables, 1 empty card, 1 GIG, 1 item-level "Atau").
- Grouped-course display text (age remark, level, duration) comes from the first campus only.
- The F1 / F1b follow-ups in halatuju_api/CLAUDE.md still stand.
