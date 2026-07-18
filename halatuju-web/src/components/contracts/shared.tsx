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
