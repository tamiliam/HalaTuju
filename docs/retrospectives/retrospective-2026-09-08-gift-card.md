# Retrospective — the gift card is the door

**2026-09-08.** api + web. No migration. Worktree `.worktrees/gift-card`, branch `feat/gift-card`,
base `ee9630cb`.

---

## What was asked

The owner had just confirmed the gift-first navigation worked, and reported one thing left over:

> *"It appears after I click B40 programme and then select the programme in the top."*

They had reached a gift the long way round — through Applications, then the breadcrumb — rather than
through the gift card sitting on the very page they had started on. Shown the two options, they went
further, with their own Supabase screenshots:

> *"In supabase, the project card is clickable. Likewise, we could change the entire gift card to
> button. But in supabase you see the settings are hidden behind the three dots, which is nice. We
> could move both the settings and delete behind three dots, as this is not something we'll be
> messing with regularly. We could add a few more facts to the card, like awarded. And, reducing the
> card length to half its size now."*

Sketch and the "add Awarded" question were both put back to them and approved before any code.

---

## The finding that made the sprint

**Nothing was broken.** "Settings" at the foot of the card already selected the gift and stepped into
it — it had done exactly that since 2026-09-06 (`GiftProgrammes.openSettings`). The owner, who
designed the flow, did not find it.

That is the whole lesson: a small grey verb in a row of verbs reads as a minor action, not as a way
in. **A control that works and is not found is indistinguishable from a missing one**, and the fix
was a bigger target rather than better explanation.

---

## What shipped

1. **The whole card opens the gift** — a `<button>` at `absolute inset-0`, with the text
   `pointer-events-none` above it so nothing steals the click.
2. **Settings and Delete moved behind a ⋮ menu.** Settings stays in there as well: the card is a
   shortcut, the menu is the named route.
3. **`MenuItem` learned to be asleep** — greyed, not focusable, with the reason rendered underneath
   and `stopPropagation` so pressing it keeps the menu open.
4. **The card is about half its old height** — three facts on one line, and the round as a sentence
   beneath ("Taking applications for 2026" / "Not taking applications") instead of a column that
   could only ever read "None". The `col.takingApplications` key was retired, not orphaned.
5. **A new served fact, `awarded`.**
6. **The application count was aligned** to the predicate the Applications list already uses.

---

## The three things that could have gone quietly wrong

**A button inside a button.** Invalid HTML; the inner control stops being reachable by keyboard.
Nothing throws, nothing warns, and it renders perfectly to a mouse. So the badge and the ⋮ menu are
SIBLINGS of the door, and a test asserts that structurally — review reads the intent, and the intent
was right the whole time.

**Hiding Delete would have undone the owner's own ruling.** On 2026-09-07 they said a destructive
control must be *"prevented at the button stage, and not wait until typed to check"* — because they
were afraid to press Delete on the live flagship. Tidying it into a menu would have taken the reason
with it, and would have read as pure housekeeping in the diff.

**And one half of that ruling INVERTED.** `redundantWithCard` suppressed the "students have applied"
refusal because an APPLICATIONS column reading 143 stood right above the sentence — a statement about
adjacency, not about the reason. The menu carries no counts, so in there it is the only explanation a
reader gets. The predicate was deleted with a comment saying it was *answered*, so nobody restores it
thinking it was an oversight.

---

## The two counts, and why each is a trap from the opposite side

**`awarded` drifts as students PROGRESS.** It is one stage in `awarded → active → maintenance →
closed`, so `status='awarded'` would have shown twelve one month and three the next with nobody
having lost an award. Counted from `awarded_at` — stamped set-if-null, never cleared — with a status
arm for rows predating the stamp (`vircle.py` notes such rows exist). `closed` is deliberately absent
from that arm: a closed case that WAS awarded carries the stamp anyway, and one that was not is not
an award.

**`applications` drifts when a ROUND moves.** The gift is copied from the cohort at first save and is
set once, so moving a round leaves its applications on the old gift. The list narrows through the
round; the card counted the column. Identical today, because no round has ever moved — which is the
cheapest possible moment to align them, since afterwards there is no way to tell which number was
right.

---

## What was NOT done, deliberately

- **No Stitch screen.** The owner supplied two reference screenshots and approved an ASCII sketch of
  the card before any code. That is the "drawn and approved before coding" rule satisfied by the
  shorter route, the same way the payment-run phone cards were.
- **The Guide and FAQ were checked and needed nothing** — grepped for prose naming the gift card, the
  Settings link, or the switch-off verb; the console's copy describes none of them.
- **No migration.** `awarded_at` and the status column both already existed.

---

## Gates

Run inside the worktree. pytest **6034** (6027 → 6034); jest **1886** (1883 → 1886); tsc **24**
(baseline, TD-221); `next lint` **0 Errors**; `check-i18n` **4901 × 3** (five keys added, one
retired); `next build` exit **0**; `makemigrations --check` clean.

**Six bite-checks, each injection verified as landed before the suite ran, each restored by writing
the original bytes back:**

| # | Fault injected | Test that bit |
|---|---|---|
| 1 | `awarded` counts `status='awarded'` only | counts a student who HAS BEEN awarded at every later stage |
| 2 | `closed` folded into the status arm | a CLOSED row that was never awarded does NOT count |
| 3 | `applications` counts the stale column | it REACHES THROUGH A ROUND THAT MOVED between gifts |
| 4 | `MenuItem` ignores `disabled` | six tests, across both files |
| 5 | the asleep item's `stopPropagation` removed | KEEPS THE MENU OPEN when pressed |
| 6 | a `<button>` nested inside the card button | never nests a button inside the card button |

---

## Honest gaps

- **No logged-in browser pass.** The rendered tests mount the real card and click the real door, but
  nobody has yet seen the new layout at a real width. That is the owner's post-check, and the one
  thing worth looking at is whether the card reads well on a phone — the facts are on one flex line
  and will wrap.
- **ms and ta are first drafts** for the five new strings, including the two interpolated round
  sentences.
- **`redundantWithCard` is gone but its RULE is not** — the comment where it stood is the only thing
  now carrying "nothing on the menu surface makes a refusal redundant". If Delete ever moves back
  beside a count, that reasoning has to be re-read rather than re-derived.
