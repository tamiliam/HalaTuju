'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import Toggle from '@/components/Toggle'
import {
  getMyScholarshipApplications,
  getSemesterResults,
  addSemesterResult,
  getPromotionalConsent,
  setPromotionalConsent,
  getGraduationMessages,
  submitGraduationMessage,
  type ScholarshipApplication,
  type SemesterResult,
  type GraduationMessage,
} from '@/lib/api'

const PROGRESS_TONE: Record<string, string> = {
  on_track: 'bg-green-100 text-green-700',
  semester_completed: 'bg-blue-100 text-blue-700',
  needs_attention: 'bg-amber-100 text-amber-700',
  graduated: 'bg-indigo-100 text-indigo-700',
}

/** F9b — the in-programme student's "My progress" home: record semester results
 *  (drives the sponsor-facing progress band), the separate 18+ promotional toggle,
 *  and the anonymity-preserving graduation thank-you relay. Shown once the award is
 *  accepted (status 'sponsored'). Mirrors the apply/onboarding card style. */
export default function InProgrammePage() {
  const { t } = useT()
  const { status: authStatus, token } = useAuth()
  const router = useRouter()

  const [app, setApp] = useState<ScholarshipApplication | null>(null)
  const [notInProgramme, setNotInProgramme] = useState(false)
  const [loading, setLoading] = useState(true)

  // Semester results
  const [results, setResults] = useState<SemesterResult[]>([])
  const [showForm, setShowForm] = useState(false)
  const [semester, setSemester] = useState('')
  const [cgpa, setCgpa] = useState('')
  const [graduated, setGraduated] = useState(false)
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
    getMyScholarshipApplications({ token })
      .then(async (res) => {
        if (!active) return
        const sponsored = res.applications.find((a) => a.status === 'active' || a.status === 'maintenance') ?? null
        if (!sponsored) { setNotInProgramme(true); setLoading(false); return }
        setApp(sponsored)
        await loadAll(sponsored.id, token)
        if (active) setLoading(false)
      })
      .catch(() => { if (active) { setNotInProgramme(true); setLoading(false) } })
    return () => { active = false }
  }, [authStatus, token, router, loadAll])

  const currentBand = results[0]
    ? results[0].graduated ? 'graduated'
      : results[0].cgpa != null && parseFloat(results[0].cgpa) <= 2.0 ? 'needs_attention'
        : results[0].cgpa != null ? 'semester_completed' : 'on_track'
    : 'on_track'

  async function saveResult() {
    if (!app || !token) return
    setSavingResult(true); setResultError(null)
    try {
      await addSemesterResult(app.id, {
        semester, cgpa: cgpa.trim() === '' ? null : cgpa.trim(), graduated,
      }, { token })
      await loadAll(app.id, token)
      setShowForm(false); setSemester(''); setCgpa(''); setGraduated(false)
    } catch (e) {
      const code = (e as Error & { code?: string }).code
      setResultError(code === 'bad_cgpa' ? t('scholarship.inProgramme.results.errorCgpa')
        : t('scholarship.inProgramme.results.errorGeneric'))
    } finally { setSavingResult(false) }
  }

  async function togglePromo(next: boolean) {
    if (!app || !token || isMinor) return
    setPromoSaving(true); setPromoError(null)
    try {
      const res = await setPromotionalConsent(app.id, next, { token })
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
      const msg = await submitGraduationMessage(app.id, compose.trim(), { token })
      if (msg.status === 'blocked') {
        setBlocked(msg.scan_result)         // keep `compose` so the student can edit
      } else {
        setCompose('')
        await loadAll(app.id, token)
      }
    } catch {
      setBlocked(null)
    } finally { setSending(false) }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        <AppHeader />
        <main className="flex-1 flex items-center justify-center text-gray-400">…</main>
        <AppFooter />
      </div>
    )
  }

  if (notInProgramme) {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        <AppHeader />
        <main className="flex-1 max-w-md mx-auto w-full px-4 py-10 text-center">
          <h1 className="text-xl font-bold text-gray-900">{t('scholarship.inProgramme.title')}</h1>
          <p className="mt-3 text-gray-600">{t('scholarship.inProgramme.notInProgramme')}</p>
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
    <div className="min-h-screen flex flex-col bg-gray-50">
      <AppHeader />
      <main className="flex-1 max-w-md mx-auto w-full px-4 py-6 space-y-4">
        <div className="flex items-center gap-2">
          <Link href="/scholarship/application" aria-label={t('scholarship.inProgramme.back')} className="text-primary-600">‹</Link>
          <h1 className="text-2xl font-bold text-gray-900">{t('scholarship.inProgramme.title')}</h1>
        </div>

        {/* ── Semester results ─────────────────────────────────────────── */}
        <section className="rounded-2xl bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-lg font-bold text-gray-900">{t('scholarship.inProgramme.results.title')}</h2>
            <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${PROGRESS_TONE[currentBand]}`}>
              {t(`scholarship.inProgramme.progress.${currentBand}`)}
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-600">{t('scholarship.inProgramme.results.subtitle')}</p>

          {results.length > 0 ? (
            <ul className="mt-3 divide-y divide-gray-100">
              {results.map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-gray-700">{r.semester || '—'}</span>
                  <span className="text-gray-500">
                    {r.graduated ? `🎓 ${t('scholarship.inProgramme.results.graduatedTag')}`
                      : r.cgpa != null ? `${t('scholarship.inProgramme.results.cgpaLabel')} ${r.cgpa}` : '—'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-gray-400">{t('scholarship.inProgramme.results.empty')}</p>
          )}

          {!showForm ? (
            <button onClick={() => setShowForm(true)}
              className="mt-3 w-full rounded-xl border border-primary-500 py-2.5 text-sm font-medium text-primary-600">
              + {t('scholarship.inProgramme.results.add')}
            </button>
          ) : (
            <div className="mt-3 space-y-3 rounded-xl bg-gray-50 p-3">
              <div>
                <label className="text-xs font-medium text-gray-600">{t('scholarship.inProgramme.results.semester')}</label>
                <input value={semester} onChange={(e) => setSemester(e.target.value)}
                  placeholder={t('scholarship.inProgramme.results.semesterPh')}
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">{t('scholarship.inProgramme.results.cgpa')}</label>
                <input value={cgpa} onChange={(e) => setCgpa(e.target.value)}
                  inputMode="decimal" placeholder="3.50"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
                <p className="mt-1 text-xs text-gray-400">{t('scholarship.inProgramme.results.cgpaHint')}</p>
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={graduated} onChange={(e) => setGraduated(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300" />
                {t('scholarship.inProgramme.results.graduated')}
              </label>
              {resultError && <p className="text-sm text-red-600">{resultError}</p>}
              <div className="flex gap-2">
                <button onClick={saveResult} disabled={savingResult}
                  className="flex-1 rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white disabled:opacity-60">
                  {savingResult ? t('scholarship.inProgramme.results.saving') : t('scholarship.inProgramme.results.save')}
                </button>
                <button onClick={() => { setShowForm(false); setResultError(null) }}
                  className="rounded-xl px-4 py-2.5 text-sm font-medium text-gray-500">
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          )}
        </section>

        {/* ── Sharing your story (18+ promotional consent) ─────────────── */}
        <section className="rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">{t('scholarship.inProgramme.promo.title')}</h2>
          <p className="mt-1 text-sm text-gray-600">{t('scholarship.inProgramme.promo.subtitle')}</p>
          {isMinor ? (
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-gray-50 p-3 text-sm text-gray-400">
              <span>🔒</span>{t('scholarship.inProgramme.promo.minor')}
            </div>
          ) : (
            <>
              <div className="mt-3 flex items-center justify-between gap-3">
                <span className="text-sm text-gray-700">{t('scholarship.inProgramme.promo.label')}</span>
                <Toggle on={promoGranted} onChange={togglePromo} label={t('scholarship.inProgramme.promo.label')} />
              </div>
              <p className="mt-2 text-xs text-gray-400">
                {promoSaving ? t('scholarship.inProgramme.promo.saving') : t('scholarship.inProgramme.promo.help')}
              </p>
              {promoError && <p className="mt-1 text-sm text-red-600">{promoError}</p>}
            </>
          )}
        </section>

        {/* ── Thank your sponsor (graduation relay) ────────────────────── */}
        <section className="rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">{t('scholarship.inProgramme.grad.title')}</h2>
          <p className="mt-1 text-sm text-gray-600">{t('scholarship.inProgramme.grad.subtitle')}</p>

          {latest && (latest.status === 'pending' || latest.status === 'approved') && (
            <div className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
              latest.status === 'approved' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
              {latest.status === 'approved' ? '✅' : '⏳'}
              {t(`scholarship.inProgramme.grad.status.${latest.status}`)}
            </div>
          )}

          {blocked && blocked.length > 0 && (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
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
            className="mt-3 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
          <button onClick={sendThankYou} disabled={sending || !compose.trim()}
            className="mt-2 w-full rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white disabled:opacity-60">
            {sending ? t('scholarship.inProgramme.grad.sending') : t('scholarship.inProgramme.grad.send')}
          </button>
        </section>
      </main>
      <AppFooter />
    </div>
  )
}
