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
 *   - `core`  = EVERY OTHER namespace. It is the complement on purpose: a namespace added
 *     tomorrow lands in core by default, so it can never be missing from a route that needs it.
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
}

const SLICE_NAMES = ['core', ...Object.keys(SLICES)]

/** The top-level namespaces of `json` that belong to slice `name`, in file order. */
function pickSlice(json, name) {
  if (!SLICE_NAMES.includes(name)) {
    throw new Error(`messages-slice-loader: unknown slice "${name}" (known: ${SLICE_NAMES.join(', ')})`)
  }
  const named = new Set(Object.values(SLICES).flat())
  const keep = name === 'core'
    ? (ns) => !named.has(ns)
    : (ns) => SLICES[name].includes(ns)
  const out = {}
  for (const ns of Object.keys(json)) {
    if (keep(ns)) out[ns] = json[ns]
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
