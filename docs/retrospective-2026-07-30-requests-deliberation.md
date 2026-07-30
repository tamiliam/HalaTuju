# Retrospective — the Requests module gains a conversation

**Date:** 2026-07-30
**Commits:** `f5e81b5d` (feature), `e5a903e2` (records)
**Trigger:** the owner reviewed one live request — #2, *"a link here to add sponsors will be
helpful"* — and raised three complaints from the experience of actually using the screen.

---

## What Was Built

**A. Screenshots became usable** (`components/OrgRequestAttachments.tsx`, frontend only).
Thumbnails now open in the existing `DocViewer`, with an open-in-new-tab link beside each.
Paste (`onPaste`) and drag-drop (`onDrop`) join upload, all through the one existing
`uploadOrgRequestAttachment` path. A pasted image carries no filename, so one is generated
(`screenshot-<timestamp>.png`) to keep the caption and stored `original_filename` meaningful.

**B. The AI draft states its model** — `ai_draft_model` was already on the model, the serializer
*and* the TypeScript type. Purely a matter of drawing it.

**C. One deliberation thread, authored** (`apps/scholarship/org_requests.py`).
`clarifications` entries gained `asked_by: 'ai' | 'owner'`, absent meaning `'ai'` — so existing rows
read correctly with no migration (`clarifications` is a `JSONField`). New `ask_question(req, admin,
question)`, a super-only `POST admin/scholarship/requests/<pk>/ask/`, and `TRANSITIONS['ask']` so a
quoted or terminal request cannot gain new questions. `MAX_OPEN_QUESTIONS` room is now computed from
**AI-asked** open questions only: that cap exists to stop the machine burying a requester, not to
ration the owner.

**D. The owner's reasoning reaches the AI** — the review prompt now carries the attributed thread,
unanswered owner questions, and `triage_note` as an explicit steer. Pinned by a test that the
org-facing serializer carries neither `triage_note` nor `ai_draft_*`.

**E. The AI sees the screenshots** — `contracts._gemini_generate(prompt, model, images=None)`, with
the default keeping every existing caller byte-identical. Replaces the *"N image(s) attached"* line,
which on a request that is entirely about a screen was close to useless.

---

## What Went Well

- **Investigation cut the sprint roughly in half before it started.** Two of the three complaints
  needed no backend at all: `download_url` was already a signed URL to the full-size original (the
  thumbnail *was* the image, cropped), and `ai_draft_model` was already on the payload. The org
  serializer's own docstring described owner questions — *"the questions the AI/owner chose to flow
  to them"* — as a thing it was designed for. Reading before planning turned three features into
  one feature and two renderings.
- **Every new capability reused an existing seam.** One `_gemini_generate`, one upload path, one
  notification email, one `clarifications` array, one `answer_clarification(req, answer, index)`
  that already answers by index. The requester side needed no change whatsoever.
- **The owner's own example was the specification.** *Adding a sponsor directly would bypass the
  terms and consent — what's needed is an invite.* That reasoning had nowhere to live: `triage_note`
  is private and the AI never read it. Designing to a real judgement beat designing to "add a
  comment box".
- **Four guards, all bite-checked** — broken, watched fail, restored, with the commit made first.

---

## What Went Wrong

**1. A concurrent agent's `git add -A` swept unfinished frontend work into a commit and pushed it.**
*Symptom:* commit `70566e55` carried a half-finished state of this sprint's frontend that was not
ready to deploy. Nothing reached production — the web build was CANCELLED — but that was luck, not
control.
*Root cause:* two agents working the same checkout without worktree isolation, and `-A` staging
whatever it finds. The workspace rule already warns about this; it was not applied to *another*
agent's commands, only to mine.
*System change:* `parallel-work-isolation.md` exists for exactly this. When a second agent is known
to be active in the same repo (the owner said so at the time), the isolation step is not optional.
Recorded in `lessons.md`.

**2. Two existing tests failed and had to be reasoned about rather than fixed.**
*Symptom:* a prompt test pinning `"ATTACHMENTS: N image(s)"`, and `test_refuses_from_invalid_statuses`
which derives its cases from `TRANSITIONS`.
*Root cause:* neither was a defect. The first pinned a line the images legitimately replaced; the
second correctly demanded to be taught the new `ask` action.
*System change:* both were updated **deliberately with the reason recorded in each**, and the
principle is now in `lessons.md`: *a guard failing when you extend a table IS the guard working —
teach it, never trim it.* The failure mode to avoid is deleting the assertion to get green.

**3. The full jest run reported failures that were not failures.**
*Symptom:* two sponsor suites failed, then the run died with exit 253.
*Root cause:* worker contention and OOM on an 8 GB box — not test logic. The output is
indistinguishable from real failures at a glance, which is the dangerous part.
*System change:* `--maxWorkers=2` is the standing invocation for the full suite on this machine
(79 suites / 1184 tests pass). In `lessons.md`.

---

## Design Decisions

Both logged in `decisions.md`:

**One authored thread, not two channels.** Owner and AI questions share `clarifications`, each
tagged with who asked. Reuses the storage, endpoint shape and notification email — but it makes the
`asked_by` badge **load-bearing**: with one thread, provenance exists only because it is rendered. A
separate owner-comments field would have carried provenance structurally and cost a migration plus a
second notification path.

**Send the screenshots, and the owner's steer.** Multimodal input raises token cost, bounded by
≤5 images × `AI_RUN_CAP = 3` and metered through the existing `usage_context(source=
'requests_triage')`. Revisit if the metered cost turns out to be material — the owner is
cost-conscious, so this is watched on the first live runs rather than assumed fine.

---

## Numbers

| | |
|---|---|
| Migrations | none (`clarifications` is a `JSONField`) |
| Tests at close | **5143 pytest** (incl. 121 subtests) · **1184 jest** / 79 suites · i18n parity 4333 ×3 |
| Production migration ledger | reconciled through `0136`, no gaps (checked 30 Jul) |
| Bite-checked guards | 4 |
| Existing tests deliberately updated | 2, each with the reason recorded in place |
| i18n | new keys in all three locales, parity equal |

---

## Carried Forward

- The amber IC-flag copy and ~20 `profile.ic*` ms/ta first drafts are **unreviewed by the owner**.
- Application **94** is currently the only record that renders the IC flag panel.
- **TD-198** (admin award withdrawal) awaits an owner decision.
- Manual verification on request **#2** is still owed after deploy: paste a screenshot; click a
  thumbnail; check the draft names its model; ask a question and confirm it appears tagged as the
  owner's and emails the requester; add a triage note and re-run, confirming the rationale engages
  with the steer and the screenshots rather than repeating itself.
