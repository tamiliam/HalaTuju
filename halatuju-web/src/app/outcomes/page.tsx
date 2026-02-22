'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  getOutcomes,
  updateOutcome,
  deleteOutcome,
  type AdmissionOutcome,
  type OutcomeStatus,
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'

const STATUS_COLOURS: Record<OutcomeStatus, string> = {
  applied: 'bg-blue-50 text-blue-700 border-blue-200',
  offered: 'bg-green-50 text-green-700 border-green-200',
  accepted: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  rejected: 'bg-red-50 text-red-700 border-red-200',
  withdrawn: 'bg-gray-50 text-gray-500 border-gray-200',
}

const STATUS_OPTIONS: OutcomeStatus[] = ['applied', 'offered', 'accepted', 'rejected', 'withdrawn']

export default function OutcomesPage() {
  const { t } = useT()
  const { token, isAuthenticated, isLoading: authLoading } = useAuth()
  const [outcomes, setOutcomes] = useState<AdmissionOutcome[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)

  useEffect(() => {
    if (authLoading) return
    if (!isAuthenticated || !token) {
      setLoading(false)
      return
    }
    getOutcomes({ token })
      .then(({ outcomes: data }) => setOutcomes(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [authLoading, isAuthenticated, token])

  const handleStatusChange = async (outcomeId: number, newStatus: OutcomeStatus) => {
    if (!token) return
    try {
      await updateOutcome(outcomeId, { status: newStatus }, { token })
      setOutcomes(prev =>
        prev.map(o => o.id === outcomeId ? { ...o, status: newStatus } : o)
      )
    } catch {
      // Silently fail — user can retry
    }
    setEditingId(null)
  }

  const handleDelete = async (outcomeId: number) => {
    if (!token) return
    if (!confirm(t('outcomes.confirmDelete'))) return
    try {
      await deleteOutcome(outcomeId, { token })
      setOutcomes(prev => prev.filter(o => o.id !== outcomeId))
    } catch {
      // Silently fail
    }
  }

  const statusLabel = (s: OutcomeStatus) => t(`outcomes.status${s.charAt(0).toUpperCase() + s.slice(1)}`)

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/saved" className="text-gray-600 hover:text-gray-900">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">{t('outcomes.title')}</h1>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          </div>
        )}

        {!loading && !isAuthenticated && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('saved.signInPrompt')}</p>
            <Link href="/login" className="btn-primary">{t('saved.signIn')}</Link>
          </div>
        )}

        {!loading && isAuthenticated && outcomes.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-2">{t('outcomes.empty')}</p>
            <p className="text-gray-500 text-sm mb-6">{t('outcomes.emptyHint')}</p>
            <Link href="/saved" className="btn-primary">{t('saved.title')}</Link>
          </div>
        )}

        {!loading && outcomes.length > 0 && (
          <div className="space-y-4">
            {outcomes.map(outcome => (
              <div key={outcome.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <Link href={`/course/${outcome.course_id}`} className="hover:underline">
                      <h3 className="font-semibold text-gray-900">{outcome.course_name}</h3>
                    </Link>
                    {outcome.institution_name && (
                      <p className="text-sm text-gray-500 mt-0.5">{outcome.institution_name}</p>
                    )}
                  </div>

                  {/* Status badge */}
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${STATUS_COLOURS[outcome.status]}`}>
                    {statusLabel(outcome.status)}
                  </span>
                </div>

                {/* Actions row */}
                <div className="mt-3 flex items-center gap-3">
                  {editingId === outcome.id ? (
                    <div className="flex flex-wrap gap-2">
                      {STATUS_OPTIONS.map(s => (
                        <button
                          key={s}
                          onClick={() => handleStatusChange(outcome.id, s)}
                          className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                            s === outcome.status
                              ? STATUS_COLOURS[s]
                              : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          {statusLabel(s)}
                        </button>
                      ))}
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-3 py-1 text-xs text-gray-400 hover:text-gray-600"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        onClick={() => setEditingId(outcome.id)}
                        className="text-sm text-primary-600 hover:text-primary-800 font-medium"
                      >
                        {t('outcomes.updateStatus')}
                      </button>
                      <span className="text-gray-300">|</span>
                      <button
                        onClick={() => handleDelete(outcome.id)}
                        className="text-sm text-gray-400 hover:text-red-500"
                      >
                        {t('outcomes.deleteOutcome')}
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
