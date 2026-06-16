'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getAdminProfile, updateAdminProfile, type AdminProfile,
  getReviewerProfile, updateReviewerProfile, type ReviewerProfile, type LangFluency,
} from '@/lib/admin-api'
import { useT } from '@/lib/i18n'
import { MALAYSIAN_STATES } from '@/lib/scholarship'
import { formatMyMobile } from '@/lib/sponsorAuth'
import InstitutionPicker from '@/components/InstitutionPicker'
import SelectWithOther from '@/components/SelectWithOther'
import { PUBLIC_UNIVERSITIES } from '@/data/publicUniversities'

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

const UNI_OPTIONS = PUBLIC_UNIVERSITIES.map((u) => ({
  name: u.name, hint: u.acronym, keywords: `${u.acronym} ${(u.aliases ?? []).join(' ')}`,
}))

const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

export default function AdminProfilePage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const [profile, setProfile] = useState<AdminProfile | null>(null)
  const [name, setName] = useState('')
  const [contactPerson, setContactPerson] = useState('')
  const [orgPhone, setOrgPhone] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // BUG FIX (2026-06): reviewer credentials belong to REVIEWERS ONLY. A super admin
  // is not a reviewer and must not see (or be asked for) reviewer credentials.
  const isReviewer = role?.role === 'reviewer'
  const [reviewer, setReviewer] = useState<ReviewerProfile | null>(null)

  useEffect(() => {
    if (!token) return
    getAdminProfile({ token }).then((data) => {
      setProfile(data)
      setName(data.name)
      setContactPerson(data.org_contact_person || '')
      setOrgPhone(data.org_phone || '')
    }).catch(() => {})
  }, [token])

  useEffect(() => {
    if (!token || !isReviewer) return
    getReviewerProfile({ token }).then(setReviewer).catch(() => {})
  }, [token, isReviewer])

  if (!profile) {
    return <div className="mt-8 text-center text-gray-500">{t('common.loading')}</div>
  }

  const setRev = (patch: Partial<ReviewerProfile>) =>
    setReviewer((prev) => ({ ...(prev ?? blankReviewer()), ...patch }))

  const qualOpts = QUAL_OPTS.map(([value, key]) => ({ value, label: t(`admin.reviewer.qualOpts.${key}`) }))
  const fieldOpts = FIELD_OPTS.map(([value, key]) => ({ value, label: t(`admin.reviewer.fieldOpts.${key}`) }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const data: Record<string, string> = { name }
      if (profile.org_name) {
        data.org_contact_person = contactPerson
        data.org_phone = orgPhone
      }
      await updateAdminProfile(data, { token: token! })
      if (isReviewer && reviewer) {
        await updateReviewerProfile(reviewer, { token: token! })
      }
      setMessage({ type: 'success', text: t('admin.profileUpdated') })
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : t('admin.profileUpdateFailed') })
    }
    setSaving(false)
  }

  const card = 'bg-white rounded-xl p-6 shadow-sm border space-y-4'
  const labelCls = 'block text-sm text-gray-600 mb-1'

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{t('admin.profileTitle')}</h1>

      {message && (
        <div className={`rounded-lg p-4 my-6 ${message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 mt-6">
        {/* Your information */}
        <div className={card}>
          <h2 className="font-semibold">{t('admin.yourInfo')}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className={labelCls}>{t('admin.name')}</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} className={inputCls} required />
            </div>
            <div>
              <label className={labelCls}>{t('admin.emailLabel')}</label>
              <p className="text-sm text-gray-800 px-3 py-2 bg-gray-50 rounded-lg truncate">{profile.email}</p>
            </div>
          </div>
        </div>

        {/* Organisation — partner only */}
        {profile.org_name && (
          <div className={card}>
            <h2 className="font-semibold">{t('admin.orgInfo', { org: profile.org_name })}</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelCls}>{t('admin.contactPersonLabel')}</label>
                <input type="text" value={contactPerson} onChange={(e) => setContactPerson(e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>{t('admin.orgPhone')}</label>
                <PhoneField value={orgPhone} onChange={setOrgPhone} />
              </div>
            </div>
          </div>
        )}

        {/* Reviewer credentials + contact — reviewer only */}
        {isReviewer && (
          <>
            <div className={card}>
              <h2 className="font-semibold">{t('admin.reviewer.title')}</h2>
              <p className="text-sm text-gray-500 -mt-2">{t('admin.reviewer.subtitle')}</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className={labelCls}>{t('admin.reviewer.highestQualification')}</label>
                  <SelectWithOther
                    value={reviewer?.highest_qualification ?? ''}
                    onChange={(v) => setRev({ highest_qualification: v })}
                    options={qualOpts}
                    placeholder={t('admin.reviewer.selectQualification')}
                    otherText={t('admin.reviewer.other')}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('admin.reviewer.fieldOfStudy')}</label>
                  <SelectWithOther
                    value={reviewer?.field_of_study ?? ''}
                    onChange={(v) => setRev({ field_of_study: v })}
                    options={fieldOpts}
                    placeholder={t('admin.reviewer.selectField')}
                    otherText={t('admin.reviewer.other')}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('admin.reviewer.university')}</label>
                  <InstitutionPicker
                    options={UNI_OPTIONS}
                    value={reviewer?.university ?? ''}
                    onChange={(v) => setRev({ university: v })}
                    placeholder={t('admin.reviewer.universityHint')}
                    allowCustom
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('admin.reviewer.graduationYear')}</label>
                  <input
                    type="number" inputMode="numeric" min={1950} max={2100}
                    value={reviewer?.graduation_year ?? ''}
                    onChange={(e) => setRev({ graduation_year: e.target.value === '' ? null : Number(e.target.value) })}
                    className={inputCls}
                  />
                </div>
              </div>
            </div>

            <div className={card}>
              <h2 className="font-semibold">{t('admin.reviewer.langTitle')}</h2>
              <p className="text-sm text-gray-500 -mt-2">{t('admin.reviewer.langSubtitle')}</p>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className={labelCls}>{t('admin.reviewer.langEnglish')}</label>
                  <select value={reviewer?.english_fluency ?? ''}
                    onChange={(e) => setRev({ english_fluency: e.target.value as LangFluency })} className={inputCls}>
                    <option value="">{t('admin.reviewer.fluencyNone')}</option>
                    <option value="conversational">{t('admin.reviewer.fluencyConversational')}</option>
                    <option value="fluent">{t('admin.reviewer.fluencyFluent')}</option>
                  </select>
                </div>
                <div>
                  <label className={labelCls}>{t('admin.reviewer.langBm')}</label>
                  <select value={reviewer?.bm_fluency ?? ''}
                    onChange={(e) => setRev({ bm_fluency: e.target.value as LangFluency })} className={inputCls}>
                    <option value="">{t('admin.reviewer.fluencyNone')}</option>
                    <option value="conversational">{t('admin.reviewer.fluencyConversational')}</option>
                    <option value="fluent">{t('admin.reviewer.fluencyFluent')}</option>
                  </select>
                </div>
                <div>
                  <label className={labelCls}>{t('admin.reviewer.langTamil')}</label>
                  <select value={reviewer?.tamil_fluency ?? ''}
                    onChange={(e) => setRev({ tamil_fluency: e.target.value as LangFluency })} className={inputCls}>
                    <option value="">{t('admin.reviewer.fluencyNone')}</option>
                    <option value="conversational">{t('admin.reviewer.fluencyConversational')}</option>
                    <option value="fluent">{t('admin.reviewer.fluencyFluent')}</option>
                  </select>
                </div>
              </div>
            </div>

            <div className={card}>
              <h2 className="font-semibold flex items-center gap-2">
                <span aria-hidden>🔒</span>{t('admin.reviewer.contactTitle')}
              </h2>
              <p className="text-sm text-gray-500 -mt-2 italic">{t('admin.reviewer.contactSubtitle')}</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className={labelCls}>{t('admin.reviewer.phone')}</label>
                  <PhoneField value={reviewer?.phone ?? ''} onChange={(v) => setRev({ phone: v })} />
                </div>
              </div>
              <label className="flex items-start gap-2 text-sm text-gray-700">
                <input type="checkbox" className="mt-0.5"
                  checked={reviewer?.share_phone_with_students ?? true}
                  onChange={(e) => setRev({ share_phone_with_students: e.target.checked })} />
                <span>{t('admin.reviewer.sharePhone')}</span>
              </label>
              <div>
                <label className={labelCls}>{t('admin.reviewer.street')}</label>
                <input type="text" value={reviewer?.street_address ?? ''} onChange={(e) => setRev({ street_address: e.target.value })} className={inputCls} />
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className={labelCls}>{t('admin.reviewer.postcode')}</label>
                  <input type="text" inputMode="numeric" value={reviewer?.postcode ?? ''}
                    onChange={(e) => setRev({ postcode: e.target.value.replace(/[^0-9]/g, '').slice(0, 5) })} className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>{t('admin.reviewer.city')}</label>
                  <input type="text" value={reviewer?.city ?? ''} onChange={(e) => setRev({ city: e.target.value })} className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>{t('admin.reviewer.state')}</label>
                  <select value={reviewer?.state ?? ''} onChange={(e) => setRev({ state: e.target.value })} className={inputCls}>
                    <option value="">{t('admin.reviewer.selectState')}</option>
                    {MALAYSIAN_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>
            </div>
          </>
        )}

        <button type="submit" disabled={saving || !name}
          className="w-full sm:w-auto px-8 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
          {saving ? t('admin.saving') : t('common.save')}
        </button>
      </form>
    </div>
  )
}

/** Malaysian phone input: a fixed +60 prefix + a masked local part (12-345 6789). */
function PhoneField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-stretch">
      <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-sm text-gray-500">+60</span>
      <input
        type="tel" inputMode="numeric"
        value={formatMyMobile(value)}
        onChange={(e) => onChange(formatMyMobile(e.target.value))}
        placeholder="12-345 6789"
        className="w-full px-3 py-2 border border-gray-300 rounded-r-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
    </div>
  )
}

function blankReviewer(): ReviewerProfile {
  return {
    highest_qualification: '', university: '', graduation_year: null,
    field_of_study: '', phone: '', address: '',
    street_address: '', postcode: '', city: '', state: '',
    english_fluency: '', bm_fluency: '', tamil_fluency: '',
    share_phone_with_students: true,
  }
}
