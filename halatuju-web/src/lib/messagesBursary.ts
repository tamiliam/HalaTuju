/**
 * HER MY BURSARY FUNDS AND CONTRACT TABS' WORDS — student maintenance S5b (2026-10-30), the
 * `documents` slice pattern (`lib/messagesDocuments.ts`) applied to the `bursaryTabs` namespace.
 *
 * ⚠ IMPORTED FOR ITS SIDE EFFECT by `/scholarship/bursary`'s PAGE only (rule D, `sliceReach.test.ts`):
 * a component importing it would carry the slice to every route that mounts the component.
 * These words lived in the `scholarship` slice for one build and pushed /scholarship/apply and
 * /scholarship/application over their first-load budgets — for words neither route ever shows.
 */
import enBursary from '@/messages/en.json?slice=bursary'
import { requireSlice } from '@/lib/messages'

requireSlice('bursary', enBursary)

export {}
