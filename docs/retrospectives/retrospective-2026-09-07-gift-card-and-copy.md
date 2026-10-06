# Retrospective — the gift card, and the console's voice (2026-09-07)

**Branch** `feat/gift-card-and-copy`, worktree `.worktrees/gift-copy`, based on `origin/main` at
`9b0a454e`. **NO migration.** api + web.

---

## What was built

Three findings from an owner live review of Organisation → Overview and Programme → Configuration.

**1. "Switch off" read as a duplicate of the intake year's Open/Close.**

It sat in a row of verbs beside Delete, one line under a column headed "Taking applications". The
owner's question was direct: *"I do not see a practical use of the switch off. Is it like archive
once the programme is done?"* — and then, sharper: *"Whether it is switched on or off, it is only
active when the intake year is open. So, I feel there are two buttons doing the work of one."*

Checking both guards settled the visible half in their favour. A round cannot be opened on an
inactive gift (`programme_not_active`); an active gift cannot be switched off while a round is open
(`has_open_year`). So *(gift off + round open)* is **unreachable**, and on the apply path
`programme__is_active` never gets to be the deciding factor.

But the gift switch answers a question nothing else answers — *is this a gift the organisation runs
at all?* — and four things read it: creating a payment run, the sponsor-invitation gift picker, the
source picker, and `signup_programme_for`. BrightPath Bursary has every round closed today and is
still paying 47 students.

So the fault was placement, not existence. The state moved into the badge that already showed it,
the badge became the control, and the action row is two verbs: **Settings** and **Delete**.

Three states now, because "inactive" was doing two jobs that rendered identically — a gift still
being SET UP (every gift is born switched off) and a gift that has FINISHED. **Draft · Live ·
Archived**, served as `lifecycle`, derived from `is_active` plus whether anybody ever applied. The
API is unchanged: the control still PATCHes `is_active`.

**2. "Next: set the rules" appeared for ever.** Deleted — see below.

**3. The console reads casually.** ~40 prose strings across the four configuration screens re-voiced
formal, in all three languages.

Plus the owner's own card redesign: **Settings** (not "Open its settings"), the status as a
colour-coded badge, and the delete-refusal line narrowed rather than removed.

## What went well

- **The disagreement was resolved by reading the code, not by arguing.** "Can these two states ever
  disagree?" has a mechanical answer, and it took two greps. That turned a matter of opinion into
  two facts — the pair is unreachable, AND the switch has four other readers — which is what made
  the answer *move the control* rather than *delete it* or *defend it*.
- **Two pushbacks on the owner's own sketch were accepted in one line each**, because each carried
  its reason: red is the colour this product reserves for trouble, and the delete-refusal sentence
  covers five reasons of which only one is visible on the card.
- **The existing `Menu` primitive took the badge with no new dependency** — it already had a
  `trigger` slot, escape handling, click-outside and arrow keys, written once precisely so the third
  and fourth users would not approximate it.
- **Three bite-checks, each verified as landed first**: red draft, an over-eager refusal predicate,
  and the derived lifecycle. Each failed exactly the test written for it.

## What went wrong

**1. I offered the owner a choice whose options shared my own mistake — again.**

*What happened.* Asked whether the gift switch had a use, I answered "yes — it is the draft switch"
and offered to rename it. The owner came back with the sharper observation that two buttons were
doing one job. Only then did I check whether the two states could disagree.

*Why.* I had reached for a justification of the control before establishing the facts about it. The
guards were two greps away and I had not run them; the answer I gave was true but incomplete, and
the incomplete half was the half they were asking about.

*What prevents recurrence.* Recorded as a lesson: **when someone says two controls look like one,
check whether they can ever disagree** — that single question separates a duplicate from a
presentation fault, and it is mechanical. This is the second sprint running where the owner
corrected a framing rather than a defect; the first was TD-232 the same day.

**2. I shipped an onward pointer whose condition could never turn off.**

*What happened.* "Next: set the rules" appeared once an intake year existed — so it appeared for
ever. On a gift running its second intake it read as unfinished homework.

*Why.* I built it as one half of a symmetric pair with the Rules tab's pointer and copied the shape
without copying the reasoning. The Rules one fires on the ABSENCE of a year (a dead end that clears
once); mine fired on its PRESENCE (a state that never clears). Same idea, inverted condition, and
only one of them was help.

*What prevents recurrence.* Deleted, with the reason at the empty spot so it is not restored by
symmetry. Lesson recorded: **before adding an onward nudge, say what makes it go away** — if nothing
does, it is furniture.

**3. A hazard I found and did not fix.**

Archiving a gift blocks creating a payment run for it. Retiring one while students are still owed
money would quietly remove the way to pay them; runs already created are unaffected. Named to the
owner in the investigation and left out of scope — the menu says where the switch will land, but it
does not warn about this. Recorded here so it is not discovered by somebody's payroll.

## Design decisions

Four, all in `docs/decisions.md`:

- *The gift's state is a badge, not a verb* — why the control moved rather than being deleted, and
  why the third state is derived rather than stored.
- *Red is reserved for trouble, so a draft gift is grey* — the one place the owner's sketch was
  refused, and on what grounds.
- *A refusal is hidden only where the card already proves it* — the narrowing, and the four reasons
  that must keep their sentence.
- *A pointer is for a dead end, not for a step somebody has passed.*

## Numbers

| Gate | Before | After |
|---|---|---|
| `pytest apps/` | 5948 | **5954** |
| `npx jest --maxWorkers=2` | 1767 | **1777** |
| `npx tsc --noEmit` | 24 | **24** (baseline, TD-221) |
| `npx next lint` | 0 Errors | **0 Errors** |
| `node scripts/check-i18n.js` | 4832 × 3 | **4839 × 3** |
| `npx next build` | exit 0 | **exit 0** |
| `makemigrations --check` | clean | **clean** |

**No migration.** The third lifecycle state is worked out from columns that already exist.

**Files:** 11 — `views_admin.py`, `test_sabah_programme_screens.py`, `admin-api.ts`,
`GiftProgrammes.tsx`, `GiftProgrammes.test.tsx`, `IntakeYearTab.tsx`, `programme/page.tsx`,
`programme/page.test.tsx`, `ProgrammeRulesTab.test.tsx`, `en/ms/ta.json`.

## Owner post-check

1. **Organisation → Overview.** Each gift shows a badge: **Live** (green) for BrightPath Bursary,
   **Draft** (grey) for a gift nobody has applied to. Press the badge — it opens and offers the one
   move that makes sense from where it is.
2. **The action row is Settings · Delete.** "Switch off" is gone from it.
3. **BrightPath Bursary's Delete is still grey**, and the sentence beneath it is gone — the
   APPLICATIONS column already says 143.
4. **Programme → Configuration → Intake year:** no "Next: set the rules" button below the table.
5. **The wording** across those four screens should read as a product, not a conversation.
6. **ms and ta are first drafts** for everything changed here.
