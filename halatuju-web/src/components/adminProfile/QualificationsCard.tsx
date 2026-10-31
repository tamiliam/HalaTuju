'use client'

import InstitutionPicker from '@/components/InstitutionPicker'
import SelectWithOther from '@/components/SelectWithOther'
import { COMMON_UNIVERSITIES } from '@/data/publicUniversities'
import type { LangFluency } from '@/lib/admin-api'
import { CardFrame, inputCls, labelCls, Req, type CardProps } from './shared'

const QUAL_OPTS = [
  ['SPM', 'spm'], ['STPM', 'stpm'], ['Matriculation', 'matriculation'], ['Diploma', 'diploma'],
  ["Bachelor's Degree", 'bachelor'], ["Master's Degree", 'master'], ['PhD', 'phd'],
  ['Professional Qualification', 'professional'],
] as const
const FIELD_OPTS = [
  ['Engineering', 'engineering'], ['Computer Science / IT', 'it'], ['Medicine & Health Sciences', 'medicine'],
  ['Science', 'science'], ['Business & Economics', 'business'], ['Accounting & Finance', 'accounting'],
  ['Law', 'law'], ['Education', 'education'], ['Arts & Humanities', 'arts'], ['Social Sciences', 'social'],
] as const

const UNI_OPTIONS = COMMON_UNIVERSITIES.map((u) => ({
  name: u.name, hint: u.hint, keywords: (u.aliases ?? []).join(' '),
}))

const LANGS = [
  ['english_fluency', 'admin.reviewer.langEnglish'],
  ['bm_fluency', 'admin.reviewer.langBm'],
  ['tamil_fluency', 'admin.reviewer.langTamil'],
] as const

/**
 * "Qualifications and languages" — the reviewer credentials and the three language fluencies,
 * the two cards of before merged into one; every field is unchanged. Holders of `review`, never a
 * super. (It carries the page's only heavy imports — the university list and its picker — which are
 * why the cards are loaded lazily, off the route's first load; see `cards.tsx`.)
 */
export default function QualificationsCard({ state }: CardProps) {
  const { t, draft, setRev } = state
  const rev = draft.reviewer
  const qualOpts = QUAL_OPTS.map(([value, key]) => ({ value, label: t(`admin.reviewer.qualOpts.${key}`) }))
  const fieldOpts = FIELD_OPTS.map(([value, key]) => ({ value, label: t(`admin.reviewer.fieldOpts.${key}`) }))
  return (
    <CardFrame title={t('admin.myProfile.qualifications')} testId="qualifications">
      <p className="text-sm text-ground-500 -mt-2">{t('admin.reviewer.subtitle')}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <span className={labelCls}>{t('admin.reviewer.highestQualification')}<Req /></span>
          <SelectWithOther
            value={rev?.highest_qualification ?? ''}
            onChange={(v) => setRev({ highest_qualification: v })}
            options={qualOpts}
            placeholder={t('admin.reviewer.selectQualification')}
            otherText={t('admin.reviewer.other')}
            className={inputCls}
          />
        </div>
        <div>
          <span className={labelCls}>{t('admin.reviewer.fieldOfStudy')}<Req /></span>
          <SelectWithOther
            value={rev?.field_of_study ?? ''}
            onChange={(v) => setRev({ field_of_study: v })}
            options={fieldOpts}
            placeholder={t('admin.reviewer.selectField')}
            otherText={t('admin.reviewer.other')}
            className={inputCls}
          />
        </div>
        <div>
          <span className={labelCls}>{t('admin.reviewer.university')}<Req /></span>
          <InstitutionPicker
            options={UNI_OPTIONS}
            value={rev?.university ?? ''}
            onChange={(v) => setRev({ university: v })}
            placeholder={t('admin.reviewer.universityHint')}
            allowCustom
            minChars={2}
          />
        </div>
        <div>
          <label htmlFor="profile-grad-year" className={labelCls}>{t('admin.reviewer.graduationYear')}<Req /></label>
          <input
            id="profile-grad-year" type="number" inputMode="numeric" min={1950} max={2100}
            value={rev?.graduation_year ?? ''}
            onChange={(e) => setRev({ graduation_year: e.target.value === '' ? null : Number(e.target.value) })}
            className={inputCls}
          />
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium text-ground-700">{t('admin.reviewer.langTitle')}<Req /></h3>
        <p className="text-sm text-ground-500">{t('admin.reviewer.langSubtitle')} {t('admin.reviewer.onboarding.langHint')}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {LANGS.map(([field, labelKey]) => (
          <div key={field}>
            <label htmlFor={`profile-${field}`} className={labelCls}>{t(labelKey)}</label>
            <select id={`profile-${field}`} value={rev?.[field] ?? ''}
              onChange={(e) => setRev({ [field]: e.target.value as LangFluency })} className={inputCls}>
              <option value="">{t('admin.reviewer.fluencyNone')}</option>
              <option value="conversational">{t('admin.reviewer.fluencyConversational')}</option>
              <option value="fluent">{t('admin.reviewer.fluencyFluent')}</option>
            </select>
          </div>
        ))}
      </div>
    </CardFrame>
  )
}
