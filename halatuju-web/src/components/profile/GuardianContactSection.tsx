'use client'

/**
 * "Parent / guardian contact" inside the profile's Family & Background card (request #26).
 *
 * The name and phone the student gave when applying — the phone is the number the bursary-signing
 * PIN is later sent to, so a typo matters. It is its OWN line, deliberately NOT attached to the
 * Father or Mother line: in production the guardian's name matches neither parent on 60 of 143
 * profiles, so pinning it to one would mislabel a third of them.
 *
 *  * Shown ONLY to a student who has applied (`has_scholarship_application`, owner ruling R4).
 *  * Editable by the student EXCEPT while bursary signing is possible for them
 *    (`guardian_contact_locked`, R2) — then read-only, with a note to contact the team, who can
 *    still correct it (R3). The server is the gate; this only mirrors it, and a save the server
 *    refuses as locked flips the view to the locked note.
 *  * Self-contained: it asks for its own data and saves on its own, so `profile/page.tsx` (held at
 *    its line budget) only mounts it. Loaded through `LazyGuardianContactSection` so `/profile`'s
 *    first-load JS (held at its byte budget) does not pay for it.
 */
import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { getGuardianContact, updateGuardianContact, type GuardianContact } from '@/lib/api'
import { formatPhone, isValidPhone } from '@/lib/scholarship'

export default function GuardianContactSection() {
  const { token } = useAuth()
  const { t } = useT()
  const [contact, setContact] = useState<GuardianContact | null>(null)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let live = true
    getGuardianContact({ token })
      .then(c => { if (live) setContact(c) })
      .catch(() => { /* supplementary: an unreadable contact is simply not shown */ })
    return () => { live = false }
  }, [token])

  if (!contact?.has_scholarship_application) return null
  const locked = contact.guardian_contact_locked
  const phoneBad = phone.trim() !== '' && !isValidPhone(phone)

  const startEditing = () => {
    setName(contact.name); setPhone(formatPhone(contact.phone)); setError(''); setEditing(true)
  }
  const save = async () => {
    if (!token) return
    setSaving(true); setError('')
    try {
      const next = await updateGuardianContact({ name: name.trim(), phone: formatPhone(phone) }, { token })
      setContact(next); setEditing(false)
    } catch (e) {
      const code = (e as Error & { code?: string }).code
      if (code === 'guardian_contact_locked') {
        setContact({ ...contact, guardian_contact_locked: true }); setEditing(false)
      } else {
        setError(code === 'guardian_phone_invalid' ? t('scholarship.apply.error.phone') : t('errors.somethingWentWrong'))
      }
    } finally { setSaving(false) }
  }

  const input = 'w-full px-3 py-2.5 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none'
  return (
    <div className="border-t border-ground-100 pt-3 mt-3 space-y-2" data-testid="guardian-contact">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-ground-900">{t('profile.guardianContact')}</span>
        {!locked && !editing && (
          <button onClick={startEditing} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
            {t('profile.edit')}
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-3">
          <label className="block">
            <span className="block text-sm font-medium text-ground-700 mb-1.5">{t('scholarship.apply.field.parentName')}</span>
            <input value={name} onChange={e => setName(e.target.value)} maxLength={255} className={input} />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-ground-700 mb-1.5">{t('scholarship.apply.field.parentPhone')}</span>
            <input value={phone} onChange={e => setPhone(formatPhone(e.target.value))} inputMode="tel" placeholder="012-345 6789" className={input} />
          </label>
          {(phoneBad || error) && <p role="alert" className="text-xs text-critical-600">{error || t('scholarship.apply.error.phone')}</p>}
          <div className="flex gap-3">
            <button onClick={() => setEditing(false)} className="flex-1 px-4 py-2.5 border border-ground-300 rounded-lg text-sm font-medium text-ground-700 hover:bg-ground-50">
              {t('profile.cancel')}
            </button>
            <button onClick={save} disabled={saving || !name.trim() || !isValidPhone(phone)} className="flex-1 px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover disabled:opacity-50">
              {saving ? '...' : t('profile.save')}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex justify-between gap-3">
            <span className="text-sm text-ground-500 shrink-0">{t('scholarship.apply.field.parentName')}</span>
            <span className="text-sm text-ground-900 text-right">{contact.name || '—'}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-sm text-ground-500 shrink-0">{t('scholarship.apply.field.parentPhone')}</span>
            <span className="text-sm text-ground-900 text-right">{contact.phone ? formatPhone(contact.phone) : '—'}</span>
          </div>
          {locked && <p className="text-xs text-caution-700">{t('profile.guardianContactLocked')}</p>}
        </>
      )}
    </div>
  )
}
