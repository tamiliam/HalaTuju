/**
 * HER MY BURSARY FUNDS AND CONTRACT TABS' WORDS — student maintenance S5b (2026-10-30), the
 * `documents` slice pattern (`lib/messagesDocuments.ts`) applied to the `bursaryTabs` namespace.
 *
 * ⚠ IMPORTED FOR ITS SIDE EFFECT by `/scholarship/bursary` and the two components that draw the tabs.
 * These words lived in the `scholarship` slice for one build and pushed /scholarship/apply and
 * /scholarship/application over their first-load budgets — for words neither route ever shows.
 */
import enBursary from '@/messages/en.json?slice=bursary'
import { requireSlice } from '@/lib/messages'

requireSlice('bursary', enBursary)

export {}
