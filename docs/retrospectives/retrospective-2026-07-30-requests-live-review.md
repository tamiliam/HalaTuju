# Retrospective — four rulings from using the Requests module live

**Date:** 2026-07-30 (wave 2)
**Commits:** `d3b5ddda`, `b78dc356`, `ee8d2de2`, merged at `ae5e6e6c`
**Trigger:** the owner opened requests #2 and #3 on the live site — after wave 1 deployed — and
used them. Everything below came from that, not from a plan.

---

## What Was Built

| Ruling | Change |
|---|---|
| A question open at quote time must stay answerable | `TRANSITIONS['answer']` widened to acceptance; `ask` stays a strict subset |
| "Answer needed" must not appear where answering is impossible | both surfaces derive the prompt from `requestActionsFor`; else neutral *Unanswered* |
| Screenshots must close when the quote is accepted | `OPEN_FOR_SHAPING` + `can_attach`, enforced at all three attachment endpoints |
| The quote belongs below the deliberation | block reordered |
| The margin is ours, not the organisation's | removed from page, email **and payload** |
| Paste/drag must work where a screenshot starts life | `lib/screenshotInput.ts` shared; create form wired; `SURFACES` guard |

The two window rulings collapsed into **one named principle** — *a request is open to shaping until
its quote is accepted* — held once per side (`org_requests.OPEN_FOR_SHAPING`,
`requestStatus.REQUEST_OPEN_FOR_SHAPING`) with a test on each side pinning them equal.

---

## What Went Well

- **Using the thing found what planning did not.** Every item here came from the owner clicking
  through two real requests. The sprint that built the deliberation had green tests, a retro and a
  CHANGELOG entry — and shipped with a permanently unanswerable question and an upload-only create
  form. **A feature is not verified until somebody uses it for its purpose.**
- **Two separate rulings turned out to be one rule.** Answering and attaching close at the same
  moment for the same reason. Naming that (rather than writing two status lists) means the next
  "…and what about X after acceptance?" question already has an answer.
- **The margin was checked before it was hidden.** Nothing in the codebase multiplies by
  `quote_margin_pct`, so removing the mention understates nothing. Had it been load-bearing, hiding
  it would have been the worse change — and that was a query, not an assumption.
- **Every guard was bite-checked**, and the one for the screenshot miss was broken in exactly the
  shape the original bug had: handlers stripped from the create form → 2 failures, both there.

---

## What Went Wrong

**1. The web build failed and only the API deployed. The owner found out by looking.**
*Symptom:* wave 1's push shipped the backend; the web build failed; the site looked unchanged while
new server code ran behind it. I had reported "both builds WORKING" and stopped watching.
*Root cause:* two `eslint-disable` comments naming `@typescript-eslint/no-var-requires` — a rule
this config never loads (it extends only `next/core-web-vitals`). `next build` **lints before it
emits**; `tsc --noEmit` and `jest` don't run ESLint at all. My gates were structurally blind to the
deploy gate. Aggravating factor: the repo carries ~6 pre-existing tsc errors in test files, so
grepping that output trains you to wave past real signal.
*System change:* **`npx next lint` (0 Errors) before any push that deploys web**, in `lessons.md`
and the project CLAUDE.md. A concurrent session independently hit the same wall the same day and
recorded the same rule — convergent evidence it belongs in the gate list. And: *"WORKING" is not an
outcome* — watch a build to a terminal state before reporting it.

**2. Paste/drag shipped to one of two surfaces, and the owner reported it twice.**
*Symptom:* the create form still accepted uploads only.
*Root cause:* my plan named `components/OrgRequestAttachments.tsx` and I built exactly that. I
searched for the attachments *component*, found one, and stopped — never asking **where else does
this input enter the system?** The two surfaces genuinely cannot share code (one uploads against an
existing id, the other stages files because no id exists yet), so no component was ever going to
cover both. Hours earlier I had written the lesson that a missing conversation is found by
*enumerating a module's verbs* — the same move on **surfaces** was available and I didn't make it.
*System change:* `screenshotInput.test.ts` walks a `SURFACES` list. A unit test of the shared helper
could not have caught this — the helper was correct, it had one caller — so the assertion has to be
a static check that no surface was forgotten.

**3. I bit an uncommitted file and deleted my own work.**
*Symptom:* `git checkout` after a bite-check reverted the create-form changes to the last commit,
losing four edits.
*Root cause:* the practice says **commit before biting**. I read past it because the change felt
small and the bite felt quick. `git checkout` is a restore only when what you want back is
committed; otherwise it is a delete.
*System change:* in `lessons.md`. Same family as the `git add -A` hazard on a shared tree — pointed
inward this time.

**4. Three of my own numbers were wrong today, all from reasoning instead of measuring.**
*Symptom:* test counts, the IC-lock population, and a defect count all needed correcting.
*Root cause:* describing a population from memory of a related query rather than running one at the
grain being claimed.
*System change:* the IC-lock figures are now recorded at **all three grains** in CLAUDE.md and
memory, because the ambiguity between "applications" and "students" is what produced the errors.

---

## Design Decisions

**`ask` stays narrower than `answer`, and a test pins it as a strict subset.** Replying to a
question raised before the quote completes the record; a *new* question after quoting would mean the
price was set against something nobody had raised. Two windows that look alike and must not be
aligned by a future tidy-up.

**The margin left the payload, not just the page.** A field the organisation must not see is a field
we must not send — which is the whole point of `OrgRequestOrgSerializer` being an allowlist. Hiding
it client-side would have put the fence in the wrong place.

**TD-201 and TD-202 were logged rather than built** (owner: *"4 can wait"*), with the analysis
recorded: share the AI's rationale, keep its hours private (the number is demonstrably unreliable —
24h for ~4h of work), keep `triage_note` private (the owner already has two shared channels and used
one). They must be ruled on together, because TD-201's first decision *is* TD-202's question.

---

## Numbers

| | |
|---|---|
| Migrations | **none** — ledger reconciled through `0136`, no gaps, `makemigrations --check` clean |
| Tests, **measured on the merged tree** | **5158 pytest** (129 subtests) · **80 jest suites / 1204 tests** |
| `next lint` | **0 Errors** — the gate whose absence failed the web build |
| i18n parity | 4337 ×3 |
| Builds spent | 3 for this bundle (1 failed) — against a two-deploy guideline |
| Guards bite-checked | 3 (answer window ×2 sides, screenshot surfaces) |
| Existing tests superseded deliberately | 6, each with the reason written in place |
| TD raised | TD-201, TD-202 (both deferred) |

---

## Carried Forward

- **TD-201 + TD-202** — the discussion model and what the org sees of our deliberation. One ruling.
- **TD-198** — no admin withdrawal from `awarded`; 47 applications sit there.
- The amber IC-flag copy and the ms/ta drafts (~20 `profile.ic*` keys plus `detail.unanswered`).
- Request #3's question stays unanswered by design — it is `approved`, so the window has closed. It
  now reads *Unanswered* rather than nagging. The reasoning lives in the quote note.
