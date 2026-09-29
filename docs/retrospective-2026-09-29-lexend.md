# Retrospective — the product paints in Lexend (TD-310)

**2026-09-29. Web only. Small sprint (a site-wide visual change). Built by a subagent; NOT
committed, pushed or deployed — the lead and an adversarial reviewer own that.** Owner's ruling,
after a before/after of every public page at desktop and phone width, including the top-bar
defect: *"on 310, go."*

## What Was Built

- **The Home top bar fits a phone — done first, on its own.** `src/app/page.tsx`: the nav and its
  control cluster `flex-wrap`, the logo is `shrink-0`; `AuthButtons.tsx`: the "Log in ▾" toggle is
  `whitespace-nowrap`, as "Sign Up" already was. No new component, no wording change. (The house
  small-screen pattern is AppHeader's hamburger, but the Home bar has no nav links to hide; moving
  Home onto AppHeader would have changed the page. Wrapping was the brief's fallback.)
- **Lexend switched on.** `fontFamily.sans` leads with `var(--font-lexend)`; the `html` base rule,
  which carried its own plain `'Lexend'` copy, now reads `theme('fontFamily.sans')`; the dead
  Google `@import` is gone.
- **Money keeps tabular figures.** One rule in `globals.css`: `.tabular-nums:not(.font-mono)` paints
  in `var(--figures-face)` — IBM Plex Sans by default, Inter inside the sponsor portal.
- **Inter kept**: the sponsor portal uses it (`sponsor/(portal)/layout.tsx`), so nothing to remove.
- **Guards**: `fontSources.test.ts` +4, new `navLayout.test.ts` (4).

## Measurements

Chromium via Playwright against `next dev`, `*.supabase.co` and `fonts.googleapis.com` aborted;
painted fonts from the DevTools protocol (`CSS.getPlatformFontsForNode`). Full data, 42 screenshots
and the bites in the scratch folder `td310b/` (`report.json`).

| page | before (1280 / 390 / 360) | after (1280 / 390 / 360) |
|---|---|---|
| `/` en | Segoe UI · 414 px at 390 · 414 at 360 | **Lexend** · 1280 / 390 / 360 |
| `/` ms | Segoe UI · 432 · 432 | **Lexend** · 1280 / 390 / 360 |
| `/` ta | Nirmala UI · 588 · 588 | Nirmala UI (+ Lexend Latin) · **458 / 458** — TD-311 |
| `/about` en | Segoe UI · fits | **Lexend** · fits |
| `/about` ta | Nirmala UI · fits | Nirmala UI, Latin in Lexend · fits |
| `/scholarship/apply` | Segoe UI · fits | **Lexend** · fits |
| `/admin/login` | Segoe UI · fits | **Lexend** · fits |

The Home bar itself is 390 at 390 and 360 at 360 in all three languages, "Log in" 32 px tall (one
line). Tamil never paints in Lexend (it has no Tamil) — every Tamil glyph lands in Nirmala UI, so
no boxes. No request to Google on any page.

**Tabular figures.** Lexend's GSUB features: ccmp, dnom, frac, liga, locl, numr — **no `tnum`**;
digit advances 500–620 units. Plex: all ten digits 600. Inter: has `tnum`. In the page's own
stylesheet, `RM 1111.11` / `RM 0000.00`: Lexend plain 81.08 / 91.36 px; under `tabular-nums` (now
Plex) 88.16 / 88.16 px.

**Bundle.** First-load JS: median 228 → 228, worst 310 → 310, shared 87.2 → 87.2; the only route
line that moved is `/`'s page chunk 3.3 → 3.33 kB (first-load 231 both). Main CSS 105,786 →
105,938 B raw, 16,603 → 16,582 B gzipped.

## Bites (byte backup, `finally`, SHA-256 verified, each needle landed exactly once)

| injection | expected | result |
|---|---|---|
| (a) `sans[0]` back to plain `'Lexend'` | red | red (1) |
| (b) the Google `@import` put back | red | red (1) |
| (c) the whole top-bar change reverted | red | red (4); **in the browser the page went to 437 px at 390 and at 360** |
| (c1–c4) each top-bar class alone | red | red (1 each) |
| (e) the tabular rule dropped | red | red (1) |
| (f) the sponsor portal's Inter override dropped | red | red (1) |
| (g) the `html` rule back to its own `'Lexend'` copy | red | red (1) |
| (d) comment-only in the config and the page | green | green |

Restored tree re-measured in the browser afterwards: `/` at 360 = 360.

## What Went Well

- **Measuring before touching found the bar's real size.** The brief knew 414 → 437 in English;
  the first browser run also showed 432 in Malay and 588 in Tamil, so the fix was sized for the
  widest language, not the one in the brief.
- **Checking the font's feature table before the switch** turned a silent regression into a
  decision: 104 `tabular-nums` would have stopped lining up money columns with no test noticing.

## What Went Wrong

- **A declared font never painted, for months.** Symptom: the product said Lexend and showed
  Segoe UI. Root cause: two lines that each read as correct — a plain family name that nothing
  provides, and an `@import` that browsers ignore because of where it sat — and nothing measured
  the painted face; jest cannot lay out, computed style reports the declared list. System change:
  the guards pin the wiring (variable first, no Google `@import` anywhere under `src/`, the `html`
  rule reading the config), and lessons.md now says a look-change is proved by the painted font.
- **The Home page still scrolls sideways in Tamil (TD-311).** Symptom: 458 px at 390/360 after the
  bar was fixed. Root cause: the hero heading is 48 px on phones and a Tamil word does not fit; the
  bar's 588 px had hidden it. Not fixed: the only honest fix changes the English hero on phones
  too, which the owner has not seen. System change: raised TD-311 with the measurement to repeat.
- **The first `/code-review` saw an empty diff.** It ran from the workspace root, which is a
  different git repository; re-run against `Production/HalaTuju` it found nothing at its bar.
  Nothing to fix in code; the lead should aim the review at the project repo.

## The adversarial review — SHIP AFTER FIXES, four findings, all fixed

Every fix was made red-first: the guard was written, run and seen failing on the unfixed tree,
then the code changed.

| finding | what was wrong | fixed by | proof |
|---|---|---|---|
| **F1** MEDIUM | TVET requirement rows (`RequirementsCard.tsx`, general + special) were a label/value flex row with no wrap and no `min-w-0`; in Lexend three TVET pages reached 380–387 px at 360 | `flex-wrap gap-x-3 gap-y-0.5`, both halves `min-w-0 break-words` | sweep at 360 in en/ms/ta, 15 course pages + `/get-started` (48 renders): max `scrollWidth` **360**; with the fix reverted the same sweep reads **380** on 4 pages × 3 languages |
| **F2** MEDIUM | `/get-started`'s "Log in" broke onto two lines at 360 | `shrink-0 whitespace-nowrap`; its sentence `min-w-0` | button 34 px tall (one line) in en/ms/ta; reverted, **54 px** in en and ms |
| **F3** MEDIUM | figure cells never marked `tabular-nums` now jitter ("1,111,111" 56.5 px vs "8,000,000" 66.6 px) | added to billing usage (5), course-data coverage (6), invoice lines and totals (8) | `figuresFace.test.ts`: every right-aligned figure `<td>` in `src/` carries it (floored walk) |
| **F4** LOW | the Plex rule caught whole elements, so words changed face | moved to the figure (invoice cells, chart value span); dropped from 2 "Showing" sentences, the date range, and 9 inline figures in running text | `figuresFace.test.ts`: never on a table/row/list, never on a figure inside a `t(…)` sentence, never on a whole `t(…)` sentence |

The walk found three more sites of the F4 kind than the review listed (the reviewer outcome
legend, the payment-run card's Students, the sponsor terms "N of M") — moved the same way.

**The sweep's data.** The local database holds no courses and production is out of bounds, so the
course API was answered from fixtures: the reviewer's three course IDs drawn with EVERY requirement
key the serializer can send (read from `serializers.py`) and the three longest TVET institution
names in `data/tvet/uptvet_latest.csv`; ten more TVET pages with random subsets (seed 310); two
poly pages. That is harsher than any real page, which is why the reverted-fix run reproduced the
reviewer's overflow.

**Review bites** (byte backup, `finally`, SHA-256 verified, needles counted): F1 reverted → jest
red + browser 380; F2 reverted → red + 54 px; a billing cell and a course-data cell each stripped
→ red; the invoice `<tbody>`, the chart `<ol>`, a "Showing" sentence and the inline Merit figure
each given `tabular-nums` back → red; comment-only → green. One run stopped early on a needle that
matched twice (the invoice file has two `<tbody>`s) — the assertion fired before any write, the
needle was made unique, and the rest were run.

**Left as recorded.** The "→" arrow paints in Arial (Lexend has no arrow glyph; the browser falls
back per glyph) — LOW, cosmetic, not changed. Tamil Home 458 px (TD-311), `/search` Tamil toggle
375 px (TD-312, pre-existing), the raw requirement-type names on TVET pages (TD-313, content).

**What the review taught.** The first pass measured the pages the brief named; the defects were on
pages it did not (a course card, a sign-up box, admin tables). A face change is site-wide, so the
sweep must be too: every page TEMPLATE at 360, in all three languages, with its longest data.

## Design Decisions

See `docs/decisions.md` 2026-09-29 (TD-310): Lexend everywhere; `tabular-nums` paints in Plex via
`--figures-face` (one rule rather than 104 edits; the sponsor portal keeps Inter).

## Numbers

- jest **3,135 / 179 → 3,143 / 180 → 3,150 / 181** after the review fixes (`npm run gates`:
  typecheck, lint, i18n, test — all green).
- pytest **7,194 passed / 3 skipped** (`pytest -q -n auto` in `halatuju_api`), before and after
  the review fixes.
- First-load JS after the review fixes: median 228, worst 310, shared 87.2 — unchanged; four page
  chunks moved by 0.01–0.03 kB (`/`, `/admin/course-data`, `/course/[id]`, `/get-started`).
- Files: 18 web source/test (2 new tests); 6 docs.
