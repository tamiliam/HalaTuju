# Gift setup flow — the cycle starts where the data starts (plan, 2026-09-06)

**Owner request, 2026-09-06.** Two things: the Settings row has no icon, and *"once a programme is
created… Intake Year (with start date and end date) > Rules > What we ask for (Questions first,
followed by Documents). For existing programmes, the gift cycle starts with the org admin creating
a new intake year. Pls investigate if this flow is there. We do not want a disconnected flow."*

**Investigated 2026-09-06. It is not there.** Findings below are measured from the code, not
remembered.

---

## What is actually broken

### 1. Two sidebar rows have no icon, and nothing complains

`Sidebar.tsx:56` renders `<Icon name={item.id} />`; `icons.tsx` falls back to `PATHS.dot`
(`M12 12h.01`) when a name is unknown. Compared the 21 nav ids against the 31 glyph keys:
**`orgSettings` and `faq` have none.** Both render as a bare dot.

`navigation.test.ts` mentions icons **zero** times, so the next new row will do the same thing.
**The missing glyph is the bug; the missing guard is the defect.**

### 2. The setup flow dead-ends on its first screen

| step | what happens today |
|---|---|
| press **Create** on a gift | `GiftProgrammes.create` closes the dialog and clears the form. **Nothing else.** |
| press **Open its settings** | `router.push('/admin/programme')` → the page opens on `useState<Tab>('rules')` |
| the Rules tab | a new gift has **0 intake years**, and `ProgrammeRulesTab:135` renders `admin.rules.noYear` |
| the message | *"…Create one on the Intake year tab and set them there."* — **prose, with no button** |

**Rules are columns on `ScholarshipCohort`** (the intake year), which the tab's own docstring says.
So the first screen a new gift shows is the one screen that cannot work yet. There is also no
`?tab=` deep link, so nothing anywhere can point a person at the tab they need.

**"What we ask for" is NOT affected** — `AdminProgrammeConfigurationView` is per-PROGRAMME, so it
works with zero years. Only Rules has the dependency. Say so rather than fixing what is not broken.

### 3. The intake year has no dates at all

`ScholarshipCohort` fields, read from the model: `code, name, year, is_active, is_open`, six
thresholds, four timing knobs, `created_at`, `updated_at`. **There is no `opens_on` and no
`closes_on`.** The create form asks `{ year, code, name }`. This is a migration, not a form field.

### 4. The two orders are both the reverse of what was asked

- Tabs are `['rules', 'config', 'year']` (`page.tsx:44`).
- Inside "What we ask for", `documents` renders before `questions` (`ProgrammeConfigTab.tsx:228-229`).

---

## ⚠ THIS SPRINT REVERSES A RULING THE OWNER GAVE ON 2026-09-03

Not a leftover — a decision, taken deliberately, recorded in three places and **pinned by a test**:

> `page.test.tsx:193` — `expect(tabs).toEqual(['tab-rules', 'tab-config', 'tab-year'])`, under the
> comment *"THREE TABS SINCE 2026-09-03, AND THE ORDER IS THE OWNER'S. Rules first, because who
> qualifies precedes what they are asked to send."*

**Both rulings are right about different things, and that is the resolution.** The old one is about
READING order for a gift already running — who qualifies does precede what they send. The new one is
about SETUP order for a gift that does not exist yet, where Rules has nothing to write to.

**The evidence favours the new one:** rules live on the year, so Rules-first is empty by
construction on day one. Setup order must follow data order.

Per the F7d lesson (*"when you invert a guard, carry its rationale forward"*), `page.test.tsx`'s
assertion is **rewritten in place with the 2026-09-03 sentence preserved in its comment**, never
deleted. A decision entry records the reversal and why.

---

## ✅ OWNER RULINGS, 2026-09-06 — both taken on the record

1. **"Dates describe."** `opens_on` / `closes_on` state the round's window and are shown on
   screen. **A person still presses Open.** Nothing opens on a clock.
2. **"One open round per GIFT PROGRAMME, not per organisation"** — and handle the plain apply
   link, which is what breaks the day two rounds are open. This is **part E** below.

**⚠ The owner CORRECTED a premise of mine, and the correction changed the sprint.** I argued for
"dates describe" partly on a 3am clash between two gifts. With a per-gift rule **that clash cannot
happen**, so that argument is void and is not carried into the decision record. The reason that
survives is the one below, and it is the only one worth writing down.

## Why "describe" still, once the clash argument is gone

**A date can fire before setup is finished.** Create a gift, type a start date, get interrupted —
and on that date the round opens to real students with no rules set and no questions configured.
A press cannot do that; a clock can. That is this sprint's own subject: setup has an order.

Also: `is_open` already exists and already means "students can walk in". A date that ALSO opens is
a second thing that can disagree with it, which is the exact shape `lessons.md` warns about
(*"make the VALUE the switch"* — here the switch already exists, so the date must not become a
second one). A timer, if ever wanted, is a job **on top of** these columns, argued on its own.

## ~~⚠ THE ONE THING I WILL NOT DECIDE: do the dates OPEN the round?~~ — ANSWERED ABOVE

Two settled positions collide here, and the collision is real:

| position | where | says |
|---|---|---|
| **"Creating an intake year never opens it"** | `decisions.md`, Sabah S2b, 2026-09-03 | *"An open intake year is the moment real students can walk in."* Opening is a separate, deliberate press. |
| **"Make the VALUE the switch"** | `lessons.md`, Sabah S2a | a date that means nothing is a second field that can disagree with `is_open` |

There is also a hard constraint on screen today: **only one round across the organisation may be
open at a time** (`another_year_open`, `views_admin.py:6723`). If a date could open a round by
itself, two gifts with overlapping dates would make a scheduled job pick one and silently refuse
the other — a guess about money, made at 3am, with nobody watching. That is exactly the class PF-1
forbids.

**My recommendation: DATES DESCRIBE, A PERSON STILL OPENS.** `opens_on` / `closes_on` are the
round's stated window, shown on the screen and in the table; `is_open` stays the deliberate press.
This honours the 2026-09-03 ruling, keeps one-open-at-a-time safe, and still gives the owner the
two fields they asked for. If they want automatic opening later it is a scheduled job on top of
these columns — additive, and it can be argued on its own merits then.

**→ Owner confirms this before the migration is written.**

---

## Deliverable

**One coherent thing: an org_admin who creates a gift is walked through setting it up in the order
the data requires, and is never left on a screen that cannot work.**

### A. The icons (3 files)
- `orgSettings` and `faq` glyphs added to `PATHS`.
- **A guard: every nav id has a glyph.** The dot fallback STAYS (a missing icon must not crash a
  console in production) — the test is what makes it loud, and a comment says so.
- Applies the F7b lesson: when a fault produces silence, ask which test should have failed.

### B. The order (3 files)
- `TABS = ['year', 'rules', 'config']`; the page opens on Intake year.
- `documents`/`questions` swapped so Questions render first.
- `page.test.tsx` rewritten in place, old rationale carried in the comment.

### C. Start and end dates (≈8 files, ONE migration)
- `opens_on` / `closes_on` — `DateField(null=True, blank=True)` on `ScholarshipCohort`.
- **NULL means "no window recorded", and there is NO BACKFILL.** The S-ASSIGN discipline, and the
  A3 lesson: ask what a new field claims about rows that already exist. The 2026 round already ran;
  inventing dates for it would be fiction on an audited row.
- Validation: `closes_on` must not precede `opens_on`; a new error code, not a silent swap.
- Create form + edit + the years table + `_cohort_row`.
- **MIGRATE-FIRST**: applied to production and verified BEFORE the push, per the standing rule.

### D. The trail (≈5 files)
- `?tab=` deep link on `/admin/programme`, so any screen can point at a tab.
- **Create → land on the new gift's Intake year tab.** Today: nothing happens.
- The Rules `noYear` box gains a **button** to the Intake year tab. Today: a sentence.
- After a year is created, the Intake year tab points on to Rules.
- Copy in **en / ms / ta** (ms + ta first drafts, as ever).

### E. One open round PER GIFT, and the plain link stops being a trap (≈8 files)

**The rule, measured:** `views_admin.py:6717` filters `owning_organisation=...`. It is org-wide
today, so Sabah cannot open while BrightPath is open. Owner ruled that wrong. → filter on
`programme=` instead.

**⚠ RELAXING THE ADMIN GUARD IS NOT THE WHOLE JOB, AND THE REST IS THE PART THAT HURTS.**
`resolve_open_cohort` counts ambiguity across **all** open rounds platform-wide, deliberately
(*"'which round?' is equally unanswerable between two intakes of the SAME organisation"*). Two
front doors, and they fail differently:

| door | with two rounds open | verdict |
|---|---|---|
| `intake/` (public, drives the landing + apply page) | returns `{open: true, cohort_name: ''}` | **degrades correctly** — generic copy, no lie |
| `applications/` POST | **409 `programme_required`** | **the trap** |
| `/scholarship/apply?p=<code>` | narrows, works | fine |
| `/scholarship/apply` bare | form fills, then 409 **at submit** | **the trap** |

The refusal is right and must stay — guessing once filed a student under the wrong foundation,
funded from the wrong money, with no error. **What is wrong is WHEN it arrives:** after the
student has filled in the entire form.

**The fix is PF-1's own rule — never pick, ASK — moved EARLIER:**
- `intake/` gains the list of open rounds when it cannot name one (it already knows; it currently
  throws the information away).
- The apply page, with no remembered `p=` and several rounds open, **asks which gift before the
  form**, and stores the answer through the seam that already exists
  (`rememberApplyProgramme` / `APPLY_PROGRAMME_KEY`) so submit is unchanged.
- The 409 stays as the backstop. It is now unreachable by an honest path, which is what a
  backstop should be.

**⚠ NOT a fence, and the code must say so.** Which round a student joins is routing. The
organisation fence is `_org_scoped` and is untouched.

**Estimated files: ~26.** Under the 40 cap, and part E is why it is not ~20.

---

## Lessons from `docs/lessons.md` that bind this sprint, and how each is handled

| lesson | how this sprint accounts for it |
|---|---|
| **"When a new field's default changes what an EXISTING row means, every direct constructor in the suite is in the blast radius"** (A3) | `opens_on`/`closes_on` are **nullable with no default and no backfill**, so an existing row keeps meaning exactly what it meant. Every test that builds a `ScholarshipCohort` by hand is checked, not assumed. |
| **"A setting with no way to say 'we do not use this' is a requirement everybody has"** (S2a) | NULL is a real answer here: a round with no stated window is a normal round, not a broken one. No `NOT NULL`, no default date. |
| **"Make the VALUE the switch"** (S2a) | Named in the open question above rather than applied silently. It is the lesson that argues *against* my recommendation, so it is stated as such — the owner should see both sides. |
| **"A guard is blind to whatever is not in its scope"** (F6/F7c/F7d) | The icon guard asserts over **every id the registry holds**, derived at runtime, never a hand-written list that can fall behind. |
| **"When an injected fault produces silence, ask which test should have failed"** (F7b) | This whole sprint's part A is that lesson: the missing icon produced silence for three days. |
| **"When you invert a guard, carry its rationale forward"** (F7d) | `page.test.tsx`'s tab-order assertion is rewritten in place, and the 2026-09-03 sentence survives in its comment. |
| **"Anchor a source-scanning test on the CALL, not the identifier"** (F7d) | The icon guard parses the registry, not a grep of the word `id:`. |
| **"A test count is only a baseline if it was measured the same way last time"** (S2) | The FULL suites are run for every recorded number: `pytest apps/` and all of jest. Never a scoped run for a figure that leaves the terminal. |
| **"NEVER GENERATE A REGEX" + sweep for control bytes after any generated write** (F4/F7a) | No codemod in this sprint; every edit is by hand with an editing tool. If any generated write happens, the file is swept and the scan is **scoped to the files that write touched** (F7e). |
| **"`next build` enforces a contract the other gates do not"** (F7c) | `next build` is in the gate list, and the `?tab=` deep link touches a PAGE file — exactly the shape that broke three builds in F7c. `useSearchParams` needs a Suspense boundary or the build refuses. Expect it, do not discover it. |
| **"A surface with no way to be looked at has NOT been reviewed"** (F7c) | The whole flow is walked in a browser: create a gift, follow the trail, set a window, open the round. A passing test is not the evidence for a flow. |
| **"Reconcile the migration ledger against PRODUCTION"** (sprint-close 3a) | One migration this sprint; it is applied migrate-first and the `django_migrations` row is verified, not assumed. |

## Decisions from `docs/decisions.md` that constrain the approach

- **"Creating a gift never activates it; creating an intake year never opens it"** (S2b, 2026-09-03)
  — the reason the dates question above is the owner's and not mine.
- **"The programme-configuration write is all-or-nothing"** (Layer 0 S5) — untouched; swapping the
  render order of two sections changes no write.
- **PF-1's rule — never pick silently** — the trail may *point*, it may never *choose*. Landing a
  person on the Intake year tab is a suggestion; it must not create a year for them.
- **`requirements_snapshot` freezes what a submitted student was asked for** — unchanged. Dates are
  not part of what a student is asked for and must not enter the snapshot.

## Verification

`npx jest --maxWorkers=2` · `npx tsc --noEmit` (**expect exactly 24**, TD-221 baseline) ·
`npx next lint` (0 Errors) · `node scripts/check-i18n.js` (×3, +new keys) · `npx next build` ·
`python -m pytest apps/` (FULL). Plus the browser walk, and a bite-check per new guard with the
injection **verified as landed** before the suite runs.

**⚠ Another agent holds the main checkout** (`.worktrees/layer1-f7f`, F7f). This sprint runs in
`.worktrees/gift-setup-flow` off `origin/main`. Do not run two full suites at once.