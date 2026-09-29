# Retrospective — a way back to "All gifts" (TD-302)

**2026-09-29. Web only. Built by a subagent; NOT committed, pushed or deployed — the lead and an
adversarial reviewer own that.** Owner's pick from TD-302's own option.

## What Was Built

- **"All gifts" in the breadcrumb's gift menu** (`ScopeSwitcher.tsx`): a first menu entry that
  calls `select('')`. `BreadcrumbScopes` offers it when the page's path is exactly one of
  `READS_ACROSS_GIFTS` (`/admin/scholarship`, `/admin/programme/overview`), a gift is chosen, and
  the scope is `ambiguous` (two or more LIVE gifts). The shell passes `usePathname()` in; the test
  harness `GiftScope` passes jsdom's `window.location.pathname`, so every `page.url.test` sees the
  crumb its real page would get.
- **The address follows to "no gift"** (`useGiftInUrl`): the `!chosen` early-return is gone, so a
  change of `chosen` to `''` rewrites the address with `router.replace` like any other change.
- **`withGift(href, '')` removes `?programme=`** (other query kept; a bare href is still returned
  untouched). No existing caller passes an empty code with an href that already carries a gift
  (`GiftProgrammes` builds from literal paths; `withGiftHrefs` returns early on `''`), so no
  existing output changes.
- New key `admin.shell.allGifts`: **"All gifts" / "Semua pemberian" / "எல்லாக் கொடைகள்"** — the
  exact phrases the codebase already uses for "every gift" (`giftEvery`), and the same nouns the
  crumb itself uses ("Pilih pemberian", "ஒரு கொடையைத் …"). Not "Semua hadiah": `hadiah` appears
  in ms too, but the crumb says `pemberian`, and the entry sits in the crumb.
- One sentence in the admin manual (`basics-programme`).

## Design Decisions

- **Absent, not disabled, when nothing is chosen.** The page already reads across gifts then (its
  heading says so), so the entry would change nothing; a disabled item would need a reason line
  (the `MenuItem` rule) to explain a no-op.
- **Single-gift tenants (item 3): never offered.** Read from the scope rather than the pages: with
  one live gift, `select('')` resolves `chosen` straight back to that gift (the provider's
  single-gift auto-resolve), so Applications and the Overview would show exactly the same thing.
  With one gift and nothing else the crumb is plain text anyway; with one live gift and a DRAFT
  (a two-item menu), "All gifts" would silently switch to the live gift — so the test is
  `ambiguous` (live gifts), not the menu's length. Pinned by a rendered test.
- **The URL is written in ONE place.** The menu entry only selects; `useGiftInUrl` rewrites the
  address, as it already does for a gift. A second writer in the shell would have needed the
  router and could disagree with the first. The cost: a gift → `''` change from any cause now
  strips the query — the only other cause on a list page is a scopes reload that no longer holds
  the gift, where stripping is the truthful answer.
- **The Overview's round resets with no code change.** `chosenIntake` is keyed on the gift, so
  `programme` going to `undefined` already made the stale round inapplicable; the rendered test
  shows the re-read goes out as `{programme: undefined, intake: undefined}` and the picker reads
  "all rounds".
- **No `!pinned` clause.** It was written and a bite showed it SILENT: a pinned crumb is `locked`
  and renders as plain text before any menu exists, and no pinned page is on the list. Removed as
  dead code; the bite now targets the `locked` guard that actually does the work.
- **`navigation.ts` untouched** (672/675). The path list lives beside the only code that reads it.

## What Went Well

- The existing harnesses (`GiftScope`, `giftUrl`'s address-moving router) made every case a
  rendered test of what a person would notice — the address bar and `history.length`.
- Bundle: no route's first-load figure moved; the two page entries moved by 0.1 and 0.01 kB.

## What Went Wrong

- **My first baseline `npm run gates` came back 1 failed / 3,094 passed** — because I began
  editing `ScopeSwitcher.tsx` while it ran, and the namespace guard caught a key used before the
  message files held it. The count (3,095 / 175) matched the brief; a baseline must be taken on an
  untouched tree, and I measured the bundle baseline properly (on a stashed tree) for that reason.
- **Tests were written after the code, not red first.** The bites below stand in for the red run:
  each behaviour's test was shown failing with that behaviour removed.

## Bite-checks (original bytes restored in a `finally`, verified by SHA-256; every needle matched exactly once)

| Bite | Result |
|---|---|
| (a) entry calls `select(firstGift)` instead of `''` | red, 3 failed |
| (b) `router.push` instead of `replace` | red, 4 failed |
| (c) offered on Payments | red, 2 failed |
| (d) the `ms` key dropped | red, parity test (1 failed) |
| (e) comment only | green |
| (f) shell stops passing the path | red, AppShell test |
| (g) the address does not follow to "no gift" | red, 3 failed |
| (h) `withGift` keeps the old gift | red, 3 failed |
| (i) offered with nothing chosen | red, 2 failed |
| (j) offered without two live gifts | red, 1 failed |
| (k, first form) `!pinned` removed | **SILENT** — dead clause; removed (see above) |
| (k) the pinned crumb unlocked | red, 2 failed |

## Numbers

- jest **3,095 / 175 → 3,116 / 176** (+21 tests, +1 suite); pytest **7,117 / 3 skipped** (unchanged).
- Bundle median **227 → 227 kB**, worst **310 → 310**, shared 87.2; headroom unchanged.

## What Is Still Open

TD-301 (the Overview's late reply), TD-303, TD-304, TD-305, TD-289, TD-299, TD-297. The owner's
eye on the Tamil and Malay wording.
