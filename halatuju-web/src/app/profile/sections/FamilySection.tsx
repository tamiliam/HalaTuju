/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import type { ComponentType } from 'react'
import { useT } from '@/lib/i18n'
import LazyGuardianContactSection from '@/components/profile/LazyGuardianContactSection'
import { FieldValue, FieldLabel } from '@/components/profile/profileFields'
import SectionCard, { PROFILE_ROWS, EditLoading } from './SectionCard'
import type { SectionProps } from '../useProfileEditor'

/** The family section: its card, its read-only rows, and (once fetched) its edit panel. */
export default function FamilySection({ f, ed, Edit }: SectionProps & { Edit?: ComponentType<SectionProps> }) {
  const { t } = useT()
  const { householdIncome, householdSize, family, familySummary } = f
  const { editingSection, startEditing } = ed
  return (
    <SectionCard
      title={t('profile.familyBackground')}
      incomplete={f.familyIncomplete}
      icon={<>
        <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
      </>}
      canEdit={editingSection === null || (editingSection === 'family' && !Edit)}
      onEdit={() => startEditing('family')}
    >
      {editingSection === 'family' && !Edit ? <EditLoading /> : editingSection === 'family' && Edit ? <Edit f={f} ed={ed} /> : (
        <div className={`${PROFILE_ROWS} md:space-y-3`}>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.householdIncome')} empty={!householdIncome} />
            <FieldValue value={householdIncome ? `RM ${parseInt(householdIncome, 10).toLocaleString('en-MY')}` : ''} t={t} />
          </div>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.householdSize')} empty={!householdSize} />
            <FieldValue value={householdSize} t={t} />
          </div>
          <div className="border-t border-ground-100 pt-3 space-y-2">
            <div className="flex justify-between gap-3">
              <span className="text-sm text-ground-500 shrink-0">{t('scholarship.nextSteps.story.cardA.father')}</span>
              <span className="text-sm text-ground-900 text-right">{familySummary('father')}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-sm text-ground-500 shrink-0">{t('scholarship.nextSteps.story.cardA.mother')}</span>
              <span className="text-sm text-ground-900 text-right">{familySummary('mother')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-ground-500">{t('profile.siblingsSchoolView')}</span>
              <span className="text-sm text-ground-900">{family.siblingsInSchool}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-ground-500">{t('profile.siblingsTertiaryView')}</span>
              <span className="text-sm text-ground-900">{family.siblingsInTertiary}</span>
            </div>
            {family.otherFamilyMembers.length > 0 && (
              <div className="flex justify-between">
                <span className="text-sm text-ground-500">{t('profile.familyOthers')}</span>
                <span className="text-sm text-ground-900">{family.otherFamilyMembers.length}</span>
              </div>
            )}
          </div>
          <LazyGuardianContactSection />{/* request #26: only for applicants; its own edit + lock */}
        </div>
      )}
    </SectionCard>
  )
}
