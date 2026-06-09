'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { sponsorSignOut } from '@/lib/sponsor-supabase'
import { registerSponsor, getSponsorPool, getSponsorWallet, getSponsorGraduationMessages, getStudentsWaitingCount, patchSponsorNotifications, type SponsorPoolCard, type SponsorWallet, type GraduationRelayMessage } from '@/lib/api'
import { SPONSOR_SOURCES, formatMyMobile, isValidMyMobile } from '@/lib/sponsorAuth'
import { KEY_SPONSOR_PENDING } from '@/lib/storage'
import SponsorLanding from '@/components/SponsorLanding'

export default function SponsorPortalPage() {
  const { t } = useT()
  const router = useRouter()
  const { isLoading, isSignedIn, session, token, account, refreshAccount } = useSponsorAuth()

  // Complete-details form state (used when registered=false or profile incomplete).
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [source, setSource] = useState('')
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const prefilled = useRef(false)

  const isRegistered = !!account?.id
  const profileComplete = !!account?.profile_complete
  const needsDetails = isSignedIn && account != null && (!isRegistered || !profileComplete)

  // One-time pre-fill of the details form from the stash / session / account.
  useEffect(() => {
    if (prefilled.current || !needsDetails) return
    let stash: { name?: string; phone?: string; source?: string } = {}
    try {
      const raw = sessionStorage.getItem(KEY_SPONSOR_PENDING)
      if (raw) stash = JSON.parse(raw)
    } catch { /* ignore malformed stash */ }
    const metaName = (session?.user?.user_metadata?.full_name as string) || (session?.user?.user_metadata?.name as string) || ''
    setName(account?.name || stash.name || metaName || '')
    setPhone(formatMyMobile(account?.phone || stash.phone || ''))
    setSource(account?.source || stash.source || '')
    prefilled.current = true
  }, [needsDetails, account, session])

  // ── Phase E2: the anonymised pool (approved sponsors only) ──────────────────
  // The pool API 404s while SPONSOR_POOL_ENABLED is off → we fall back to the
  // "browsing coming soon" shell. Any fetch error degrades to that same shell.
  const [pool, setPool] = useState<SponsorPoolCard[] | null>(null)
  const [poolUnavailable, setPoolUnavailable] = useState(false)
  // F2: the sponsor's own "My students" — balance + their (offered/active) allocations.
  const [wallet, setWallet] = useState<SponsorWallet | null>(null)
  // F9b: staff-approved graduation thank-yous from the students this sponsor funds.
  const [gradMessages, setGradMessages] = useState<GraduationRelayMessage[]>([])

  useEffect(() => {
    if (account?.status !== 'approved' || !token) return
    let cancelled = false
    getSponsorPool({ token })
      .then((d) => { if (!cancelled) setPool(d.students) })
      .catch(() => { if (!cancelled) setPoolUnavailable(true) })
    getSponsorWallet({ token })
      .then((w) => { if (!cancelled) setWallet(w) })
      .catch(() => { /* wallet 404s while the pool flag is off — leave it null */ })
    getSponsorGraduationMessages({ token })
      .then((r) => { if (!cancelled) setGradMessages(r.messages) })
      .catch(() => { /* 404s while the pool flag is off — leave it empty */ })
    return () => { cancelled = true }
  }, [account?.status, token])

  const showBrowse = account?.status === 'approved' && !poolUnavailable

  // F3: notification cadence (realtime | weekly | off). Optimistic-ish — saves then refreshes.
  const [savingNotify, setSavingNotify] = useState(false)
  const changeNotify = async (freq: 'realtime' | 'weekly' | 'off') => {
    if (!token || savingNotify || account?.notify_frequency === freq) return
    setSavingNotify(true)
    try {
      await patchSponsorNotifications(freq, { token })
      await refreshAccount()
    } catch { /* keep the current preference on failure */ }
    finally { setSavingNotify(false) }
  }

  // ── F1: public sponsor landing ─────────────────────────────────────────────
  // The live "students waiting" counter is a public, flag-gated endpoint. While
  // SPONSOR_POOL_ENABLED is off it reports enabled:false → signed-out visitors keep
  // the plain sign-in card (the programme stays dark until go-live). When it's on,
  // signed-out visitors get the full marketing landing with the live counter.
  const [waitingCount, setWaitingCount] = useState(0)
  const [landingEnabled, setLandingEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false
    getStudentsWaitingCount()
      .then((d) => { if (!cancelled) { setWaitingCount(d.count); setLandingEnabled(d.enabled) } })
      .catch(() => { /* leave the landing disabled → falls back to the sign-in card */ })
    return () => { cancelled = true }
  }, [])

  const phoneInvalid = phone.length > 0 && !isValidMyMobile(phone)
  const canSubmit = !!name.trim() && isValidMyMobile(phone) && !!source && consent && !submitting

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit || !token) return
    setSubmitting(true)
    setError('')
    try {
      await registerSponsor({ name: name.trim(), phone: `+60 ${phone}`, source, consent: true }, { token })
      try { sessionStorage.removeItem(KEY_SPONSOR_PENDING) } catch { /* ignore */ }
      await refreshAccount()
    } catch {
      setError(t('sponsorAuth.registerFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleSignOut = async () => {
    await sponsorSignOut()
    router.replace('/sponsor/login')
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  // Signed-out visitors see the public marketing landing once the programme is live.
  if (!isLoading && !isSignedIn && landingEnabled) {
    return <SponsorLanding count={waitingCount} />
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Slim sponsor top bar */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/logo-icon.png" alt="HalaTuju" width={100} height={36} />
            <span className="text-sm font-semibold text-blue-600">{t('sponsorAuth.badge')}</span>
          </Link>
          {isSignedIn && (
            <button onClick={handleSignOut} className="text-sm text-red-600 hover:text-red-800">{t('header.logout')}</button>
          )}
        </div>
      </header>

      {showBrowse ? (
        /* ── Approved + pool enabled: My students + the anonymised browse grid ── */
        <main className="flex-1 container mx-auto px-6 py-8">
          {/* F2: account + balance header */}
          <div className="rounded-2xl border bg-white px-6 py-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400">{t('sponsorPortal.myStudents.welcome')}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-lg font-bold text-gray-900">{account?.name || ''}</span>
                <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">
                  {t('sponsorPortal.myStudents.approvedPill')}
                </span>
              </div>
            </div>
            {wallet && (
              <div className="rounded-xl bg-blue-50 border border-blue-100 px-4 py-2.5 text-right">
                <p className="text-xs uppercase tracking-wide text-blue-500">{t('sponsorPortal.myStudents.balance')}</p>
                <p className="text-lg font-bold text-blue-800">RM {wallet.balance}</p>
              </div>
            )}
          </div>

          {/* F2: My students grid */}
          {wallet && wallet.sponsorships.length > 0 && (
            <section className="mt-8">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">{t('sponsorPortal.myStudents.title')}</h2>
              <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.myStudents.subtitle')}</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {wallet.sponsorships.map((sp) => {
                  const st = sp.student
                  const offered = sp.status === 'offered'
                  return (
                    <div key={sp.id} className={`rounded-xl border p-4 ${offered ? 'bg-gray-50' : 'bg-white'}`}>
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-gray-900">{st.ref}</span>
                        {st.state && <span className="text-xs text-gray-500">{st.state}</span>}
                      </div>
                      <p className="text-sm text-gray-800 mt-2">{st.field || '—'}</p>
                      {st.academic && <p className="text-xs text-gray-500 mt-1">{st.academic}</p>}
                      <p className="text-xs text-gray-500 mt-1">
                        RM {sp.amount}{st.programme_months ? ` · ${st.programme_months} ${t('sponsorPortal.myStudents.months')}` : ''}
                      </p>
                      <div className="mt-3">
                        {offered ? (
                          <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-gray-200 text-gray-600">
                            ⏳ {t('sponsorPortal.myStudents.awaiting')}
                          </span>
                        ) : (
                          <ProgressBadge state={st.progress_state} t={t} />
                        )}
                      </div>
                      {st.funding_categories.length > 0 && (
                        <p className="text-xs text-gray-400 mt-3 pt-3 border-t">{st.funding_categories.join(' · ')}</p>
                      )}
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {/* F9b: messages from students you supported — anonymous, linked to ref only */}
          {gradMessages.length > 0 && (
            <section className="mt-8">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">{t('sponsorPortal.graduationMessages.title')}</h2>
              <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.graduationMessages.subtitle')}</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {gradMessages.map((m, i) => (
                  <div key={i} className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
                    <p className="text-sm text-gray-800">💬 “{m.text}”</p>
                    <p className="text-xs text-gray-500 mt-3">
                      {t('sponsorPortal.graduationMessages.attribution')} · {m.ref}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mt-10">{t('sponsorPool.browseTitle')}</h1>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPool.browseIntro')}</p>
          <div className="mt-3 mb-6 rounded-lg bg-blue-50 border border-blue-100 px-4 py-2.5 text-xs text-blue-800">
            {t('sponsorPool.anonymityNote')}
          </div>
          {pool === null ? (
            <p className="text-center text-gray-500 mt-12">{t('common.loading')}</p>
          ) : pool.length === 0 ? (
            <div className="text-center text-gray-500 mt-12 rounded-xl bg-white border border-dashed px-6 py-10">
              {t('sponsorPool.empty')}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {pool.map((s) => (
                <Link key={s.id} href={`/sponsor/pool/${s.id}`}
                  className="block bg-white rounded-xl border p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900">{s.ref}</span>
                    {s.state && <span className="text-xs text-gray-500">{s.state}</span>}
                  </div>
                  <p className="text-sm text-gray-800 mt-2">{s.field || '—'}</p>
                  {s.academic && <p className="text-xs text-gray-500 mt-1">{s.academic}</p>}
                  {s.funding_categories.length > 0 && (
                    <p className="text-xs text-gray-500 mt-1">{s.funding_categories.join(' · ')}</p>
                  )}
                </Link>
              ))}
            </div>
          )}
        </main>
      ) : (
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border p-8">
          {isLoading ? (
            <p className="text-center text-gray-500">{t('common.loading')}</p>
          ) : !isSignedIn ? (
            /* ── Not signed in ── */
            <div className="text-center">
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.signInTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.signInBody')}</p>
              <Link href="/sponsor/login" className="mt-6 block w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition-colors">
                {t('sponsorAuth.signIn')}
              </Link>
              <p className="text-sm text-gray-500 mt-4">
                {t('sponsorAuth.noAccount')}{' '}
                <Link href="/sponsor/register" className="font-semibold text-blue-600 hover:underline">{t('sponsorAuth.createAccount')}</Link>
              </p>
            </div>
          ) : needsDetails ? (
            /* ── Signed in, details incomplete (e.g. via Google) ── */
            <>
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.completeTitle')}</h1>
              <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.completeBody')}</p>
              <form onSubmit={handleSubmit} className="mt-5 space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.fullName')} <span className="text-red-500">*</span></label>
                  <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.phone')} <span className="text-red-500">*</span></label>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm text-gray-600 whitespace-nowrap">🇲🇾 +60</span>
                    <input inputMode="tel" value={phone} onChange={(e) => setPhone(formatMyMobile(e.target.value))} placeholder="12-345 6789" className={inputCls} />
                  </div>
                  {phoneInvalid && <p className="text-xs text-red-600 mt-1">{t('sponsorAuth.mobileInvalid')}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.source')} <span className="text-red-500">*</span></label>
                  <select value={source} onChange={(e) => setSource(e.target.value)} className={inputCls}>
                    <option value="">{t('sponsorAuth.sourcePlaceholder')}</option>
                    {SPONSOR_SOURCES.map((s) => <option key={s} value={s}>{t(`sponsorAuth.sourceOption.${s}`)}</option>)}
                  </select>
                </div>
                <label className="flex items-start gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
                  <span>{t('sponsorAuth.consent')}{' '}
                    <Link href="/privacy" className="text-blue-600 hover:underline">{t('sponsorAuth.privacyNotice')}</Link>.
                  </span>
                </label>
                {error && <p className="text-sm text-red-600">{error}</p>}
                <button type="submit" disabled={!canSubmit}
                  className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50">
                  {submitting ? t('sponsorAuth.submitting') : t('sponsorAuth.submitDetails')}
                </button>
              </form>
            </>
          ) : account?.status === 'pending' ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-xl">⏳</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.pendingTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.pendingBody')}</p>
            </div>
          ) : account?.status === 'approved' ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 text-xl">✓</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.approvedTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.approvedBody')}</p>
              <div className="mt-5 rounded-xl bg-gray-50 border border-dashed border-gray-200 px-4 py-5 text-sm text-gray-500">
                {t('sponsorPortal.comingSoon')}
              </div>

              {/* F3: email-update preference */}
              <div className="mt-5 text-left">
                <p className="text-sm font-medium text-gray-700">{t('sponsorPortal.notify.title')}</p>
                <p className="text-xs text-gray-500 mt-0.5">{t('sponsorPortal.notify.intro')}</p>
                <div className="mt-2 space-y-2">
                  {(['realtime', 'weekly', 'off'] as const).map((f) => {
                    const selected = (account?.notify_frequency || 'weekly') === f
                    return (
                      <button
                        key={f} type="button" disabled={savingNotify}
                        onClick={() => changeNotify(f)}
                        className={`w-full text-left rounded-lg border px-3 py-2 transition-colors disabled:opacity-60 ${
                          selected ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'
                        }`}
                      >
                        <span className={`text-sm font-medium ${selected ? 'text-blue-800' : 'text-gray-800'}`}>
                          {t(`sponsorPortal.notify.${f}`)}
                        </span>
                        <span className="block text-xs text-gray-500">{t(`sponsorPortal.notify.${f}Desc`)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center">
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.inactiveTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.inactiveBody')}</p>
            </div>
          )}
        </div>
      </main>
      )}
    </div>
  )
}

/** F2: the coarse, non-identifying progress badge on a sponsored-student card. */
function ProgressBadge({ state, t }: {
  state: SponsorPoolCard['progress_state']
  t: (k: string) => string
}) {
  if (!state) return null
  const tone: Record<string, string> = {
    on_track: 'bg-green-100 text-green-700',
    semester_completed: 'bg-blue-100 text-blue-700',
    needs_attention: 'bg-amber-100 text-amber-700',
    graduated: 'bg-indigo-100 text-indigo-700',
  }
  return (
    <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${tone[state] || 'bg-gray-100 text-gray-600'}`}>
      {t(`sponsorPortal.myStudents.progress.${state}`)}
    </span>
  )
}
