# Retrospective — the token vocabulary, the switch, and one surface (Layer 1, F1)

**Date:** 2026-07-29
**Deliverable:** light and dark as CSS-variable ramps; the before-paint mechanism; the sponsor
portal converted; a mode toggle in the sandbox so every later repaint sprint can be reviewed.
**Verification:** 1153 jest / 77 suites - `tsc` clean - `next build` clean - i18n 4293 x3 - **no
migration** - **both modes reviewed in a browser on the real page**.

**NOT THE WHOLE SPRINT.** The switch a person clicks and its account persistence are unbuilt and
split out deliberately - see *Carry*.

---

## The decision the rest of the arc rests on

Ramps keep Tailwind's **numbers** (`bg-gray-50` becomes `bg-ground-50`) rather than taking semantic
names, and **dark is the light set read from the other end.**

This was extracted from measurement, not designed: 93% of the 1,963 chromatic utilities already
belong to four tone families, twelve property/shade pairs cover 88% of them, and `InfoBox.tsx` names
the convention outright. What it buys - light mode pixel-identical *by construction*, ~5,500
utilities converting mechanically, and nobody deciding 3,681 times whether a white thing is a card
or a modal - is recorded in `docs/decisions.md`.

## What the browser found that the tests could not

The suite was green and the sponsor portal reported zero raw colours. Then I looked at it.

**1. The primary button was classified as "information", not as the brand.** The codemod's
`blue -> info` rename was right in every individual case and wrong about the page. Two consequences,
and the second is the serious one: it reversed to a pale blue under white text in dark mode, **and**
a tenant's own colour would never have reached it. The sponsor portal had 90 blues and exactly
**one** brand-aware colour - tenant theming that does not reach the buttons is not tenant theming.

Resolved by a rule now in `decisions.md`: *a filled control the user acts on carries the brand; a
coloured surface that informs carries the tone.*

**2. The giving donut kept raw hex in an inline style.** A `conic-gradient` cannot be a utility, so
its three colours sat as `#2563eb` / `#22c55e` / `#e5e7eb` - invisible to a class scan, and a
light-mode island in dark. The guard now refuses a bare hex too, with a documented allowlist for
Google's logo (a third-party mark must not follow our theme).

**Both were found by looking. Neither was findable by any test I would have thought to write** -
which is the argument for the sandbox, made concretely rather than in principle.

## What went wrong, and what changed

**I destroyed an hour of uncommitted work with `git checkout --`.** Bite-checking a guard meant
injecting a fault into `globals.css`; I reverted it with `git checkout`, which reverted the whole
uncommitted token block with it. Recoverable only because the block was script-generated rather than
typed. *System change:* commit before bite-checking, or restore from a string held in the same
process - never reach for git to undo a deliberate mutation in a dirty file.

**A test matched its own explanation.** The assertion that the boot script is not `async`/`defer`
searched the whole `<head>` block - including the comment explaining why `async` and `defer` are
wrong. It failed the moment I wrote that comment. *System change:* assert against the element, not
the surrounding text.

**A lint rule blocked the correct implementation, twice.** Raw HTML injection was refused by a hook
(rightly - the habit is worth not having), so the boot script became a real static file. Then
`no-sync-scripts` failed the build, because blocking is precisely the requirement here. Suppressed
at that line with the reason written beside it. Then the *prose* of that reason was itself parsed as
a second eslint directive. Three rounds on one line, all avoidable by writing the exception once and
keeping the disable keyword out of the explanation.

**A fixture that cannot rot is not automatically a good fixture.** A 2099 reporting date rendered
"Starts in 26,697 days". Near-dated instead: when it rots the chip simply stops rendering, which is
a state another card already covers.

## Guards, verified by watching them fail

Every one was disabled and observed to fail before being trusted:
- a theme writing `--brand-*` -> **2 failed**
- a dark stop drifting off the reversal -> **1 failed**
- raw colour creeping back into a converted surface -> **1 failed**

And two verified live in the browser rather than only in CI: `--brand-500` is **unchanged** across a
mode flip, and an open collapsible **stays open** - no re-mount, so a half-filled form survives the
sunset.

## Things fixed rather than noted

- The same six-entry status badge map lived in two files, one carrying a comment saying it
  "mirrored" the other. One side deleted into `lib/poolCard.ts`.
- `graduated` was indigo - a fifth meaning the vocabulary does not name, on three uses against
  ~1,800, and the only badge that would have failed to invert. Now the deeper weight of `positive`.
  **The one deliberate visual change in this sprint.**
- The sandbox fixture, being typed, refused to compile without four fields the equivalent jsdom test
  has silently omitted for months. A cast in a test silences the compiler; a typed fixture does not.

## Carry

- **The switch a person clicks, and its account storage - split out as its own sprint.** Four
  settings surfaces across three identity models plus a migration; bolting it onto F1 would have
  made a sprint nobody could review in one sitting. Nothing needs it until F7.
- **A tone-tuning pass.** The reversal handles the ground well; saturated mid-stops want an eye.
  One CSS file, best done with two or three converted surfaces to look at.
- Sprints F2a to F6 repaint the rest. The codemod and the sandbox toggle exist for them now.
