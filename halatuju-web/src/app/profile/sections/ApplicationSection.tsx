/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import type { ComponentType } from 'react'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { setOnboardingReturn } from '@/lib/scholarship'
import { FieldValue, FieldLabel } from '@/components/profile/profileFields'
import SectionCard, { PROFILE_ROWS, EditLoading } from './SectionCard'
import type { SectionProps } from '../useProfileEditor'

/** The application section: its card, its read-only rows, and (once fetched) its edit panel. */
export default function ApplicationSection({ f, ed, Edit }: SectionProps & { Edit?: ComponentType<SectionProps> }) {
  const { t } = useT()
  const router = useRouter()
  const { pathwayForm, angkaGiliran, school, resultsPath, meritShown, meritLabel } = f
  const { editingSection, startEditing } = ed
  return (
    <SectionCard
      title={t('profile.applicationTracking')}
      incomplete={f.appIncomplete}
      icon={<>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
      </>}
      canEdit={editingSection === null || (editingSection === 'application' && !Edit)}
      onEdit={() => startEditing('application')}
    >
      {editingSection === 'application' && !Edit ? <EditLoading /> : editingSection === 'application' && Edit ? <Edit f={f} ed={ed} /> : (
        <div className={`${PROFILE_ROWS} md:space-y-3`}>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.school')} empty={!school} />
            {school ? (
              <span className="text-sm text-ground-900 text-right">{school}</span>
            ) : (
              <FieldValue value="" t={t} />
            )}
          </div>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.angkaGiliran')} empty={!angkaGiliran} />
            {angkaGiliran ? (
              <span className="text-sm text-ground-900 font-mono">{angkaGiliran}</span>
            ) : (
              <FieldValue value="" t={t} />
            )}
          </div>
          {/* Merit — tap to the grades editor, then return here (not the
              course-guide recommendations). */}
          <button type="button" onClick={() => { setOnboardingReturn('/profile'); router.push(resultsPath) }}
            className="w-full min-h-11 flex justify-between items-center gap-3 text-left group">
            <span className="text-sm text-ground-500">{meritLabel}</span>
            <span className={`text-sm text-right ${meritShown != null ? 'text-ground-900 font-semibold' : 'text-caution-700'} group-hover:text-primary-600`}>
              {meritShown != null ? meritShown : t('profile.meritTapAdd')}
            </span>
          </button>
          {/* Pathway — show the chosen COURSE when one exists, else the pathway type;
              tap to edit inline. */}
          <button type="button" onClick={() => startEditing('application')}
            className="w-full min-h-11 flex justify-between items-center gap-3 text-left group">
            <span className="text-sm text-ground-500">{t('profile.pathway')}</span>
            <span className={`text-sm text-right ${(pathwayForm.chosenProgramme?.courseName || pathwayForm.chosenPathway) ? 'text-ground-900' : 'text-caution-700'} group-hover:text-primary-600`}>
              {pathwayForm.chosenProgramme?.courseName
                || (pathwayForm.chosenPathway ? t(`scholarship.apply.plan.pathway.${pathwayForm.chosenPathway}`) : t('profile.pathwayTapAdd'))}
            </span>
          </button>
        </div>
      )}
    </SectionCard>
  )
}
