/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import { useT } from '@/lib/i18n'
import { formatIc, maskIc } from '@/lib/ic-utils'
import { hasIcFlags, icFieldValue, icFlags } from '@/lib/icEditor'
import BumiputeraField from '@/components/profile/BumiputeraField'
import type { SectionProps } from '../../useProfileEditor'

/** The identity section's edit panel. Fetched as one chunk with the other four (see `useProfileEditors`). */
export default function IdentityEdit({ f, ed }: SectionProps) {
  const { t } = useT()
  const { name, setName, nric, gender, setGender, nationality, setNationality, bumiputera, setBumiputera, colorblind, setColorblind, disability, setDisability, icFlagCodes, icCardNric, icCardName, nricDraft, setNricDraft, nricError, setNricError, saving, malaysian, icEditable, icFixable } = f
  const { cancelEditing, saveSection } = ed
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.icMasked')}</label>
        <div className="relative">
          {/* ⚠ Keyed on `nricLocked` (the STORED lock), never on identityVerified.
              Until 2026-07-29 `disabled` was a bare attribute here, so every student
              saw a padlock whether or not anything had locked — which is why Gopal's
              "correct it on your Profile page" read as nonsense. */}
          <input
            type="text"
            value={icEditable
              ? nricDraft
              : icFieldValue(nric, nric ? maskIc(nric) : '', false) || '—'}
            onChange={e => { setNricDraft(formatIc(e.target.value)); setNricError('') }}
            disabled={!icEditable}
            inputMode="numeric"
            placeholder="XXXXXX-XX-XXXX"
            aria-label={t('profile.icMasked')}
            className={`w-full px-3 py-2.5 border rounded-lg text-sm font-mono pr-10 ${
              icEditable
                ? 'border-ground-300 focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none'
                : 'border-ground-200 bg-ground-50 text-ground-500 cursor-not-allowed'
            }`}
          />
          {!icEditable && (
            <svg className="w-4 h-4 text-ground-400 absolute right-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
            </svg>
          )}
        </div>
        {nricError && <p className="mt-1.5 text-xs text-critical-600">{nricError}</p>}
        <p className="mt-1.5 text-xs text-ground-500">
          {icEditable ? t('profile.icEditable') : t('profile.icLockedNote')}
        </p>
      </div>

      {/* What the uploaded card disagrees with. Deliberately shows BOTH values and
          does not say which is wrong: our OCR splits and glues names (apps #27, #118),
          so blaming the student would sometimes be blaming ourselves. */}
      {hasIcFlags(icFlagCodes) && (
        <div className="rounded-lg border border-caution-200 bg-caution-50 px-3 py-2.5">
          <p className="text-xs font-medium text-caution-900">{t('profile.icFlagTitle')}</p>
          <ul className="mt-1.5 space-y-1">
            {icFlags(icFlagCodes).map(code => (
              <li key={code} className="text-xs text-caution-800">
                {t(`profile.icFlag.${code}`)}
              </li>
            ))}
          </ul>
          <dl className="mt-2 space-y-0.5 text-xs text-caution-900">
            {icCardNric && (
              <div className="flex gap-2">
                <dt className="font-medium">{t('profile.icOnCard')}</dt>
                <dd className="font-mono">{icCardNric}</dd>
              </div>
            )}
            {icCardName && (
              <div className="flex gap-2">
                <dt className="font-medium">{t('profile.icNameOnCard')}</dt>
                <dd>{icCardName}</dd>
              </div>
            )}
          </dl>
          <p className="mt-2 text-xs text-caution-800">
            {t(`profile.icFixable.${icFixable}`)}
          </p>
        </div>
      )}
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.name')} <span className="text-critical-600">*</span></label>
        <input
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          className="w-full px-3 py-2.5 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('onboarding.gender')} <span className="text-critical-600">*</span></label>
          <div className="flex gap-2">
            {(['male', 'female'] as const).map(g => (
              <button
                key={g}
                onClick={() => setGender(g)}
                className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                  gender === g
                    ? 'bg-primary-50 border-brand-shape text-primary-700'
                    : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'
                }`}
              >
                {t(`onboarding.${g}`)}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('onboarding.nationality')}</label>
          <div className="flex gap-2">
            {(['malaysian', 'non_malaysian'] as const).map(n => (
              <button
                key={n}
                onClick={() => { setNationality(n); if (n !== 'malaysian') setBumiputera(null) }}   // Foreign wipes the answer
                className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${
                  nationality === n
                    ? 'bg-primary-50 border-brand-shape text-primary-700'
                    : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'
                }`}
              >
                {n === 'malaysian' ? t('onboarding.malaysian') : t('onboarding.nonMalaysian')}
              </button>
            ))}
          </div>
        </div>
      </div>
      {malaysian && <div className="grid grid-cols-1 md:grid-cols-2 gap-4"><BumiputeraField value={bumiputera} onChange={setBumiputera} t={t} /></div>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.colorBlindness')}</label>
          <div className="flex gap-2">
            <button onClick={() => setColorblind(true)} className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${colorblind ? 'bg-primary-50 border-brand-shape text-primary-700' : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'}`}>{t('profile.yes')}</button>
            <button onClick={() => setColorblind(false)} className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${!colorblind ? 'bg-primary-50 border-brand-shape text-primary-700' : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'}`}>{t('profile.no')}</button>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.physicalDisability')}</label>
          <div className="flex gap-2">
            <button onClick={() => setDisability(true)} className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${disability ? 'bg-primary-50 border-brand-shape text-primary-700' : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'}`}>{t('profile.yes')}</button>
            <button onClick={() => setDisability(false)} className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all border ${!disability ? 'bg-primary-50 border-brand-shape text-primary-700' : 'bg-ground-0 border-ground-300 text-ground-600 hover:border-ground-400'}`}>{t('profile.no')}</button>
          </div>
        </div>
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
