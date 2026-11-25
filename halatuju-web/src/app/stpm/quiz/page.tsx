'use client'

import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  getStpmQuizQuestions,
  resolveStpmQuizQ3Q4,
  submitStpmQuiz,
  type StpmQuizQuestion,
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import '@/lib/messagesDiscovery'   // its Next on a phone (`discovery.quizNext`, page-loaded slice)
import { PHONE_GUTTER } from '@/lib/phoneSection'   // rule 15 (Mobile M4c)
import { STPM_SUBJECT_TO_API_KEY } from '@/lib/stpmResultsSubjects'
import {
  KEY_STPM_GRADES,
  KEY_STPM_QUIZ_SIGNALS,
  KEY_STPM_QUIZ_BRANCH,
  KEY_REPORT_GENERATED,
} from '@/lib/storage'

const ICON_EMOJI: Record<string, string> = {
  laptop_code: '\u{1f4bb}', handshake_chart: '\u{1f91d}',
  heart_stethoscope: '\u{2764}\ufe0f', paintbrush_ruler: '\u{1f3a8}',
  leaf_tractor: '\u{1f33f}', lightning_bolt: '\u{26a1}', hardhat_crane: '\u{1f3d7}\ufe0f', airplane_ship: '\u{2708}\ufe0f',
  gradcap_arrow: '\u{1f393}', flexed_arm_star: '\u{1f4aa}',
    // STPM icons: exactly the names stpm_quiz_data.py uses (quizIconMaps.test.ts keeps it so)
  arrow_turn: '\u21aa\ufe0f', atom_formula: '\u269b\ufe0f', atom_laptop: '\u269b\ufe0f',
  atom_microscope: '\u{1f52c}', brain_chart: '\u{1f4ca}', brain_heart: '\u{1f49e}',
  briefcase_star: '\u{1f4bc}', building_flag: '\u{1f3db}\ufe0f', calculator_chart: '\u{1f9ee}',
  calculator_check: '\u{1f9ee}', camera_sparkle: '\u{1f4f7}', certificate_crown: '\u{1f4dc}',
  chalkboard_apple: '\u{1f34e}', chart_money: '\u{1f4c8}', clipboard_heart: '\u{1f4cb}',
  compass_arrow: '\u{1f9ed}', dna_leaf: '\u{1f9ec}', family_heart: '\u{1f46a}', family_star: '\u{1f46a}',
  flask_bubbles: '\u2697\ufe0f', flask_fire: '\u{1f9ea}', flexed_arm_fire: '\u{1f4aa}',
  gear_blueprint: '\u2699\ufe0f', gear_wrench: '\u{1f527}', globe_handshake: '\u{1f30d}',
  gradcap_heart: '\u{1f393}', gradcap_people: '\u{1f393}', graph_shield: '\u{1f6e1}\ufe0f',
  hands_heart: '\u{1f932}', hands_up: '\u{1f64c}', heart_book: '\u{1f4d6}', heart_dna: '\u{1f9ec}',
  heart_shield: '\u{1f6e1}\ufe0f', laptop_gear: '\u{1f4bb}', leaf_globe: '\u{1f30d}',
  magnifying_question: '\u{1f50d}', megaphone_chart: '\u{1f4e3}', megaphone_star: '\u{1f4e3}',
  money_briefcase: '\u{1f4bc}', newspaper_mic: '\u{1f4f0}', paintbrush_mic: '\u{1f399}\ufe0f',
  paintbrush_screen: '\u{1f58c}\ufe0f', paintbrush_star: '\u{1f3a8}', people_gear: '\u2699\ufe0f',
  people_scale: '\u2696\ufe0f', people_tree: '\u{1f333}', person_arrow: '\u{1f6b6}',
  pill_microscope: '\u{1f48a}', rocket_chart: '\u{1f680}', rocket_star: '\u{1f680}',
  scales_document: '\u2696\ufe0f', scales_gavel: '\u2696\ufe0f', shield_money: '\u{1f4b0}',
  shield_network: '\u{1f310}', stethoscope: '\u{1fa7a}', target_bullseye: '\u{1f3af}',
  wallet_people: '\u{1f45b}',
}

/**
 * Convert localStorage STPM grades (uppercase IDs) to API format (lowercase keys).
 * Returns {subjects, grades} ready for the quiz API.
 */
function convertGradesToApiFormat(stpmGrades: Record<string, string>): {
  subjects: string[]
  grades: Record<string, string>
} {
  const subjects: string[] = []
  const grades: Record<string, string> = {}

  for (const [frontendId, grade] of Object.entries(stpmGrades)) {
    if (!grade || frontendId === 'PA') continue // PA is not used for quiz branching
    const apiKey = STPM_SUBJECT_TO_API_KEY[frontendId]
    if (apiKey) {
      subjects.push(apiKey)
      grades[apiKey] = grade
    }
  }

  return { subjects, grades }
}

export default function StpmQuizPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, showAuthGate } = useAuth()
  const { t, locale } = useT()

  // Quiz state
  const [allQuestions, setAllQuestions] = useState<StpmQuizQuestion[]>([])
  const [branch, setBranch] = useState<string>('')
  const [apiSubjects, setApiSubjects] = useState<string[]>([])
  const [apiGrades, setApiGrades] = useState<Record<string, string>>({})
  const [currentStep, setCurrentStep] = useState(0)
  // TD-708: the one pending auto-advance. Next, Previous and the dots cancel it; it moves on from the
  // step the answer was given on, so an answer then Next is one step, not two.
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cancelAdvance = useCallback(() => {
    if (advanceTimer.current !== null) { clearTimeout(advanceTimer.current); advanceTimer.current = null }
  }, [])
  function goToStep(step: number) { cancelAdvance(); setCurrentStep(step) }
  const advanceTo = useCallback((step: number, delay: number) => {
    cancelAdvance()
    advanceTimer.current = setTimeout(() => {
      advanceTimer.current = null
      setCurrentStep(step)
    }, delay)
  }, [cancelAdvance])
  useEffect(() => cancelAdvance, [cancelAdvance])
  const [answers, setAnswers] = useState<(number | null)[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Track Q2 field signal → Q3/Q4 resolution
  const [q2Resolved, setQ2Resolved] = useState(false)

  // Load questions on mount
  useEffect(() => {
    if (authLoading || !isAuthenticated) return

    const stpmGradesStr = localStorage.getItem(KEY_STPM_GRADES)
    if (!stpmGradesStr) {
      router.push('/onboarding/stpm-grades')
      return
    }

    const stpmGrades = JSON.parse(stpmGradesStr)
    const { subjects, grades } = convertGradesToApiFormat(stpmGrades)

    if (subjects.length < 2) {
      router.push('/onboarding/stpm-grades')
      return
    }

    setApiSubjects(subjects)
    setApiGrades(grades)

    const lang = locale === 'ms' ? 'bm' : locale
    getStpmQuizQuestions(subjects, grades, lang)
      .then((data) => {
        // Build initial question list: Q1, Q2 (Q3/Q4 resolved later), Q5, trunk Q7-Q10
        const initial: StpmQuizQuestion[] = [
          ...data.questions, // Q1 + Q2
          // Q3/Q4 placeholders — will be replaced after Q2 answer
        ]
        // Store the full response for Q3 resolution
        setBranch(data.branch)

        // We start with Q1 + Q2 only. Q3/Q4 get inserted after Q2 is answered.
        // Then Q5 + trunk (Q7-Q10) follow.
        const q5AndTrunk = [data.q5, ...data.trunk_remaining]
        // Store everything: initial questions + a marker for Q3/Q4 + rest
        setAllQuestions([...initial, ...q5AndTrunk])
        setAnswers(new Array(initial.length + q5AndTrunk.length).fill(null))
        setLoading(false)
      })
      .catch(() => {
        setError(t('stpmQuiz.loadError'))
        setLoading(false)
      })
  }, [authLoading, isAuthenticated, locale, router, t])

  // After Q2 is answered, resolve Q3 and Q4 from the backend
  const handleQ2Answered = useCallback(async (q2OptionIndex: number) => {
    if (q2Resolved || allQuestions.length < 2) return

    const q2 = allQuestions[1] // Q2 is always index 1
    const chosenOption = q2.options[q2OptionIndex]
    if (!chosenOption) return

    // Find the field signal from the chosen option
    const fieldSignal = Object.keys(chosenOption.signals).find(s => s.startsWith('field_'))
    if (!fieldSignal) return

    const lang = locale === 'ms' ? 'bm' : locale
    try {
      const resolved = await resolveStpmQuizQ3Q4(fieldSignal, branch, apiGrades, lang)

      // Insert Q3 and Q4 after Q2 (index 1), before Q5 and trunk
      const q1q2 = allQuestions.slice(0, 2) // Q1, Q2
      const rest = allQuestions.slice(2) // Q5, trunk Q7-Q10

      const newQuestions: StpmQuizQuestion[] = [...q1q2]
      if (resolved.q3) newQuestions.push(resolved.q3)
      if (resolved.q4) newQuestions.push(resolved.q4)
      newQuestions.push(...rest)

      setAllQuestions(newQuestions)
      setAnswers(new Array(newQuestions.length).fill(null).map((_, i) => {
        // Preserve existing answers for Q1 and Q2
        if (i < 2) return answers[i]
        return null
      }))
      setQ2Resolved(true)

      // Auto-advance to Q3
      advanceTo(2, 300)
    } catch {
      // If resolve fails, continue with remaining questions (skip Q3/Q4)
      setQ2Resolved(true)
      advanceTo(2, 300)
    }
  }, [q2Resolved, allQuestions, branch, apiGrades, locale, answers, advanceTo])

  const question = currentStep < allQuestions.length ? allQuestions[currentStep] : null
  const currentAnswer = currentStep < answers.length ? answers[currentStep] : null
  const currentAnswered = currentAnswer !== null && currentAnswer !== undefined

  function handleCardClick(optIdx: number) {
    if (!question) return

    const updated = [...answers]
    updated[currentStep] = optIdx
    setAnswers(updated)

    // If Q2 was just answered, resolve Q3/Q4 before advancing
    if (currentStep === 1 && !q2Resolved) {
      handleQ2Answered(optIdx)
      return
    }

    // Auto-advance after 300ms
    if (currentStep < allQuestions.length - 1) {
      advanceTo(currentStep + 1, 300)
    }
  }

  const handleSubmit = async () => {
    const lang = locale === 'ms' ? 'bm' : locale
    const quizAnswers = allQuestions.map((q, i) => ({
      question_id: q.id,
      option_index: answers[i]!,
    }))

    setSubmitting(true)
    try {
      const result = await submitStpmQuiz(quizAnswers, apiSubjects, apiGrades, lang)
      // Store signals in localStorage for dashboard to pick up
      localStorage.setItem(KEY_STPM_QUIZ_SIGNALS, JSON.stringify(result.student_signals))
      localStorage.setItem(KEY_STPM_QUIZ_BRANCH, result.branch)
      // Reset report gate — new quiz unlocks report generation
      localStorage.removeItem(KEY_REPORT_GENERATED)
      router.push('/dashboard')
    } catch {
      setError(t('stpmQuiz.submitError'))
      setSubmitting(false)
    }
  }

  const allAnswered = allQuestions.length > 0 && answers.every(a => a !== null)

  const answeredCount = answers.filter(a => a !== null).length

  // Auth gate
  if (!authLoading && !isAuthenticated) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-primary-50 to-ground-0 flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <h1 className="text-2xl font-bold text-ground-900 mb-4">
            {t('authGate.title')}
          </h1>
          <p className="text-ground-600 mb-6">
            {t('authGate.quizReason')}
          </p>
          <button
            onClick={() => showAuthGate('quiz')}
            className="btn-primary"
          >
            {t('saved.signIn')}
          </button>
          <Link href="/dashboard" className="block mt-4 text-ground-500 hover:text-ground-700 text-sm">
            {t('authGate.continueBrowsing')}
          </Link>
        </div>
      </main>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-ground-0">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-brand-shape border-t-transparent mb-4" />
          <p className="text-ground-600">{t('stpmQuiz.loading')}</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-critical-600 mb-4">{error}</p>
          <button onClick={() => window.location.reload()} className="btn-primary">
            {t('common.retry')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-ground-50">
      {/* Gradient header */}
      <header className="bg-gradient-to-r from-brand-fill to-brand-fill-hover text-brand-fill-ink">
        <div className={`container mx-auto ${PHONE_GUTTER} py-2 flex items-center justify-between`}>
          <Link href="/dashboard" className="-ml-2 inline-flex min-h-11 items-center px-2 text-brand-fill-ink/90 hover:text-brand-fill-ink text-sm font-medium">
            &larr; {t('common.appName')}
          </Link>
          <Link href="/dashboard" className="-mr-2 inline-flex min-h-11 items-center px-2 text-brand-fill-ink/70 hover:text-brand-fill-ink text-sm">
            {t('stpmQuiz.skip')}
          </Link>
        </div>

        {/* Progress bar */}
        <div className={`${PHONE_GUTTER} pb-4`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-brand-fill-ink/90">
              {t('quiz.questionOf', { current: String(currentStep + 1), total: String(allQuestions.length) })}
            </span>
            <span className="text-sm text-brand-fill-ink/60">
              {t('quiz.answered', { count: String(answeredCount) })}
            </span>
          </div>
          <div className="w-full bg-ground-0/20 rounded-full h-1.5">
            <div
              className="bg-ground-0 h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${((currentStep + 1) / allQuestions.length) * 100}%` }}
            />
          </div>
        </div>
      </header>

      <div className={`container mx-auto ${PHONE_GUTTER} py-4 max-w-md md:py-6`}>
        {/* Step dots — md and up only (owner, 2026-11-02): ten 10 px dots cannot be 44 px targets on a phone,
            so a phone shows the header's progress bar and "Question n of N" and moves with Next / Previous. */}
        <div className="hidden md:flex justify-center gap-2 mb-6" data-testid="quiz-dots">
          {allQuestions.map((q, i) => {
            const hasAnswer = answers[i] !== null
            return (
              <button
                key={q.id}
                onClick={() => {
                  // Only allow navigating to answered questions or the current one
                  if (i <= currentStep || hasAnswer) goToStep(i)
                }}
                className={`w-2.5 h-2.5 rounded-full transition-all ${
                  i === currentStep
                    ? 'bg-info-500 scale-125'
                    : hasAnswer
                      ? 'bg-info-300'
                      : 'bg-ground-300'
                }`}
                aria-label={t('quiz.goToQuestion', { n: String(i + 1) })}
              />
            )
          })}
        </div>

        {/* Question */}
        {question && (
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-ground-900 mb-4 text-center">
              {question.prompt}
            </h2>

            {/* Card grid — 2x2 for 4 options, single column for 3 */}
            <div className={`grid gap-3 mb-5 md:gap-4 ${
              question.options.length <= 3 ? 'grid-cols-1' : 'grid-cols-2'
            }`}>
              {question.options.map((option, optIdx) => {
                const selected = currentAnswer === optIdx
                return (
                  <button
                    key={optIdx}
                    onClick={() => handleCardClick(optIdx)}
                    className={`
                      ${question.options.length <= 3 ? 'py-4 px-5' : 'aspect-square p-5'}
                      rounded-2xl border-2
                      flex ${question.options.length <= 3 ? 'flex-row items-center gap-4' : 'flex-col items-center justify-center gap-3'}
                      transition-all duration-200 shadow-sm
                      ${selected
                        ? 'border-info-500 bg-info-50 shadow-lg scale-[1.04]'
                        : 'border-ground-100 bg-ground-0 hover:border-info-200 hover:shadow-md'}
                      cursor-pointer active:scale-95
                    `}
                  >
                    <span className={question.options.length <= 3 ? 'text-3xl' : 'text-5xl leading-none'}>
                      {ICON_EMOJI[option.icon] || '\u2753'}
                    </span>
                    <span className={`text-sm font-bold ${question.options.length <= 3 ? 'text-left' : 'text-center'} leading-tight ${selected ? 'text-primary-700' : 'text-ground-700'}`}>
                      {option.text}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={() => goToStep(Math.max(0, currentStep - 1))}
            disabled={currentStep === 0}
            className="-ml-2 inline-flex min-h-11 items-center px-2 md:ml-0 md:min-h-0 md:px-0 text-ground-400 hover:text-ground-600 disabled:opacity-30 disabled:cursor-not-allowed text-sm"
          >
            {t('quiz.previous')}
          </button>

          {currentStep === allQuestions.length - 1 ? (
            <button
              onClick={handleSubmit}
              disabled={!allAnswered || submitting}
              className="btn-primary disabled:opacity-40"
            >
              {submitting ? t('quiz.submitting') : t('quiz.seeResults')}
            </button>
          ) : (
            <>
              {/* Phones (owner, 2026-11-02): no dot row, so Next moves on — once this question has an answer. */}
              <button
                onClick={() => goToStep(currentStep + 1)}
                disabled={!currentAnswered}
                className="btn-primary min-h-11 md:hidden disabled:opacity-40"
                data-testid="quiz-next"
              >
                {t('discovery.quizNext')}
              </button>
              <div className="hidden md:block" /> {/* Spacer for flex alignment (desktop, as before) */}
            </>
          )}
        </div>
      </div>
    </main>
  )
}
