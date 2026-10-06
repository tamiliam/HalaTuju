# Retrospective — the reviewer stops quoting, and starts being heard

**Date:** 2026-07-30 (wave 3)
**Commits:** `7aee74dd` (TD-202), `d3592817` (the reviewer stops pricing)
**Trigger:** the owner filed request **#4** as an org_admin and reported *"no response from AI"*.

---

## What Was Built

**TD-202 — the reviewer's reasoning crosses the fence.** `ai_draft_note` + `ai_draft_model` +
`ai_draft_at` now reach the organisation, rendered as *How we read this* on the detail page
(requester-only; the super keeps the fuller block). `ai_draft_hours`, `triaged_kind`, `lane` and
`triage_note` stay withheld, each for a distinct reason recorded in the serializer docstring.

**The reviewer is no longer asked to price.** `_build_review_prompt` drops `estimated_hours` and
says why; `_parse_draft` **discards** a volunteered figure rather than storing it. The owner panel
stops rendering the column. No migration — the column stays so historical drafts keep their values.

---

## What Went Well

- **The bug report was a measurement, not an impression.** *"No response from AI"* looked like a
  broken integration. The database said the reviewer answered in **21 seconds** with an accurate
  reading of the bug — into a room the requester was not in. Querying before diagnosing turned a
  suspected outage into a visibility ruling. Same discipline that separated "no wallet" (benign)
  from "no membership" (severe) a day earlier.
- **The three `ai_draft_*` fields were argued separately and ended up in two places.** Bundling them
  as "the AI stuff" would have produced either a leak or a pointless fence. Sharing the *reasoning*
  is the accountability fix; sharing the *hours* would have published an unreliable number as the
  basis of a price.
- **The estimate claim was evidenced, not asserted.** "The AI is bad at estimates" became: 24h for a
  request whose engine is in `referrals.py`, 8h for one whose mailer is in `emails.py`. Both
  checkable in a minute, which is the same standard now expected of the engineer's estimates.
- **Every superseded test was taught to assert the inverse.** Four tests pinned "the hours are
  stored"; all four now pin "the hours did not land". A rule that stops being checked is a rule that
  comes back.

---

## What Went Wrong

**1. A guard I wrote the previous day had to be narrowed on its second day alive.**
*Symptom:* `test_the_org_NEVER_sees_the_steer_or_the_ai_draft` failed the moment the owner ruled.
*Root cause:* I wrote it as *"no `ai_draft_*` reaches the org"* when the thing worth protecting was
narrower — the owner's private judgement and the untrustworthy number. The blanket version encoded a
convenience, not the actual invariant.
*System change:* narrowed to the steer and the hours, renamed, with the reason in place, plus a
positive twin (`test_the_ai_split_is_exact`) so the rule is pinned from both directions. **When a
guard says "never any of this family", check whether the family is really uniform** — three fields
sharing a prefix are not thereby one policy.

**2. I described TD-202 as "sprint territory" when it was four files.**
*Symptom:* the owner had to ask *"is this TD-201 or a minor fix?"*.
*Root cause:* I conflated the weight of the **decision** with the size of the **work**. The ruling
was genuinely the owner's and genuinely consequential; the code was a serializer line and a render
block.
*System change:* say which of the two is large. "Small change, but it needs your ruling first" is a
sentence I should have used and didn't.

**3. The workflow's manual labour was visible for days and I never named it.**
*Symptom:* the owner described it back to me — analysis → paste into `triage_note` → re-run the AI →
type a quote — and proposed the fix themselves.
*Root cause:* I kept optimising inside the loop (a better steer, a better estimate) without asking
whether the loop was the right shape. The re-run adds nothing once the code has been read; the AI
agrees rather than verifies.
*System change:* the agreed model is recorded in `decisions.md`. Step 3 — a way to post a
**statement** to the requester, not only a question — is the remaining gap and is TD-201-shaped.

---

## Design Decisions

**The reasoning is shared; the estimate is not.** Recorded in `decisions.md` and in the serializer
docstring, with the caveat accepted knowingly: `ai_draft_note` is free-form prose and *may* state an
hours figure even though the field is withheld. Negotiation optics, not correctness — the owner sets
the final quote. If it bites, the fix is a line in the review prompt, not a filter.

**A prompt cannot bind a model, so the parser is the enforcement.** Asking it not to estimate is
advisory; dropping a volunteered figure is not. Guarding only the prompt would have left the number
one chatty response away from returning.

**TD-201 inherits TD-202's rule** rather than re-deciding it: a comment stream's visibility column
splits the same way — shared reasoning, private judgement.

---

## Numbers

| | |
|---|---|
| Migrations | **none in this wave**; prod ledger reconciled — scholarship **137/137**, courses **67/67** |
| Tests, measured at close | **5182 pytest** (129 subtests) · **81 jest suites / 1212 tests** · `next lint` **0 errors** · i18n **4340 ×3** |
| Guards bite-checked | the AI split (all three fire when the hours are let through) |
| Existing tests superseded deliberately | 5, each now asserting the inverse |
| TD closed | **TD-202** |

---

## Carried Forward

- **TD-201** — the thread is a register, not a discussion. Now also the home for *step 3*: a way to
  post a **conclusion** to the requester, which is what removes the owner's remaining manual work.
- **TD-198** — no admin withdrawal from `awarded`; 47 applications sit there.
- Tamil first drafts for review: `dropZone`, `unanswered`, `aiReading`, `aiReadingNote`, and the
  ~20 `profile.ic*` keys.
- The create form's paste has **no rendered test** — the shared handler is identical to the panel's,
  which is an argument, not evidence.
