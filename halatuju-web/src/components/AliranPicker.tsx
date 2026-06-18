'use client'

// School-type (Aliran) chooser for the PISMP teacher-training pathway — the first of the
// two taps in the Aliran → Bidang picker. Shows only the alirans the student has eligible
// courses for (eligible-only, like PathwaySelect), each a large chip with a short label +
// the full Malay school name. i18n reuses the `scholarship.apply.plan.aliran*` keys.
import { useT } from '@/lib/i18n'
import type { PismpAliran } from '@/lib/scholarship'

export default function AliranPicker({
  alirans,
  value,
  onChange,
}: {
  alirans: PismpAliran[]
  value: string
  onChange: (aliran: PismpAliran) => void
}) {
  const { t } = useT()
  if (alirans.length === 0) return null

  return (
    <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label={t('scholarship.apply.plan.aliranLabel')}>
      {alirans.map((a) => {
        const on = value === a
        return (
          <button
            key={a}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(a)}
            className={`flex flex-col items-start rounded-xl border p-3 text-left transition-colors ${
              on ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <span className={`flex w-full items-center justify-between text-sm font-medium ${on ? 'text-primary-700' : 'text-gray-800'}`}>
              {t(`scholarship.apply.plan.aliran.${a}`)}
              {on && <span aria-hidden className="text-primary-600">✓</span>}
            </span>
            <span className="mt-0.5 text-xs text-gray-500">{t(`scholarship.apply.plan.aliranSub.${a}`)}</span>
          </button>
        )
      })}
    </div>
  )
}
