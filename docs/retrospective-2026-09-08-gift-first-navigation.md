# Retrospective — the gift must be known before the menu offers to configure one

**2026-09-08.** Web only. No migration, no API change. 10 files.
Worktree `.worktrees/gift-first`, branch `feat/gift-first`, base `c145b677`.

---

## What was asked

The owner, looking at the gift switcher that had shipped an hour earlier:

> *"I feel the programme shouldn't show up until they are selected, perhaps in the overview. See the
> supabase sample image. 1) So, when an admin logs in, they'd land in the overview page, with links
> to the programme page. Selecting a programme would show the programme links below. Otherwise, the
> programme menu items would be hidden as well. 2) But reviewers do not have access to the overview
> page. They are brought straight to the Application page, I think. So, I think we need to think
> this through."*

They asked for an investigation and a plan before any code. That is what happened, and the
investigation changed the shape of the answer twice.

---

## What the investigation found that the request did not contain

**1. Nobody was landing on the Overview. Not one role.** The owner's step 1 read like a tweak and
was a rule that did not exist. `defaultRoute` sent everyone but a reviewer to `/admin`, and `/admin`
is `roles: ['super', 'partner']` — the platform dashboard. org_admin, admin, qc and finance were all
bounced off it by `admin/page.tsx`.

**2. `finance` was being bounced onto a page it may not open.** The registry omits `finance` from
`applications` deliberately: its `_b40_scope` is `'none'`, so every call it makes there can only
403. The scholarship page had no client guard, so the failure looked like an empty table rather
than a refusal. Nobody had reported it. **This was not in the request and is the most valuable thing
the sprint found.**

**3. The owner's reviewer worry was worse than they thought.** `navigation.test.ts` pins
`visibleNav(ctx('reviewer')).map(g => g.scope)` as `['programme', 'utility']`, and the sidebar skips
`utility`. Programme is a reviewer's **only** group. Hiding it would have given them a completely
empty rail.

**4. Most of the mechanism already existed.** `ChooseProgramme` (the picker), `GiftProgrammes
.openSettings` (the gift card that selects a gift and steps into it — the Supabase click, already
built), and `Sidebar`'s `programmeName` prop, which had been fed `undefined` since N4.

---

## The decision, and why it beat the two obvious answers

**Hide by consequence, not by role.**

| Row | No gift chosen | Why |
|---|---|---|
| Programme → Configuration | **hidden** | it WRITES a gift's settings; with nothing chosen it can only ask, and it invites editing the wrong gift's rules |
| Programme → Applications | **stays** | it READS; "every gift under a neutral heading" is true, just less specific — and it is a reviewer's only door |

The two answers this beat:

- **Hide the group, exempt reviewers.** A role check that would have to be re-reasoned for `qc`, for
  `finance`, and for every role added after — and the exemption would itself need a reason, which is
  "they have nowhere to choose from", which is a statement about the ROW, not the person.
- **Hide both, add a "Choose a gift" row.** Closer to the literal Supabase feel, and it buys a new
  surface, three translations, and a decision about where that row leads for somebody with no
  Overview page. Offered to the owner as Option 2; they chose Option 1.

The line was not invented here. The gift-switcher sprint the day before had already written it into
the pages — *"Configuration ASKS, because a silent pick would edit the wrong gift; a list is a READ,
so wider is true, just less specific"*. This sprint applied the same sentence one level up, to the
menu. That is why it needed no new concept and no new copy.

---

## What shipped

1. **`NavItem.needsProgramme`** — one row carries it. `canSee` hides such a row when
   `ctx.programmeChosen === false`. Hidden, never "soon": a Soon pill promises a feature that is
   coming, and this one is here, waiting on the reader.
2. **`NavContext.programmeChosen`**, optional, checked as `=== false` (the
   `reviewer_profile_complete` shape). Omitted means show, so a caller that predates the dimension
   cannot silently lose a row.
3. **`scopesLoaded`** on the shell. An empty `programmes` array is two facts — "no gifts" and "not
   asked yet" — and reading the second as the first would have hidden the row on the first paint of
   every page load and slid it in a moment later.
4. **`defaultRoute` derives the landing route** from the registry instead of naming `/admin`.
5. **`adminLanding()` genuinely delegates** to it now. The docstring had claimed it for months
   while two hand-copied implementations sat side by side.
6. **A role guard on the Applications page**, mirroring the registry.
7. **The rail names the gift** in the Programme heading.

---

## What was NOT done, deliberately

- **No new page, no new i18n key, no Stitch screen.** A row hides and a heading gains a name. The
  Stitch-first rule is for new pages and layout redesigns; nothing here is either.
- **The four organisation-scope surfaces still ignore the gift.** Unchanged from yesterday's note:
  a reviewer's `programme` is nullable and NULL means EVERY gift, so a naive filter would hide the
  organisation-wide reviewers. Each needs its own owner ruling.
- **Applications was not given a gift chooser.** Listing every gift is the correct answer there.

---

## Gates

Run inside the worktree. jest **1864** (1853 → 1864); tsc **24** (baseline, TD-221); `next lint`
**0 Errors**; `check-i18n` **4887 × 3** (no new keys); `next build` exit **0**.

**No Python file was touched** (`git status` shows ten files, all under `halatuju-web/`), so the API
suite and `makemigrations --check` are unchanged from `main` at `c145b677`, where both are green.
Stated rather than re-run, because running 5997 tests to prove a zero-line Python diff is waste.

**Six bite-checks, each injection verified as landed before the suite was run, each restored by
writing the original bytes back:**

| # | Fault injected | Test that bit |
|---|---|---|
| 1 | `canSee` ignores `needsProgramme` | hides Configuration, and only Configuration |
| 2 | `applications` marked `needsProgramme` | never empties a sidebar — a reviewer keeps their queue |
| 3 | `defaultRoute` returns `/admin` again | lands every role on the first page it may open |
| 4 | the Applications role guard removed | shows a refusal to finance and asks the server for nothing |
| 5 | `Sidebar.heading()` ignores `programmeName` | names the gift in the Programme heading |
| 6 | the shell stops feeding `programmeChosen` | hides Configuration when several gifts and none chosen |

Bite 1 failed **one** test rather than two: the reviewer-strand test asserts `['applications']`
under no-gift, and a reviewer never sees `programmeConfig` anyway because of its role set. That is
correct — that test guards the strand, not the hiding — and it is recorded here rather than
smoothed over, because a bite-check that bites less than expected is worth understanding.

---

## Honest gaps

- **No logged-in browser pass.** The rendered tests mount the real shell against the real registry,
  which is why the wiring bug in bite 6 is catchable at all — but nobody has yet signed in as the
  BrightPath `org_admin` and watched the row appear. That is the owner's post-check.
- **The Guide and FAQ were checked and needed nothing.** Grepped for prose describing the sidebar's
  contents and the post-login destination ("when you sign in", "you'll find it under", "in the
  sidebar"); the console's copy describes neither. Verified rather than assumed, per the
  2026-07-28 lesson that a term-based grep finds copy that NAMES a thing and misses copy that
  DESCRIBES it.
- **`AppShell` was split into two components** (`AppShell` provides the programme context, `Chrome`
  consumes it) because a component cannot read a context it is itself mounting. It is a mechanical
  move, covered by the existing 24 shell tests, but it is the largest structural change here and
  the one most worth a second pair of eyes.
