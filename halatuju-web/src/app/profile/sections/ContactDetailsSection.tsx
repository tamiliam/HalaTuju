/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import type { ComponentType } from 'react'
import { useT } from '@/lib/i18n'
import { FieldValue, FieldLabel } from '@/components/profile/profileFields'
import SectionCard, { PROFILE_ROWS, EditLoading } from './SectionCard'
import type { SectionProps } from '../useProfileEditor'

/** The contactDetails section: its card, its read-only rows, and (once fetched) its edit panel. */
export default function ContactDetailsSection({ f, ed, Edit }: SectionProps & { Edit?: ComponentType<SectionProps> }) {
  const { t } = useT()
  const { contactEmail, contactEmailVerified, contactPhone, contactPhoneVerified, whatsappOptIn, loginMethod } = f
  const { editingSection, startEditing } = ed
  return (
    <SectionCard
      title={t('profile.contactDetails')}
      incomplete={f.contactDetailsIncomplete}
      icon={<>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
      </>}
      canEdit={editingSection === null || (editingSection === 'contactDetails' && !Edit)}
      onEdit={() => startEditing('contactDetails')}
    >
      {editingSection === 'contactDetails' && !Edit ? <EditLoading /> : editingSection === 'contactDetails' && Edit ? <Edit f={f} ed={ed} /> : (
        <div className={`${PROFILE_ROWS} md:space-y-3`}>
          <div className="flex justify-between">
            <span className="text-sm text-ground-500">{t('profile.loginMethod')}</span>
            <span className="text-sm text-ground-900">{loginMethod || '—'}</span>
          </div>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.contactEmail')} empty={!contactEmail} />
            {contactEmail ? (
              <span className="flex min-w-0 flex-wrap items-center justify-end gap-1.5 break-all text-right text-sm text-ground-900">
                {contactEmail}
                {contactEmailVerified ? (
                  <span className="px-1.5 py-0.5 bg-positive-50 text-positive-700 text-[10px] font-medium rounded-full">{t('profile.verified')}</span>
                ) : (
                  <span className="text-caution-700 text-xs">{t('profile.notVerified')}</span>
                )}
              </span>
            ) : (
              <FieldValue value="" t={t} />
            )}
          </div>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.contactPhone')} empty={!contactPhone} />
            {contactPhone ? (
              <span className="flex min-w-0 flex-wrap items-center justify-end gap-1.5 break-all text-right text-sm text-ground-900">
                {contactPhone}
                {contactPhoneVerified ? (
                  <span className="px-1.5 py-0.5 bg-positive-50 text-positive-700 text-[10px] font-medium rounded-full">{t('profile.verified')}</span>
                ) : (
                  <span className="text-caution-700 text-xs">{t('profile.notVerified')}</span>
                )}
              </span>
            ) : (
              <FieldValue value="" t={t} />
            )}
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-ground-500">{t('profile.whatsappUpdates')}</span>
            <span className="text-sm text-ground-900">{whatsappOptIn ? t('profile.whatsappOn') : t('profile.whatsappOff')}</span>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
