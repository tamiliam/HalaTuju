# Retrospective — 2026-08-18: the SPM exam year, BrightPath request #12

A request quoted at six hours, delivered in about three — because the first half removed the
population the second half was priced for.

## What Was Built

Request #12: *"show year SPM was taken … this Student did her SPM in 2023!! we should get the AI to
highlight this."* Delivered in four parts.

1. **The exam-year anchor tolerates a clipped scan.** `PERIKSAAN\s+TAHUN\s+(20\d{2})` in place of
   the literal `PEPERIKSAAN`. Application #140's certificate was trimmed at the left edge.
2. **The merit score carries the year** — `94.7 (SPM 2023)` in the cockpit's Academic card, the
   year tinted only when it is off the expected sitting, never for an STPM student.
3. **The signal stays silent on a document that is not an SPM result** — #77's matriculation letter
   was announcing "SPM 2026".
4. **A Check-2 clarify** (`spm_year_unknown`) asks the student, in the one case reading the paper
   cannot settle.

## What Went Well

- **The owner's re-run happened between the diagnosis and the build, and it changed the design.**
  Three of the four "no readable year" students recovered the moment the `exam_type` gate stopped
  skipping the SPM parser. Had part two been built to the approved analysis, it would have shipped
  a form question for a population of zero.
- **The document itself answered the question.** One screenshot of #140's certificate settled a
  diagnosis that no amount of code reading would have: `JMLAH`, `JIAN`, `AHAP`, `PERIKSAAN` — a
  left-edge crop, visible to a human in seconds and invisible to every query I had run.
- **Blast radius measured, not estimated, on all three engine changes.** The anchor can only fill a
  blank (proven by a test, not by argument); the SPM gate moves exactly two live documents, both of
  which currently state something false; the clarify fires for nobody today.
- **Every guard bite-checked** — the clipped anchor, the SPM gate, the superseded-slip filter, the
  gap wiring. Four disable-and-watch-it-fail cycles.

## What Went Wrong

**1. The approved analysis priced the wrong thing, and I wrote it.**
*Symptom:* #12 was quoted at 6.0h on a split of ~2h visibility + ~4h "ask the student", the second
half justified by four students whose slip had no readable year. By the time it was built, that
population was zero and the work took about an hour.
*Root cause:* the analysis treated "four slips have no readable year" as a property of the
documents. It was a property of **our reading of them** — three were being skipped by our own
`exam_type` gate and one by a two-character anchor. I priced a fix for a symptom without asking
what caused it, on a request whose whole subject was that very field.
*Fix:* before pricing "we cannot read X, so ask the human instead", establish WHY it cannot be
read. An unreadable-field population is a claim about the parser until proven otherwise. Added to
lessons.md.

**2. I proposed a banner; the right home was the merit score, and the owner said so.**
*Symptom:* my first design put an always-visible note under the verification tiles. The owner:
*"perhaps it should be near the merit score. Something like SPM 2023 (94.7) or 94.7 (SPM 2023)."*
*Root cause:* I reasoned from the failure mode (the signal is quiet, so make it loud) rather than
from the fact (the year is a property of the merit score, which is computed from those very
grades). A banner announces something *about* a number; a qualifier states what the number *is*.
*Fix:* no system change — this is judgement, and the owner's was better. Recorded in decisions.md
so the placement is not re-litigated as a styling preference later.

**3. Two clip-defeated anchors were found together and only one was fixed.**
*Symptom:* `JUMLAH MATA PELAJARAN` fails on the same clipped certificate as `PEPERIKSAAN`, silently
disabling the under-read guard. Shipped unfixed.
*Root cause:* not an oversight — a deliberate split, because the two have **opposite blast radii**.
The year anchor can only fill a blank; the count anchor can only start rejecting documents that
parse today. But the pair is easy to mistake for one change and "finish the job" on.
*Fix:* **TD-217** records both the fix and the reason it was held, so the next reader meets the
argument rather than the omission.

## Design Decisions

Logged in `docs/decisions.md`: the year belongs on the merit score rather than a banner; the
clarify is capped where its neighbour is not; the answer stays read text rather than a stored field.

## Numbers

- `pytest` **4326** scholarship + **1295** courses/reports · `jest` **1465** / 96 suites
- `next lint` **0 errors** · `tsc` no new errors · i18n **4534 × 3** (+4)
- **No migration.** Ledger reconciled against production: courses **70/70**, scholarship
  **146/146**, no gaps; `makemigrations --check` clean.
- Four commits, one deploy, both services SUCCESS on `9e80030`, smoke-tested.
- **Effort: ~3.0h against 6.0h quoted.** Not re-quoted — the owner's standing rule is that the
  close-out report states the actual and that is the official cost.

## Live outcome

- 2023: **8** applications · 2024: 13 · 2022: 3 · 2025 (expected): 84 · not an SPM document: 1.
  **24 of 109 did not sit SPM the year before this intake** — closer to one in four than the one in
  five the analysis told BrightPath.
- #140 (KIIRTHESWARY) sat SPM in **2023** and was invisible for it. Her certificate needs one
  cockpit Re-run to pick up the fix.
