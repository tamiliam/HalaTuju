# Retrospective — TD-201: the Requests thread becomes a discussion (2026-07-31)

## What Was Built

`OrgRequest.clarifications` — a JSONField of `{question, answer}` pairs — became
`OrgRequestComment`, a table. The load-bearing idea is that **a question is a comment awaiting a
reply**, which is what makes this ONE stream rather than a comment log sitting beside a question
log. Everything else follows from that.

- **Model + migrations.** `0138` (DDL, RLS, `service_role` policy) and `0139` (data). Both applied
  migrate-first to production and verified **per request**, not in aggregate — 2 requests carried
  threads, 3 comments moved, all 7 requests reconciled.
- **`visibility`, from the first migration.** `internal` is the owner's private judgement;
  `shared` is the conversation. Retrofitting this would have meant a second migration and a window
  in which everything written was shared.
- **The statement verb.** `comment()` — the thing the module never had. A conclusion can now reach
  the requester as itself instead of as a quote note.
- **Three windows**, each with its own reason, now visible in the UI: comments to terminal,
  answering and attaching to acceptance, a new question to the quote.
- **`_settle_open_questions`** — the requester speaking settles what stood before it.
- **Frontend**: one stream with authorship, an internal badge, a post box, a super-only internal
  toggle; en/ms/ta. **17 rendered tests.**

## What Went Well

- **Bite-checking caught nothing, which is the point.** Five guards broken, each failed as
  designed, each restored. The row filter failed *two* tests — serializer and endpoint — which is
  the belt-and-braces working.
- **Verifying production before proposing.** Reading the actual thread text off prod turned an
  abstract deploy plan into "2 requests, 3 comments, here is your own stuck question". The owner
  approved from a before/after built on their real data rather than a description.
- **The migration kept its source.** `clarifications` survives, so the copy stayed checkable and
  the whole change stayed reversible. Cost: one follow-up. Worth it.
- **The rendered test earned itself immediately** — it is the artefact that would have caught the
  paste bug from earlier in the same sprint.

## What Went Wrong

**1. I bit a guard before committing, and `git checkout` ate the fix — twice in one sprint.**
- *Symptom:* after bite-checking `_settle_open_questions`, `git checkout org_requests.py` restored
  to the last commit, which did not contain the fix. I lost it and re-typed it by hand.
- *Root cause:* the sprint's own rule is "commit BEFORE biting". I followed it for the first five
  bites (all against committed code) and then broke it for the sixth, because the sixth arose from
  live feedback mid-flow rather than from the plan. The rule was attached to *the bite-check step*
  in my head, not to *the act of reverting*.
- *System change:* the rule belongs on the revert, not the ritual — **never `git checkout <path>`
  while that path has uncommitted work you want.** `git stash` first, or commit first. Added to
  `lessons.md`, phrased around the destructive command rather than the workflow step.

**2. The two-box design created a state that could never clear.**
- *Symptom:* the owner answered a question in the comment box on an approved request. The question
  kept reading "Unanswered" directly above its own answer, and the owner's badge stayed lit.
- *Root cause:* I built two boxes with different windows (reply closes at acceptance, comment runs
  to terminal) and gave only one of them the power to clear `awaiting_reply`. Past acceptance the
  comment box is the only box — so the flag became unclearable by construction. I reasoned about
  each window separately and never asked what happens where they *disagree*.
- *System change:* when two affordances write the same state through different windows, test the
  window where only ONE of them is available — that intersection is where a permanent state hides.
  Five tests now pin it, including the endpoint-level badge consequence.

**3. Three of my four cases in the first cut of the frontend test used jest-dom matchers this
project does not install.**
- *Symptom:* 17 tests failed with `toBeInTheDocument is not a function`.
- *Root cause:* I wrote the assertions from habit rather than from the neighbouring test files.
  `@testing-library/jest-dom` is absent; the house style is `toBeTruthy()`/`toBeNull()`.
- *System change:* minor, but the general form is real — **read a sibling test's assertions before
  writing new ones in an unfamiliar repo area**, the same way we read a sibling migration for
  column types. Cost was one cheap round trip, so this stays a note rather than a lesson.

## Design Decisions

Logged in `docs/decisions.md`:
1. The visibility filter is a ROW filter and lives in the service, not the serializer.
2. Three windows, deliberately different, held apart on purpose.
3. An org comment settles the questions before it.
4. The data migration keeps its source.

## Numbers

| | |
|---|---|
| pytest | **5211** (+29 this sprint) |
| jest | **1234** (+22) |
| `next lint` | 0 errors |
| Files touched | 22 (budget 40) |
| Migrations | 2 (`0138` DDL, `0139` data) — applied migrate-first, verified per request |
| Guards bite-checked | 5, each confirmed to fail |
| Production rows moved | 3 comments across 2 requests; 0 deleted |
| Deploys | 2 (the feature; then the settle fix, api only) |

## Carried

- **`clarifications` is still populated** on requests 2 and 3. Nothing reads it. Dropping the
  column is its own small change.
- **Tamil first drafts** for the new `detail.author.*`, `commentLabel`, `commentPlaceholder`,
  `commentSend`, `commentInternal`, `commentInternalHint`, `noComments`, `internalBadge`.
- **TD-198** (no admin withdrawal from `awarded`; 47 sit there) — unchanged, owner's call.
- **The "UI asserts what nothing checks" cluster reached FIVE** with the Unanswered label. It is
  tracked in `consolidation-log.md` and wants a guardrail, not a sixth fix.
