'use client'

import { useEffect, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatPhone, isValidPhone } from '@/lib/scholarship'
import { refusalKey } from '@/lib/sourceConsole'
import { inputCls } from '@/components/admin/StaffAdmin'
import { getSourceProfile, updateSourceProfile, type SourceProfile as Payload } from '@/lib/admin-api'
import { CARD, K, PageTitle } from './shared'

const P = `${K}.profile`
type Form = { name: string; source_name: string; contact_person: string; contact_email: string; phone: string }
const formOf = (d: Payload): Form => ({
  name: d.user.name, source_name: d.source.name, contact_person: d.source.contact_person,
  contact_email: d.source.contact_email, phone: d.source.phone,
})

/**
 * A source user's Profile (source sign-in S3): "You" — their own name (the sign-in email is shown,
 * never edited) — and "Organisation": the source's name, contact person, email for updates and
 * phone, which are the source's OWN once it has signed in (the Sources page locks them, 409
 * `managed_by_source`). `GET/PATCH admin/source/profile/` only; the code and the organisation stay
 * the organisation's. Save wakes only when something changed (request #6).
 */
export default function SourceProfile() {
  const { token, refreshRole } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [failed, setFailed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (!token) return
    getSourceProfile({ token }).then((d) => { setData(d); setForm(formOf(d)) }).catch(() => setFailed(true))
  }, [token])

  if (!data || !form) {
    return <p className="text-sm text-ground-500">{t(failed ? `${P}.loadError` : 'common.loading')}</p>
  }

  const saved = formOf(data)
  const dirty = (Object.keys(form) as (keyof Form)[]).some((k) => form[k] !== saved[k])
  const phoneBad = form.phone.trim() !== '' && !isValidPhone(form.phone)

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !dirty || phoneBad) return
    setSaving(true); setMessage(null)
    try {
      const next = await updateSourceProfile({
        ...(form.name !== saved.name ? { user: { name: form.name.trim() } } : {}),
        source: { name: form.source_name.trim(), contact_person: form.contact_person.trim(),
                  contact_email: form.contact_email.trim(), phone: form.phone.trim() },
      }, { token })
      setData(next); setForm(formOf(next))
      setMessage({ ok: true, text: t(`${P}.saved`) })
      if (form.name !== saved.name) void refreshRole()   // the header shows the name
    } catch (err) {
      setMessage({ ok: false, text: t(refusalKey('profile', (err as { code?: string })?.code)) })
    } finally { setSaving(false) }
  }

  const field = (key: keyof Form, label: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-ground-700">{label}</span>
      <input className={inputCls} value={form[key]} {...extra}
        onChange={(e) => setForm({ ...form, [key]: key === 'phone' ? formatPhone(e.target.value) : e.target.value })} />
    </label>
  )

  return (
    <form onSubmit={save} className="max-w-3xl space-y-5" data-testid="source-profile">
      <PageTitle title={t('admin.profile')} />
      {message && (
        <p role={message.ok ? 'status' : 'alert'}
          className={`rounded-lg border p-3 text-sm ${message.ok ? 'border-positive-200 bg-positive-50 text-positive-700'
            : 'border-critical-200 bg-critical-50 text-critical-600'}`}>{message.text}</p>
      )}
      <section className={CARD}>
        <h2 className="mb-3 text-base font-semibold text-ground-900">{t(`${P}.you`)}</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {field('name', t(`${P}.name`), { required: true })}
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-ground-700">{t(`${P}.email`)}</span>
            <input className={`${inputCls} bg-ground-50 text-ground-500`} value={data.user.email} disabled readOnly />
          </label>
        </div>
      </section>
      <section className={CARD}>
        <h2 className="mb-3 text-base font-semibold text-ground-900">{t(`${P}.organisation`)}</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {field('source_name', t(`${P}.orgName`), { required: true })}
          {field('contact_person', t(`${P}.contactPerson`))}
          {field('contact_email', t(`${P}.contactEmail`), { type: 'email' })}
          <div>
            {field('phone', t(`${P}.phone`), { inputMode: 'tel' })}
            {phoneBad && <span className="mt-1 block text-xs text-critical-600">{t('profile.invalidPhone')}</span>}
          </div>
        </div>
        <p className="mt-3 text-xs text-ground-500">{t(`${P}.note`)}</p>
      </section>
      <button type="submit" disabled={saving || !dirty || phoneBad}
        title={dirty ? undefined : t('common.nothingToSave')}
        className="rounded-lg bg-brand-fill px-6 py-2.5 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
        {t(saving ? 'admin.sources.saving' : 'common.save')}
      </button>
    </form>
  )
}
