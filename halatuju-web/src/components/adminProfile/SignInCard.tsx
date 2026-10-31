'use client'

import { useEffect, useRef, useState } from 'react'
import { getAdminSupabase } from '@/lib/admin-supabase'
import { formatDateTime } from '@/lib/formatDate'
import { CardFrame, inputCls, labelCls, type CardProps } from './shared'

/** The set-password page's rule (`app/admin/set-password`): eight characters at least. */
const MIN_LEN = 8

/** A Supabase refusal, in the reader's words. Unknown codes read as the generic failure. */
function refusal(err: { code?: string; message?: string }): string {
  const code = err.code ?? ''
  if (code === 'same_password') return 'admin.myProfile.samePassword'
  if (code === 'weak_password') return 'admin.myProfile.weakPassword'
  // The project re-checks a password change (GoTrue "secure password change"): an older session is
  // asked to prove itself again, which a fresh sign-in does.
  if (code === 'reauthentication_needed' || /current password|reauthenticat/i.test(err.message ?? '')) {
    return 'admin.myProfile.reauthNeeded'
  }
  return 'admin.myProfile.passwordFailed'
}

/**
 * "Sign-in" — everyone: how the person signs in (read off the admin Supabase session's
 * `app_metadata.providers`), the last time the console recorded them (`last_seen_at`, throttled to
 * about once a day — NULL is "not recorded"), and, ONLY for an account that has the email
 * provider, a password change.
 *
 * ⚠ The change is its own action, not part of the page's Save: it goes straight to Supabase on
 * the ADMIN client (`updateUser({ password })`), never to our API, so a source user may use it too.
 */
export default function SignInCard({ state }: CardProps) {
  const { t, me, providers } = state
  const hasPassword = providers.includes('email')
  const methods = providers.map((p) => p === 'google' ? 'Google'
    : p === 'email' ? t('admin.myProfile.password') : p)

  const [open, setOpen] = useState(false)
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const msgRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (msg && !msg.ok) msgRef.current?.focus() }, [msg])

  const change = async () => {
    setMsg(null)
    if (pw.length < MIN_LEN) { setMsg({ ok: false, text: t('admin.passwordTooShort') }); return }
    if (pw !== pw2) { setMsg({ ok: false, text: t('admin.passwordMismatch') }); return }
    setBusy(true)
    try {
      const { error } = await getAdminSupabase().auth.updateUser({ password: pw })
      if (error) { setMsg({ ok: false, text: t(refusal(error)) }); return }
      setPw(''); setPw2(''); setOpen(false)
      setMsg({ ok: true, text: t('admin.myProfile.passwordChanged') })
    } catch {
      setMsg({ ok: false, text: t('admin.myProfile.passwordFailed') })
    } finally { setBusy(false) }
  }

  return (
    <CardFrame title={t('admin.myProfile.signin')} testId="signin">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-ground-500">{t('admin.myProfile.method')}</dt>
        <dd className="text-ground-900">{methods.length ? methods.join(', ') : t('admin.myProfile.unknown')}</dd>
        <dt className="text-ground-500">{t('admin.myProfile.lastSignedIn')}</dt>
        <dd className="text-ground-900">
          {me?.last_seen_at ? formatDateTime(me.last_seen_at) : t('admin.reviewers.lastSeenUnknown')}
        </dd>
      </dl>
      {hasPassword && !open && (
        <button type="button" onClick={() => { setOpen(true); setMsg(null) }}
          className="text-sm font-medium text-info-700 hover:underline">
          {t('admin.myProfile.changePassword')}
        </button>
      )}
      {hasPassword && open && (
        <div className="grid gap-4 sm:grid-cols-2" data-testid="change-password">
          <div>
            <label htmlFor="profile-new-password" className={labelCls}>{t('admin.myProfile.newPassword')}</label>
            <input id="profile-new-password" type="password" autoComplete="new-password" minLength={MIN_LEN}
              value={pw} onChange={(e) => setPw(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label htmlFor="profile-new-password2" className={labelCls}>{t('admin.myProfile.confirmPassword')}</label>
            <input id="profile-new-password2" type="password" autoComplete="new-password" minLength={MIN_LEN}
              value={pw2} onChange={(e) => setPw2(e.target.value)} className={inputCls} />
          </div>
          <div className="flex flex-wrap gap-3 sm:col-span-2">
            <button type="button" onClick={change} disabled={busy || !pw || !pw2}
              className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
              {busy ? t('admin.saving') : t('admin.myProfile.changePassword')}
            </button>
            <button type="button" onClick={() => { setOpen(false); setPw(''); setPw2(''); setMsg(null) }}
              className="rounded-lg border border-ground-300 px-5 py-2 text-sm text-ground-700">
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}
      {msg && (
        <p ref={msgRef} tabIndex={-1} role={msg.ok ? 'status' : 'alert'}
          className={`text-sm outline-none ${msg.ok ? 'text-positive-700' : 'text-critical-600'}`}>{msg.text}</p>
      )}
    </CardFrame>
  )
}
