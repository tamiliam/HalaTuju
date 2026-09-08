# Retrospective — one layout standard for the console

**Date:** 2026-09-08
**Worktree:** `.worktrees/console-layout`, branch `feat/console-layout`
**Migration:** none. No Python changed at all.

---

## What the owner asked

Five screenshots, side by side, and one sentence: *"All are in desktop view, but the table width,
even alignment, is not standardised. I think standardisation would elevate the design. This must be
done both for desktop view and mobile view. If something cannot be seen in mobile view, it must be
communicated, and not allowed to break silently."*

That last clause is the whole sprint. The width was the visible complaint; the phone was the real
defect.

## What the survey found

Measured across 35 admin pages and 14 tables, before any code:

| | |
|---|---|
| Distinct page widths in use | **8** (`max-w-4xl` ×8, `5xl` ×6, full-bleed ×7, `3xl`, `2xl`, `xs`, `md`, `full`) |
| Shared page container | none |
| Shared table component | none — 14 tables built 14 times |
| Tables that scroll properly on a phone | 6 |
| Tables that **squash** (no minimum width) | 5 |
| Tables **clipped with no scrollbar** | **2** — Intake years, Course data |
| Screens that tell you there is more to the right | **0** |
| Pages that centre themselves | 1 (the B40 cockpit) |
| Table header styles | 2 (38 places vs 18) |
| Card radii | 3 (`rounded-lg` 284, `xl` 62, `2xl` 44) |

## The centring, answered

The owner asked whether the B40 application page's centring was design or oversight. It was one
line — `mx-auto max-w-6xl` — added on **30 May 2026** in a commit titled *"modern, compact
applicant-detail redesign"*. That message describes the header bar, the card masonry and the
two-column action grid in detail and **never mentions width or alignment**. It moved house on
2 September when the file was split, unexamined.

Not senseless, though: it was the only page with a maximum width, so it was the only page that ever
had spare room to distribute. The fault was not the centring — it was that one page had a limit and
no other page shared it.

## What shipped

**One home for the width.** `lib/pageWidth` holds the rule and `AppShell` applies it, so the width
is not something a page has to remember. Fifteen pages had their own `max-w-*` deleted. Longest-
prefix matching lets a detail page below a table page read narrow — `/admin/scholarship` is wide,
`/admin/scholarship/143` reads.

**One shell for every table.** `TableFrame` keeps three promises, and each half is load-bearing:
the card clips only its corners while a *separate* element scrolls; a `minWidth` floor keeps
columns in shape; and a measured edge cue plus a sentence says there is more. The cue is measured,
never assumed — it appears when content is actually hidden and goes when you reach the end.

## What went wrong

**1. A guard that a file could satisfy by importing something.**
*Symptom:* bite-check 3 — putting Intake years back into a clipping card — **passed**. *Cause:* the
test asked `/TableFrame/.test(src)`, and the file still carried the import line. *Fix:* count
`<TableFrame` against `<table` per file. *And the fix immediately earned its keep*: it found a real
miss the same minute — the **Payments funding table**, which my own survey had never seen because
the survey counted one table per file. A guard weak enough to pass a deliberate fault was also weak
enough to hide a real one.

**2. Five invented i18n keys.** I wrote `label={t('admin.staff.title')}` and four like it for the
frames' accessible names. None existed. jest caught two of them only because `admin.sponsors.*` has
a usage test; the other three would have shipped, rendering a raw dotted string as a screen
reader's name for the table — invisible on screen, and invisible to the i18n parity check too,
because the key would be missing from all three locales identically. *Fix:* a test that reads every
`label={t('…')}` out of the source and resolves it against `en.json`.

**3. A test pinned the markup instead of the behaviour.** The Sources test found its panel with
`closest('div[class*="overflow-x-auto"]')`. That class moved into the frame, so the test broke
while the behaviour it protects — the registry stays mounted but hidden — was untouched. It now
addresses the panel by test id.

## Numbers

| Gate | Result |
|------|--------|
| jest | **1828** (+10) |
| `next lint` | 0 errors |
| `tsc --noEmit` | 24 (baseline; the two my test added were removed by avoiding `matchAll`) |
| i18n | **4868 × 3** (+1 key: the scroll sentence) |
| `next build` | compiled successfully |
| pytest | not run — **no Python file changed** |

Three bite-checks landed (a page taking its width back, the cockpit centring itself, Intake years
returning to a clipping card) and one deliberately did not, which is written up above.

## Not in this sprint

Card layouts for lists on phones. Only the Students page has one, and extending it changes *what
each screen shows*, which needs the owner's eye per screen. Named as a separate job in the plan he
approved.

## The lesson worth carrying

A guard is only as strong as the cheapest way to satisfy it. "Does this file mention the safe
component?" is satisfied by an import; "does every table have a frame?" is not. The difference
between those two questions was one real defect, found by accident, in a file I had already
surveyed.
