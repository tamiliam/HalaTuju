# Retrospective — TD-360 Sprint 1: the admin console's words leave every non-admin route (2026-10-21)

Roadmap: `docs/plans/2026-10-20-td360-split-messages-roadmap.md` (owner "yes" to all three open
questions on 2026-10-21). Decision: `docs/decisions.md` 2026-10-21. Commits `7d5f5054` (the super-check
leaf) and `8b1b57ce` (the slices). Built on branch `td360` (base `6aec3206`). **Not pushed, not
deployed.** Non-billed hygiene; the prerequisite for request #39 Sprint 4.

## What Was Built

- **One source file per language, two slices at build time.** `scripts/messages-slice-loader.js`
  (wired in `next.config.js`, `resourceQuery: /slice=/`) answers `@/messages/xx.json?slice=core|admin`.
  `admin` = the `admin` namespace; `core` = every other one, so a new namespace can never go missing.
  The three files are untouched (`git diff --stat src/messages` empty).
- **Runtime, one provider.** English core is static (`lib/messages.ts`); English admin is merged into
  the same English object by `lib/messagesAdmin.ts`, which only the admin and sandbox layouts import.
  ms/ta arrive as four literal lazy slices (`lib/messageChunks.ts`). `loadCatalogue` waits for every
  REQUIRED slice; the provider re-renders when one lands; an ABSENT namespace answers in English.
- **The reach guard** (`sliceReach.test.ts`) walks the import graph from every route entry outside
  `/admin` and fails on any reachable `admin.*` key, naming the chain. It found one on its first run.
- **Budgets ratcheted** in the same sprint: median 229 → 180, `/profile` 271 → 220,
  `/scholarship/apply` 244 → 193, `/scholarship/application` 274 → 223; `CEILING_KB` 300 → 250;
  `NEAR_LINE_KB` 0.15 → 0.25. TD-344 and TD-360 closed.

## The numbers (local exact, page entry; the deploy gate reads ~0.06 kB heavier)

| | Before (`6aec3206`) | After (`8b1b57ce`) |
|---|---|---|
| Median (89 routes) | 228.833 | **178.829** |
| `/scholarship/application` | 273.611 | 221.861 |
| `/profile` | 270.306 | 218.548 |
| `/scholarship/apply` | 243.716 | 191.962 |
| `/` | 232.418 | 180.666 |
| `/admin/scholarship/[id]` page / first paint | 268.103 / 300.809 | 218.955 / **303.641** |
| First-paint median, non-admin / admin | 252.648 / 263.089 | 201.311 / **265.919** |
| Malay / Tamil lazy chunk (gz) | 98.7 / 128.9 | core 48.1 + admin 51.9 / core 63.1 + admin 66.9 |

The en-admin words sit in `static/chunks/app/admin/layout-*.js` (59.2 kB gz with the shell) and in
no other manifest entry; the ms/ta slices are in no entry at all (lazy). Checked once by hand from
`.next/app-build-manifest.json`, as the roadmap's acceptance asked.

## What Went Well

- **The spike passed first time** — TypeScript (an ambient `*.json?slice=…` module), Next 14.2's
  webpack and jest's `moduleNameMapper` all took the query. The prebuild fallback was not needed.
- **The guard paid for itself on its first run.** `lib/sessionPolicy.ts` (imported by `auth-context`
  and `AuthGateModal`, i.e. every page) imported `navigation.effectiveRole` for one `=== 'super'` check,
  so the admin route registry rode on every route. The roadmap's static scan had called the audience
  line "clean"; it missed this because it traced importers of files holding keys, not the graph from
  the routes. A leaf (`lib/superRole.ts`) took a further ~2.5 kB off every route.
- **The browser smoke caught a real waste the tests had blessed.** The first cut made `requireSlice`
  fetch the admin slice of EVERY language already in memory; a tab that visited Malay then Tamil
  downloaded both admin slices (~52 kB for nothing) on opening the console. Now only the language on
  screen is fetched (the provider asks); a registry test pins it.

## What Went Wrong / Doubts

- **The admin printed figures fell ~49 kB with no real gain**, as the roadmap predicted: the words moved
  into the admin LAYOUT, which the budget does not count (TD-304). Admin first paint ROSE ~2.9 kB —
  two slices compress a little worse than one file, plus the merge code. No admin-layout budget was
  invented (a new standard is the lead's / owner's call); the first-paint line shows the truth.
- **jest cannot see the cut.** `?slice=` maps to the whole file in jest, so render tests pass on a
  superset. `messagesSlice.test.ts` (the cut on the real files) and `sliceReach.test.ts` (the reach)
  are what stand between a mistake and a raw dotted key in production.
- **No in-console language switcher exists** (only `/`, `/settings` and `AppHeader` mount one), so the
  browser smoke could not "switch on an admin page"; it verified the reachable equivalents (choose a
  language, then client-navigate into the console; hard refresh on a deep admin URL with Tamil stored).
  The switch-while-on-the-console path is covered by `localeSlices.test.tsx` on a rendered provider.
  A signed-in console walk needs a local API (TD-345's shape); not done.
- **Deviation from the roadmap:** the four literal `import()`s live in a new `lib/messageChunks.ts`, not
  `messages.ts`, so tests can own the network edge while the real registry runs. The guard checks them
  there. The new locale tests are new files (`messagesRegistry.test.ts`, `localeSlices.test.tsx`) rather
  than additions to `localeDelivery` / `localeSwitch` (the latter mocks the whole loader).

## Lessons

- **A reach claim is proved by walking FROM the routes, not by tracing who imports a file.** The roadmap's
  scan was careful and still missed a two-hop path through the sign-in code.
- **Smoke the network panel, not just the words.** Every word on screen was right while a whole
  language's admin slice downloaded for nothing.

## Not done

- Roadmap Sprint 2 (scholarship / sponsor slices) — parked by the owner behind its trigger.
- No deploy; the gate's build has not read these figures yet.
