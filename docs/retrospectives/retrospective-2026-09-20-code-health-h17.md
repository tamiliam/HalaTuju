# Retrospective — Code health H17: one locale per visitor, and the route that told me the scope was short

**Date:** 2026-09-20 · **Sprint:** code health H17 (Phase 5 opens — the first sprint of the arc
that is **not** moves-only) · **Cost:** ~5h against the ~5h estimate.

Every visitor to HalaTuju used to download 1.53 MB of raw JSON — English, Malay **and** Tamil —
to read one language of it. They now download one. **The median route fell from 478.5 kB of
first-load JS to 255.5 kB**, measured from two real `next build` runs, and not one word on one
screen changed in any language.

Phase 4's proof does not apply here. "Green suites on identical counts" says nothing about a
sprint whose entire point is that the browser fetches different bytes, so the acceptance was a
measurement, and the interesting part of the sprint was **a number that disagreed with the plan**.

---

## What Was Built

| | before | after |
|---|---|---|
| modules naming `@/messages/*.json` statically | **3** (`i18n.tsx`, `scholarship.ts`, `applyCopy.ts`) | **3**, but each confined — see below |
| catalogues in the root layout chunk | en + ms + ta (1.53 MB raw) | **en only** |
| median first-load JS, 88 routes | **478.5 kB** | **255.5 kB** |
| worst route | `/profile`, 562 kB | `/admin/scholarship/[id]`, 389 kB |
| shared-by-all chunk | 87.1 kB | 87.2 kB |
| routes that shrank / grew / unchanged | — | **74 / 11 / 3** (the 11 grew by 0.1–1.0 kB) |

Four production modules and two new test files:

1. **`src/lib/messages.ts` (new)** — the loader, and the one place in the application where
   `@/messages/*.json` is written. English is static; Malay and Tamil come through `import()` with
   **literal** specifiers. Loaded catalogues are cached for the life of the tab.
2. **`src/lib/i18n.tsx`** — the provider carries ONE catalogue, in the same piece of state as the
   locale it belongs to, and the fetch is kicked off at module evaluation rather than from an
   effect.
3. **`src/lib/preUPlan.ts` (new)** — `preUTrackMalay` and its `ms.json` import leave
   `lib/scholarship.ts`, which fifteen route pages import.
4. **`src/lib/applyCopyPlatform.ts` (new)** — `platformApplyCard` and its three catalogue imports
   leave `lib/applyCopy.ts`, which a student-facing page imports. `ApplyCopyTab` reaches the new
   module through an `import()`.

| Route | before | after |
|---|---|---|
| `/` | 483 kB | **259 kB** |
| `/dashboard` | 504 kB | **280 kB** |
| `/scholarship/apply` | 538 kB | **314 kB** |
| `/profile` | 562 kB | **339 kB** |
| `/admin/scholarship/[id]` | 515 kB | **389 kB** (TD-280) |
| shared by all | 87.1 kB | 87.2 kB |

---

## What Went Well

1. **Two builds, not an argument.** H13's lesson — *"an argument for why a number is fine is not a
   number"* — was the whole method here. The baseline build ran before a line was edited, and the
   route table it printed is the only reason the sprint knows what it did. It is also the only
   reason the sprint knows what it had NOT done: see What Went Wrong 1.

2. **All three baselines were measured before anything moved, and all three matched the brief.**
   pytest 7,043 / 3 skipped, jest 2,934 / 160, and the full route table. H13 paid for this lesson
   the hard way and H17 got it for the cost of two background commands.

3. **One piece of state was the whole anti-flash design.** The obvious shape — `locale` in one
   `useState`, `catalogue` in another — has a render in which `locale` says Tamil and the words on
   screen are still English. That is the flash the brief forbids, and it is not a race that shows
   up on a dev box. Keeping them in one object makes it unrepresentable, and
   `localeDelivery.test.tsx` asserts it ("the locale and the words it names change TOGETHER")
   rather than leaving it to a comment.

4. **The fetch starts before React does.** A returning Tamil reader has *always* seen English
   first — the server cannot read `localStorage`, so the HTML it sends is English and the browser
   paints it before hydration. What this sprint could have ADDED is a second, longer wait: English
   on screen until an effect fires after hydration and only then asks for `ta.json`. Kicking the
   load off as the module is evaluated removes that; on every visit after the first the chunk is
   in the HTTP cache and the swap is synchronous.

5. **The guard sweep was ten minutes and found the cross-tree reader before it mattered.**
   `apps/scholarship/tests/test_card_display.TestTrackLabelParity` reads
   `halatuju-web/src/messages/ms.json` **by path**, for exactly the sixteen labels
   `preUTrackMalay` uses. The JSON did not move, so it survived — but bite (f) proved it still
   bites rather than assuming so, in both runtimes at once.

6. **Six bite-checks, all six behaved. No silent bite.** Byte backup, SHA-256 verified before and
   after, needle proved unique, restored in a `finally`.

---

## What Went Wrong

### 1. The scope named one file. There were three, and only a BUILD could say so.

The roadmap's H17 scope reads: *"`src/lib/i18n.tsx` statically imports all three locale files
(1.53 MB) into every client bundle."* True, and the largest part of it — but two other production
modules held a static catalogue import:

- **`lib/scholarship.ts`** imported `ms.json` for `preUTrackMalay`, and **fifteen route pages
  import `lib/scholarship`**. A grep found this one before any code was written.
- **`lib/applyCopy.ts`** imported all three for `platformApplyCard`. The grep found it too, and
  **I reasoned my way past it**: `platformApplyCard` is called only by the admin Apply-copy tab,
  so making that tab's import lazy would confine the catalogues to one panel. That reasoning was
  correct about `platformApplyCard` and wrong about the FILE. `applyCard` — a different function,
  in the same module, reading no catalogue at all — is imported by `/scholarship/apply`, a
  student-facing page.

Nothing failed. `tsc`, lint, 2,953 jest tests and `next build` were all green, and the change
looked finished. The build's route table said otherwise: every route had fallen to about 260 kB
and **`/scholarship/apply` was sitting at 539 kB**, one kilobyte *above* where it started. Its
page size had gone from 8.31 kB to 135 kB, which is the shape of a module that has just absorbed
something the layout used to carry for it.

The fix was a four-line split: `platformApplyCard` into `applyCopyPlatform.ts`, `applyCard` left
where it was with a comment saying why nothing in that file may import a catalogue. `/scholarship/apply`
then read **314 kB**.

**The lesson is not "grep harder" — I did grep.** It is that a module is not a unit of
consumption. Two functions in one file have one import graph between them, so a heavy dependency
that only one of them needs is paid for by every caller of either. No test in this repository
could have seen that, because it is not a correctness property; the route table is the only
instrument that reports it, and it only reports it *after* the change.

### 2. The acceptance's number was in the wrong place, and no route could ever have met it.

*"First-load JS for `/` down by roughly three-quarters."* `/` fell 483 → 259 kB — **46%**. The
target was unreachable by any change of this kind, because **87 kB of React, the Next runtime and
the shared chunk is the floor** for every route in the application, and the catalogues were never
in that shared chunk at all: they sat in the root LAYOUT chunk, which is reported inside each
route's own first-load figure. Three-quarters off 483 kB is 121 kB, which is below the floor.

This is H14's lesson and H16's lesson for the third time — *a target inherited from a differently
shaped predecessor needs its own arithmetic before it is accepted* — and H17 did the arithmetic
only after the first build. Ten minutes with the baseline route table on day one would have said
so, and would have turned a missed number into a re-stated one.

### 3. A budget was asked for, and the honest answer was to refuse it.

The brief offered: add a ratcheting first-load-JS number to `code-standards.json` if it is cheap.
It is not cheap, and the reason is worth writing down. **That number exists in exactly one place —
the route table `next build` prints — and nothing that runs in a test builds.** jest has no build
output; `code_health.py` does not build either. A kilobyte figure written into the ledger today
would be read by nobody, enforced by nothing, and would *look* enforced, which is worse than an
empty column.

What H17 wrote instead is the SOURCE rule, in `oneLocalePerVisitor.test.ts`: no production module
outside a three-entry, reasoned exemption list may statically import a catalogue. That is the
thing that actually caused the 1.53 MB — somebody wrote an entirely reasonable import line — and
it bites in jest today. The byte budget is TD-281, inside H18, and its first task is a reader.

### 4. 130 kB for sixteen words, and it is not mine to fix.

`/admin/scholarship/[id]` is 389 kB against ~256 kB for every other route. The whole difference is
`ms.json`, kept for `preUTrackMalay` — **sixteen Malay pre-U track labels** shown to an officer who
is usually reading English. It cannot be lazy: there is no `ms` catalogue in memory to answer from
and no loading state to hang a label off, so a lazy version would blank a word the officer is
reading mid-render.

The cheap fix is a guarded copy of sixteen strings with a drift test — and the owner has
**already ruled for exactly that**, on 2026-07-18, when the backend kept `card_display._TRACK_LABEL`
beside the same block with `TestTrackLabelParity` guarding it. A bundle boundary is the same kind
of boundary as a process boundary, so the precedent fits.

I did not take it. Adding a third home for a string that two files go out of their way to say has
one home is a decision about single-source-of-truth, and this sprint's brief says a string is the
owner's, not an engineer's. What H17 did instead was **confine** it: from fifteen route pages to
one. The number, the three ways out and the precedent are in TD-280, priced.

---

## Bite-checks

Six, each with a byte backup, a SHA-256 verified before and after, a needle proved unique, and a
restore in a `finally`. All six behaved; **none was silent.**

| | bite | expected | result |
|---|---|---|---|
| (a) | the loader always returns English | a named test red | **8 of 13** in `localeDelivery` red — both switcher arms, the stored-locale arm, the loader's own "hands back the catalogue that was ASKED for". The 5 that stayed green are the English-only and key-absence cases, which is right. |
| (b) | a key leaves `ta.json` | the parity test red | `namespaces-i18n` → *"scholarship › en / ms / ta hold the identical key set"*, 1 of 92 red |
| (c) | `getNestedValue` returns `''` instead of the key | a named test red | `localeDelivery` → both *"the fallback still falls back"* tests red. This is the TD-259 idiom, and it is what `tOr` is built on. |
| (d) | all three catalogues imported into `i18n.tsx` again | the budget test red | `oneLocalePerVisitor` → *"only the declared modules statically import a message catalogue"* **and** *"the provider itself imports no catalogue at all"* |
| (e) | **NO-CRY-WOLF:** one trailing space inside a comment | everything green | **2,954 / 162, exit 0** |
| (f) | one Malay label changed in `ms.json` | both guards red | web `scholarship.test.ts` red **and** api `TestTrackLabelParity` red — the move did not orphan either. |

Bite (f) was added because it is the failure this arc has met four times: a guard that quietly
covers less after a move and goes on passing. `preUTrackMalay` changing files is exactly that
shape, so it was proved rather than assumed.

---

## Gates

| | |
|---|---|
| pytest | **7,043 passed / 3 skipped** — IDENTICAL to the baseline, no api file touched |
| jest | **2,954 / 162 suites** (2,934 / 160 before; +20 new tests, +2 suites) |
| existing test expectations edited | **none.** Two import lines were re-pointed at the module that now holds the function (`scholarship.test.ts`, `applyCopyDraft.test.ts`) — the H13/H15/H16 precedent — and one comment added beside each saying so. |
| `tsc --noEmit` | 0 |
| `next lint` | 0 errors; no new warning on any file touched |
| i18n check | 5,389 keys per locale, all three, 0 warnings |
| `next build` | exit 0, 88 routes |
| `manage.py check` | 0 issues |
| `makemigrations --check --dry-run` | *No changes detected* |
| `code_health.py` (read-only) | **0 FAIL**, 6 WARN (H16's set, unchanged): `fix%` 42, `big` 17, `long` 15, `dup` 4, `mirror` 3, `guard%` 20. `std` **ok**, `xapp` **45**, `hot#1` `officerCockpit.ts` 49 — all three unmoved. |

`code-standards.json` was **not edited**. No ledger key moved, so no `_moved` record was needed:
`scholarship.ts` and `applyCopy.ts` both keep their own paths (H13's rule), and the two new
modules are 39 and 52 lines, far under the 600-line standard for a new file. `scholarship.ts`
shrank 1,342 → 1,326 lines, which is inside the budget's shrink slack, so no ratchet was owed.

**Findings raised:** TD-280 (130 kB of `ms.json` for sixteen labels on the officer cockpit — an
owner decision, priced, with the 2026-07-18 precedent), TD-281 (the byte budget has no reader that
runs in a test; H18's first task).

---

## For H18

1. **Build the reader before you write a number** (TD-281). And key it on a route path with
   `_moved` from day one — the first route rename has TD-272's problem exactly.
2. **The new low is median 255.5 kB, worst 389 kB, floor 87 kB.** Put the floor in the ledger's
   header or somebody will set a target no route can reach.
3. **Pinning 389 kB for `/admin/scholarship/[id]` blesses TD-280; pinning 256 kB refuses it.** Ask
   first.
4. **Budget ~6h of the 9 for the QUERY half.** It is now the larger half: H17 learnt nothing that
   makes the applicant-detail N+1 cheaper, and that endpoint has been unmeasured since June.
5. **A recorded Playwright run per locale** is still worth an hour. H17's acceptance asked for one
   and settled for a rendered jest test; the test pins what the first paint HOLDS, which is the
   important half, but only a browser can time it.
