'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { getQuizQuestions, submitQuiz, type QuizQuestion, type QuizAnswer } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'

const ICON_EMOJI: Record<string, string> = {
  wrench_gears: '🔧', laptop_code: '💻', handshake_chart: '🤝',
  heart_stethoscope: '❤️', question_sparkle: '✨', paintbrush_ruler: '🎨',
  chef_suitcase: '👨‍🍳', leaf_tractor: '🌿', bolt_ship: '⚡',
  lightning_bolt: '⚡', hardhat_crane: '🏗️', airplane_ship: '✈️',
  oil_rig_flame: '🛢️', hands_tools: '🛠️', brain_lightbulb: '🧠',
  people_bubbles: '👥', pencil_star: '✏️', workshop_garage: '🏭',
  desk_monitor: '🖥️', trees_sun: '🌳', building_people: '🏢',
  hammer_check: '🔨', book_magnifier: '📖', clipboard_group: '📋',
  loop_arrows: '🔄', shield_check: '🛡️', money_rocket: '💰',
  gradcap_arrow: '🎓', lightning_briefcase: '⚡', crowd_sweat: '😰',
  brain_weight: '🧠', arm_weight: '💪', flexed_arm_star: '💪',
  wallet_coins: '👛', house_heart: '🏠', handshake_door: '🤝',
  trophy_star: '🏆',
}

export default function QuizPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, showAuthGate } = useAuth()
  const { t } = useT()
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [currentStep, setCurrentStep] = useState(0)
  const [answers, setAnswers] = useState<(number | number[] | null)[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load questions on mount (only if authenticated)
  useEffect(() => {
    if (authLoading || !isAuthenticated) return
    const lang = localStorage.getItem('halatuju_lang') || 'en'
    getQuizQuestions(lang)
      .then(({ questions: qs }) => {
        setQuestions(qs)
        setAnswers(new Array(qs.length).fill(null))
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load quiz questions. Please try again.')
        setLoading(false)
      })
  }, [authLoading, isAuthenticated])

  // Compute visible questions (filter out conditional questions whose condition is not met)
  const visibleQuestions = useMemo(() => {
    return questions.filter(q => {
      if (!q.condition) return true
      // Only show if the required signal was selected in the required question
      const reqQIdx = questions.findIndex(qq => qq.id === q.condition!.requires)
      if (reqQIdx === -1) return false
      const reqAnswer = answers[reqQIdx]
      if (reqAnswer == null) return false
      const indices = Array.isArray(reqAnswer) ? reqAnswer : [reqAnswer]
      const reqQ = questions[reqQIdx]
      return indices.some(idx => {
        const option = reqQ.options[idx]
        return option && q.condition!.option_signal in option.signals
      })
    })
  }, [questions, answers])

  // Map visible step to original question index
  const origIdx = visibleQuestions.length > 0 && currentStep < visibleQuestions.length
    ? questions.indexOf(visibleQuestions[currentStep])
    : -1
  const question = origIdx >= 0 ? questions[origIdx] : null
  const isMultiSelect = question?.select_mode === 'multi'
  const currentAnswer = origIdx >= 0 ? answers[origIdx] : null

  function isOptionSelected(optIdx: number): boolean {
    if (currentAnswer == null) return false
    if (Array.isArray(currentAnswer)) return currentAnswer.includes(optIdx)
    return currentAnswer === optIdx
  }

  function isOptionDisabled(optIdx: number): boolean {
    if (!isMultiSelect || !question) return false
    const option = question.options[optIdx]
    // If "Not Sure Yet" is selected, disable all others
    if (Array.isArray(currentAnswer) && currentAnswer.some(i => question.options[i]?.not_sure)) {
      return !option.not_sure
    }
    // If max selections reached and this isn't already selected
    if (Array.isArray(currentAnswer) && currentAnswer.length >= (question.max_select || 2)) {
      return !currentAnswer.includes(optIdx)
    }
    return false
  }

  function handleCardClick(optIdx: number) {
    if (!question || origIdx < 0) return
    const option = question.options[optIdx]
    const updated = [...answers]

    if (isMultiSelect) {
      const current = (Array.isArray(currentAnswer) ? currentAnswer : []) as number[]

      if (option.not_sure) {
        // "Not Sure Yet" is exclusive — select only it
        updated[origIdx] = [optIdx]
        setAnswers(updated)
        // Auto-advance after brief pause (exclusive selection = done)
        setTimeout(() => setCurrentStep(prev => Math.min(prev + 1, visibleQuestions.length - 1)), 400)
        return
      }

      // If "Not Sure Yet" was selected, clear it
      const filtered = current.filter(i => !question.options[i]?.not_sure)

      if (filtered.includes(optIdx)) {
        // Deselect
        const newSel = filtered.filter(i => i !== optIdx)
        updated[origIdx] = newSel.length > 0 ? newSel : null
      } else {
        // Select (if under max)
        if (filtered.length < (question.max_select || 2)) {
          updated[origIdx] = [...filtered, optIdx]
        }
      }
      setAnswers(updated)
    } else {
      // Single select
      updated[origIdx] = optIdx
      setAnswers(updated)
      // Auto-advance after 300ms
      if (currentStep < visibleQuestions.length - 1) {
        setTimeout(() => setCurrentStep(prev => prev + 1), 300)
      }
    }
  }

  const handleSubmit = async () => {
    const lang = localStorage.getItem('halatuju_lang') || 'en'
    const quizAnswers: QuizAnswer[] = visibleQuestions.map((q) => {
      const qOrigIdx = questions.indexOf(q)
      const answer = answers[qOrigIdx]
      if (Array.isArray(answer)) {
        return { question_id: q.id, option_indices: answer }
      }
      return { question_id: q.id, option_index: answer! as number }
    })

    setSubmitting(true)
    try {
      const result = await submitQuiz(quizAnswers, lang)
      // Store signals in localStorage for dashboard to pick up
      localStorage.setItem('halatuju_quiz_signals', JSON.stringify(result.student_signals))
      localStorage.setItem('halatuju_signal_strength', JSON.stringify(result.signal_strength))
      router.push('/dashboard')
    } catch {
      setError('Failed to submit quiz. Please try again.')
      setSubmitting(false)
    }
  }

  const allAnswered = visibleQuestions.every(q => {
    const qOrigIdx = questions.indexOf(q)
    const a = answers[qOrigIdx]
    if (a == null) return false
    if (Array.isArray(a)) return a.length > 0
    return true
  })

  // Count answered visible questions
  const answeredCount = visibleQuestions.filter(q => {
    const qOrigIdx = questions.indexOf(q)
    const a = answers[qOrigIdx]
    if (a == null) return false
    if (Array.isArray(a)) return a.length > 0
    return true
  }).length

  // Auth gate: show sign-in prompt if not authenticated
  if (!authLoading && !isAuthenticated) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            {t('authGate.title')}
          </h1>
          <p className="text-gray-600 mb-6">
            {t('authGate.quizReason')}
          </p>
          <button
            onClick={() => showAuthGate('quiz')}
            className="btn-primary"
          >
            {t('saved.signIn')}
          </button>
          <Link href="/dashboard" className="block mt-4 text-gray-500 hover:text-gray-700 text-sm">
            {t('authGate.continueBrowsing')}
          </Link>
        </div>
      </main>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-white">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
          <p className="text-gray-600">{t('quiz.loadingQuiz')}</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button onClick={() => window.location.reload()} className="btn-primary">
            {t('quiz.retry')}
          </button>
        </div>
      </div>
    )
  }

  // Separate regular options from "Not Sure Yet"
  const regularOptions = question ? question.options.filter(o => !o.not_sure) : []
  const notSureOption = question ? question.options.find(o => o.not_sure) : undefined
  const notSureIndex = notSureOption && question ? question.options.indexOf(notSureOption) : -1

  // Check if multi-select has at least 1 selected
  const hasMultiSelection = isMultiSelect && currentAnswer && (Array.isArray(currentAnswer) ? currentAnswer.length > 0 : true)

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Image src="/logo-icon.png" alt="HalaTuju" width={120} height={40} />
          </Link>
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-700 text-sm">
            {t('quiz.skipQuiz')}
          </Link>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">
              {t('quiz.questionOf', { current: String(currentStep + 1), total: String(visibleQuestions.length) })}
            </span>
            <span className="text-sm text-gray-400">
              {t('quiz.answered', { count: String(answeredCount) })}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentStep + 1) / visibleQuestions.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Step dots */}
        <div className="flex justify-center gap-2 mb-8">
          {visibleQuestions.map((q, i) => {
            const qOrigIdx = questions.indexOf(q)
            const a = answers[qOrigIdx]
            const hasAnswer = a != null && (!Array.isArray(a) || a.length > 0)
            return (
              <button
                key={q.id}
                onClick={() => setCurrentStep(i)}
                className={`w-3 h-3 rounded-full transition-all ${
                  i === currentStep
                    ? 'bg-primary-500 scale-125'
                    : hasAnswer
                      ? 'bg-primary-300'
                      : 'bg-gray-300'
                }`}
                aria-label={`Go to question ${i + 1}`}
              />
            )
          })}
        </div>

        {/* Question */}
        {question && (
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-2 text-center">
              {question.prompt}
            </h2>

            {/* Multi-select subtitle */}
            {isMultiSelect && (
              <p className="text-sm text-gray-500 mb-4 text-center">
                {t('quiz.pickUpTo', { count: String(question.max_select || 2) })}
              </p>
            )}

            {/* 2x2 icon card grid */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              {regularOptions.map((option) => {
                const actualIdx = question.options.indexOf(option)
                const selected = isOptionSelected(actualIdx)
                const disabled = isOptionDisabled(actualIdx)
                return (
                  <button
                    key={actualIdx}
                    onClick={() => handleCardClick(actualIdx)}
                    disabled={disabled}
                    className={`
                      aspect-square rounded-2xl border-2 p-4
                      flex flex-col items-center justify-center gap-3
                      transition-all duration-200
                      ${selected
                        ? 'border-primary-500 bg-primary-50 shadow-md scale-[1.03]'
                        : 'border-gray-200 bg-white hover:border-primary-200 hover:shadow-sm'}
                      ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
                    `}
                  >
                    <span className="text-4xl">{ICON_EMOJI[option.icon] || '❓'}</span>
                    <span className={`text-sm font-semibold text-center ${selected ? 'text-primary-700' : 'text-gray-700'}`}>
                      {option.text}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* "Not Sure Yet" pill button */}
            {notSureOption && (
              <div className="flex justify-center">
                <button
                  onClick={() => handleCardClick(notSureIndex)}
                  className={`
                    flex items-center gap-2 px-6 py-2.5 rounded-full border-2
                    transition-all duration-200
                    ${isOptionSelected(notSureIndex)
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 bg-white text-gray-500 hover:border-primary-200'}
                  `}
                >
                  <span className="text-lg">✨</span>
                  <span className="text-sm font-medium">{notSureOption.text}</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
            disabled={currentStep === 0}
            className="text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {t('quiz.previous')}
          </button>

          {currentStep < visibleQuestions.length - 1 ? (
            <>
              {/* For multi-select: show Next button when at least 1 option selected */}
              {isMultiSelect ? (
                <button
                  onClick={() => setCurrentStep(prev => Math.min(prev + 1, visibleQuestions.length - 1))}
                  disabled={!hasMultiSelection}
                  className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {t('quiz.next')}
                </button>
              ) : (
                /* For single-select: show Next as fallback (auto-advance handles most cases) */
                <button
                  onClick={() => setCurrentStep(currentStep + 1)}
                  className="btn-primary"
                >
                  {t('quiz.next')}
                </button>
              )}
            </>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!allAnswered || submitting}
              className="btn-primary"
            >
              {submitting ? t('quiz.submitting') : t('quiz.seeResults')}
            </button>
          )}
        </div>
      </div>
    </main>
  )
}
