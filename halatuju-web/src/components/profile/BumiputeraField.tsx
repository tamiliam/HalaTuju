/**
 * /profile's Bumiputera answer (Bumi coverage Sprint B) — COURSE GUIDE ONLY: it unlocks
 * Bumiputera-only courses (UiTM, MARA) and nothing else reads it. The page draws it only for a
 * Malaysian. With `onChange` it is the Yes/No edit pair; without, the read-only row.
 */
import { FieldValue } from '@/components/profile/profileFields'

export default function BumiputeraField({ value, onChange, t }: {
  value: boolean | null
  onChange?: (v: boolean) => void
  t: (key: string) => string
}) {
  const label = t('onboarding.bumiputera')
  const answer = value === null ? '' : t(value ? 'onboarding.bumiYes' : 'onboarding.bumiNo')
  if (!onChange) {
    return <div className="flex justify-between"><span className="text-sm text-ground-500">{label}</span><FieldValue value={answer} t={t} /></div>
  }
  const pill = (b: boolean) => (
    <button key={String(b)} onClick={() => onChange(b)} className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
      value === b ? 'bg-primary-50 border-brand-shape text-primary-700' : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'}`}>
      {t(b ? 'onboarding.bumiYes' : 'onboarding.bumiNo')}
    </button>
  )
  return (
    <div data-testid="profile-bumiputera">
      <label className="block text-sm font-medium text-ground-700 mb-1.5">{label}</label>
      <div className="flex gap-2">{pill(true)}{pill(false)}</div>
      <p className="text-xs text-ground-400 mt-1.5">{t('onboarding.bumiHelp')}</p>
    </div>
  )
}
