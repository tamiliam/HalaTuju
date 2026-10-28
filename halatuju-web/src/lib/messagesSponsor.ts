/**
 * THE SPONSOR ROUTES' WORDS — TD-416 (2026-10-29), TD-360's slice pattern (`lib/messagesAdmin.ts`)
 * applied to the four `sponsor*` namespaces (`sponsorPortal`, `sponsorAuth`, `sponsorPool`,
 * `sponsorLanding`; ~6 kB gz on 2026-10-29).
 *
 * ⚠ **IMPORTED FOR ITS SIDE EFFECT** by `app/sponsor/(portal)/layout.tsx` (the portal shell shows
 * these words itself, so they must be merged before IT renders) and by the PAGE of each sponsor
 * route that shows them — the seven portal pages, `/sponsor/login`, `/sponsor/register` and
 * `/sponsor/auth/reset`. The page import is what puts the slice in that route's budgeted
 * first-load JS; a layout-only import would hide it from the budget (TD-304) while every sponsor
 * still downloaded it. No student, public or admin route loads it.
 *
 * What evaluating this module does is exactly what the admin slice does: merge the English words
 * into the English catalogue (SSR and first paint have them), mark `sponsor` REQUIRED (a Malay or
 * Tamil load waits for it), and announce it (the provider fetches it for the language on screen).
 * A Malay or Tamil reader arriving by a client-side link sees these words in English for the
 * moment the chunk is in the air, the first time per tab only.
 *
 * ⚠ IMPORT IT FROM A `'use client'` ROUTE FILE only — never a server component, never a shared
 * component. `sliceReach.test.ts` proves every route that reaches a `sponsor*` key loads it and
 * names the routes that do.
 */
import enSponsor from '@/messages/en.json?slice=sponsor'
import { requireSlice } from '@/lib/messages'

requireSlice('sponsor', enSponsor)

export {}
