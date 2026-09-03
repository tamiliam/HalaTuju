# The shape — sixteen menu rows become twelve, and four of them were guesses

**2026-09-03. web + a two-line backend audit. NO MIGRATION.**
pytest **5792** (full suite across `apps/`, +2); jest 1631 → **1657** (+26);
tsc **24** (baseline, TD-221); lint **0 errors**;
i18n 4714 → **4722 × 3**; `next build` clean. **Two guards bite-checked.**

Not on the Sabah roadmap. The owner opened the console, read the sidebar, and said the parts did
not fit: *"We cannot open new branches that are disconnected."*

---

## The rule that settled every question

One question, asked of each row: **what is a subset of what?** Answered from the database, not from
the menu.

```
Organisation
├── invitations · reviewers · sponsors · sources
├── payments · contracts · billing · requests
├── COLOURS                    ← one row per ORGANISATION
└── Gift programme
    ├── Configuration          ← per PROGRAMME
    └── Intake year            ← per PROGRAMME
        ├── the six thresholds ← columns on the YEAR
        └── applications       ← a `cohort` COLUMN on the application
```

The sidebar looked nothing like that. Four rows in the Programme group were **reserved slots** —
each a promise about where a thing would live, made before anyone had scoped it.

## ▶ THREE OF THE FOUR RESERVED SLOTS GUESSED THE SHAPE WRONGLY

- **Rules** was to be a page. The six thresholds are **columns on the intake year**, and S2b's
  create form already wrote them. A Rules page would have been a second view of an existing form.
- **Reviewer scoping** was to be a page. Which gift a reviewer covers is **one field on that
  reviewer**, and belongs on their record under Organisation → Reviewers.
- **Fund** was to be a page. It is a report — money in lives under Sponsors, money out under
  Payments.
- **Intake years** had already been built as a page one sprint earlier, and is a **child of the
  gift**, not a sibling of the gift's settings.

lessons.md said this a month ago (N4, 2026-07-28): *"a placeholder for future work encodes an
assumption about that work — if the assumption is not yours to make, do not leave the placeholder."*
It was written about a `uiPrefs` key and applied to a menu, where the slots looked legitimate
because they were owner-approved, visibly disabled, and guarded by a test forcing the flag off when
a page appeared. **All of that was true and none of it checked whether the slot was in the right
place.**

`billingRates` survives, and the difference is the rule worth keeping: **its endpoint shipped on
2026-07-27** and only the page is missing. A slot is for a thing that demonstrably exists, not for a
thing somebody intends.

## ▶ COLOURS WAS WRITING A TENANT-WIDE ROW FROM INSIDE ONE GIFT

`OrganisationTheme` holds ONE colour for the whole organisation, and its endpoint **derives** the
organisation from `admin.owning_organisation` — it has never taken a programme. The tab sat on the
Programme screen.

With one gift nobody could tell. With two, an admin standing in the new gift would set "its" colour
and change the older gift with it, silently. It is Organisation → Settings now, and the i18n
namespace moved with it (`admin.programme.colours` → `admin.orgSettings.colours`) so a later reader
greping `admin.programme.` does not find it there.

**The tell, for next time: a screen that writes a row whose scope is BROADER than the screen's own.**

## ▶ THE BREADCRUMB SWITCHER HAD BEEN INERT FOR FIVE WEEKS, WITH A WRITTEN TRIGGER

N3a shipped the organisation/programme switchers on 2026-07-28 and logged **TD-193**: *"the switcher
moves the breadcrumb and NOTHING ELSE — it filters no list. Trigger: a second organisation or
programme going active."* BrightPath Sabah is that trigger, and the owner raised it themselves:
*"When a reviewer or others have access to two or more programmes, they select the programme at the
top through a drop down list."*

`lib/programmeScope` now holds the choice and hands it to each Programme-scope page. **The N3a rule
is intact and restated in the code**: the value is passed to each endpoint as an EXPLICIT request
parameter the server re-fences on the caller's own `owning_organisation` — the `?programme=<code>`
contract `AdminProgrammeConfigurationView` has always had. Nothing became ambient. A client that
ignores it reaches identical data.

**It never picks silently.** One gift resolves; several with no choice made resolves to *nothing*,
and the page asks. That is PF-1's refusal (`resolve_open_cohort` raises rather than choosing) applied
to a screen — and it is why the crumb shows a prompt rather than naming the first gift, which would
have the console asserting an answer the page below it is still asking for.

**It is not persisted.** `uiPrefs` says in as many words not to reach for it by default, and a stored
gift code would outlive the tab and silently reopen someone else's gift after a reload.

## ▶ THE OWNER'S MODEL WAS RIGHT ABOUT THE DATA, AND ONE ASYMMETRY IT DOES NOT SHOW

*"The intake year is merely a column within the application table, and not a superset."* Correct —
an application carries `cohort_id`, only one round may be open, and the year's other job is holding
the thresholds. So Rules is a tab, and the year is a tab beside it.

But two settings now share one screen with **different blast radius**, and that had to be said out
loud rather than left to be discovered:

| | Changing it mid-intake |
|---|---|
| **What we ask for** | Frozen per application at submit (`requirements_snapshot`). Nobody already in is touched. |
| **Rules** | `shortlisting.evaluate()` reads them **live**. The bar moves for everybody still to be judged. |

Hence a warning on one tab and not the other, and a second audit line carrying **old → new**.

## ▶ THE REVERSE CONVERSION IS THE DANGEROUS HALF, AND S2b'S RETRO SAID SO

The B+ requirement is **shown as an extra and stored as a total**. Until today the conversion ran one
way: a create form wrote a total, and nothing ever read one back. S2b's retro warned, under *"Not
built, deliberately"*: *"If a future screen ever sends what it displays, '4 plus 1' silently becomes
'4 plus 1 more than 4'."*

**The Rules tab is that screen**, and every save it makes starts from a value it read. The live row
is `(4, 5)`; loading 5 into the extra box and saving would have written `(4, 9)` — nine subjects, on
a live programme, with nobody touching a control.

`requirementsToDraft` is the inverse, pinned by a round-trip test and by a rendered test asserting
what actually reaches the wire. **Bite-checked**: replacing the subtraction with the raw total
failed five tests, including the rendered one; restored by writing the original back.

## What the tests found that reading could not

- **The requirement inputs were remounting on every keystroke.** `Req` was declared inside the
  component body, so React saw a new component type each render and the field lost focus after one
  character. Live since S2b, invisible to every source-shape guard — and the *identical* defect
  lessons.md records for the 2026-07-21 invite form. Hoisted to module scope, with the reason at the
  line.
- **The Rules tab announced "this gift has no intake year yet" on every load.** It keyed its empty
  state on `useSelectedProgramme`'s loading flag, which goes false when the PROGRAMMES arrive —
  strictly before the YEARS. An empty card is never merely useless; it asserts something, and this
  one asserted something false about a gift with a live round (lessons.md, 2026-08-18). It has its
  own `yearsLoading` now.
- **`useSelectedProgramme` could throw into a tab.** `.catch()` on the chain sees a rejected promise
  and cannot see the CALL itself throwing. Now `try/catch` around the await, so a failure from either
  direction leaves an empty list and the caller's own empty state.
- **The brand guard caught a real tenant name in sandbox copy.** I wrote "BrightPath" into a surface
  note; the sandbox uses invented names precisely so no tenant leaks into a design surface.

## For the next sprint

**The owner's model merges three sprints into one pattern**: reviewers, sponsors and sources are all
invited by the ORGANISATION and then assigned to a GIFT. Sponsors already have the model
(`SponsorProgrammeMembership`) and one hard-coded line; **reviewers and sources have no such field at
all.** So old S4 + old S5 + a new sources piece are one shape, built three times — one migration,
three near-identical screens.

**Owed, and asked twice: contract wording — one per organisation, or one per gift?**
`ContractTemplate.organisation` allows exactly one ACTIVE template per organisation, so a second gift
would today have its students sign the first gift's agreement.
