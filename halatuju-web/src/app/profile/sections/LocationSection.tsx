/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import type { ComponentType } from 'react'
import { useT } from '@/lib/i18n'
import { FieldLabel } from '@/components/profile/profileFields'
import SectionCard, { PROFILE_ROWS } from './SectionCard'
import type { SectionProps } from '../useProfileEditor'

/** The contact section: its card, its read-only rows, and (once fetched) its edit panel. */
export default function LocationSection({ f, ed, Edit }: SectionProps & { Edit?: ComponentType<SectionProps> }) {
  const { t } = useT()
  const { state, address, postalCode, city } = f
  const { editingSection, startEditing } = ed
  return (
    <SectionCard
      title={t('profile.contactLocation')}
      incomplete={f.contactIncomplete}
      icon={<>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
      </>}
      canEdit={editingSection === null}
      onEdit={() => startEditing('contact')}
    >
      {editingSection === 'contact' && Edit ? <Edit f={f} ed={ed} /> : (
        <div className={`${PROFILE_ROWS} md:space-y-3`}>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.address')} empty={!address && !postalCode && !city && !state} />
            <span className="text-sm text-ground-900 text-right max-w-[60%]">
              {[address, [postalCode, city].filter(Boolean).join(' '), state].filter(Boolean).join(', ') || (
                <span className="text-caution-700 italic">{t('profile.notSet')}</span>
              )}
            </span>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
