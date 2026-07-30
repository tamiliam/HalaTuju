# Retrospective — the awarded sign-off, and a reason nobody could read

**Date:** 2026-07-30
**Commit:** `a1552464`
**Trigger:** the owner sent two screenshots — applications #27 and #118 — and asked why the
sign-off rendered differently. It was not a rendering quirk. It was two separate defects that
happened to surface in the same panel.

---

## What Was Built

**1. `awarded` restored to the QC-accepted set.**
The lifecycle is `recommended → awarded → active → maintenance → closed`. The post-award sprints
inserted `awarded` in the *middle*, and three inline conditions in
`app/admin/scholarship/[id]/page.tsx` enumerated the states either side of it. Replaced with a
single named export in `lib/officerCockpit.ts`:

```ts
export const QC_ACCEPTED_STATES = ['recommended', 'awarded', 'active', 'maintenance', 'closed']
export function isQcAccepted(status: string): boolean
```

**2. The QC override trail, given a surface.**
`qc_override_by` / `_at` / `_reason` were write-only in `serializers_admin.py` — stored since the V5
QC floor and rendered nowhere. Added to the payload (plus `qc_override_by_name`) and rendered by a
module-scope `QcOverrideNote` in amber. `ai_draft_model` was in the same condition and is now shown.

**3. A guard on the case that is *not* a bug.**
`test_reject_status_sets.py` pins that `awarded` stays *out* of the reject sets.

**4. Two payload guards instead of a snapshot.**
`test_admin_detail_payload.py` — an allowlist-by-construction check and a role-invariance check.

---

## What Went Well

- **The screenshot was the better bug report.** Two records side by side isolated the variable
  faster than reading the component would have. The owner comparing two live records is a
  diagnostic the test suite cannot replicate.
- **`QUERYING_LOCKED_STATES` settled intent without a conversation.** The same file already listed
  `awarded` correctly in a neighbouring constant. That asymmetry is what distinguished *staleness*
  from *a decision somebody made* — and it meant the fix needed no ruling.
- **The lookalike was checked before being "fixed".** `awarded` is absent from the reject sets too.
  Sweeping it in would have been consistent and wrong. Asking produced a product rule:
  *"They cannot be rejected directly. It should only happen after a proper withdrawal of the
  award."*
- **Test-shape argued on merit.** A 154-key snapshot was proposed and declined with a reason —
  see Design Decisions.

---

## What Went Wrong

**1. Two false-positive findings were reported to the owner as evidence.**
*Symptom:* #27 and #118 were cited as cases where OCR mis-blamed the student on name matching. The
owner checked and both read "Verified · Exact". They were right.
*Root cause:* the claim came from a SQL approximation of `name_match` written in the query rather
than from calling the function. The real matcher has a **glued-token path** for OCR space-splits
(`SITILAILA` vs `SITI LAILA`) which the SQL had no equivalent of, so it manufactured mismatches
that the product does not have.
*System change:* recorded in `lessons.md` — **never re-implement a matcher in SQL to measure its
output.** Call it over the rows, or query the stored result the real code wrote. This was the
second time in two days that reconstructing behaviour instead of reading it produced a wrong
number for the owner.

**2. A defect count was stated before it was scoped.**
*Symptom:* the "47 of 143" figure was initially reasoned about at the wrong grain — a repeat of the
application-vs-student confusion from the IC lock sprint the day before.
*Root cause:* the same misjudgement recurring inside 24 hours: describing a population from memory
of a related query rather than running one at the grain being claimed.
*System change:* any number that reaches the owner or a document is measured at a stated grain in
the same breath. Applied in this sprint's close — the lock figures are now recorded with all three
grains spelled out, because the ambiguity is what caused the error twice.

**3. A "stored but never displayed" defect was found by accident, not by looking.**
*Symptom:* `qc_override_reason` had been dead since V5 shipped. Nothing flagged it. It surfaced only
because an unrelated screenshot led into the same panel.
*Root cause:* no check exists that asks "which persisted fields does no surface read?". The write
side has tests; the *absence* of a read has nothing to fail.
*System change:* logged as a pattern in `lessons.md` after a third instance the same week (the
hard-coded padlock, `qc_override_reason`, `ai_draft_model`). Candidate future guard: a fixture
diffing model fields against serializer fields against grep hits in the web app.

---

## Design Decisions

**No key-set snapshot on `AdminApplicationDetailSerializer`** (owner asked whether one was
warranted; logged in `decisions.md`). The sponsor and finance snapshots exist because those payloads
cross an *audience boundary* — the risk they manage is a field reaching someone who should not see
it. This payload is the back office reading its own applicant, already org-fenced with its own CI
guard. A 154-key snapshot fails on every legitimate addition, the remedy is to paste the key in, and
by the third time nobody reads what they are blessing — the appearance of review without the
friction. Two narrower guards were written instead: allowlist-by-construction, and role-invariance
(pinning the owner's ruling that *"it should be open to anyone who has access to the relevant
pages"* as a decision rather than an accident).

**`awarded` stays unrejectable, and that is now load-bearing.** TD-198 records the consequence: no
admin route out of `awarded` once the student has been emailed. Deliberately left open — it moves
money back to a sponsor and retracts a promise, so it is the owner's call, not a gap to quietly
close.

---

## Numbers

| | |
|---|---|
| Production records with a missing sign-off | 47 of 143 |
| Files touched | 12 |
| Migrations | none |
| Tests at close | 5079 pytest · 1180 jest · i18n parity 4322 ×3 |
| New test files | 2 (`test_reject_status_sets.py`, `test_admin_detail_payload.py`) |
| Bite-checked guards | both fixes, plus the reject-set guard |
| TD raised | TD-198 |
