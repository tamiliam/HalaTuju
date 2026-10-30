# Retrospective — Matriculation + polytechnic Diploma results read "Exact" (M1–M5, 2026-10-29 → 10-30)

Roadmap: `docs/plans/2026-10-29-matric-diploma-exact-read-roadmap.md`. Trigger: BrightPath request #49
(triaged a bug by the owner; charge absorbed). Planned ~30 h.

## What shipped
- **M1** — `results_kind` issuer tier (polytechnic name, Matriculation college, the fixed subject
  "Pengajian Am Matrikulasi"), gated on the page reading as a result; `backfill_higher_results_kind`.
- **M2** — `matric_parse`: Matriculation transcripts read Exact, every value proven by the semester sums;
  only rows a sum proves are returned.
- **M3** — `poly_diploma_parse`: polytechnic transcripts (text layer only) read Exact; calibrated on one
  document, so it refuses widely.
- **M4** — genuineness for Matriculation and polytechnic transcripts, genuine-or-nothing.
- **M4b** — the owner's rulings: only the final result counts; a semester slip or the polytechnic portal
  reads as "final transcript owed" (Probable cap + ask, never the fake step); a provisional transcript with
  its completion status counts as final; a Matriculation offer letter is not a results document.
- **M5** — one live re-read pass (61 docs, 0 errors). Five Matriculation transcripts and the polytechnic
  transcript now score genuine; application 304's semester slip now asks for the final transcript.

## What went well
- Every sprint went through an adversarial review before its push, and every review found something
  real. Two found blockers (M4: a genuine 2-year transcript read page-1-only scored suspect; M4b: a real
  final transcript could be asked for again) — both were caught before any student saw them.
- Readers return nothing when unsure. Across all corpora the wrong-value count stayed at 0.
- Pushes were coordinated with four other sessions with no collisions and no red builds.

## What to do differently
- **Write the owner's question before building the rule.** M4b was built twice: the first version treated
  a semester slip like a checker page (the −2 step), which would have put a genuine student on Fail. One
  question ("what is this upload for?") settled it; asking it before M4 would have saved a build round.
- **"Hard rule" cases deserve their own probe list up front.** "Never ask a student with a real final
  transcript to re-upload" was broken three ways in a row (status wording, a page-1-only read, a bundled
  upload). Listing the ways a real document can look incomplete before building would have caught them
  in one pass.
- **Small corpora.** The polytechnic reader and its rulings rest on one transcript, two slips and one
  portal page. Expect a low live hit rate until more examples arrive; everything unseen stays "not checked".

## Effort
Planned ~30 h. Spent about 15 h, estimated from the builder and reviewer run times (about 11.5 h) plus
lead time for briefing, gates, coordination and deploys. Most of the elapsed time was waiting on test runs
and on other sessions' builds.

## Open items
- Reading all pages of a scanned PDF (`higher_pages.py`) is proposed, not built.
- Asasi and non-polytechnic Diplomas (UiTM, private colleges) stay AI-read and "not checked".
- An Exact Matriculation read leaves out English, co-curriculum and Moral rows (they cannot be proven);
  showing them as "not checked" is a possible small change if the owner wants it.
