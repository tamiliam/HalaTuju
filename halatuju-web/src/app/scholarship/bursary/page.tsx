'use client'

import '@/lib/messagesScholarship'   // TD-416: this page's scholarship.* words (their own slice)
import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import Toggle from '@/components/Toggle'
import {
  getBursarySummary,
  getSemesterResults,
  signUploadDocument,
  uploadFileToSignedUrl,
  addSemesterResult,
  getPromotionalConsent,
  setPromotionalConsent,
  getGraduationMessages,
  submitGraduationMessage,
  type BursarySummary,
  type SemesterResult,
  type GraduationMessage,
} from '@/lib/api'
import { rememberBursaryFile } from '@/lib/storage'
import { formatMoney2dp as rm } from '@/lib/scholarship'
import { formatDate } from '@/lib/formatDate'

/**
 * A STATE map, so these are TONES — not the `category-N` family (Layer 1 F3, 2026-08-31).
 *
 * ⚠ Maintenance S4a removed the page's own "progress" chip, which judged her CGPA in the browser
 * (≤ 2.0 → "needs attention"). A result is now REVIEWED by an officer, and what she sees is each
 * result's REVIEW — awaiting review, accepted, or queried with the officer's note — never a
 * standing (that is staff-side, `standing.py`). `graduated` keeps the filled weight against the
 * accepted TINT: same tone, the stronger one for the thing that actually finished.
 */
const REVIEW_TONE: Record<string, string> = {
  pending: 'bg-ground-100 text-ground-600',
  accepted: 'bg-positive-100 text-positive-700',
  queried: 'bg-caution-100 text-caution-700',
}
const GRADUATED_TONE = 'bg-positive-fill text-positive-fill-ink'

type Tab = 'overview' | 'results'
const TABS: readonly Tab[] = ['overview', 'results']

/** "My Bursary" (student maintenance S3; was `/scholarship/in-programme`, which redirects here) — a
 *  funded student's home from award acceptance to closure. Design of record: the owner-approved phone
 *  artboard (2026-10-29).
 *
 *  ⚠ WHO REACHES IT IS THE SERVER'S ANSWER: `scholarship/bursary/summary/` serves her OWN file or 404s
 *  (`maintenance_scope.has_file` — in maintenance, or closed after it). Nothing is re-derived here.
 *  ⚠ TWO TABS NOW, AND THE REST ARE HIDDEN, NOT "COMING SOON": the roadmap's rule is that a later
 *  tab appears only when its module is switched on, and a student shown six empty tabs reads a
 *  programme that is not working. Funds, Contract, Letters, News and Mentoring arrive with their
 *  sprints. The Overview's money card is what Funds will grow from.
 *  ⚠ NOTHING STAFF-SIDE: `support_paused` is the only maintenance signal she gets (never probation),
 *  and no result is judged against a minimum (Sprint 4). The results form shows only when the server
 *  says `can_record_results` (active / maintenance until Sprint 4). */
export default function BursaryPage() {
  const { t, locale } = useT()
  const { status: authStatus, token } = useAuth()
  const router = useRouter()

  const [app, setApp] = useState<BursarySummary | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  // A failure that is NOT "no file" is said as such, with a retry (S3 review L2).
  const [loadFailed, setLoadFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [notInProgramme, setNotInProgramme] = useState(false)
  const [loading, setLoading] = useState(true)

  // Semester results
  const [results, setResults] = useState<SemesterResult[]>([])
  const [showForm, setShowForm] = useState(false)
  const [semester, setSemester] = useState('')
  const [cgpa, setCgpa] = useState('')
  const [graduated, setGraduated] = useState(false)
  const [slip, setSlip] = useState<File | null>(null)
  const [savingResult, setSavingResult] = useState(false)
  const [resultError, setResultError] = useState<string | null>(null)

  // Promotional consent
  const [promoGranted, setPromoGranted] = useState(false)
  const [isMinor, setIsMinor] = useState(false)
  const [promoSaving, setPromoSaving] = useState(false)
  const [promoError, setPromoError] = useState<string | null>(null)

  // Graduation thank-you
  const [messages, setMessages] = useState<GraduationMessage[]>([])
  const [compose, setCompose] = useState('')
  const [sending, setSending] = useState(false)
  const [blocked, setBlocked] = useState<string[] | null>(null)

  const loadAll = useCallback(async (appId: number, tok: string) => {
    const [r, p, m] = await Promise.all([
      getSemesterResults(appId, { token: tok }).catch(() => ({ results: [] })),
      getPromotionalConsent(appId, { token: tok }).catch(() => ({ granted: false, is_minor: false })),
      getGraduationMessages(appId, { token: tok }).catch(() => ({ messages: [] })),
    ])
    setResults(r.results)
    setPromoGranted(p.granted)
    setIsMinor(p.is_minor)
    setMessages(m.messages)
  }, [])

  useEffect(() => {
    let active = true
    if (authStatus === 'loading') return
    if (authStatus === 'anonymous' || authStatus === 'needs-nric' || !token) {
      router.replace('/scholarship/apply')
      return
    }
    setLoadFailed(false)
    getBursarySummary({ token })
      .then(async (summary) => {
        if (!active) return
        rememberBursaryFile(true)
        setApp(summary)
        await loadAll(summary.application_id, token)
        if (active) setLoading(false)
      })
      .catch((e: Error & { status?: number }) => {
        if (!active) return
        // A 404 is "no file" (never applied, not funded yet, or a pre-award close — TD-352).
        if (e?.status === 404) { rememberBursaryFile(false); setNotInProgramme(true) }
        else setLoadFailed(true)
        setLoading(false)
      })
    return () => { active = false }
  }, [authStatus, token, router, loadAll, attempt])


  async function saveResult() {
    if (!app || !token) return
    setSavingResult(true); setResultError(null)
    try {
      // S4a: the slip goes to storage first (a signed URL), then the result names it — the server
      // records the slip itself, so the pre-award document pipeline never runs on it.
      // ⚠ OWNER RULING 2026-10-29: no slip uploaded HERE, no result (emailed slips are not accepted).
      // The server refuses `slip_required`; Save stays asleep until a slip is chosen to mirror it.
      if (!slip) { setResultError(t('scholarship.bursary.resultError.slip_required')); return }
      const signed = await signUploadDocument('semester_result', { token })
      await uploadFileToSignedUrl(signed.upload_url, slip)
      const upload = { storage_path: signed.storage_path, original_filename: slip.name,
        content_type: slip.type, size: slip.size }
      await addSemesterResult(app.application_id, {
        semester, cgpa: cgpa.trim() === '' ? null : cgpa.trim(), graduated, slip: upload,
      }, { token })
      await loadAll(app.application_id, token)
      setShowForm(false); setSemester(''); setCgpa(''); setGraduated(false); setSlip(null)
    } catch (e) {
      const code = (e as Error & { code?: string }).code || ''
      const known = ['bad_cgpa', 'unsupported_format', 'file_too_large', 'upload_incomplete', 'bad_slip', 'too_many_results',
        'slip_required']
      setResultError(t(`scholarship.bursary.resultError.${known.includes(code) ? code : 'generic'}`))
    } finally { setSavingResult(false) }
  }

  async function togglePromo(next: boolean) {
    if (!app || !token || isMinor) return
    setPromoSaving(true); setPromoError(null)
    try {
      const res = await setPromotionalConsent(app.application_id, next, { token })
      setPromoGranted(res.granted)
    } catch (e) {
      const code = (e as Error & { code?: string }).code
      if (code === 'minor_not_allowed') setIsMinor(true)
      setPromoError(t('scholarship.inProgramme.promo.error'))
    } finally { setPromoSaving(false) }
  }

  async function sendThankYou() {
    if (!app || !token || !compose.trim()) return
    setSending(true); setBlocked(null)
    try {
      const msg = await submitGraduationMessage(app.application_id, compose.trim(), { token })
      if (msg.status === 'blocked') {
        setBlocked(msg.scan_result)         // keep `compose` so the student can edit
      } else {
        setCompose('')
        await loadAll(app.application_id, token)
      }
    } catch {
      setBlocked(null)
    } finally { setSending(false) }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-ground-50">
        <AppHeader />
        <main className="flex-1 flex items-center justify-center text-ground-400">…</main>
        <AppFooter />
      </div>
    )
  }

  if (loadFailed) {
    return (
      <div className="min-h-screen flex flex-col bg-ground-50">
        <AppHeader />
        <main className="flex-1 max-w-md mx-auto w-full px-4 py-10 text-center" data-testid="bursary-load-failed">
          <p className="text-ground-700">{t('scholarship.bursary.loadFailed')}</p>
          <button type="button" onClick={() => { setLoading(true); setAttempt((n) => n + 1) }}
            className="mt-4 rounded-xl bg-brand-fill px-5 py-2.5 text-sm font-medium text-brand-fill-ink">
            {t('scholarship.bursary.retry')}
          </button>
        </main>
        <AppFooter />
      </div>
    )
  }

  if (notInProgramme) {
    return (
      <div className="min-h-screen flex flex-col bg-ground-50">
        <AppHeader />
        <main className="flex-1 max-w-md mx-auto w-full px-4 py-10 text-center">
          <h1 className="text-xl font-bold text-ground-900">{t('scholarship.inProgramme.title')}</h1>
          <p className="mt-3 text-ground-600">{t('scholarship.inProgramme.notInProgramme')}</p>
          <Link href="/scholarship/application" className="mt-6 inline-block text-primary-600 font-medium">
            {t('scholarship.inProgramme.backToApplication')}
          </Link>
        </main>
        <AppFooter />
      </div>
    )
  }

  const latest = messages[0]

  return (
    <div className="min-h-screen flex flex-col bg-ground-50">
      <AppHeader />
      <main className="flex-1 max-w-md mx-auto w-full px-4 py-6 space-y-4">
        <div className="flex items-center gap-2">
          <Link href="/scholarship/application" aria-label={t('scholarship.inProgramme.back')} className="text-primary-600">‹</Link>
          <h1 className="text-2xl font-bold text-ground-900">{t('scholarship.bursary.title')}</h1>
        </div>

        {/* Who and where — her name, her gift, her course, and one plain sentence of state. */}
        {app && (
          <section className="rounded-2xl bg-ground-0 p-5 shadow-sm" data-testid="bursary-hello">
            <p className="text-lg font-semibold text-ground-900">
              {t('scholarship.bursary.hello', { name: firstName(app.name) })}
            </p>
            <p className="mt-1 text-sm text-ground-600">{[app.gift_names?.[locale as 'en' | 'ms' | 'ta'] || app.gift, app.course].filter(Boolean).join(' · ')}</p>
            <span className={`mt-2 inline-block rounded-full px-3 py-1 text-xs font-medium ${
              app.status === 'closed' ? 'bg-ground-100 text-ground-600'
                : app.support_paused ? 'bg-caution-100 text-caution-700' : 'bg-positive-100 text-positive-700'}`}>
              {t(app.status === 'closed' ? 'scholarship.bursary.state.closed'
                : app.support_paused ? 'scholarship.bursary.state.paused' : 'scholarship.bursary.state.in')}
            </span>
          </section>
        )}

        <div role="tablist" aria-label={t('scholarship.bursary.title')} className="flex gap-2">
          {TABS.map((k) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
              className={`h-10 rounded-full border px-4 text-sm font-medium ${tab === k
                ? 'border-brand-shape bg-brand-fill text-brand-fill-ink'
                : 'border-ground-300 bg-ground-0 text-ground-700'}`}>
              {t(`scholarship.bursary.tab.${k}`)}
            </button>
          ))}
        </div>

        {/* S5: a paused (on-hold) student sees a clear, non-alarming notice. */}
        {app?.in_maintenance && app?.support_paused && (
          <div className="rounded-2xl border border-caution-200 bg-caution-50 p-4">
            <p className="text-sm font-medium text-caution-900">{t('scholarship.inProgramme.onHold.title')}</p>
            <p className="mt-1 text-sm text-caution-800">{t('scholarship.inProgramme.onHold.body')}</p>
          </div>
        )}

        {/* S6: once closed, a warm "programme complete" note (graduated/completed) or a
            neutral closed note. The thank-you section below stays available. */}
        {app?.status === 'closed' && (() => {
          const positive = app.closure_reason === 'graduated' || app.closure_reason === 'completed'
          const key = positive ? app.closure_reason : 'neutral'
          return (
            <div className={`rounded-2xl border p-4 ${positive ? 'border-positive-200 bg-positive-50' : 'border-ground-200 bg-ground-50'}`}>
              <p className={`text-sm font-medium ${positive ? 'text-positive-900' : 'text-ground-800'}`}>
                {t(`scholarship.inProgramme.closed.${key}.title`)}
              </p>
              <p className={`mt-1 text-sm ${positive ? 'text-positive-800' : 'text-ground-600'}`}>
                {t(`scholarship.inProgramme.closed.${key}.body`)}
              </p>
            </div>
          )
        })()}

        {tab === 'overview' && app && (<>
          <section className="rounded-2xl bg-ground-0 p-5 shadow-sm" data-testid="bursary-funds">
            <h2 className="text-lg font-bold text-ground-900">{t('scholarship.bursary.funds.title')}</h2>
            {app.funds.award_amount ? (
              <>
                <p className="mt-2 text-sm text-ground-600">
                  <strong className="text-xl text-ground-900">RM{rm(app.funds.received)}</strong>{' '}
                  {t('scholarship.bursary.funds.of', { award: `RM${rm(app.funds.award_amount)}` })}
                </p>
                <div role="img" aria-label={t('scholarship.bursary.funds.barLabel', { pct: String(pct(app)) })}
                  className="mt-2 h-2.5 overflow-hidden rounded-full bg-ground-200">
                  <div className="h-full bg-brand-fill" style={{ width: `${pct(app)}%` }} />
                </div>
              </>
            ) : <p className="mt-2 text-sm text-ground-600">RM{rm(app.funds.received)}</p>}
            <p className="mt-2 text-xs text-ground-500">
              {app.funds.last_payment
                ? t('scholarship.bursary.funds.last', {
                  amount: `RM${rm(app.funds.last_payment.amount)}`, date: formatDate(app.funds.last_payment.at) })
                : t('scholarship.bursary.funds.none')}
            </p>
          </section>
          <section className="rounded-2xl bg-ground-0 p-5 shadow-sm" data-testid="bursary-latest">
            <h2 className="text-lg font-bold text-ground-900">{t('scholarship.bursary.latest.title')}</h2>
            <p className="mt-2 text-sm text-ground-700">
              {app.latest_result
                ? t('scholarship.bursary.latest.line', {
                  semester: app.latest_result.semester || '—', cgpa: app.latest_result.cgpa ?? '—' })
                : t('scholarship.bursary.latest.none')}
            </p>
            {app.next_result_due && (
              <p className={`mt-1 text-sm ${app.next_result_overdue ? 'font-medium text-critical-700' : 'text-ground-600'}`}
                data-testid="bursary-next-due">
                {/* "Late" is the SERVER's word (due date + grace, nothing waiting for review) — never a date sum here. */}
                {t(app.next_result_overdue ? 'scholarship.bursary.nextDue.late' : 'scholarship.bursary.nextDue.on',
                  { date: formatDate(app.next_result_due) })}
              </p>
            )}
            <button type="button" onClick={() => setTab('results')} className="mt-2 text-sm font-medium text-primary-600">
              {t('scholarship.bursary.latest.open')}
            </button>
          </section>
        </>)}

        {/* ── Semester results (the Results tab) ───────────────────────────── */}
        {tab === 'results' && <section className="rounded-2xl bg-ground-0 p-5 shadow-sm">
          <h2 className="text-lg font-bold text-ground-900">{t('scholarship.inProgramme.results.title')}</h2>
          <p className="mt-1 text-sm text-ground-600">{t('scholarship.inProgramme.results.subtitle')}</p>

          {results.length > 0 ? (
            <ul className="mt-3 divide-y divide-ground-100">
              {results.map((r) => (
                <li key={r.id} className="py-2 text-sm" data-testid="result-row">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-ground-700">{r.semester || '—'}</span>
                    <span className="flex items-center gap-2 text-ground-500">
                      {r.graduated
                        ? <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${GRADUATED_TONE}`}>
                            {t('scholarship.inProgramme.results.graduatedTag')}</span>
                        : r.cgpa != null ? `${t('scholarship.inProgramme.results.cgpaLabel')} ${r.cgpa}` : '—'}
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${REVIEW_TONE[r.review_status] ?? REVIEW_TONE.pending}`}>
                        {t(`scholarship.bursary.review.${r.review_status || 'pending'}`)}
                      </span>
                    </span>
                  </div>
                  {r.review_status === 'queried' && r.review_note && (
                    <p className="mt-1 rounded-lg bg-caution-50 px-3 py-2 text-xs text-caution-800">
                      {t('scholarship.bursary.review.queriedNote', { note: r.review_note })}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-ground-400">{t('scholarship.inProgramme.results.empty')}</p>
          )}

          {!app?.can_record_results ? null : !showForm ? (
            <button onClick={() => setShowForm(true)}
              className="mt-3 w-full rounded-xl border border-brand-shape py-2.5 text-sm font-medium text-primary-600">
              + {t('scholarship.inProgramme.results.add')}
            </button>
          ) : (
            <div className="mt-3 space-y-3 rounded-xl bg-ground-50 p-3">
              <div>
                <label className="text-xs font-medium text-ground-600">{t('scholarship.inProgramme.results.semester')}</label>
                <input value={semester} onChange={(e) => setSemester(e.target.value)}
                  placeholder={t('scholarship.inProgramme.results.semesterPh')}
                  className="mt-1 w-full rounded-lg border border-ground-300 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium text-ground-600">{t('scholarship.inProgramme.results.cgpa')}</label>
                <input value={cgpa} onChange={(e) => setCgpa(e.target.value)}
                  inputMode="decimal" placeholder="3.50"
                  className="mt-1 w-full rounded-lg border border-ground-300 px-3 py-2 text-sm" />
                <p className="mt-1 text-xs text-ground-400">{t('scholarship.inProgramme.results.cgpaHint')}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-ground-600">{t('scholarship.bursary.slip.label')}</label>
                <input type="file" accept="image/*,application/pdf"
                  onChange={(e) => setSlip(e.target.files?.[0] ?? null)}
                  className="mt-1 block w-full text-sm" data-testid="slip-input" />
                <p className="mt-1 text-xs text-ground-400">{t('scholarship.bursary.slip.hint')}</p>
              </div>
              {/* A student's on/off choice is the site Toggle, never a tick box (house rule). */}
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-ground-700">{t('scholarship.inProgramme.results.graduated')}</span>
                <Toggle on={graduated} onChange={setGraduated} label={t('scholarship.inProgramme.results.graduated')} />
              </div>
              {resultError && <p className="text-sm text-critical-600">{resultError}</p>}
              <div className="flex gap-2">
                <button onClick={saveResult} disabled={savingResult || !slip}
                  className="flex-1 rounded-xl bg-brand-fill py-2.5 text-sm font-medium text-brand-fill-ink disabled:opacity-60">
                  {savingResult ? t('scholarship.inProgramme.results.saving') : t('scholarship.inProgramme.results.save')}
                </button>
                <button onClick={() => { setShowForm(false); setResultError(null) }}
                  className="rounded-xl px-4 py-2.5 text-sm font-medium text-ground-500">
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          )}
        </section>}

        {/* ── Sharing your story (18+ promotional consent) ─────────────── */}
        {tab === 'overview' && <section className="rounded-2xl bg-ground-0 p-5 shadow-sm">
          <h2 className="text-lg font-bold text-ground-900">{t('scholarship.inProgramme.promo.title')}</h2>
          <p className="mt-1 text-sm text-ground-600">{t('scholarship.inProgramme.promo.subtitle')}</p>
          {isMinor ? (
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-ground-50 p-3 text-sm text-ground-400">
              <span>🔒</span>{t('scholarship.inProgramme.promo.minor')}
            </div>
          ) : (
            <>
              <div className="mt-3 flex items-center justify-between gap-3">
                <span className="text-sm text-ground-700">{t('scholarship.inProgramme.promo.label')}</span>
                <Toggle on={promoGranted} onChange={togglePromo} label={t('scholarship.inProgramme.promo.label')} />
              </div>
              <p className="mt-2 text-xs text-ground-400">
                {promoSaving ? t('scholarship.inProgramme.promo.saving') : t('scholarship.inProgramme.promo.help')}
              </p>
              {promoError && <p className="mt-1 text-sm text-critical-600">{promoError}</p>}
            </>
          )}
        </section>}

        {/* ── Thank your sponsor (graduation relay) ────────────────────── */}
        {tab === 'overview' && <section className="rounded-2xl bg-ground-0 p-5 shadow-sm">
          <h2 className="text-lg font-bold text-ground-900">{t('scholarship.inProgramme.grad.title')}</h2>
          <p className="mt-1 text-sm text-ground-600">{t('scholarship.inProgramme.grad.subtitle')}</p>

          {latest && (latest.status === 'pending' || latest.status === 'approved') && (
            <div className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
              latest.status === 'approved' ? 'bg-positive-100 text-positive-700' : 'bg-ground-100 text-ground-600'}`}>
              {latest.status === 'approved' ? '✅' : '⏳'}
              {t(`scholarship.inProgramme.grad.status.${latest.status}`)}
            </div>
          )}

          {blocked && blocked.length > 0 && (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-caution-200 bg-caution-50 p-3 text-sm text-caution-800">
              <span>⚠️</span>
              <span>
                {t('scholarship.inProgramme.grad.blockedIntro')}{' '}
                <strong>{blocked.map((f) => t(`scholarship.inProgramme.grad.identifier.${f}`)).join(', ')}</strong>.{' '}
                {t('scholarship.inProgramme.grad.blockedTail')}
              </span>
            </div>
          )}

          <textarea value={compose} onChange={(e) => setCompose(e.target.value)} rows={4} maxLength={2000}
            placeholder={t('scholarship.inProgramme.grad.placeholder')}
            className="mt-3 w-full rounded-xl border border-ground-300 px-3 py-2 text-sm" />
          <button onClick={sendThankYou} disabled={sending || !compose.trim()}
            className="mt-2 w-full rounded-xl bg-brand-fill py-2.5 text-sm font-medium text-brand-fill-ink disabled:opacity-60">
            {sending ? t('scholarship.inProgramme.grad.sending') : t('scholarship.inProgramme.grad.send')}
          </button>
        </section>}
      </main>
      <AppFooter />
    </div>
  )
}

/** The first word of her name, for the greeting ("Hi Aisyah"). */
function firstName(name: string): string {
  const first = (name || '').trim().split(/\s+/)[0] || ''
  return first ? first.charAt(0) + first.slice(1).toLowerCase() : ''
}

/** How much of the award has reached her, as a whole percentage (0-100). */
function pct(app: BursarySummary): number {
  const award = Number(app.funds.award_amount)
  if (!award) return 0
  return Math.max(0, Math.min(100, Math.round((Number(app.funds.received) / award) * 100)))
}
