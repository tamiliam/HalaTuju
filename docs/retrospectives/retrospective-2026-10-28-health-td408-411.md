# Retrospective — health light, TD-408, TD-411 (2026-10-28)

Run autonomously after a compaction, on the owner's instruction ("plan and implement 1, 2 and 3 … little to no
input from me midway, except key decisions"). Owner input taken three times: the Stitch design, the TD-408 + TD-411
push, and the health-light push with its migration and a 3-document paid re-read.

## What shipped
- **TD-408** (`cc47ef04`, api-01168-5v7, VERDICT 2026-10-28.2): a true father/son reversal ("ALI BIN ABU" /
  "ABU BIN ALI") no longer matches; bare ANAK/AK/BT/BTE give a father name, which can only turn 'unknown' into
  'match'; a leading AK title (Awangku) is skipped.
- **TD-411** (same push, MODEL 1.17.0; hotfix 1.17.1 in `305b0434`): a PDF text layer that is only a scanner
  app's stamp is no layer; the KWSP app balance screen reads suspect `epf_app`. Re-read 3281 → genuine EPF,
  3209 → genuine certificate, 1395 → suspect epf_app.
- **Health light** (`305b0434`, api-01169-s5k / web-01003-xsf, scholarship 0180): super-admin status light over
  Gemini, Vision, email, scheduled jobs and AI credit; email alerts unchanged.

## What went well
- **Looking at the documents before fixing.** TD-411's premise ("the EPF scorer is broken") was mostly wrong:
  of 31 `not_epf` EPF-slot documents, ~26 were genuinely the wrong document. Viewing contact sheets of the real
  files (free, local) turned a scorer rewrite into a two-line text-layer fix plus one new screen type.
- **The live dry-run caught a TD-408 regression before deploy.** The first veto ("any part mismatches") split a
  Chinese name at its BIN syllable; 1448 real stored pairs showed it as 1 of 4 changes. Narrowed to a true
  reversal: 3 changes, all good.
- Three adversarial reviews; each found real, small issues (Awangku titles, stamp words inside company names,
  twitchy health thresholds, a missing scheduled job in the cadence table).

## What went wrong
- **TD-411's letter-spacing rule turned away a real 3-page statement** (doc 3919, Canva-style spaced headings).
  The eval corpus did not contain such a document; the post-deploy affected-list run did. Caught before any
  re-read, hotfixed in the next push (1.17.1). New uploads of that shape were read page-1-only for ~2 hours.

## Lesson
- A rule that turns text or documents away is dry-run over the LIVE stored data (here: every live PDF's text
  layer, free, via release-decisions) BEFORE deploy — not only over the eval corpus. TD-408 did this and was
  clean; TD-411 did not and needed a hotfix.
