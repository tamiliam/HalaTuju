/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { setOnboardingReturn } from '@/lib/scholarship'
import SchoolSelect from '@/components/SchoolSelect'
import PathwayPicker from '@/components/scholarship/LazyPathwayPicker'
import type { SectionProps } from '../../useProfileEditor'

/** The application section's edit panel. Fetched as one chunk with the other four (see `useProfileEditors`). */
export default function ApplicationEdit({ f, ed }: SectionProps) {
  const { t } = useT()
  const { token } = useAuth()
  const router = useRouter()
  const { pathwayForm, profileObj, angkaGiliran, setAngkaGiliran, school, setSchool, saving, resultsPath, meritShown, meritLabel, updatePathway } = f
  const { cancelEditing, saveSection } = ed
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">
          {t('profile.school')} <span className="text-ground-400 font-normal">({t('profile.optional')})</span>
        </label>
        <SchoolSelect value={school} onChange={setSchool} />
      </div>
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.angkaGiliran')}</label>
        <input
          type="text"
          value={angkaGiliran}
          onChange={e => setAngkaGiliran(e.target.value.toUpperCase().slice(0, 9))}
          placeholder="AB123C456"
          maxLength={9}
          className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-1 outline-none font-mono uppercase ${
            angkaGiliran && !/^[A-Z]{2}\d{3}[A-Z]\d{3}$/.test(angkaGiliran)
              ? 'border-critical-400 focus:border-critical-500 focus:ring-critical-500'
              : 'border-ground-300 focus:border-brand-shape focus:ring-brand-shape'
          }`}
        />
        {angkaGiliran && !/^[A-Z]{2}\d{3}[A-Z]\d{3}$/.test(angkaGiliran) && (
          <p className="text-xs text-critical-600 mt-1">{t('profile.angkaGiliranInvalid')}</p>
        )}
        <p className="text-xs text-ground-400 mt-1">{t('profile.angkaGiliranHelper')}</p>
      </div>
      {/* Merit — computed from grades, so "editing" it means the grades editor. Make it
          the SAME tappable shortcut as the view state (it was an inert span here, which is
          why merit looked editable from the view but not from inside edit). Tapping jumps
          to the grades page (stashing a return to /profile). */}
      <button type="button" onClick={() => { setOnboardingReturn('/profile'); router.push(resultsPath) }}
        className="w-full min-h-11 flex justify-between items-center gap-3 text-left group">
        <span className="text-sm font-medium text-ground-700">{meritLabel}</span>
        <span className={`text-sm text-right ${meritShown != null ? 'text-ground-900 font-semibold' : 'text-caution-700'} group-hover:text-primary-600`}>
          {meritShown != null ? meritShown : t('profile.meritTapAdd')}
        </span>
      </button>
      <div className="border-t border-ground-100 pt-4">
        <p className="text-sm font-medium text-ground-900 mb-3">{t('profile.pathway')}</p>
        <PathwayPicker value={pathwayForm} onChange={updatePathway} profile={profileObj} token={token} />
      </div>
      <div className="flex gap-3 pt-4">
        <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-ground-300 rounded-lg text-sm font-medium text-ground-700 hover:bg-ground-50">
          {t('profile.cancel')}
        </button>
        <button onClick={saveSection} disabled={saving || (!!angkaGiliran && !/^[A-Z]{2}\d{3}[A-Z]\d{3}$/.test(angkaGiliran))} className="flex-1 px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover disabled:opacity-50">
          {saving ? '...' : t('profile.save')}
        </button>
      </div>
    </div>
  )
}
