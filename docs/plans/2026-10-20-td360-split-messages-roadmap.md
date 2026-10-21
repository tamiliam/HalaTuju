# TD-360: split the English message file by audience — roadmap

**Owner decisions (2026-10-21):** approved. "Yes" to all three open questions: (1) do the admin split
only now, park the scholarship / sponsor split (Sprint 2) behind its trigger; (2) lower the 300 kB
"must be named" ceiling to 250 kB in Sprint 1; (3) accept the brief English flash for a Malay / Tamil
staff member on the first admin load in a tab (no spinner).

**Status (2026-10-20):** PLAN, written on `td360` (base `6aec3206`). Not billed (hygiene). The owner
approved doing it now, before request #39 Sprint 4 (the staff permission editor), because the median
route has **0.167 kB** of room under its 229 kB line and Sprint 4 adds admin strings.
**Workflows followed:** `Settings/_workflows/implementation-planning.md`. Not a money / identity /
eligibility sprint, so `sprint-start.md` step 3b is not mandatory; a door list is given anyway
because a missing key on a screen is how this change would fail.

---

## The problem in one paragraph

Every route that uses `t()` downloads the WHOLE English catalogue (`src/messages/en.json`, 97.4 kB gz,
5,400+ keys). It sits in chunk `1703-*.js` (101.0 kB gz with the i18n code), which is in the **page
entry** of 74 of 89 routes, so it is counted in every budgeted figure. Any new string, even one only an
org admin will ever read, moves the median and all three ledgered student lines. **More than half of
the file (the `admin.*` namespace: 2,918 keys, 49.9 kB gz) is read only by the admin console.**

## How i18n works today (read 2026-10-20)

| Piece | What it does |
|---|---|
| `src/lib/messages.ts` | The ONE static catalogue import: `import en from '@/messages/en.json'` (`FALLBACK_CATALOGUE`). Malay and Tamil come by two LITERAL `import()` specifiers (a computed one would make webpack bundle the whole folder). Loaded catalogues are cached for the tab. |
| `src/lib/i18n.tsx` | `I18nProvider` (state = `{locale, catalogue}` in ONE commit), `useT()`, `tOr()`. Warm start: the stored locale's chunk is fetched as the module evaluates. `setLocale` commits only once the words are in memory and rejects on failure. `contentLocale` is DERIVED by identity: `catalogue === FALLBACK_CATALOGUE ? 'en' : locale`. `t()` = nested lookup, returns the key itself if missing, then branding interpolation. |
| Layout tree | `app/layout.tsx` → `Providers` (`QueryClient` › `BrandingProvider` › `I18nProvider` › `AuthProvider` › `ToastProvider` › `AuthGateModal`). Sub-layouts: `app/admin/layout.tsx` (client, guard + `AppShell`), `app/sponsor/layout.tsx`, `app/sponsor/(portal)/layout.tsx`, `app/sandbox/layout.sandbox.tsx` (compiled out of production). Student routes have **no** shared route group. |
| SSR | Always English (the server cannot read `localStorage`); the first client paint is English too. `HtmlLang` sets `<html lang>` from `contentLocale`. |
| `scripts/bundle-budget.js` | Reads `next build`'s route table, re-measures each route's PAGE entry exactly from `.next/app-build-manifest.json` (gzip level 9). Fails: a route ≥ 300 kB (`CEILING_KB`) not in the ledger; a ledgered route over its line; the median over `first_load_js_median_kb`; **the ratchet** — a line more than 2 kB (`SHRINK_SLACK_KB`, `MEDIAN_SLACK_KB`) above the build must be LOWERED; locally, less than `NEAR_LINE_KB` = 0.15 kB of room (the gate passes `--gate` and only prints it). Prints, without budgeting, the **first-paint** figure (page + every layout). |
| `scripts/check-i18n.js` (`npm run i18n`) | Reads the three files BY PATH: parse, en/ms/ta key parity, no empty values. |
| `src/messages/__tests__/namespaces-i18n.test.ts` | Every `t('<ns>.…')` literal resolves in `en.json`; per-namespace parity; dynamic families enumerated in `DYNAMIC`. |
| `src/lib/__tests__/oneLocalePerVisitor.test.ts` | Only `lib/messages.ts` (en) and `lib/applyCopyPlatform.ts` (reached by `import()` from `ApplyCopyTab`) may statically import a catalogue; ms/ta must be literal `import()`s. ⚠ Its regex matches `'@/messages/(en|ms|ta).json'` exactly — a `?slice=` specifier would make it go BLIND (see risks). |
| Sol (`50c786c7`) | Translation review happens in Sol: `sol_tag --project halatuju --tag "<sprint>" --new`; `Development/Sol/projects.yaml` maps HalaTuju to `halatuju-web/src/messages/{en,ms,ta}.json` BY PATH. |
| Other readers by path | ~40 jest tests import the whole files (consent snapshot, consent text, placeholder parity, cockpit renders…); backend tests read them from Python (`test_requirements.py` reads `en.json`; `test_card_display.py` reads `ms.json` `scholarship.apply.plan.*`); migration 0098 cites them. **No runtime backend code and no email reads the message files** (emails are Python templates, listed separately in Sol's `outside.yaml`). |

## Measurements (build of `6aec3206`, 2026-10-20, this machine)

**Whole files:** en 378.6 kB raw / 103.4 kB gz (97.4 kB gz minified, as shipped); ms 402.2 / 98.7 gz;
ta 872.7 / 128.9 gz. **Build:** 89 routes, median **228.833 kB** (line 229, 0.167 kB of room, "0 routes
may cross before the median does"), worst 273.611 (`/scholarship/application`, line 274); first-paint
median 258.989. 39 of the 89 routes are `/admin/*`.

**Top-level namespaces (en, gz measured alone; the marginal figure is what removing it saves):**

| Namespace | Keys | raw kB | gz kB | Read by |
|---|---|---|---|---|
| `admin` | 2,918 | 156.4 | 50.7 (**49.9 marginal**) | admin console only (+ sandbox) |
| `scholarship` | 1,412 | 100.7 | 30.1 (29.3 marginal) | student scholarship screens, profile, dashboard; the cockpit reads `scholarship.apply` + `scholarship.docs`; `AppHeader` reads 3 keys |
| `sponsorPortal`, `sponsorAuth`, `sponsorPool`, `sponsorLanding` | 381 | 18.9 | 6.1 marginal | sponsor portal and `/sponsor` landing |
| the other 27 (`common`, `profile`, `onboarding`, `authGate`, `courses`, `apiErrors`, `errors`, …) | ~700 | ~34 | ~11.9 together | everyone |

Biggest `admin.*` children: `scholarship` (cockpit) 16.4 gz, `sponsors` 5.4, `orgSettings` 3.9,
`billing` 3.1, `requests` 3.0. Biggest `scholarship.*`: `actionCentre` 7.4, `docs` 6.2, `apply` 4.9.

**Who reads `admin.*` (static scan of literals and template prefixes, then importers traced):** every
file holding an `admin.*` key is under `app/admin`, `components/admin`, or a component / lib module
whose ONLY importers are under `app/admin` (`components/contracts|emails|reviewers|sources`,
`components/sponsors/*` except `SponsorTermsWizard`, `Pagination`, `DocViewer`, `AiReliabilityCard`,
`lib/navigation.ts` and its importers, `lib/applicationStatus|blockers|closeOffer|disbursement|
invoices|…`). The sponsor portal's `SponsorTermsWizard` reads `sponsorPortal.terms.*` only. **No
student, public or sponsor-portal route reaches an `admin.*` key.** The audience line is clean today;
the guard below keeps it so.

**Dynamic keys:** 374 template-literal sites and 342 `t(variable)` sites. Only three build a key from
a bare namespace (`courses.${id}`, `theme.${m}`, and `admin.${h}` in `components/admin/InvitationsTable`),
and all three stay inside one audience. Because the split is by TOP-LEVEL namespace, a dynamic key is
safe as long as its first segment is in the slice its route loads, which is what the guard checks.

## The approach (Sprint 1): two slices, cut at build time, one source file

**Slices.** `core` = every top-level namespace EXCEPT `admin` (so a new namespace defaults to core and
can never go missing); `admin` = `admin` only. Scholarship and sponsor slices are Sprint 2, deferred
(open question 1).

**The three message files stay exactly as they are** — one file per language, every key, same path.
Sol, `check-i18n.js`, the backend tests, the consent snapshot and ~40 jest tests keep reading them
unchanged. Moving keys into new files would touch all of those and Sol's import for no runtime gain.

**Cut at build time by a tiny webpack loader.** `import enAdmin from '@/messages/en.json?slice=admin'`;
a rule in `next.config.js` (`resourceQuery: /slice=/`) runs `scripts/messages-slice-loader.js`, which
returns only the named top-level namespaces (a pure `pickSlice(json, name)` it exports for jest).
TypeScript gets an ambient `declare module '*.json?slice=core'` / `'*.json?slice=admin'`; jest gets a
`moduleNameMapper` that maps `?slice=` imports to the whole file (a superset, so no existing test
changes meaning). **Spike first (1 h, time-boxed):** if TS, Next 14.2's webpack or `next dev` will not
take the query, the fallback is a prebuild script writing gitignored slice files — same runtime design,
one extra build step. Decide at the spike, before anything else is written.

**Runtime — one provider, no second context:**

1. `lib/messages.ts` statically imports `en.json?slice=core` as `FALLBACK_CATALOGUE`, and keeps a
   small registry of REQUIRED slices. `loadCatalogue(locale)` loads `core` plus every required slice
   for that locale in parallel, all by LITERAL specifiers (`ms`/`ta` × `core`/`admin` = 4), and merges
   them into ONE catalogue object per locale.
2. `lib/messagesAdmin.ts` (new): statically imports `en.json?slice=admin`, merges it INTO the existing
   English catalogue object (`Object.assign`, so `FALLBACK_CATALOGUE` keeps its identity and the
   `contentLocale` derivation is untouched), marks `admin` required, and warm-starts the stored
   locale's admin chunk, all at module evaluation (the `i18n.tsx` pattern).
3. `app/admin/layout.tsx` (and the sandbox layout) import `@/lib/messagesAdmin` for its side effect.
   Module evaluation precedes the layout's render, so SSR and the first paint have the admin words:
   **no flash of dotted keys, no hydration mismatch** (server and client both render English).
4. `I18nProvider` subscribes to the registry (a version counter) so a slice arriving after commit
   re-renders. `setLocale` already waits for `loadCatalogue`, which now waits for every required
   slice: a switch on an admin page commits only when core AND admin are in hand, and rejects if either
   fails (today's rule, unchanged).
5. **The one new state:** a staff member who has been browsing the public site in Tamil and then opens
   `/admin` in the same tab. Core-ta is in memory, admin-ta is not. `t()` falls back to ENGLISH for a
   namespace that is ABSENT (never for a missing key — `tOr` and the key-echo rule are unchanged) until
   the chunk lands, then re-renders in Tamil. A few hundred ms, first time only (open question 3).

`applyCopyPlatform.ts` (reads `scholarship.apply` of all three locales through an `import()` in one
admin panel) is left alone: it is lazy and admin-only.

## Expected gain (estimate from the measured build; the sprint records the real numbers)

| Route | Today (page entry) | After Sprint 1 | Real gain for the reader |
|---|---|---|---|
| Median (45th of 89) | 228.833 | **≈ 178.9** (−49.9) | — |
| `/scholarship/application` (line 274) | 273.611 | ≈ 223.7 | −49.9 kB, real |
| `/profile` (line 271) | 270.306 | ≈ 220.4 | −49.9 kB, real |
| `/scholarship/apply` (line 244) | 243.716 | ≈ 193.8 | −49.9 kB, real |
| `/`, `/course/[id]`, `/search`, sponsor portal… (35 non-admin routes with en in the page) | | −49.9 each | real, first-paint too |
| 39 `/admin/*` routes | | −49.9 PRINTED | **≈ 0 real**: the admin words move into the admin LAYOUT chunk, which the budget does not count (TD-304's warning). First-paint is unchanged. |
| A Malay / Tamil student (lazy chunk, not budgeted) | ms 98.7 / ta 128.9 gz | ms 48.0 / ta 62.9 gz | −50.8 / −65.9 kB, real |

**What it fixes in TD-360's terms:** an `admin.*` string (54% of all keys, and every string request #39
Sprint 4 will add) then moves **no budgeted line at all** — only the admin layout, which is printed in
the first-paint line. A student / public / sponsor string still moves every non-admin route and the
three ledgered lines, but over a core of 47.5 kB gz instead of 97.4 (Sprint 2 would narrow that).

**Ratchet — yes, the budgets MUST be lowered in the same sprint.** The house rule is mechanical:
`bundle-budget.js` FAILS when a line sits more than 2 kB above the build, and every line is then
recorded at about the build plus 1–2 kB, never at the printed figure (TD-309, TD-300, TD-352, all
noted in `code-standards.json` `last_tightened_on`). Expected: median 229 → **~181**; `/profile`
271 → **~222**; `/scholarship/apply` 244 → **~195**; `/scholarship/application` 274 → **~225**.
So the 50 kB does NOT become 50 kB of headroom: room goes from 0.167 kB to the usual 1–2 kB, and the
gain is that every visitor downloads ~50 kB less and admin strings stop eating the room. With 1–2 kB
of room on both student lines, **TD-344 closes and `NEAR_LINE_KB` is raised 0.15 → 0.25** as that
entry asks. Lowering `CEILING_KB` is open question 2.

## Risks and the guard for each

| Risk | Guard |
|---|---|
| **A route renders an `admin.*` key without the admin slice** (a shared component starts using one) → a raw dotted key on a student screen | **New `src/messages/__tests__/sliceReach.test.ts`.** Walks the import graph (static `import` AND `import()`, `@/` and relative) from every route entry outside `app/admin` (`page`, `layout`, `error`, `not-found`, `loading`, `template`) and fails if any reachable production file holds an `admin.`-prefixed literal or template prefix — naming the file and the import chain. A second claim: every file holding an `admin.*` key is reachable from `app/admin` only (or the sandbox). Floors against a blind walk (TD-276): ≥ N non-admin entries, ≥ M reachable files, ≥ K admin keys seen. Conservative on purpose: a key in a reachable file fails even if that branch never renders. |
| A key passed as a variable or built at run time | Same test: the variable's value is a literal somewhere in a reachable file and is caught there; whole-namespace templates (`admin.${h}`) are caught by prefix. A key that comes from the SERVER (`apiErrors.*`, status labels) is in core. |
| `oneLocalePerVisitor.test.ts` goes BLIND to `?slice=` imports | Its regex and allow-list are updated in the same commit: allowed statics `lib/messages.ts` (en core) and `lib/messagesAdmin.ts` (en admin); exactly four literal `import()` specifiers for ms/ta. A test that a `'@/messages/ta.json?slice=core'` STATIC import in a fixture string is caught. |
| A slice drops or duplicates a key | `messagesSlice.test.ts`: for en/ms/ta, `core ∪ admin` = the whole file, `core ∩ admin` = ∅, an unknown slice name throws. Parity (`check-i18n.js`, `namespaces-i18n.test.ts`) is untouched because the files are. |
| SSR / hydration | Admin slice merged at module evaluation, before render; server and client both English. Smoke: `next start`, fetch `/admin/login` HTML, assert no `admin.` dotted string in it. |
| Language switcher | `localeSwitch.test.tsx` / `localeDelivery.test.tsx` gain: on an admin tree a switch to `ta` fetches core-ta AND admin-ta before commit; an admin-chunk failure rejects and leaves English; superseded-request token still holds; a student tree never fetches an admin chunk. |
| ms / ta parity | Unchanged files → unchanged checks. |
| Sol | Unchanged paths; nothing to do. New strings from this sprint: none. |
| Consent / legal text | `scholarship.consent` is in core; the consent byte-snapshot reads the whole files and is untouched. Contract clauses and sponsor terms come from the database, not the files. |
| Emails | None read the message files. |
| The admin printed figure falls ~50 kB with no real gain | Stated in the commit, `code-standards.json` `_first_load_js_note` and the retrospective; the first-paint line (already printed) shows the truth. No new budget invented (TD-304: that is a lead / owner call). |
| `next.config.js` gains a `webpack` hook | `sandbox-safety.test.ts` reads `pageExtensions` only; a jest assertion that the loader rule exists and points at the script (a reader nobody wires is the TD-281 failure). Dockerfile `COPY . .` already carries `scripts/`. |

## Door list (where a missing word would hurt)

Every surface that renders an `admin.*` key and must have the slice: `/admin/*` incl. the chromeless
`/admin/login`, `/admin/auth/callback`, `/admin/set-password`, `/admin/[...notFound]`; the sandbox.
Every surface that must NOT need it and is proven by the guard: the student apply / application /
award / consent screens, `AuthGateModal` (mounted on every page), the sponsor portal incl.
`SponsorTermsWizard`, `/r/[code]`, root `error.tsx` / `not-found.tsx`, `AppHeader` / `AppFooter`.

## Sprint breakdown

### Sprint 1 — the admin slice (do now; ~22 files, moves-first, vertical)

**Goal:** the admin console's words leave every non-admin route; budgets ratcheted; guard in place.

**Order:** (1) spike the loader + TS + jest mapper and prove with a build that the admin chunk is in
the admin layout's files only; (2) `pickSlice` + loader + its test; (3) runtime (`messages.ts`,
`messagesAdmin.ts`, `i18n.tsx`, admin + sandbox layouts) with the locale tests; (4) `sliceReach` guard;
(5) `oneLocalePerVisitor` update; (6) `npm run gates`, `npm run bundle-budget`, ratchet the four lines,
raise `NEAR_LINE_KB` to 0.25; (7) local smoke; (8) docs.

**Files (≈ 22):** `next.config.js`, `scripts/messages-slice-loader.js` (new), `src/types/messages-slice.d.ts`
(new), `jest.config.js`, `src/lib/messages.ts`, `src/lib/messagesAdmin.ts` (new), `src/lib/i18n.tsx`,
`src/app/admin/layout.tsx`, `src/app/sandbox/layout.sandbox.tsx`, tests: `messagesSlice.test.ts` (new),
`sliceReach.test.ts` (new), `oneLocalePerVisitor.test.ts`, `localeDelivery.test.tsx`,
`localeSwitch.test.tsx`, `bundleBudgetReader.test.ts`, `codeStandards.test.ts` (loader wiring);
`code-standards.json`, `scripts/bundle-budget.js` (`NEAR_LINE_KB`, comments naming en.json);
docs: `CHANGELOG.md`, `docs/technical-debt.md` (close TD-360 and TD-344), `halatuju_api/CLAUDE.md`
(lines ~460 and ~515: the median figure and "the next en.json string moves every route"),
`.claude/ARCHITECTURE_MAP.md`, `docs/sprint-history.md`, a retrospective.

**Acceptance:**
- `npm run gates` green; `npm run bundle-budget` green on this machine with ≥ 0.25 kB of room everywhere.
- Median ≤ ~181 and the three lines lowered per the ratchet, from a real build; numbers recorded.
- In `.next/app-build-manifest.json`, the en-admin chunk appears in no non-`/admin` route's page or
  layout files (checked once by hand, recorded in the retrospective).
- `next start` smoke: `/`, `/scholarship/apply`, `/sponsor`, `/admin/login` render with no dotted
  key in the HTML; switch en → ta → ms on a student page and an admin page (no English under a Tamil
  switcher after commit); public site in Tamil → `/admin` shows Tamil after the brief fallback.
- No key added, removed or reworded in any message file (`git diff --stat src/messages` is empty).

**Hours:** spike 1.0 · loader + types + jest 0.75 · runtime 2.0 · guard test 1.5 · other tests 1.25 ·
build, measure, ratchet 0.75 · smoke 0.75 · docs + retrospective 1.0 · code review + fixes 1.0 =
**10.0 h**. (A wrong spike that forces the prebuild fallback adds ~1 h.)

**As built (2026-10-21, `7d5f5054` + `8b1b57ce`, branch `td360`, not deployed):**
- **Spike passed** — TS ambient `*.json?slice=…`, Next 14.2 webpack and the jest mapper all took the
  query on the first build; no prebuild fallback. en-admin sits only in `app/admin/layout-*.js`; the
  ms/ta slices are in no manifest entry (lazy).
- **Measured** (local exact): median 228.833 → **178.829**; `/scholarship/application` 273.611 → 221.861;
  `/profile` 270.306 → 218.548; `/scholarship/apply` 243.716 → 191.962 (the estimate was −49.9; the real
  −51.7 includes the leaf below). Ratcheted: 180 / 223 / 220 / 193; ceiling 250; `NEAR_LINE_KB` 0.25.
  Admin first paint +2.9 kB (two slices compress slightly worse than one file).
- **Deviations:** (1) the four literal `import()`s are in a new `lib/messageChunks.ts` (the mockable
  network edge), not `messages.ts`; (2) the guard found `lib/sessionPolicy.ts` → `lib/navigation.ts` on
  every page (missed by the static scan above), fixed by the leaf `lib/superRole.ts` (`7d5f5054`);
  (3) `requireSlice` fetches nothing — the first cut fetched the admin slice of every language in memory,
  caught in the browser smoke; (4) one declared unrouted file in the guard (`AiReliabilityCard.tsx`,
  hidden since 2026-06-13, mounted by no route); (5) new test files `messagesRegistry.test.ts` and
  `localeSlices.test.tsx` instead of additions to `localeDelivery` / `localeSwitch`.
- **What covers the slice registration (review, 2026-10-21):** jest's `moduleNameMapper` hands every
  `?slice=` import the WHOLE file, so no jest render test can see a missing slice. Only
  `messagesSlice.test.ts` (the cut on the real files), the `next.config.js` wiring test in
  `codeStandards.test.ts` and a real `next build` (`npm run bundle-budget`, the deploy gate) cover it;
  `sliceReach.test.ts` covers the reach. Review fixes: the reach guard reads files with the TypeScript
  parser (a `/*` inside a `//` comment had hidden imports), refuses a bare `'admin'` value off the
  console (one declared allowance, `sessionPolicy.ts`'s session scope), and pins `label_key` readers to
  the admin side. Raised: TD-388 (pre-existing hydration mismatch with ms/ta stored), TD-389 (`admin`
  stays required for the tab).
- **Not done:** no in-console switcher exists to click, so the browser smoke switched on student pages and
  entered / hard-refreshed the console in each language; the in-console switch is a rendered jest test.

### Sprint 2 — scholarship and sponsor slices (DEFERRED; open question 1)

Would take `scholarship` (29.3 kB gz) and the four `sponsor*` namespaces (6.1 kB gz) off the ~20
public routes that never show them (`/`, `/about`, `/course/[id]`, `/search`, `/quiz`, `/pathway/*`,
`/stpm/*`, legal pages…). It does **not** help the three ledgered lines (they need `scholarship`), it
needs the 3 `scholarship.*` keys `AppHeader` reads moved into `header.*` (a key move in all three files,
re-tagged in Sol), and student routes have no shared layout, so each scholarship route (or a new
`(student)` route group, URLs unchanged) must declare the slice. ≈ 25–30 files, **≈ 8 h**. Trigger to
do it: a third near-line fight caused by a non-admin string after Sprint 1.

**Total: 10 h now (Sprint 1); 18 h if Sprint 2 is ever done.**

## Open questions for the owner

1. **Do only the admin split now and park the scholarship / sponsor split behind a trigger?**
   *Recommend yes.* Sprint 1 takes ~50 kB off every non-admin route and stops admin strings (all of
   request #39 Sprint 4's) from touching any budgeted line; Sprint 2 would not move the three tight
   student lines at all.
2. **Lower the 300 kB "must be named" ceiling to 250 kB once the build shows the worst route at ~224?**
   *Recommend yes* (the house rule is lower-never-raise; at 300 the ceiling would watch nothing for a
   long time). The three ledgered lines stay, each at its own ratcheted figure.
3. **A staff member who switched the public site to Malay or Tamil and then opens the admin console in
   the same tab sees admin words in English for a fraction of a second, the first time only. Accept
   that, or hold the console on a spinner until its words arrive?** *Recommend accept* — the spinner
   would delay every Malay/Tamil staff member's first console page for the same chunk, and the words
   are right in a language, just briefly not theirs (the rule `messages.ts` already states).
