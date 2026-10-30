# Retrospective — Bumi coverage Sprint F1b (held TVET flag fix) — 2026-10-30

Live in `579e27ca` (api-01199-vz4, then the fix re-revision api-01200-s7p). No migration.
`fix_held_tvet_flags --apply`: 208 field changes on 63 held IJTM-* / IKBN-* courses.

## What Was Built

- `held_flag_fix_F1b.json`, built by code (`tvet_held_flags.py`) from the October page cache: per held course every
  read campus page, the old and new value of `req_malaysian`, `no_colorblind`, `no_disability` and `remarks`.
- `fix_held_tvet_flags`: dry run first; `--apply` in one transaction with compare-and-set on every field (refuses
  the whole run on any stale value, missing course, duplicate, or id outside IJTM- / IKBN-); `--reverse` is the
  rollback; `--sql` prints the read-only pre-check.
- Result: 63 x `req_malaysian` true; 19 x `no_colorblind` true; 63 x `no_disability` false; 63 remarks filled with
  the age / health / qualified OKU text, so an OKU student sees the note.

## What Went Well

- **The pre-check matched prod exactly** (0 rows) before the push, and the dry run printed the runbook's number
  (208 on 63). Compare-and-set made the apply exact and the rollback safe.
- **The golden master named every student who moved** (non-citizen -50, colour-blind -19 each, OKU +62) and the
  reverse test restored the pre-fix digest.
- **Live smoke agreed:** citizen 83 held courses, non-citizen 20 (the 20 held courses with no October page),
  colour-blind 34, OKU 63; the remark carries the OKU line.

## What Went Wrong

1. **The first build would have shown OKU students these courses with no note at all.** *What:* the fix removed
   `no_disability` but left the held remarks empty, so the owner's "show as text" ruling had no text. *Why:* the
   brief named only the three flags; a gate turned into text needs the text to land in the same change. *Fix:*
   remarks became a fourth compare-and-set field (review M2). Covered by the D2 lesson on every reader; no new
   lesson.
2. **Colour flags changed on courses whose other campuses had no page.** *Why:* "all campuses agree" counted only
   read pages. *Fix:* the owner ruled colour hides on ANY read page, which makes the rule explicit and independent
   of unread campuses.

## Design Decisions (decisions.md, 2026-10-30)

- A page silent on disability means no OKU gate (26 IKBN courses, as F1 reads the same pages).
- Colour: hide if any read campus page excludes colour blindness.
- The 20 held courses with no October page are unchanged; they still lack `req_malaysian`.

## Numbers

- 10,511 pytest / 3 skipped (`-n auto`, on 9ad721a2 + F1b); no web change.
- Golden: original 5,293; full bumi=False 6,787; bumi=True 7,552; STPM 2,025.

## Follow-ups

- The 20 held TVET courses with no October page (June ids not in today's catalogue): retire or re-match.
- The 92 out-of-scope held differences (`three_m_only` 50, subject rules) for an owner decision.
- Sprint F2 (MARA).
