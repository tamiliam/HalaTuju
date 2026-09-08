# Retrospective — the payment run reads as cards on a phone

**Date:** 2026-09-08
**Worktree:** `.worktrees/pay-cards`, branch `feat/payment-phone-cards`
**Migration:** none. Web only.

---

## What this is

The first of the phone card layouts the console-layout sprint deliberately did **not** do. That
sprint made every table safe on a phone — it scrolls, keeps its shape, and says when there is more
to the right. Safe is not the same as good: a payment run is still an eight-column table you drag
sideways on a screen you are probably using to check something quickly.

## The process, and why it was the right one here

The owner asked what "phone card layouts" meant. Rather than describe it, I **drew it** — the real
row from run PR-2026-09-01-03, at phone width, with every column mapped to where it would land —
and asked one question. He approved the shape and answered the question. Then I built it.

That order mattered because the design decision is not a layout decision. A card cannot hold seven
columns, so **something must lead and something must drop**, and which facts lead is a judgement
about the work, not about CSS. On this screen: the name (recognition), the include toggle (the
reason you opened a draft run), and the amount to pay (the decision figure).

## The question, and the owner's answer

On a draft run the amount is an editable box. On a phone that is a **money field a thumb can
graze**, on the screen people use to look rather than to work.

> *"I am OK with your suggestion. Desktop is the preferred option. Phone is for quick checking."*

So the card **shows** the amount and **says where to change it** — it does not render a control
that silently does nothing, which would be the "UI asserts what nothing checks" defect wearing a
different hat. The **include toggle stays live**, because that is the reason to open a draft run on
a phone at all.

## Two things the card does BETTER than the table

Worth recording, because a phone layout is usually a compromise and these are not:

- **An excluded student's reason shows in full.** In the table it lives in a small box off to the
  right — past the fold on a phone, and easy to skim past on a desktop.
- **The not-activated warning stays welded to the e-wallet ID.** It is the one fact on the row that
  stops a payment, so it travels with the thing it is about rather than becoming a column.

## What went wrong

**I filed this as a small change, and it is not one.** `wat_lint` flagged it: the lane's own
boundary says *"anything needing design, or touching money / consent / auth / PII → stop, this is a
sprint"*. This needed design (I drew it and sought approval) and it is the payment screen. Nothing
about the work was wrong — it was planned, drawn, approved, tested and bite-checked — but the
**classification** was, and a money change sitting in the small-change queue is exactly the drift
that queue exists to surface.

*Root cause:* I reached for the lane because the diff was small (4 files). Size is only one of the
lane's four tests, and it is the one that says least.
*Prevention:* the linter already catches it, and it did. What was missing was me reading the
boundary before choosing the lane rather than after — the workflow's step 1 is called "Classify
first" for this reason.

## Numbers

| Gate | Result |
|------|--------|
| jest | **1857** (+8) |
| `next lint` | 0 errors |
| `tsc --noEmit` | 24 (baseline) |
| i18n | **4889 × 3** (+2 keys; ms/ta first drafts) |
| `next build` | compiled successfully |
| pytest | not run — no Python changed |

Two bite-checks, both on the parts that would be silently wrong rather than visibly broken: making
the amount editable on a phone fails the money test, and dropping the not-activated chip fails the
warning test.

## Next

The remaining lists — applications, reviewers, sponsors, sources, staff, billing — each need the
same treatment and the same conversation, one screen at a time. The pattern is now established
twice (Students, and this), so the next one is a drawing and an approval, not a design problem.
