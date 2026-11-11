/**
 * THE STUDENT DISCOVERY SCREENS' NEW WORDS — Mobile M3 (2026-11-01), the `bursary` slice pattern
 * (`lib/messagesBursary.ts`) applied to the `discovery` namespace: the phone search filters, the
 * course page's "show all" and the saved-course compare.
 *
 * G13 (2026-11-11): the slice also holds the `courseDetail.*` and `saved.*` children outside
 * `CORE_KEEPS`, so /stpm/[id] loads it too.
 *
 * ⚠ IMPORTED FOR ITS SIDE EFFECT by the PAGES of /search, /course/[id], /stpm/[id] and /saved only
 * (rule D/E, `sliceReach.test.ts`), and by the sandbox layout. A shared component importing it
 * would carry the slice to every route that mounts the component; in core these words would have
 * moved every route's first load, with the median 0.44 kB under its budget.
 */
import enDiscovery from '@/messages/en.json?slice=discovery'
import { requireSlice } from '@/lib/messages'

requireSlice('discovery', enDiscovery)

export {}
