'use client'

/**
 * "YOUR RESULTS" FOR MATRICULATION, ASASI OR DIPLOMA — the third results route (S2b, 2026-10-26;
 * the owner-approved mock, roadmap `docs/plans/2026-10-25-third-results-route-roadmap.md`).
 *
 * Three steps, in the STPM page's own style: (1) which qualification — and for a Diploma, where it
 * is from: only a PUBLIC diploma counts (ruling D5; a private-college diploma is not accepted
 * through UA), so "private college" shows a plain message and Continue stays shut; (2) the CGPA as
 * printed, the co-curriculum score (Matriculation / Asasi only — a Diploma's CGPA is its overall
 * figure as is), the MUET band, and the Overall CGPA and Merit worked out by the SERVER
 * (`calculateHigherCgpa` → `exam_questions.third_route_calculation`, the gate's own arithmetic —
 * never a second copy of the formula here); (3) the SPM results, REQUIRED (D4), the STPM page's
 * own block.
 *
 * Continue records the completion: the kind as the exam AND as `results_exam_type`, and the
 * entries under their own keys; the profile sync sends them with the whole completed list
 * (`lib/resultsSync.ts`). The server still refuses a private or unstated diploma at the gate (S2a).
 */
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import BrandLogo from '@/components/BrandLogo'
import ProgressStepper from '@/components/ProgressStepper'
import SpmResultsBlock, { useSpmResultsBlock } from '@/components/SpmResultsBlock'
import { useT } from '@/lib/i18n'
import { MUET_BANDS } from '@/lib/subjects'
import { calculateHigherCgpa } from '@/lib/api'
import { THIRD_ROUTE, isThirdRoute, type ThirdRouteKind } from '@/lib/qualification'
import {
  KEY_EXAM_TYPE, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO, KEY_MUET_BAND,
  KEY_RESULTS_EXAM_TYPE,
} from '@/lib/storage'

type Institution = 'public' | 'private'

/** A number typed into a box, or null when it is blank or not a number inside [min, max]. */
function inRange(raw: string, min: number, max: number, minExclusive = false): number | null {
  if (raw.trim() === '') return null
  const n = Number(raw)
  if (!Number.isFinite(n) || n > max || (minExclusive ? n <= min : n < min)) return null
  return n
}

const pill = (on: boolean) => `flex-1 py-3 px-4 rounded-xl text-sm font-medium transition-all ${
  on ? 'bg-brand-fill text-brand-fill-ink shadow-md' : 'bg-ground-0 text-ground-700 border border-ground-200 hover:bg-ground-50'}`

function Step({ n, title, hint }: { n: number; title: string; hint?: string }) {
  return (
    <>
      <div className={`flex items-center gap-2 ${hint ? 'mb-1' : 'mb-4'}`}>
        <span className="w-6 h-6 bg-brand-fill text-brand-fill-ink rounded text-xs flex items-center justify-center font-bold">{n}</span>
        <h2 className="text-lg font-semibold text-ground-900">{title}</h2>
      </div>
      {hint && <p className="text-sm text-ground-500 mb-4 ml-8">{hint}</p>}
    </>
  )
}

export default function HigherGradesPage() {
  const router = useRouter()
  const { t } = useT()
  const spm = useSpmResultsBlock()

  const [kind, setKind] = useState<ThirdRouteKind | null>(null)
  const [institution, setInstitution] = useState<Institution | null>(null)
  const [cgpaText, setCgpaText] = useState('')
  const [kokoText, setKokoText] = useState('')
  const [muetBand, setMuetBand] = useState<number | null>(null)
  const [figures, setFigures] = useState<{ cgpa: number; merit: number } | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem(KEY_EXAM_TYPE)
    if (isThirdRoute(saved)) setKind(saved)
    const inst = localStorage.getItem(KEY_HIGHER_INSTITUTION)
    if (inst === 'public' || inst === 'private') setInstitution(inst)
    setCgpaText(localStorage.getItem(KEY_HIGHER_CGPA) ?? '')
    setKokoText(localStorage.getItem(KEY_HIGHER_KOKO) ?? '')
    const muet = parseInt(localStorage.getItem(KEY_MUET_BAND) || '')
    if (MUET_BANDS.includes(muet)) setMuetBand(muet)
  }, [])

  const diploma = kind === 'diploma'
  const cgpa = inRange(cgpaText, 0, 4, true)
  const koko = diploma ? null : inRange(kokoText, 0, 10)
  const resultsReady = kind !== null && cgpa !== null && (diploma || koko !== null)

  // The overall CGPA and merit, from the server's calculator, a moment after typing stops.
  useEffect(() => {
    setFigures(null)
    if (!resultsReady || kind === null || cgpa === null) return
    let live = true
    const timer = setTimeout(() => {
      calculateHigherCgpa(kind, cgpa, koko)
        .then((r) => { if (live) setFigures({ cgpa: r.cgpa, merit: r.merit_percent }) })
        .catch(() => { /* no figure is better than a made-up one */ })
    }, 400)
    return () => { live = false; clearTimeout(timer) }
  }, [resultsReady, kind, cgpa, koko])

  const privateDiploma = diploma && institution === 'private'
  const isComplete = resultsReady && (!diploma || institution === 'public')
    && muetBand !== null && spm.complete

  const chooseKind = (k: ThirdRouteKind) => setKind(k)

  const handleContinue = () => {
    if (!isComplete || kind === null || cgpa === null) return
    localStorage.setItem(KEY_HIGHER_CGPA, String(cgpa))
    if (diploma) {
      localStorage.removeItem(KEY_HIGHER_KOKO)
      localStorage.setItem(KEY_HIGHER_INSTITUTION, 'public')
    } else {
      localStorage.setItem(KEY_HIGHER_KOKO, String(koko))
      localStorage.removeItem(KEY_HIGHER_INSTITUTION)
    }
    localStorage.setItem(KEY_MUET_BAND, String(muetBand))
    spm.save()
    localStorage.setItem(KEY_EXAM_TYPE, kind)
    // Completed, so it is a RESULT and not merely a selection — see results_exam_type.
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, kind)
    router.push('/onboarding/profile')
  }

  const inputCls = 'w-32 px-3 py-2 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none'

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-ground-0">
      <div className="bg-ground-0 border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <BrandLogo width={120} height={40} />
            </Link>
            <ProgressStepper currentStep={2} />
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8 max-w-3xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-ground-900 mb-3">{t('onboarding.higherGradesTitle')}</h1>
          <p className="text-ground-600">{t('onboarding.higherGradesSubtitle')}</p>
        </div>

        {/* 1. Which qualification — and, for a Diploma, where it is from (D5) */}
        <div className="mb-8">
          <Step n={1} title={t('onboarding.higherWhich')} />
          <div className="flex gap-3">
            {THIRD_ROUTE.map((k) => (
              <button key={k} type="button" onClick={() => chooseKind(k)} className={pill(kind === k)}>
                {t(`onboarding.higherKind.${k}`)}
              </button>
            ))}
          </div>
          {diploma && (
            <div className="mt-5">
              <p className="text-sm font-medium text-ground-700 mb-2">{t('onboarding.higherWhere')}</p>
              <div className="flex flex-col sm:flex-row gap-3">
                {(['public', 'private'] as const).map((i) => (
                  <button key={i} type="button" onClick={() => setInstitution(i)} className={pill(institution === i)}>
                    {t(`onboarding.higherInst.${i}`)}
                  </button>
                ))}
              </div>
              {privateDiploma && (
                <p role="alert" className="mt-3 rounded-xl border border-caution-200 bg-caution-50 p-3 text-sm text-ground-700">
                  {t('onboarding.higherPrivateNo')}
                </p>
              )}
            </div>
          )}
        </div>

        {/* 2. CGPA, co-curriculum (not for a Diploma), MUET, and the server's figures */}
        <div className="mb-8">
          <Step n={2} title={t('onboarding.higherResults')} />
          <div className="bg-ground-0 rounded-2xl border border-ground-200 shadow-sm p-5">
            <div className="mb-5">
              <label htmlFor="higher-cgpa" className="text-sm font-medium text-ground-700 mb-2 block">{t('onboarding.higherCgpa')}</label>
              <input id="higher-cgpa" type="number" min="0" max="4" step="0.01" inputMode="decimal"
                value={cgpaText} onChange={(e) => setCgpaText(e.target.value)} placeholder="0.00 – 4.00" className={inputCls} />
              <p className="text-xs text-ground-400 mt-1">{t('onboarding.higherCgpaHint')}</p>
            </div>

            {!diploma && (
              <div className="mb-5">
                <label htmlFor="higher-koko" className="text-sm font-medium text-ground-700 mb-2 block">{t('onboarding.kokoScore')}</label>
                <input id="higher-koko" type="number" min="0" max="10" step="0.01" inputMode="decimal"
                  value={kokoText} onChange={(e) => setKokoText(e.target.value)} placeholder="0.00 – 10.00" className={inputCls} />
                <p className="text-xs text-ground-400 mt-1">{t('onboarding.kokoHint')}</p>
              </div>
            )}

            {/* MUET band pills — the STPM page's own control */}
            <div className="mb-5">
              <label className="text-sm font-medium text-ground-700 mb-2 block">{t('onboarding.muetBand')}</label>
              <div className="flex gap-2 flex-wrap">
                {MUET_BANDS.map(band => (
                  <button
                    key={band}
                    type="button"
                    onClick={() => setMuetBand(band)}
                    className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${
                      muetBand === band
                        ? 'bg-brand-fill text-brand-fill-ink shadow-md'
                        : 'bg-ground-50 text-ground-700 border border-ground-200 hover:bg-ground-100'
                    }`}
                  >
                    {band}
                  </button>
                ))}
              </div>
              <p className="text-xs text-ground-400 mt-1">{t('onboarding.muetHint')}</p>
            </div>

            {figures && (
              <div className="border-t pt-4 grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-ground-500">{t('onboarding.cgpaLabel')}</div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-ground-900">{figures.cgpa.toFixed(2)}</span>
                    <span className="text-sm text-ground-400">/ 4.00</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-ground-500">{t('onboarding.meritLabel')}</div>
                  <span className="text-3xl font-bold text-ground-900">{figures.merit}</span>
                  <div className="text-xs text-ground-400 mt-0.5">{t('onboarding.cgpaAutoCalc')}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 3. SPM results — REQUIRED (D4), the STPM page's own block */}
        <SpmResultsBlock block={spm} step={3} />

        <div className="flex justify-between items-center">
          <Link href="/onboarding/exam-type" className="px-6 py-3 text-ground-600 hover:text-ground-900">
            {t('common.back')}
          </Link>
          <button onClick={handleContinue} disabled={!isComplete}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed">
            {t('common.continue')}
          </button>
        </div>
      </div>
    </main>
  )
}
