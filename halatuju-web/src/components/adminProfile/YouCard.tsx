'use client'

import { useEffect, useRef, useState } from 'react'
import { deleteAdminPhoto, uploadAdminPhoto } from '@/lib/admin-api'
import StaffAvatar from '@/components/admin/StaffAvatar'
import { CardFrame, inputCls, labelCls, readOnlyCls, Req, type CardProps } from './shared'

/** The server's limits (`apps/scholarship/staff_photo.py`, `views_admin/me.py`) — said early here so a
 *  doomed upload or an over-long About is caught before the call; the server still refuses. */
const MAX_PHOTO_BYTES = 2 * 1024 * 1024
export const ABOUT_MAX = 600
const P = 'admin.myProfile'

/** A photo refusal, in the reader's words. */
function photoRefusal(err: { code?: string; status?: number }): string {
  switch (err.code) {
    case 'too_large': return `${P}.photo.tooLarge`
    case 'not_an_image': case 'unsupported_type': return `${P}.photo.wrongType`
    case 'storage_unavailable': return `${P}.photo.unavailable`
    default: return err.status === 429 ? `${P}.tooManyAttempts` : `${P}.photo.failed`
  }
}

/**
 * "You" — everyone: the photo (a 96 px circle; Add / Change / Remove, each its own action straight
 * to `admin/me/photo/`, not part of Save), the name (required), job title, About (600 characters,
 * with a counter) and the sign-in email, shown, never edited. Common profile S2.
 */
export default function YouCard({ state }: CardProps) {
  const { t, draft, set, setCard, email, token, photoUrl, onPhoto } = state
  const file = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const msgRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (msg && !msg.ok) msgRef.current?.focus() }, [msg])
  const auth = { token: token ?? undefined }

  const pick = async (f: File | undefined) => {
    if (file.current) file.current.value = ''
    if (!f) return
    setMsg(null)
    if (f.size > MAX_PHOTO_BYTES) { setMsg({ ok: false, text: t(`${P}.photo.tooLarge`) }); return }
    setBusy(true)
    try {
      const { photo_url } = await uploadAdminPhoto(f, auth)
      onPhoto(photo_url)
      setMsg({ ok: true, text: t(`${P}.photo.saved`) })
    } catch (err) {
      setMsg({ ok: false, text: t(photoRefusal(err as { code?: string; status?: number })) })
    } finally { setBusy(false) }
  }
  const remove = async () => {
    setMsg(null); setBusy(true)
    try {
      await deleteAdminPhoto(auth)
      onPhoto(null)
      setMsg({ ok: true, text: t(`${P}.photo.removed`) })
    } catch (err) {
      setMsg({ ok: false, text: t(photoRefusal(err as { code?: string; status?: number })) })
    } finally { setBusy(false) }
  }

  const link = 'text-sm font-medium text-info-700 hover:underline disabled:opacity-50'
  return (
    <CardFrame title={t(`${P}.you`)} testId="you">
      <div className="flex flex-wrap items-center gap-4">
        <StaffAvatar name={draft.name} photoUrl={photoUrl} size={96} alt={t(`${P}.photo.alt`)} />
        <div className="space-y-1">
          <div className="flex flex-wrap gap-4">
            <button type="button" className={link} disabled={busy} onClick={() => file.current?.click()}>
              {t(photoUrl ? `${P}.photo.change` : `${P}.photo.add`)}
            </button>
            {photoUrl && (
              <button type="button" className={link} disabled={busy} onClick={remove}>{t(`${P}.photo.remove`)}</button>
            )}
          </div>
          <p className="text-xs text-ground-500">{t(`${P}.photo.hint`)}</p>
          <input ref={file} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
            aria-label={t(`${P}.photo.add`)} data-testid="photo-input"
            onChange={(e) => void pick(e.target.files?.[0])} />
          {msg && (
            <p ref={msgRef} tabIndex={-1} role={msg.ok ? 'status' : 'alert'}
              className={`text-sm outline-none ${msg.ok ? 'text-positive-700' : 'text-critical-600'}`}>{msg.text}</p>
          )}
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="profile-name" className={labelCls}>{t('admin.name')}<Req /></label>
          <input id="profile-name" type="text" required value={draft.name}
            onChange={(e) => set({ name: e.target.value })} className={inputCls} />
        </div>
        <div>
          <label htmlFor="profile-job-title" className={labelCls}>{t(`${P}.jobTitle`)}</label>
          <input id="profile-job-title" type="text" maxLength={120} value={draft.card.job_title}
            placeholder={t(`${P}.jobTitleHint`)}
            onChange={(e) => setCard({ job_title: e.target.value })} className={inputCls} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="profile-about" className={labelCls}>{t(`${P}.about`)}</label>
          <textarea id="profile-about" rows={3} maxLength={ABOUT_MAX} value={draft.card.about}
            aria-describedby="profile-about-count" placeholder={t(`${P}.aboutHint`)}
            onChange={(e) => setCard({ about: e.target.value.slice(0, ABOUT_MAX) })} className={inputCls} />
          <p id="profile-about-count" className="mt-1 text-right text-xs text-ground-500">
            {t(`${P}.aboutCount`, { n: String(draft.card.about.length), max: String(ABOUT_MAX) })}
          </p>
        </div>
        <div>
          <label htmlFor="profile-email" className={labelCls}>{t(`${P}.signInEmail`)}</label>
          <input id="profile-email" className={readOnlyCls} value={email} disabled readOnly />
        </div>
      </div>
    </CardFrame>
  )
}
