/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import type { ComponentType } from 'react'
import { useT } from '@/lib/i18n'
import { maskIc } from '@/lib/ic-utils'
import { hasIcFlags } from '@/lib/icEditor'
import BumiputeraField from '@/components/profile/BumiputeraField'
import { FieldValue, FieldLabel } from '@/components/profile/profileFields'
import SectionCard, { PROFILE_ROWS } from './SectionCard'
import type { SectionProps } from '../useProfileEditor'

/** The identity section: its card, its read-only rows, and (once fetched) its edit panel. */
export default function IdentitySection({ f, ed, Edit }: SectionProps & { Edit?: ComponentType<SectionProps> }) {
  const { t } = useT()
  const { name, nric, gender, bumiputera, colorblind, disability, identityVerified, icFlagCodes, malaysian, icEditable } = f
  const { editingSection, startEditing } = ed
  return (
    <SectionCard
      title={t('profile.personalDetails')}
      incomplete={f.identityIncomplete}
      icon={<>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0" />
      </>}
      canEdit={editingSection === null}
      onEdit={() => startEditing('identity')}
    >
      {editingSection === 'identity' && Edit ? <Edit f={f} ed={ed} /> : (
        <div className={`grid grid-cols-1 md:grid-cols-2 md:gap-3 ${PROFILE_ROWS}`}>
          <div className="flex justify-between">
            <span className="text-sm text-ground-500 flex items-center gap-1.5">
              {/* Same correction as the edit panel: the padlock is drawn only when the IC
                  is actually locked, not on every render. */}
              {!icEditable && (
                <svg className="w-3.5 h-3.5 text-ground-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                </svg>
              )}
              {t('profile.icMasked')}
            </span>
            <span className="text-sm text-ground-900 font-mono flex items-center gap-1.5">
              {nric ? maskIc(nric) : '—'}
              {nric && identityVerified && (
                <span className="px-1.5 py-0.5 bg-positive-50 text-positive-700 text-[10px] font-medium rounded-full">{t('profile.verified')}</span>
              )}
              {/* A quiet marker that something needs their attention, so a student who
                  never opens the edit panel still learns the card disagrees. */}
              {hasIcFlags(icFlagCodes) && (
                <span className="px-1.5 py-0.5 bg-caution-50 text-caution-700 text-[10px] font-medium rounded-full">{t('profile.icNeedsCheck')}</span>
              )}
            </span>
          </div>
          <div className="flex justify-between">
            <FieldLabel label={t('profile.name')} empty={!name} />
            {name ? (
              <span className="text-sm text-ground-900 flex items-center gap-1.5">
                {name}
                {identityVerified && (
                  <span className="px-1.5 py-0.5 bg-positive-50 text-positive-700 text-[10px] font-medium rounded-full">{t('profile.verified')}</span>
                )}
              </span>
            ) : (
              <FieldValue value="" t={t} />
            )}
          </div>
          <div className="flex justify-between">
            <FieldLabel label={t('onboarding.gender')} empty={!gender} />
            {gender ? (
              <span className="text-sm text-ground-900">{t(`onboarding.${gender}`)}</span>
            ) : (
              <FieldValue value="" t={t} />
            )}
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-ground-500">{t('onboarding.nationality')}</span>
            <span className="text-sm text-ground-900">{malaysian ? t('onboarding.malaysian') : t('onboarding.nonMalaysian')}</span>
          </div>
          {malaysian && <BumiputeraField value={bumiputera} t={t} />}
          <div className="flex justify-between">
            <span className="text-sm text-ground-500">{t('profile.colorBlindness')}</span>
            <span className="text-sm text-ground-900">{colorblind ? t('profile.yes') : t('profile.no')}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-ground-500">{t('profile.physicalDisability')}</span>
            <span className="text-sm text-ground-900">{disability ? t('profile.yes') : t('profile.no')}</span>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
