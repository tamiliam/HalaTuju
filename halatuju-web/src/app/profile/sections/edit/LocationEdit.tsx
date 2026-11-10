/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import { useT } from '@/lib/i18n'
import { MALAYSIAN_STATES } from '@/components/profile/profileFields'
import type { SectionProps } from '../../useProfileEditor'

/** The contact section's edit panel. Fetched as one chunk with the other four (see `useProfileEditors`). */
export default function LocationEdit({ f, ed }: SectionProps) {
  const { t } = useT()
  const { state, setState, address, setAddress, postalCode, setPostalCode, city, setCity, saving, postcode } = f
  const { cancelEditing, saveSection } = ed
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.street')}</label>
        <textarea
          value={address}
          onChange={e => setAddress(e.target.value)}
          placeholder="No. 12, Jalan ABC, Taman XYZ"
          rows={2}
          className="w-full px-3 py-2.5 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none resize-none"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.postalCode')}</label>
          <input
            type="text" inputMode="numeric" autoComplete="postal-code"
            value={postalCode}
            onChange={e => {
              const val = e.target.value.replace(/\D/g, '').slice(0, 5)
              setPostalCode(val)
              void postcode.lookup(val)   // the table loads on the 5th digit (request #26)
            }}
            placeholder="08000"
            maxLength={5}
            className="w-full px-3 py-2.5 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.city')}</label>
          <input
            type="text"
            value={city}
            onChange={e => { postcode.edited(); setCity(e.target.value) }}
            placeholder="Sungai Petani"
            className="w-full px-3 py-2.5 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('onboarding.state')}</label>
        <select
          value={state}
          onChange={e => { postcode.edited(); setState(e.target.value) }}
          className="w-full px-3 py-2.5 border border-ground-300 rounded-lg text-sm bg-ground-0 focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
        >
          <option value="">{t('onboarding.selectState')}</option>
          {MALAYSIAN_STATES.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="flex gap-3 pt-4">
        <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-ground-300 rounded-lg text-sm font-medium text-ground-700 hover:bg-ground-50">
          {t('profile.cancel')}
        </button>
        <button onClick={saveSection} disabled={saving} className="flex-1 px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover disabled:opacity-50">
          {saving ? '...' : t('profile.save')}
        </button>
      </div>
    </div>
  )
}
