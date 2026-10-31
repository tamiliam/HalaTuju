'use client'

import { useEffect } from 'react'
import { formatPhone, isValidPhone } from '@/lib/scholarship'
import { CardFrame, inputCls, labelCls, PhoneField, Req, type CardProps, type SourceForm } from './shared'

const S = 'admin.sourceConsole.profile'

/**
 * "Organisation" — role `partner` or `source_partner`, two shapes of one card:
 *
 *  - a referral PARTNER edits its organisation's contact person and phone (`admin/profile/` PUT,
 *    as before);
 *  - a SOURCE user edits its source's name, contact person, email for updates and phone
 *    (`admin/source/profile/` PATCH, as before) — which are the source's OWN once it has signed in
 *    (the Sources page locks them, 409 `managed_by_source`). The code and the organisation stay
 *    the organisation's.
 */
export default function OrganisationCard({ state }: CardProps) {
  return state.role === 'source_partner' ? <SourceOrganisation state={state} /> : <PartnerOrganisation state={state} />
}

function PartnerOrganisation({ state }: CardProps) {
  const { t, draft, set, orgName } = state
  if (!orgName) {
    return (
      <CardFrame title={t('admin.myProfile.organisation')} testId="organisation">
        <p className="text-sm text-ground-500">{t('admin.myProfile.noOrganisation')}</p>
      </CardFrame>
    )
  }
  return (
    <CardFrame title={t('admin.orgInfo', { org: orgName })} testId="organisation">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="profile-org-contact" className={labelCls}>{t('admin.contactPersonLabel')}</label>
          <input id="profile-org-contact" type="text" value={draft.orgContact}
            onChange={(e) => set({ orgContact: e.target.value })} className={inputCls} />
        </div>
        <div>
          <label htmlFor="profile-org-phone" className={labelCls}>{t('admin.orgPhone')}</label>
          <PhoneField id="profile-org-phone" value={draft.orgPhone} onChange={(v) => set({ orgPhone: v })} />
        </div>
      </div>
    </CardFrame>
  )
}

function SourceOrganisation({ state }: CardProps) {
  const { t, draft, saved, set, report } = state
  const form = draft.source
  // Judged only once the phone itself is edited (review M2): a number stored before this check
  // existed must never stop somebody saving their name.
  const phoneBad = !!form && form.phone !== saved.source?.phone && form.phone.trim() !== ''
    && !isValidPhone(form.phone)
  useEffect(() => { report('sourcePhone', phoneBad) }, [phoneBad, report])
  if (!form) return null

  const edit = (patch: Partial<SourceForm>) => set({ source: { ...form, ...patch } })
  const field = (key: keyof SourceForm, label: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div>
      <label htmlFor={`profile-source-${key}`} className={labelCls}>{label}{extra.required && <Req />}</label>
      <input id={`profile-source-${key}`} className={inputCls} value={form[key]} {...extra}
        aria-invalid={key === 'phone' && phoneBad ? true : undefined}
        onChange={(e) => edit({ [key]: key === 'phone' ? formatPhone(e.target.value) : e.target.value })} />
      {key === 'phone' && phoneBad && (
        <span className="mt-1 block text-xs text-critical-600">{t('profile.invalidPhone')}</span>
      )}
    </div>
  )
  return (
    <CardFrame title={t(`${S}.organisation`)} testId="organisation">
      <div className="grid gap-4 sm:grid-cols-2">
        {field('source_name', t(`${S}.orgName`), { required: true })}
        {field('contact_person', t(`${S}.contactPerson`))}
        {field('contact_email', t(`${S}.contactEmail`), { type: 'email' })}
        {field('phone', t(`${S}.phone`), { inputMode: 'tel' })}
      </div>
      <p className="text-xs text-ground-500">{t(`${S}.note`)}</p>
    </CardFrame>
  )
}
