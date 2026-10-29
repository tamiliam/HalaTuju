/*
 * THE MESSAGE-SLICE LOADER — TD-360 Sprint 1 (2026-10-21).
 *
 * `import enAdmin from '@/messages/en.json?slice=admin'` is answered by THIS file, wired in
 * `next.config.js` (a rule on `resourceQuery: /slice=/`). It hands webpack only the named
 * top-level namespaces of the message file, so a route that never shows the admin console never
 * downloads its 2,918 keys (49.9 kB gz on 2026-10-20).
 *
 * ⚠ THE THREE MESSAGE FILES ARE NOT TOUCHED AND NOT COPIED. `src/messages/{en,ms,ta}.json` stay
 * the one source of truth — Sol, `check-i18n.js`, the backend tests and ~40 jest tests read them
 * by path. The cut happens at build time, in memory, and nothing is written to disk.
 *
 * The slices:
 *   - `admin` = the `admin` namespace only.
 *   - `documents` = the `documentsTab` namespace only (the student Documents tab's own words).
 *   - `scholarship` = the `scholarship` namespace (TD-416, 2026-10-29) EXCEPT the few children in
 *     `CORE_KEEPS` — the words a component on most routes reads (`AppHeader`'s menu, the dashboard
 *     banner). Those children stay in core; the slice holds every other child.
 *   - `sponsor` = the four `sponsor*` namespaces (`sponsorPortal`, `sponsorAuth`, `sponsorPool`,
 *     `sponsorLanding`) — the sponsor routes' words (TD-416).
 *   - `core`  = EVERY OTHER namespace, plus the `CORE_KEEPS` children. It is the complement on
 *     purpose: a namespace added tomorrow lands in core by default, so it can never be missing from
 *     a route that needs it. (A new `scholarship.*` CHILD lands in the slice, not core — safe
 *     because `sliceReach.test.ts` proves every route that reads one loads the slice.)
 *
 * ⚠ A NAMESPACE IN `CORE_KEEPS` IS SPLIT ACROSS TWO SLICES, one level down. Whoever merges slices
 * must merge that namespace's CHILDREN (`lib/messages.ts` `mergeSlice`), never replace the object,
 * and `lib/messages.ts` `SPLIT_NAMESPACES` must name the same namespaces (`messagesSlice.test.ts`
 * holds the two lists together).
 * An unknown slice name THROWS (a typo would otherwise ship an empty catalogue and every key on
 * the page would echo as a raw dotted path).
 *
 * `pickSlice` is pure and exported for `src/messages/__tests__/messagesSlice.test.ts`, which
 * proves on the real files that `core ∪ admin` is the whole file and `core ∩ admin` is empty.
 */
'use strict'

/** The named slices and the top-level namespaces each holds. `core` is everything else. */
const SLICES = {
  admin: ['admin'],
  // Third results route S3 (2026-10-26): the student Documents tab's own words, loaded with the
  // tab's chunk (`lib/messagesDocuments.ts`) — never on a route that does not open the tab.
  documents: ['documentsTab'],
  // TD-416 (2026-10-29): the student scholarship screens' words — ~30 kB gz, the biggest namespace
  // after `admin` — loaded by `lib/messagesScholarship.ts` on the routes that show them only.
  scholarship: ['scholarship'],
  // TD-416: the sponsor portal's and the sponsor sign-in screens' words (~6 kB gz), loaded by
  // `lib/messagesSponsor.ts` on the sponsor routes only.
  sponsor: ['sponsorPortal', 'sponsorAuth', 'sponsorPool', 'sponsorLanding'],
}

/**
 * Children of a sliced namespace that STAY IN CORE, because a component on most routes reads them:
 * `scholarship.nav` / `scholarship.subnav` (`AppHeader`, on nearly every student and sponsor page)
 * and `scholarship.banner` (`ScholarshipBanner`, on `/dashboard`). 0.1 kB gz together on 2026-10-29.
 * ⚠ Adding a child here puts it back on every route; that is the trade to weigh, not a free fix.
 */
const CORE_KEEPS = {
  scholarship: ['nav', 'subnav', 'banner'],
}

const SLICE_NAMES = ['core', ...Object.keys(SLICES)]

/** `json[ns]` with only the children `want` accepts — a fresh object, in file order. */
function children(value, want) {
  const out = {}
  for (const k of Object.keys(value)) if (want(k)) out[k] = value[k]
  return out
}

/** The top-level namespaces of `json` that belong to slice `name`, in file order. */
function pickSlice(json, name) {
  if (!SLICE_NAMES.includes(name)) {
    throw new Error(`messages-slice-loader: unknown slice "${name}" (known: ${SLICE_NAMES.join(', ')})`)
  }
  const named = new Set(Object.values(SLICES).flat())
  const out = {}
  for (const ns of Object.keys(json)) {
    const kept = CORE_KEEPS[ns]
    if (name === 'core') {
      if (!named.has(ns)) out[ns] = json[ns]
      else if (kept) out[ns] = children(json[ns], (k) => kept.includes(k))
    } else if (SLICES[name].includes(ns)) {
      out[ns] = kept ? children(json[ns], (k) => !kept.includes(k)) : json[ns]
    }
  }
  return out
}

/** The slice named by a resource query such as `?slice=admin`. */
function sliceOfQuery(resourceQuery) {
  const name = new URLSearchParams(String(resourceQuery || '').replace(/^\?/, '')).get('slice')
  if (!name) throw new Error(`messages-slice-loader: no slice named in "${resourceQuery}"`)
  return name
}

/**
 * The webpack loader. Its output is JSON text, so webpack's own JSON module type (chosen by the
 * `.json` extension) parses it exactly as it parses a whole message file.
 */
function messagesSliceLoader(source) {
  const name = sliceOfQuery(this.resourceQuery)
  return JSON.stringify(pickSlice(JSON.parse(source), name))
}

module.exports = messagesSliceLoader
module.exports.pickSlice = pickSlice
module.exports.sliceOfQuery = sliceOfQuery
module.exports.SLICES = SLICES
module.exports.SLICE_NAMES = SLICE_NAMES
module.exports.CORE_KEEPS = CORE_KEEPS
