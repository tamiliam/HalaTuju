/**
 * THE STUDENT SCHOLARSHIP SCREENS' WORDS — TD-416 (2026-10-29), TD-360's slice pattern
 * (`lib/messagesAdmin.ts`) applied to the `scholarship` namespace.
 *
 * ⚠ **IMPORTED FOR ITS SIDE EFFECT, BY THE PAGE OF EACH ROUTE THAT SHOWS THESE WORDS** — the six
 * `/scholarship/*` routes, `/profile`, `/onboarding/profile` and the admin pages that render
 * applicant answers (and the sandbox layout). `scholarship.*` was ~30 kB gz of the ~49 kB English
 * core that every route downloaded; 17 of 91 routes read it. It is now a slice, and THIS module is
 * the only place that asks for it — so it travels with those pages and no other.
 *
 * NOT ALL OF `scholarship.*` IS HERE. `scholarship.nav`, `scholarship.subnav` (`AppHeader`, on most
 * pages) and `scholarship.banner` (`/dashboard`) stay in core — `CORE_KEEPS` in
 * `scripts/messages-slice-loader.js`. The namespace is therefore split one level down, and the
 * registry merges its CHILDREN (`mergeSlice` in `lib/messages.ts`).
 *
 * What evaluating this module does, before the page renders a single word (exactly what the admin
 * slice does):
 *  1. merges the English `scholarship` slice INTO the English catalogue, so the server render and
 *     the first client paint have every word — no dotted keys, no hydration mismatch;
 *  2. marks `scholarship` REQUIRED, so `loadCatalogue('ms' | 'ta')` waits for core AND this slice,
 *     and a language switch on these pages commits only when both are in hand;
 *  3. announces it, so `I18nProvider` fetches the slice of the language ON SCREEN only.
 * A Malay or Tamil reader who arrives on one of these pages by a client-side link sees its
 * scholarship words in English for the moment the chunk is in the air, the first time per tab only
 * (the admin slice's accepted state, TD-360 open question 3).
 *
 * ⚠ IMPORT IT FROM A `'use client'` PAGE, never from a server component (it would run on the server
 * only and the browser would never get the words) and never from a widely shared component (it
 * would put the slice back on every route that mounts it). `sliceReach.test.ts` proves every route
 * that reaches a `scholarship.*` key outside `CORE_KEEPS` loads this module, and names the routes
 * that do.
 */
import enScholarship from '@/messages/en.json?slice=scholarship'
import { requireSlice } from '@/lib/messages'

requireSlice('scholarship', enScholarship)

export {}
