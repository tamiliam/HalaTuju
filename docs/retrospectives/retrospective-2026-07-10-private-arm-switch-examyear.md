# Retrospective — Private/IPTS offer arms + course-switch note + SPM exam-year fix (2026-07-10)

A live-review round off two owner-flagged applicants: **#13** (a UTM SPACE offer reading a silent
Certain green) and **#8** (a 2025 SPM slip chipped "SPM 2026").

## What Was Built

1. **Private / continuing-education (IPTS) arm → disqualifying.** A public university's fee-paying
   continuing-education arm (UTM SPACE, UM CCE, …) prints the PARENT UA name, so the `ua_offer`
   genuineness anchor fired and the letter read `genuine`. The scorer (`genuineness/results_doc.py`,
   **MODEL_VERSION 1.6.0**) now vetoes it to `not_offer_letter` on the arm's own textual 'tell'
   (`Pendidikan Berterusan` / `(SPACE)` / `Continuing Education` / `Sdn Bhd`) → the −2 step, exactly as
   a standalone private college that misses the 20-UA list. The reporting-bonus **gate 3b** blocks the
   +1 "Tarikh" lift for the same arms. Net: fake(−2) + pathway(−1) = **Fail**. Activates on an offer
   re-run.

2. **Course-switch notification (any → any).** `offer_pathway_switch` compares the live offer with the
   most-recently superseded one; a genuine difference surfaces an always-visible blue **info banner**
   on the verdict card (survives the green-collapse) + a **Switched** doc chip. **Neutral by design:** a
   PUBLIC switch does NOT downgrade the band (a student may legitimately move STPM → matriculation → a
   UA diploma); a switch into a private arm is red via the genuineness veto, not the switch.

3. **SPM exam-year read fixed.** `academic_engine._slip_exam` grabbed the first `20xx` in the flattened
   OCR — the download timestamp at the top of a downloaded slip ("12/04/2026") — not the exam year.
   New anchored `_spm_exam_year` reads the year next to the exam label only; wired into the slip, cert,
   and Gemini-backfill readers. One live doc affected (#8), corrected from the stored OCR.

## What Went Well

- **Read the doc's OWN recorded state before theorising** (the standing lesson, applied). For #13 I
  queried the stored `authenticity`/`fields` before proposing; for #8 I pulled the stored `_debug_rows`
  (raw OCR) and it proved the OCR read "TAHUN 2025" correctly — the bug was 100% in the parser, not the
  read. No wrong root cause offered this time.
- **Cohort scan sized every change before shipping** — 3 private-arm offers found (only #13 mis-scored;
  #12/#64 already fake), exactly 1 exam-year doc (#8). Small, known blast radius.

## What Went Wrong

- **First cut of the private-arm fix built a NEW deterministic override in `pathway_engine`, when the
  owner wanted the EXISTING genuineness mechanism extended.** Symptom: I added `offer_private_arm` +
  an `offer_official_status` override. Root cause: I optimised for "self-correcting on deploy (no
  re-run)" and missed that the owner's mental model is the genuineness ladder (private → fake −2).
  Fix: reverted the override; put the veto in the scorer (the existing "not in UA list → fake" path),
  accepting the re-run as the activation step (the codebase's standard pattern for any genuineness
  change). Lesson below.
- **First cut of the switch note downgraded a public switch to Probable.** Symptom: a legit
  public → public switch dropped from Certain. Root cause: I put the note in the verdict `unresolved`
  list, which caps the band. Owner clarified a public switch is *acceptable* — inform, don't penalise.
  Fix: moved it out of the verdict entirely into an always-visible banner (the green-collapse hides
  `evidence`/`unresolved` on a green tile, so a banner outside that logic was the only way to flash it
  without downgrading).

## Design Decisions

- Private-arm disqualification lives in the **genuineness scorer** (durable, auditable record; re-run
  activates), not a read-time override. See decisions.md.
- The switch note is a **display-only banner**, carrying zero points; band impact comes solely from the
  genuineness veto + the existing pathway mismatch/not-official chip.

## Numbers

- **2332 scholarship pytest** (+11 private-arm/switch, +5 exam-year), **123 jest** (cockpit + i18n
  parity). No migration. MODEL_VERSION 1.5.0 → 1.6.0.
- Data: #13 flips to Fail on the next offer re-run; #8 exam year corrected to 2025 (data patch).
