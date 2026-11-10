/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import { useT } from '@/lib/i18n'
import FamilyRosterFields from '@/components/FamilyRosterFields'
import type { SectionProps } from '../../useProfileEditor'

/** The family section's edit panel. Fetched as one chunk with the other four (see `useProfileEditors`). */
export default function FamilyEdit({ f, ed }: SectionProps) {
  const { t } = useT()
  const { householdIncome, setHouseholdIncome, householdSize, setHouseholdSize, family, saving, updateFamily, addFamilyMember, removeFamilyMember, updateFamilyMember, householdSizeInvalid, householdIncomeInvalid } = f
  const { cancelEditing, saveSection } = ed
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.householdIncome')}</label>
        <input
          type="number"
          min="0"
          inputMode="numeric"
          placeholder="2500"
          value={householdIncome}
          onChange={e => setHouseholdIncome(e.target.value)}
          className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-1 outline-none ${householdIncomeInvalid ? 'border-critical-400 focus:border-critical-500 focus:ring-critical-500' : 'border-ground-300 focus:border-brand-shape focus:ring-brand-shape'}`}
        />
        {householdIncomeInvalid
          ? <p className="text-xs text-critical-600 mt-1">{t('profile.invalidHouseholdIncome')}</p>
          : <p className="text-xs text-ground-400 mt-1">{t('profile.householdIncomeHelper')}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.householdSize')}</label>
        <input
          type="number"
          min="1"
          max="20"
          value={householdSize}
          onChange={e => setHouseholdSize(e.target.value)}
          className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-1 outline-none ${householdSizeInvalid ? 'border-critical-400 focus:border-critical-500 focus:ring-critical-500' : 'border-ground-300 focus:border-brand-shape focus:ring-brand-shape'}`}
        />
        {householdSizeInvalid
          ? <p className="text-xs text-critical-600 mt-1">{t('profile.invalidHouseholdSize')}</p>
          : <p className="text-xs text-ground-400 mt-1">{t('profile.householdSizeHelper')}</p>}
      </div>
      {/* Structured family roster — the shared editor; while a B40
          application is open these values stay linked to it. */}
      <div className="border-t border-ground-100 pt-4">
        <p className="text-sm font-medium text-ground-900 mb-3">{t('profile.familyMembers')}</p>
        <FamilyRosterFields
          form={family}
          onUpdate={updateFamily}
          onUpdateMember={updateFamilyMember}
          onAddMember={addFamilyMember}
          onRemoveMember={removeFamilyMember}
          t={t}
          profileStyle
        />
      </div>
      <div className="flex gap-3 pt-4">
        <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-ground-300 rounded-lg text-sm font-medium text-ground-700 hover:bg-ground-50">
          {t('profile.cancel')}
        </button>
        <button onClick={saveSection} disabled={saving || householdSizeInvalid || householdIncomeInvalid} className="flex-1 px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover disabled:opacity-50">
          {saving ? '...' : t('profile.save')}
        </button>
      </div>
    </div>
  )
}
