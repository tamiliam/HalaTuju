# Retrospective — TD-300: the bundle gets its headroom back (2026-09-28 → 29)

**Written by the lead on 2026-09-29, with the owner's consent.** The builder's own retrospective
was refused by the workspace security-guidance hook on 2026-09-28, because its text names the
hook's own trigger word (the default Supabase session storage key ends in that word). The builder
did not reword it to slip past — that is the rule (`feedback_guardrail_block_is_a_question`) — and
recorded the block instead. The owner was asked and said "write it". This file is that retro,
reconstructed from the CHANGELOG entry, `docs/decisions.md` (2026-09-28, TD-300), TD-300 and
TD-304, the builder's final report and the adversarial reviewer's report. Where a number came from
the builder's or reviewer's report rather than a file, it says so.

## What Was Built

**The problem.** `npm run bundle-budget` read a first-load median of **256 kB** against a ledger of
256, with exactly 44 of 87 routes at or under 256 — the median WAS the 44th route. TD-296 had added
about 0.5 kB to six list routes and tipped `/admin/payments/[id]` to 257 the moment it imported a
two-line helper; that link was spelled out inline for that reason alone. The next byte on any route
at 256 would have turned the deploy gate red for a reason unrelated to the change. The budget is
never raised; the only honest fix is to make routes lighter so the median falls and the ledger
ratchets DOWN with room under it.

**Phase A — measured, not argued.** A real `next build` and its chunk manifest, read for the route
at the median (`/admin/payments/[id]`, 256 kB), gzipped:

| Contributor | kB | Pulled in by |
|---|---|---|
| `en.json` (chunk 7867) | 97.1 | `lib/i18n.tsx`, on 74 routes |
| react-dom | 53.6 | Next itself |
| supabase-js | 44.8 | the three `get…Supabase()` clients, via the global auth contexts |
| Next runtime | 31.5 | shared chunk |
| `next/link` + router utils | 6.8 | links |
| `buffer` polyfill | 6.0 | supabase-js (its Storage, Realtime and Functions parts) |
| the page itself | 5.5 | — |
| admin-api client, `payments.ts`, `TableFrame` | 2.7 | the page |
| `navigation.ts` | 2.1 | the page |
| webpack runtime | 1.9 | Next itself |

Answers to the questions the brief asked: `en.json` is 96.3 kB gz on its own, of which the
`admin.*` keys are 49.0 kB; both `@/lib/api` and `admin-api` barrels DO tree-shake (only the modules a
page uses land in its chunk); there is no icon library (inline SVGs) and no date library; and
supabase-js builds Realtime, PostgREST, Storage and Functions clients the moment `createClient` is
called, although the app only ever calls `.auth` — so **54% of its 51 kB was never used**.

The three largest safe cuts, by measured saving: (1) auth-only Supabase clients, ~29 kB off 73
routes; (2) splitting `en.json` so student routes skip the `admin.*` keys, up to ~49 kB on student
routes; (3) moving React Query out of the root layout, ~8.8 kB off every route. Cut 1 alone reached
the target, so (2) and (3) were not built — (2) is the risky one (a missing key is a raw key on a
student's screen) and the brief said not to ship it on the builder's own judgement.

**Phase B — the cut.** New `halatuju-web/src/lib/supabaseAuthClient.ts` constructs ONLY the
`AuthClient` from `@supabase/auth-js` (2.95.3, newly declared in `package.json` — the exact version
supabase-js pins; `npm ls` shows one deduped copy), field for field what `createClient` passes to
GoTrue. The three client factories (`supabase.ts`, `admin-supabase.ts`, `sponsor-supabase.ts`) use
it. Nothing else changed: no wording, no route, no i18n.

| | Before | After |
|---|---|---|
| Median | 256 kB | **227 kB** |
| Worst (`/profile`) | 339 kB | **310 kB** |
| Shared by all | 87.2 kB | 87.2 kB |
| Routes lighter / unchanged / heavier | — | 73 / 14 / 0 |
| Routes within 1 kB of the median | 7 | 7 |

Counting layout chunks too, all 87 routes are lighter, by 29 kB on average. The three routes still
over the 300 kB ceiling are ledgered at 310, 285 and 275.

**Phase C — locked in.** `first_load_js_median_kb` ratcheted to **229**, not 227: the script already
tolerates 2 kB before it asks for a lower number, and 227 would have left zero routes to spare —
exactly TD-300's trap again. The reasoning is in `decisions.md`. `bundle-budget.js` now prints a
headroom line on every run ("N routes may cross the budget before the median does"): 6 today.

**Measured and rejected.** Splitting `Toast.tsx` (TD-289) saved 0.40 kB on `/`, under the 0.5 kB bar
the brief set, and was reverted. TD-289 stays open.

## Design Decisions

- **Measure, then cut, then measure again — and never raise a budget.** The lead's own lazy sign-in
  gate of 2026-09-21 was built, browser-verified and reverted because it measured a saving of ZERO
  (the modal's heavy imports belonged to the global `auth-context`). This sprint started from the
  route that was over, read what was actually in it, and built only what the numbers named.
- **Cut the library, not the text.** `en.json` is the largest single contributor and stayed
  untouched: a catalogue split changes what a student can see at first paint, and H17 taught that
  the defects live in the seconds mid-flight. The Supabase cut changes nothing a person can see.
- **Field-for-field parity, proved against the real client.** A jsdom test builds the REAL
  `createClient(...).auth` beside the auth-only client for all three option sets and compares every
  plain setting, the headers in order, lock, storage, user storage and the default student session
  storage key — so nobody is signed out by the deploy. The same test fails if anything under `src/`
  imports a value from `@supabase/supabase-js` (type imports are erased and stay allowed).
- **The median budget keeps the script's own 2 kB as headroom** (229 over a 227 median). Not slack
  in the ratchet — the ratchet still refuses a rise — but room for the rounding line to move
  without a deploy failing for nothing.

## What Went Well

- The anatomy was right the first time because it was read off a build, not reasoned about.
- One cut reached the target with margin, so the risky option (i18n) never had to be argued.
- No route got heavier — the check the reverted gate had failed.
- The parity test caught, on the day: `persistSession: false`, `autoRefreshToken: false`,
  `detectSessionInUrl: false`, `flowType: 'implicit'`, a different storage key, a memory `storage`,
  a custom `lock`, `debug: true`, `hasCustomAuthorizationHeader: true`, swapped header order, a
  changed auth URL, `lockAcquireTimeout`, and the `X-Client-Info` environment (reviewer's mutation
  run: 12 of 14 caught).

## What Went Wrong

- **The retrospective could not be written by the builder.** *Symptom:* the Write was refused by the
  security-guidance hook. *Root cause:* the default session storage key that the parity test
  compares ends in the hook's trigger word, and the retro named it. *System change:* the builder
  recorded the block and the owner was asked; this file exists because the owner consented. The
  hook did its job; the lesson is that a retro about auth will trip it and should be written by
  the lead with consent in hand, not reworded around.
- **A custom `fetch` was invisible to the parity test.** *Symptom:* the reviewer passed a custom
  transport into the auth-only client and the test stayed green; the lead's first fix compared
  `String(fetch)` and was ALSO green, because GoTrue wraps a custom fetch and the default one in the
  same `resolveFetch` wrapper — identical source, type and name either way. *Root cause:* the
  built client cannot show which transport it was given. *System change:* the guard moved to the
  SOURCE: the module must pass `fetch: undefined` and nothing else; a smuggled transport now goes
  red for all three clients (bitten, restored byte-identical).
- **The value-import guard missed re-exports.** `export { createClient } from '@supabase/supabase-js'`
  would have brought the 29 kB back unseen. The pattern now covers `export … from` and
  `export * from` (bitten with a probe file: red).
- **The browser check touched production.** Loading `/about` in dev fired the app's own,
  pre-existing anonymous sign-in against production Supabase; it was refused (401) and nothing was
  created; later loads blocked `*.supabase.co`. Not new behaviour (the reviewer traced it to the
  student auth provider's first-visit sign-in, commit 4dc27a76), but a browser check of an auth
  change must block the auth host before the first page load.
- **The deploy failed once, for a reason outside the repo.** The first web build died in the
  Docker step: `next/font/google` downloads Lexend, Inter and IBM Plex Sans inside `next build`, and
  Google returned a malformed answer (`loader.js:112 Cannot read properties of null (reading '1')`).
  Every gate had passed; the change touched neither the layout nor the fonts. Re-running the same
  commit passed. Raised as **TD-305: self-host the fonts with `next/font/local`** so a deploy needs
  nothing from Google. (Also learnt: `gcloud builds triggers run … --sha` is refused for this
  trigger; `--branch main` works; an empty commit would not fire the path-filtered trigger.)
- Two housekeeping slips by the builder, recorded honestly: `git checkout --` was used to inject
  one fault (the restore was from byte backups, verified), and the `/code-review` step of
  sprint-close was left to the adversarial reviewer.

## Bite-checks (final run against the shipping bytes; originals restored, SHA-256 verified)

Builder: (a) undo the cut → budget red at median 256 AND the import guard red; (b) median ledger
lowered to 226 → red; (e) comment-only change → green with an identical route table; a changed
default storage key → parity test red; the `drift-test` marker removed → `codeStandards.test.ts`
red. Lead, after the review: a smuggled `fetch` → red ×3 (after the source-level rewrite; the first
draft was silent); an `export … from` re-export in a probe file → red; clean tree → green.

## Numbers

- jest **3,076 → 3,095** (+19: the parity suite and the two review hardenings); 175 suites.
- pytest 7,117 / 3 skipped — the api tree was not touched (only `halatuju_api/CLAUDE.md`).
- `npm run bundle-budget`: median 227, worst 310, shared 87.2, 6 routes of headroom.
- `code_health`: 0 FAIL, 6 WARN, all pre-existing kinds; `std` ok.
- Deploy: `fdcd5e06` → `halatuju-web-00927-m4t` on the SECOND build (see TD-305); site 200; 0 web
  errors on the new revision; `/`, `/login`, `/admin/login`, `/about`, `/sponsor` all 200.

## After the adversarial review — verdict "ship after fixes"

The reviewer (who did not build it) compared every GoTrue option one by one between supabase-js
2.95.3 and `supabaseAuthClient.ts` — `url`, `headers` (in order), `storageKey`, `autoRefreshToken`,
`persistSession`, `detectSessionInUrl`, `storage`, `userStorage`, `flowType`, `lock`, `debug`,
`throwOnError`, `fetch`, `hasCustomAuthorizationHeader` — and found them identical; confirmed every
auth call the app makes exists on the auth-only client and that NO non-auth call (`.from`, `.rpc`,
`.storage`, `.channel`, `.functions`) exists anywhere under `src/`; confirmed one deduped copy of
auth-js; confirmed the budget script still fails closed and the headroom line cannot mask a
failure. Findings: F1 a dangling link to this (then unwritten) retro in `halatuju_api/CLAUDE.md`
(fixed, then superseded by this file); F2 the custom-fetch blind spot (fixed at the source); F3 the
re-export gap (fixed); F4 the headroom count is exact only for an odd route count (informational,
left).

## What Is Still Open

- **TD-305** — self-host the fonts; the deploy should not depend on Google being up.
- **TD-304** — Next's printed first-load figure omits chunks that only a layout loads (`/login`
  prints 87.6 kB, the browser fetches ~231 kB), so weight moved into a layout passes the budget
  unseen.
- **TD-289** — the Toast split, 0.40 kB; below the bar, still open.
- **The `en.json` split** — up to ~49 kB more on student routes, the next-largest cut and the only
  one that touches what a student can see. An owner's decision, with H17's mid-flight tests as the
  price of entry.
