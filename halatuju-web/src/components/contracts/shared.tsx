'use client'

// Shared bits for the contract-template editor tabs.
export const CLOCALES = ['en', 'ms', 'ta'] as const
export type CLocale = typeof CLOCALES[number]

export const inputCls =
  'w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500'
export const btnPrimary =
  'px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50'
export const btnGhost =
  'px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50'

/**
 * A stable fingerprint of the clause list, for "is there anything to save?" (request #6).
 *
 * ⚠ A NO-OP SAVE IS NOT HARMLESS HERE, which is why the button must actually go dead rather than
 * merely look calmer. `contracts.replace_clauses` DELETES every clause row and recreates it, so
 * pressing Save having changed nothing churns the rows and moves the template's "last changed"
 * time — on a document people sign, and with no field recording who did it. The requester's
 * instinct ("it may confuse who actually edited the document") was righter than the wording
 * suggests: there is no author to overwrite, only a timestamp that stops being true.
 *
 * Compares by VALUE over a fixed field order rather than by `JSON.stringify` of the objects: a
 * clause added in the editor is built from a local literal whose key order differs from the
 * server's, so a whole-object stringify reports "changed" for two identical clauses. Only the
 * fields this editor can alter are included — plus position, which `map` preserves, so a move,
 * indent or delete counts too.
 */
// ⚠ Takes `unknown[]`, not `Record<string, unknown>[]`. An INTERFACE (ContractClauseData) has no
// index signature, so it is not assignable to a Record parameter — a mismatch `next lint` and jest
// both pass over and only the production build catches. Widening here rather than casting at each
// call site keeps the two editors' code honest about what they hold.
export function clauseFingerprint(list: readonly unknown[]): string {
  return JSON.stringify((list || []).map((raw) => (raw || {}) as Record<string, unknown>).map((c) => [
    c.level ?? 0,
    c.heading_en ?? '', c.heading_ms ?? '', c.heading_ta ?? '',
    c.body_en ?? '', c.body_ms ?? '', c.body_ta ?? '',
    !!c.is_quiz_candidate,
    c.quiz_en ?? {}, c.quiz_ms ?? {}, c.quiz_ta ?? {},
  ]))
}

/** en | ms | ta selector; en is labelled authoritative. */
export function LangTabs({ value, onChange }: { value: CLocale; onChange: (l: CLocale) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs">
      {CLOCALES.map((l) => (
        <button key={l} type="button" onClick={() => onChange(l)}
          className={`px-3 py-1.5 font-medium uppercase ${value === l ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}>
          {l}{l === 'en' ? ' ★' : ''}
        </button>
      ))}
    </div>
  )
}
