# STPM results read "Exact" — roadmap (drafted 2026-10-27, awaiting owner approval)

## Why
SPM results slips and certificates are read **Exact**: fixed labels are parsed from the OCR text, and Gemini is
only the fallback. STPM results are always read by **AI**: `higher_results.extract` is Gemini with
`capture='ai'` hard-coded. In the `higher_results` slot there is no genuineness check at all
(`higher_results_not_checked` is always added), so owner ruling 1A (an online results-checker screenshot is
not accepted) only works in the `results_slip` slot. Example: corpus doc d3303, a checker screenshot in the
STPM place, was never flagged.

The owner wants STPM read Exact. To read well, the parser must know whether it holds an **STPM certificate**
or an **STPM results slip**, because the two print the same facts in different places. This was the lesson
from SPM.

**Owner ruling (2026-10-27): the certificate/slip difference is for the READER ONLY.** For our purpose the two
are one and the same document. Nothing is shown to reviewers or students. There is no label, marker or note,
and no rule treats a certificate differently from a slip.

## The two layouts (owner's 2025 examples, 2026-10-27)
Both are issued by Majlis Peperiksaan Malaysia and show the same facts, but in different places:

| Fact | Certificate | Results slip |
|---|---|---|
| Title | "SIJIL TINGGI PERSEKOLAHAN MALAYSIA (MALAYSIA HIGHER SCHOOL CERTIFICATE)", bilingual labels | "Slip Keputusan Peperiksaan STPM <year>" |
| Name | sentence after "Dengan ini disahkan bahawa" | "Nama :" row in a key–value block |
| IC | "No. Kad Pengenalan", digits without dashes | "No. Kad Pengenalan :", with dashes |
| Index no. | "Angka Giliran" + school name | "Angka Giliran :" |
| Year | "Tahun Peperiksaan: <year>" | in the title |
| Subjects | one row per subject: Gred, Nilai Gred, LULUS PENUH | KOD + subject row, then paper rows (e.g. Pengajian Am 1–4, with % and paper grade); subject grade + Nilai Gred on the subject row |
| PNGK | "Purata Nilai Gred Keseluruhan", bottom right | "Purata Nilai Gred Keseluruhan (PNGK) :", top block |
| Serial | bottom right ("nnnnnnn / yy") | "No. Siri :" — the same number |
| Fixed text | "Bilangan Mata Pelajaran Lulus", signatories | "Nota Penting: Slip keputusan ini bukan sijil STPM" |

The exam year (title / "Tahun Peperiksaan") is the year BEFORE the results date: STPM 2025 results were
released on 18 Jun 2026. The reader takes the exam year from the title, never from the release date.
(Owner, checked with an expert, 2026-10-27: "STPM 2025" = the cohort that joined in 2025 and finished in
2026; results released in 2026; typically born in 2006.) A slip seen with title "STPM 2025" but release date
18 Jun 2025 is SUSPECT (perhaps a misprint) — see the S3 date-consistency signal.
The slip's paper rows must not be read as subjects; only the subject rows (with a KOD) count.
**Layouts vary slightly between years** (stable over about 3 years). The reader keys on a SET of anchors
with tolerance, never on one exact phrase or position, and an unknown variant falls back to AI.

## Corpus (local, gitignored, PII)
`halatuju_api/apps/scholarship/eval/fixtures/results_split/`, sorted by the owner and split by page on
2026-10-27:
- stpm_cert 21, stpm_slip 18
- controls: spm_cert 8, spm_slip 6, fake 2
- also: matric 3, diploma 5, asasi 1, muet 1, spvm 1, other 4

There are no OCR caches for STPM yet. The stored prod reads (snapshots `higher_results__*.json`) are all AI.

## Ground rules
- Opus builder to a written brief. The lead verifies the diff and re-runs every gate.
- Adversarial review before every push (S2–S4 touch document recognition and verdicts).
- Bump `MODEL_VERSION` on any recognition change, and `VERDICT_ENGINE_VERSION` when a band can move.
- Size guards: `vision.py` (2341/2321) and `_run_field_extraction_impl` (316/306) are at their ceilings. The new
  reader lives in a new `stpm_parse.py`, and vision.py takes at most a one-line call.
- No re-extraction from a local checkout. Live re-reads only, with the job flags (CLAUDE.md:163–170, TD-407).
- Coordinate pushes with the other session (it owns vision.py/str_route.py work).

## Sprints

### S1 — OCR capture + labels (no product change) · low · ~4 h · paid: Vision OCR, a few cents
- `eval/capture_ocr.py`: capture ALL pages and word boxes (today page 1, text only).
- Capture the 39 STPM docs plus the controls (SPM cert/slip, the fakes, Matric/Diploma).
- `labels.json` regressions: the expected form (certificate / slip / checker page), name, PNGK, subject–grade
  rows, and the expected 1A/2A outcome.
- **Done when:** every STPM doc has an `.ocr.txt` cache and a label; the harness lists them.

### S2 — `stpm_parse.py`: a deterministic reader + certificate/slip classification · high · ~12 h
- Text-first parser (like `offer_parse`/`bc_parse`), so a digital PDF works from its text layer.
- It reads: name, NRIC, index number, year, PNGK, subject–grade rows (STPM grade scale A … F) and MUET where
  printed.
- It first recognises the layout from fixed printed markers: **certificate** (certificate wording, Higher
  School Certificate, notes back page) or **results slip** (Keputusan / slip wording). Then it applies that
  layout's reading rules. The layout is an internal routing step only. It is not stored as a field anyone sees
  and no rule reads it.
- Unsure → returns nothing, and the read falls back to Gemini (still AI). It never guesses.
- Wired into `higher_results.extract`. A hit stores `capture='deterministic'`. The same seam serves an STPM
  doc in the `results_slip` slot.
- The web chip reads the stored tag, so no change is expected there; verify.
- `PARSER_VERSION`; unit tests from synthetic twins (no PII in tests); offline score against S1.
- **Done when:** at least 90% of the corpus reads Exact with correct name/PNGK/grades; 0 wrong values (a miss
  falls back to AI, never a wrong Exact); full gates green.

### S3 — STPM genuineness in the STPM results place + 1A/2A · medium · ~9 h
- Score STPM docs in `higher_results` with the existing C3 STPM signatures (`genuineness/stpm_doc.py`) plus
  the crest check.
- Replace the blanket `higher_results_not_checked` with a real result.
- A checker page (1A) asks the student for the real slip or certificate. A certified copy (2A) is accepted.
- Certificate and slip are judged the same way. No new reviewer label.
- ~~Date-consistency signal~~ DROPPED (S1, 2026-10-27): two different genuine-looking "STPM 2025" slips carry
  release date 18 Jun 2025, so it is a recurring council misprint; a date check would wrongly mark real students.
- Owner ruling (2026-10-27) on online-portal prints: a PDF saved from the MPM results website (URL + timestamp
  footer) is ACCEPTED like a slip. Owner ruling A (2026-10-27, after review): a printout of the MPM results web
  page counts as a slip in ANY form — scanned, photographed or certified (2A). Only the CHECKER PAGE itself is 1A,
  recognised by its own heading / buttons; a screen photo without them is judged by the signatures.
- Bump `MODEL_VERSION` to 1.10.0, and `VERDICT_ENGINE_VERSION` (bands can move).
- **Done when:** d3303-style checker pages are asked for the real document; certified copies pass;
  Matric/Diploma docs are not misjudged as STPM; owner sees the before/after list of affected applications
  before release.

### S4 — Live re-read + close · low · ~3 h · paid: Gemini fallback on misses only
- Targeted live `reextract_documents` for `higher_results` plus the STPM docs still in the `results_slip`
  slot, with the job flags. Spot-check capture and authenticity.
- CHANGELOG, decisions, retrospective, and a completion note.
- **Done when:** live STPM docs show Exact (or AI with a reason); no stored genuineness was wiped.

**Total: 4 sprints, ~28 h.** S1 is safe to start at once. S2 is the core. S3 is where students and reviewers
see a change, so the owner sees a before/after list first.

## Owner decisions
1. **1A in the STPM place:** a checker screenshot uploaded as STPM results → ask for the real slip or
   certificate (same as the SPM place). RULED: yes — the checker page only (its own heading / buttons); a
   printout of the results web page in any form is a slip (ruling A, 2026-10-27).
2. ~~Reviewer label~~ — RULED 2026-10-27: no. Certificate vs slip is for the reader only; nothing is shown.
3. **Paid steps:** S1 Vision OCR (a few cents) and S4 live re-read — approve at each step.
4. **Out of scope:** Matriculation / Asasi / Diploma Exact reads (corpus too small: 3 / 1 / 5) and a MUET
   document (1 sample). Revisit when more arrive.
