# Retrospective — Check-1 Academic (results slip)

**Dates:** 2026-06-02 → 06-03 · **Branch:** `check1/academic` → `main` (`62339e9` + follow-up `177aed2`) · **Deployed:** yes (no migration)

## What Was Built
The results slip got the IC-style clinical treatment — *good feedback on every read*.
- **Band-word bug fix (the headline).** An SPM row prints the grade twice — a Malay word-band AND a letter (`MATEMATIK … CEMERLANG TINGGI … A`). Gemini glued the band words onto the subject, so `"MATEMATIK CEMERLANG TINGGI"` ≠ `"Matematik"` and **every** subject read as *missing* → "Entered 0 of 9". `academic_engine._split_band` strips a trailing band phrase (`cemerlang|kepujian|lulus|gagal` + optional `tinggi|tertinggi|atas`) **at read time**, with a band→letter map as a fallback for an unread grade. Read-time → existing prod slips self-corrected, and the officer verdict was fixed for free.
- **Clinical 3-check.** `student_slip_check` is the single source for **Name · Subjects · Results** (+ the exam year as a soft data point), consumed by both `ResultsSlipChecklist` and Cikgu Gopal so they can't disagree.
- **Specific Gopal advice.** Three verdict codes — `slip_name_mismatch` ("someone else's slip"), `slip_subjects_missing` ("add it on your Profile"), `slip_grade_mismatch` ("the slip is the official record — update your Profile") — with a `/profile` link for the fix-on-profile cases.

## Numbers
543 scholarship pytest (peak) · 231 jest · i18n 1811 · 2 deploys (initial + follow-up), 0 migrations.

## What Went Well
- The deterministic band-strip is independent of the model, so it's robust and made the prompt instruction redundant.
- Single-source `student_slip_check` kept the student checklist and Gopal perfectly aligned.
- Pulling the actual extracted JSON from prod (via Supabase MCP) turned a vague "it's wrong" into a precise root cause in one query.

## What Went Wrong
- **A prompt instruction silently produced an empty extraction.** *Symptom:* a re-uploaded slip came back with only the candidate name — `results: []`, `exam: ""`. *Root cause:* the only slip extracted under the new "drop the band words from the subject" prompt instruction returned an empty table; the instruction was both **redundant** (the deterministic strip already handles bands) and a **possible cause** of the empty read. *Fix:* reverted the prompt instruction and rely on the tested deterministic strip. *System change:* lesson recorded — *prefer deterministic post-processing over prompt-engineering when both can do the job; a prompt tweak can degrade extraction in ways unit tests won't catch.*
- **"Not checked yet" misrepresented an unreadable read.** A slip that extracted but read no subject rows showed "Not checked yet" (implying it was still coming). Fixed by distinguishing `pending` (extraction not run / rate-limited) from `unreadable` (ran, read nothing → "Couldn't read" + a clearer-copy nudge).

## Design Decisions
See `docs/decisions.md` → "Results slip is the authoritative grade record" and "Deterministic band-strip over prompt-engineering".

## Carried Forward
TD-081 residual (Income document Check-1).
