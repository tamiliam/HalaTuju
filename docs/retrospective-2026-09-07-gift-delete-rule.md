# Retrospective — students hold a gift, not intake years (2026-09-07)

**Branch** `feat/gift-delete-rule`, worktree `.worktrees/gift-delete-rule`, based on `origin/main`
at `5a677f91`. **NO migration.** api + web.

---

## What was built

The gift-delete rule, reversed on the owner's ruling.

Since the gift setup flow shipped earlier the same day, `programme_delete_blocker` checked **intake
years first**. A gift with a single year could not be deleted, and there is no way to delete a year
on its own — so a gift created by mistake and given one round was permanent. I logged that as
TD-232, put two options to the owner (reword the refusal / build a year-delete), and they chose the
wording fix. They then read the ticket back and rejected the rule underneath both options:

> *"I don't [want] the ability to delete a gift programme that has students, and not merely intake
> years."*

So:

- **An intake year is no longer a blocker.** The list is applications, benefactors, money, payment
  runs. Students are the line.
- **An empty year is deleted WITH the gift**, in one `transaction.atomic()`, years first. The model
  is untouched — `ScholarshipCohort.programme` stays `PROTECT`.
- **The applications query reaches through the cohort**: `Q(programme=p) | Q(cohort__programme=p)`.
- **The dialog says the years go and names the count** (`deleteYears`, en/ms/ta), shown only when
  there is at least one.
- **The `hasIntakeYears` string and its guard are deleted.**

## What went well

- **The one-function-two-readers shape held under a rule change.** The blocker is read by the list
  row and by the delete handler. Changing what holds a gift was one edit to one tuple; the disabled
  button, the visible reason and the server's refusal all moved together, and the test that welds
  them (`test_what_the_row_SAYS_and_what_the_delete_REFUSES_are_the_same_answer`) needed only a new
  fixture. That is the design paying for itself one day after it was written.
- **The model answered the safety question again.** "Is it safe to delete the years here?" was
  answerable by reading `on_delete`: exactly ONE relation points at `ScholarshipCohort`
  (`ScholarshipApplication.cohort`, PROTECT), so a year with no application has nothing behind it.
  No guessing, no owner ruling needed for the mechanics — only for the policy.
- **Three bite-checks, each injection verified as landed first.** Restoring `has_intake_years`
  failed four tests; dropping the `cohort__programme` arm failed exactly the one written for it;
  disabling the dialog's year note failed exactly one. No silent injections.

## What went wrong

**1. I framed the owner's choice around my own mistake and both options preserved it.**

*What happened.* I found the trap, wrote TD-232, and asked the owner to choose between rewording
the refusal and building a year-delete. They chose the wording; I shipped it; they then said it was
not what they wanted and named the real rule. A day of work — the reworded copy in three languages,
a source-scanning guard, a bite-check that caught the guard being dead — is now deleted.

*Why.* Both options took "an intake year blocks deletion" as a fixed fact of the system. It was my
own decision from earlier the same day, made by reading `on_delete=PROTECT` off the model and
treating every protected relation as equivalent. They are not equivalent: an application is a
person's submission, a year is rules somebody typed a minute ago. **The ticket said so in its own
words** — it argued that the trap "bites on a test gift, not real data" and that a year is not
history — and I read those as reasons the ticket was low priority rather than as the finding.

*What prevents recurrence.* A lesson, and it is specific: **before putting options to the owner,
state the rule the options share and ask whether it survives.** Two options that differ only inside
one assumption are one option.

**2. A careful guard was deleted the day after it was written.**

*What happened.* `deleteRefusalCopy.test.ts` was written as a PAIRING — read the code for the
year-delete capability, and only then assert the copy — precisely so it would retire itself rather
than forbid an honest sentence for ever. It did not survive the refusal itself being removed.

*Why.* It guarded a STRING. The string was a symptom of the rule; the rule changed; the string went.
A guard is only as durable as the thing it names, and a phrase is the least durable thing in a
product.

*What prevents recurrence.* The claim is re-homed as behaviour: a rendered test asserting Delete
stays LIVE for a gift with years and no students, and a backend test asserting the same of the
served row. Both fail if anybody re-adds `has_intake_years`. Lesson recorded: **write the guard
against the behaviour unless the string IS the deliverable.**

**3. Removing a check silently promoted a latent bug in a neighbour.**

*What happened.* With the years no longer blocking, `filter(programme=p)` became the only thing
standing between "delete this gift" and its students — and that column is **set-once**, copied from
the cohort at first save and never rewritten. A cohort moved between gifts leaves its applications
pointing at the old gift, so the new gift would have read empty while its own round held people,
and `PROTECT` would have refused only after the confirmation phrase was typed out in full.

*Why.* I changed the rule and audited the rule, not its neighbours. The stale column was harmless
while the year check ran first, so nothing had ever exercised it.

*What prevents recurrence.* The query reaches through the relation as well as the column, with a
test that reproduces the stale column via `.update()`. Lesson recorded: **when you remove a check,
ask which other check it was silently protecting.**

## Design decisions

Both are in `docs/decisions.md`:

- *An intake year does not hold a gift; a student does* — why the exception lives in the handler
  rather than in a `CASCADE` on the model, and why the blocker had to widen as the price of it.
- *The refusal-copy guard is deleted rather than repointed* — and what is now guarded instead.

## Numbers

| Gate | Before | After |
|---|---|---|
| `pytest apps/` | 5924 | **5926** |
| `npx jest --maxWorkers=2` | 1754 | **1754** (a 5-test file out, a 5-test file in) |
| `npx tsc --noEmit` | 24 | **24** (baseline, TD-221) |
| `npx next lint` | 0 Errors | **0 Errors** |
| `node scripts/check-i18n.js` | 4816 × 3 | **4816 × 3** (one key out, one in) |
| `npx next build` | clean | **clean** |
| `makemigrations --check` | clean | **clean** |

**No migration**, so the production ledger is unchanged and still reconciled at the gift setup
flow's close (scholarship 150/150, courses 74/74, no gaps).

**Files:** 9 changed — `views_admin.py`, `test_sabah_programme_screens.py`, `admin-api.ts`,
`GiftProgrammes.tsx`, `GiftProgrammes.test.tsx` (new), `en/ms/ta.json`, and
`deleteRefusalCopy.test.ts` (deleted).

## Owner post-check

1. **A gift with intake years and no students should have a LIVE Delete button.** This is the whole
   ruling; it was grey before.
2. **Deleting it should say how many years go with it**, in the dialog, above the typed phrase.
3. **BrightPath Bursary's Delete must still be grey**, reading *"Students have applied to this
   gift…"*. That is the line the ruling draws, and it is the one thing this sprint could have got
   wrong in the dangerous direction.
4. **ms and ta are first drafts** for the one new string (`deleteYears`).
