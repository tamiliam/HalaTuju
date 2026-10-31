'use client'

import { useEffect, useRef, useState } from 'react'
import { changeOwnPassword } from '@/lib/admin-api'
import { adminSignInWithPassword, getAdminSupabase } from '@/lib/admin-supabase'
import { MIN_PASSWORD_LENGTH } from '@/lib/adminPassword'
import { formatDateTime } from '@/lib/formatDate'
import { CardFrame, inputCls, labelCls, type CardProps } from './shared'

const P = 'admin.myProfile'

/** A refusal of `admin/me/password/`, in the reader's words. Unknown codes read as the generic one. */
function refusal(err: { code?: string; status?: number }): string {
  if (err.status === 429) return `${P}.tooManyAttempts`
  switch (err.code) {
    case 'wrong_current_password': return `${P}.wrongCurrent`
    case 'current_password_required': return `${P}.currentRequired`
    case 'password_too_short': return 'admin.passwordTooShort'
    case 'same_password': return `${P}.samePassword`
    case 'weak_password': return `${P}.weakPassword`
    case 'no_password_sign_in': return `${P}.noPasswordSignIn`
    case 'supabase_unavailable': return `${P}.unavailable`
    default: return `${P}.passwordFailed`
  }
}

/**
 * "Sign-in" — everyone: how the person signs in (read off the admin Supabase session's
 * `app_metadata.providers`), the last time the console recorded them (`last_seen_at`, throttled to
 * about once a day — NULL is "not recorded"), and, ONLY for an account that has the email
 * provider, a password change.
 *
 * ⚠ THE CHANGE GOES THROUGH OUR SERVER (`admin/me/password/`), NOT `updateUser({ password })`: the
 * project refuses a client-side change ("Current password required", `app/admin/set-password`). The
 * current password is the proof. It is its own action, not part of the page's Save, and a source
 * user may use it too (opted in).
 *
 * ⚠ STAYING SIGNED IN. The server sets the password through the service-role admin API, which does
 * not end this tab's session (`app/admin/set-password` relies on the same: it reads `admin/role/`
 * with the same token straight after). The card still checks: if the session can no longer be
 * refreshed, it signs in again with the new password and says so.
 */
export default function SignInCard({ state }: CardProps) {
  const { t, me, providers, token, email } = state
  const hasPassword = providers.includes('email')
  const methods = providers.map((p) => p === 'google' ? 'Google'
    : p === 'email' ? t(`${P}.password`) : p)

  const [open, setOpen] = useState(false)
  const [current, setCurrent] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const msgRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (msg && !msg.ok) msgRef.current?.focus() }, [msg])

  const clear = () => { setCurrent(''); setPw(''); setPw2('') }

  /** After a change: is this tab's session still good? If not, sign in again with the new one. */
  const stayIn = async (newPassword: string, othersOut: boolean): Promise<string> => {
    try {
      const { error } = await getAdminSupabase().auth.refreshSession()
      // Review fix M2: the server ends every OTHER session; when it could not, say so.
      if (!error) return othersOut ? `${P}.passwordChanged` : `${P}.othersStillIn`
    } catch { /* fall through to a fresh sign-in */ }
    try {
      const { error } = await adminSignInWithPassword(email, newPassword)
      return error ? `${P}.signInAgainNeeded` : `${P}.signedInAgain`
    } catch {
      return `${P}.signInAgainNeeded`
    }
  }

  const change = async () => {
    setMsg(null)
    if (!current) { setMsg({ ok: false, text: t(`${P}.currentRequired`) }); return }
    if (pw.length < MIN_PASSWORD_LENGTH) { setMsg({ ok: false, text: t('admin.passwordTooShort') }); return }
    if (pw !== pw2) { setMsg({ ok: false, text: t('admin.passwordMismatch') }); return }
    if (pw === current) { setMsg({ ok: false, text: t(`${P}.samePassword`) }); return }
    setBusy(true)
    try {
      const done = await changeOwnPassword(current, pw, { token: token ?? undefined })
      const newPassword = pw
      clear(); setOpen(false)
      setMsg({ ok: true, text: t(await stayIn(newPassword, done?.others_signed_out !== false)) })
    } catch (err) {
      setMsg({ ok: false, text: t(refusal(err as { code?: string; status?: number })) })
    } finally { setBusy(false) }
  }

  return (
    <CardFrame title={t(`${P}.signin`)} testId="signin">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-ground-500">{t(`${P}.method`)}</dt>
        <dd className="text-ground-900">{methods.length ? methods.join(', ') : t(`${P}.unknown`)}</dd>
        <dt className="text-ground-500">{t(`${P}.lastSignedIn`)}</dt>
        <dd className="text-ground-900">
          {me?.last_seen_at ? formatDateTime(me.last_seen_at) : t('admin.reviewers.lastSeenUnknown')}
        </dd>
      </dl>
      {hasPassword && !open && (
        <button type="button" onClick={() => { setOpen(true); setMsg(null) }}
          className="text-sm font-medium text-info-700 hover:underline">
          {t(`${P}.changePassword`)}
        </button>
      )}
      {hasPassword && open && (
        <div className="grid gap-4 sm:grid-cols-2" data-testid="change-password">
          {/* The browser's password manager pairs a password with the nearest text field before it —
              on this page the phone. This hidden field names the sign-in email as the username it
              should save (owner report 2026-10-31: Chrome stored the phone number). */}
          <input type="text" name="username" autoComplete="username" value={email} readOnly hidden
            aria-hidden="true" tabIndex={-1} data-testid="password-username" />
          <div className="sm:col-span-2 sm:max-w-[50%] sm:pr-2">
            <label htmlFor="profile-current-password" className={labelCls}>{t(`${P}.currentPassword`)}</label>
            <input id="profile-current-password" type="password" autoComplete="current-password"
              value={current} onChange={(e) => setCurrent(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label htmlFor="profile-new-password" className={labelCls}>{t(`${P}.newPassword`)}</label>
            <input id="profile-new-password" type="password" autoComplete="new-password" minLength={MIN_PASSWORD_LENGTH}
              value={pw} onChange={(e) => setPw(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label htmlFor="profile-new-password2" className={labelCls}>{t(`${P}.confirmPassword`)}</label>
            <input id="profile-new-password2" type="password" autoComplete="new-password" minLength={MIN_PASSWORD_LENGTH}
              value={pw2} onChange={(e) => setPw2(e.target.value)} className={inputCls} />
          </div>
          <div className="flex flex-wrap gap-3 sm:col-span-2">
            <button type="button" onClick={change} disabled={busy || !current || !pw || !pw2}
              className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
              {busy ? t('admin.saving') : t(`${P}.changePassword`)}
            </button>
            <button type="button" onClick={() => { setOpen(false); clear(); setMsg(null) }}
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
