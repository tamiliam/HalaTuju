'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import {
  acceptSponsorTerms, getSponsorTerms, getSponsorTermsQuiz,
  type SponsorTermsCheckpoint, type SponsorTermsDocument,
} from '@/lib/api'

/**
 * Read → quiz → sign. The whole acceptance, in one place a sponsor cannot navigate around.
 *
 * Three things here are deliberate and were decided by the owner:
 *  1. **A wrong answer is never penalised.** It marks itself, explains, and leaves the other
 *     options live. Unlimited retries. Accept unlocks only once every checkpoint is passed.
 *  2. **Typing a name IS the signature** — no tick-box. Their account name is shown above the
 *     field so they know what to type, and a variant spelling is RECORDED, never refused: there is
 *     no IC to check against, and telling someone their own name is wrong here would be worse than
 *     storing the difference.
 *  3. **A 409 re-takes rather than records.** If a new version is published while they are
 *     reading, we refetch and start again rather than log an acceptance of wording nobody saw.
 */
type Phase = 'read' | 'quiz' | 'sign' | 'done'

export default function SponsorTermsWizard({ token, accountName, onAccepted }: {
  token: string | null
  accountName: string
  onAccepted: () => void
}) {
  const { t, locale } = useT()
  const [doc, setDoc] = useState<SponsorTermsDocument | null>(null)
  const [checkpoints, setCheckpoints] = useState<SponsorTermsCheckpoint[]>([])
  const [phase, setPhase] = useState<Phase>('read')
  const [i, setI] = useState(0)
  const [wrong, setWrong] = useState<number[]>([])
  const [passed, setPassed] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!token) return
    // Deliberately does NOT clear `error`. The 409 path sets a message and then reloads, and a
    // clear here would wipe the one explanation the sponsor needs — why they are back at the top.
    // Errors are cleared when a new ACTION starts, not when data is fetched.
    Promise.all([getSponsorTerms(locale, { token }), getSponsorTermsQuiz(locale, { token })])
      .then(([a, b]) => { setDoc(a.terms); setCheckpoints(b.checkpoints) })
      .catch(() => setError(t('sponsorPortal.terms.loadError')))
  }, [token, locale, t])

  useEffect(() => { load() }, [load])

  const restart = () => {
    setPhase('read'); setI(0); setWrong([]); setPassed(false); setName('')
  }

  const accept = async () => {
    if (!token || !doc) return
    setBusy(true); setError('')
    try {
      await acceptSponsorTerms(
        { version: doc.version, signed_name: name.trim(), locale }, { token })
      setPhase('done')
      onAccepted()
    } catch (e) {
      const status = (e as { status?: number })?.status
      if (status === 409) {
        // Published under them mid-read. Start over on the new wording rather than record an
        // acceptance of something they never saw.
        setError(t('sponsorPortal.terms.versionChanged'))
        restart()
        load()
      } else {
        setError(t('sponsorPortal.terms.acceptFailed'))
      }
    } finally { setBusy(false) }
  }

  if (error && !doc) return <p className="text-sm text-critical-600">{error}</p>
  if (!doc) return <p className="text-sm text-ground-500">{t('common.loading')}</p>

  const current = checkpoints[i]

  return (
    <div className="flex flex-col gap-5">
      {error && <p className="text-sm text-critical-600">{error}</p>}

      {phase === 'read' && (
        <>
          <div>
            <h1 className="text-2xl font-bold text-ground-900">{doc.title}</h1>
            {doc.intro && <p className="text-ground-600 italic mt-2">{doc.intro}</p>}
          </div>
          <div className="flex flex-col gap-5">
            {doc.sections.map((s) => (
              <section key={s.order}>
                <h2 className="font-semibold text-ground-900">{s.order}. {s.heading}</h2>
                {s.body.split('\n\n').map((para, pi) => (
                  <p key={pi} className="text-ground-700 mt-1.5 whitespace-pre-wrap">{para}</p>
                ))}
              </section>
            ))}
          </div>
          {/* §12 refers to the privacy notice, and section bodies are plain text with no links —
              so the link lives in the chrome, at the moment someone is reading the reference. */}
          <p className="text-xs text-ground-500 border-t border-ground-200 pt-4">
            {t('sponsorPortal.terms.privacyNote')}{' '}
            <Link href="/privacy" className="text-info-600 hover:underline">
              {t('sponsorAuth.privacyNotice')}
            </Link>.
          </p>
          <button type="button" onClick={() => setPhase('quiz')}
            className="self-start px-6 py-3 bg-brand-fill text-brand-fill-ink rounded-xl font-medium hover:bg-brand-fill-hover">
            {checkpoints.length > 0
              ? t('sponsorPortal.terms.startQuiz', { n: String(checkpoints.length) })
              : t('sponsorPortal.terms.continue')}
          </button>
        </>
      )}

      {phase === 'quiz' && current && (
        <div className="bg-ground-0 border border-ground-200 rounded-2xl overflow-hidden">
          <div className="flex gap-1 px-5 pt-5" aria-hidden>
            {checkpoints.map((c, k) => (
              <span key={c.order} className={`flex-1 h-1 rounded ${
                k < i ? 'bg-positive-600' : k === i ? 'bg-primary-600' : 'bg-ground-200'}`} />
            ))}
          </div>
          <div className="p-5 flex flex-col gap-3">
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-ground-400">
              {current.tag}
            </p>
            <p className="text-sm text-ground-500">{current.plain}</p>
            <p className="text-lg font-semibold text-ground-900">{current.question}</p>
            <div className="flex flex-col gap-2">
              {current.options.map((o, k) => {
                const isRight = passed && k === current.correct
                const isWrong = wrong.includes(k)
                return (
                  <button key={k} type="button" disabled={passed || isWrong}
                    onClick={() => {
                      if (passed) return
                      if (k === current.correct) setPassed(true)
                      else if (!wrong.includes(k)) setWrong([...wrong, k])
                    }}
                    className={`text-left rounded-xl border px-4 py-3 transition-colors ${
                      isRight ? 'border-positive-500 bg-positive-50 text-positive-800 font-medium'
                        : isWrong ? 'border-critical-300 bg-critical-50 text-critical-700'
                          : 'border-ground-200 hover:border-info-400 hover:bg-info-50/50'}`}>
                    {o}
                  </button>
                )
              })}
            </div>
            {(passed || wrong.length > 0) && (
              <div className={`rounded-xl border px-4 py-3 text-sm ${
                passed ? 'border-positive-300 bg-positive-50 text-positive-800'
                  : 'border-critical-300 bg-critical-50 text-critical-700'}`}>
                <p className="font-semibold mb-0.5">
                  {passed ? t('sponsorPortal.terms.right') : t('sponsorPortal.terms.wrong')}
                </p>
                {current.why}
              </div>
            )}
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-ground-100 bg-ground-50 px-5 py-3">
            <span className="text-xs text-ground-500 tabular-nums">
              {t('sponsorPortal.terms.progress', {
                n: String(i + 1), total: String(checkpoints.length),
              })}
            </span>
            <button type="button" disabled={!passed}
              onClick={() => {
                if (i + 1 >= checkpoints.length) setPhase('sign')
                else { setI(i + 1); setWrong([]); setPassed(false) }
              }}
              className="px-5 py-2.5 bg-brand-fill text-brand-fill-ink rounded-xl font-medium hover:bg-brand-fill-hover disabled:opacity-40">
              {i + 1 >= checkpoints.length
                ? t('sponsorPortal.terms.toSign')
                : t('sponsorPortal.terms.next')}
            </button>
          </div>
        </div>
      )}

      {(phase === 'sign' || (phase === 'quiz' && !current)) && (
        <div className="bg-ground-0 border border-ground-200 rounded-2xl p-6 flex flex-col gap-3 max-w-lg">
          <h2 className="text-lg font-bold text-ground-900">{t('sponsorPortal.terms.signTitle')}</h2>
          <p className="text-sm text-ground-600">{t('sponsorPortal.terms.signBody')}</p>
          <p className="text-sm text-ground-500">
            {t('sponsorPortal.terms.yourName')} <b className="text-ground-900">{accountName}</b>
          </p>
          <label className="text-[11px] font-bold uppercase tracking-wider text-ground-500"
            htmlFor="sig">
            {t('sponsorPortal.terms.typeName')}
          </label>
          <input id="sig" type="text" autoComplete="off" value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-ground-300 border-b-2 rounded-lg px-4 py-3 text-lg
                       focus:border-info-500 focus:outline-none" />
          <button type="button" disabled={busy || name.trim().length < 3} onClick={accept}
            className="px-6 py-3 bg-brand-fill text-brand-fill-ink rounded-xl font-medium hover:bg-brand-fill-hover disabled:opacity-40">
            {busy ? t('sponsorPortal.terms.accepting') : t('sponsorPortal.terms.accept')}
          </button>
          <p className="text-xs text-ground-500">{t('sponsorPortal.terms.signNote')}</p>
        </div>
      )}

      {phase === 'done' && (
        <div className="bg-positive-50 border border-positive-300 rounded-2xl p-6 text-center">
          <p className="font-semibold text-positive-800">{t('sponsorPortal.terms.accepted')}</p>
          <p className="font-serif text-2xl text-positive-900 my-2">{name.trim()}</p>
          <p className="text-xs text-positive-800/80">
            {t('sponsorPortal.terms.acceptedStamp', { version: doc.version })}
          </p>
        </div>
      )}
    </div>
  )
}
