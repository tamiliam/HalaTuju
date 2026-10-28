# Retrospective — Income declarations (#374), the hotfix, and its follow-ups (2026-10-27 → 2026-10-28)

Live: `afaf23cd` … `8a11d41e` (the sprint and five review rounds), hotfix `c58b7237` + the lead's VERDICT bump
`00f1f7eb` (api-01164-sfb). Follow-ups: this close's commit (govt-letterhead tightening, the approver prompt).
Built in the worktree `td404-name-forms`.

## What Was Built

- **#374's cause, fixed at the scorer.** A self-filled "Borang Pengesahan Pendapatan" read `genuine` / `govt` 0.79
  because the form's own sector field ("Kumpulan Perkhidmatan") counted as a civil-service marker. `govt` now
  needs a real government payslip or pension-statement layout (salary_doc 1.2.0), and declaration forms are
  recognised in either income slot (`genuineness/declaration_doc.py`).
- **The approver rule (owner rulings 1A–4A + the chop ruling).** Every informal income document — support
  letters, informal payslips, declaration forms — counts only when approved; a declared amount is never Certain
  (1A); bank statements naming a known bank are exempt (4A); a stamp alone approves with a header (3A).
- **The approval is read off the IMAGE** (one multimodal call; a PDF's pages stacked so the last page is seen),
  never the OCR text. A failed read on our side is "still checking" for 72 hours, then checked by eye.
- **Not-yet-checked documents** (read before the rule) never count and never blame: the gate says "still
  checking", Check 2 waits, the hourly sweep re-reads them.
- **The hotfix** (live re-read): a stamp with a named / titled approver needs no letterhead; government
  payslips and pension statements (JHEV, DBP) are not informal; a bank may be named on the letterhead.

## What Went Well

- **Review caught two production-grade defects before deploy** — the approval read from OCR text and the
  dropped JPA pension statements — each pinned by the reviewer's own probe as a test.
- **The live impact queries were written before deploy** and the lead ran them, so the hotfix's damage was
  measured row by row within hours, not discovered by families.
- **Every change bitten** — around eighty mutations across seven rounds; the silent ones became sharper tests.

## What Went Wrong

1. **The header requirement failed genuinely approved village forms in production (7 not-submitted students
   blocked for about two hours).** A village form has no letterhead: its stamp, with the Ketua Kampung or
   Pengerusi JKKK named, IS the issuing authority. *Root cause:* the rule was specified from ONE document (#374)
   and never validated against real APPROVED forms before deploy — every test was synthetic, and the only real
   sample checked (the eval payslips) tested the scorer, not the approver rule. *System change:* (a) run the
   after-deploy "exact affected list" query on the re-read results BEFORE anyone tells families anything;
   (b) a new document rule is validated pre-deploy by a dry run over a sample of real APPROVED documents'
   stored fields (how many would it refuse, and are they really unapproved?). Both recorded as lessons.
2. **The approval was first asked of the OCR text** (caught in review round 2). Real forms print "Cop dan
   tandatangan" whether the box is stamped or empty, and a signature has no text — a text read cannot see ink.
   *Root cause:* the field was added to the existing text extraction because it was the cheapest seam, without
   asking what the text CAN show. *System change:* a separate image read, with the prompt naming the empty-box
   and printed-label traps.
3. **JPA pension statements were dropped from `govt`** (caught in review). Removing "PERKHIDMATAN AWAM" to stop
   #374 also removed the only marker the pension statements carried. *Root cause:* a marker was removed without
   re-scoring the real corpus that marker had been carrying. *System change:* every scorer change re-scores the
   99 eval payslips old-vs-new and lists every family that moves (done from round 1 of the review on).
4. **A shared-worktree gate run mixed in-progress edits.** A gate was run while edits for the next round were
   already on disk, so its result described neither commit. *Root cause:* one worktree served two steps at once.
   *System change:* commit (or stash by tag) before a gate run; report the gate against a SHA.

## Review (sprint-close step 4b)

Five review rounds by the lead (pension statements / sweep / chop; image read / pension layout; last page /
retry; known banks; the hotfix's follow-ups), plus the owner's rulings 1A, 2A, 3A, 4A and the chop ruling.

## Numbers

- API 9,098 → 9,370 at close (3 skipped); web 4,617.
- Genuineness `MODEL_VERSION` 1.13.0 → 1.16.0 (the approver prompt); `VERDICT_ENGINE_VERSION` 2026-10-27.6 → .7
  (hotfix) → .8 (the govt-letterhead tightening can move a band back down).
- Cost: one extra Gemini image call per informal income document (support letter / informal payslip /
  declaration); formal payslips, bank statements naming a known bank and EPF cost nothing extra.
