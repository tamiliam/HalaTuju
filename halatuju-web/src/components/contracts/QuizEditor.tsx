'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  generateContractQuiz, putContractClauses,
  type ContractTemplateDetail, type ContractClauseData, type ContractQuizPayload,
} from '@/lib/admin-api'
import { CLocale, LangTabs, inputCls, btnPrimary, btnGhost } from './shared'

// The Quiz tab — for each clause flagged a quiz candidate: "Generate with Gemini" drafts a
// question in en/ms/ta (draft-only, on-demand, billable); the author reviews/edits/regenerates,
// then Save persists the edited quiz payloads (via the clauses PUT).
export default function QuizEditor(
  { template, token, onChange }: {
    template: ContractTemplateDetail; token: string
    onChange: (t: ContractTemplateDetail) => void
  }) {
  const { t } = useT()
  const draft = template.status === 'draft'
  const [lang, setLang] = useState<CLocale>('en')
  const [clauses, setClauses] = useState<ContractClauseData[]>(template.clauses.map((c) => ({ ...c })))
  const [busy, setBusy] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const qk = `quiz_${lang}` as 'quiz_en' | 'quiz_ms' | 'quiz_ta'
  const candidates = clauses.filter((c) => c.is_quiz_candidate)

  const patchQuiz = (order: number, next: ContractQuizPayload) =>
    setClauses((prev) => prev.map((c) => (c.order === order ? { ...c, [qk]: next } : c)))

  const generate = async (order: number) => {
    setBusy(order); setErr(null); setMsg(null)
    try {
      const clause = await generateContractQuiz(template.id, order, { token })
      setClauses((prev) => prev.map((c) => (c.order === order ? { ...clause } : c)))
    } catch (e) {
      setErr((e as Error)?.message || t('admin.contracts.actionFailed'))
    }
    setBusy(null)
  }

  const save = async () => {
    setSaving(true); setErr(null); setMsg(null)
    try {
      const updated = await putContractClauses(template.id, clauses, { token })
      onChange(updated); setClauses(updated.clauses.map((c) => ({ ...c }))); setMsg(t('admin.contracts.saved'))
    } catch (e) {
      setErr((e as Error)?.message || t('admin.contracts.actionFailed'))
    }
    setSaving(false)
  }

  if (candidates.length === 0) {
    return <p className="text-sm text-gray-500">{t('admin.contracts.quizCandidatesOnly')}</p>
  }

  return (
    <div className="space-y-5">
      {err && <div className="rounded-lg p-3 bg-red-50 border border-red-200 text-red-600 text-sm">{err}</div>}
      {msg && <div className="rounded-lg p-3 bg-green-50 border border-green-200 text-green-700 text-sm">{msg}</div>}
      <div className="flex justify-end"><LangTabs value={lang} onChange={setLang} /></div>

      {candidates.map((c) => {
        const q = (c[qk] || {}) as ContractQuizPayload
        const opts = q.options || ['', '', '']
        const has = !!q.question
        return (
          <div key={c.order} className="bg-white rounded-xl border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-900">{c.order}. {c.heading_en}</span>
              {draft && (
                <button type="button" onClick={() => generate(c.order)} disabled={busy === c.order} className={btnGhost}>
                  {busy === c.order ? t('admin.contracts.generating')
                    : has ? t('admin.contracts.regenerate') : t('admin.contracts.generateWithGemini')}
                </button>
              )}
            </div>

            {!has ? <p className="text-sm text-gray-400">{t('admin.contracts.noQuizYet')}</p> : (
              <div className="space-y-2">
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">{t('admin.contracts.quizPlain')}</span>
                  <textarea rows={2} className={inputCls} disabled={!draft} value={q.plain || ''}
                    onChange={(e) => patchQuiz(c.order, { ...q, plain: e.target.value })} />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">{t('admin.contracts.quizQuestion')}</span>
                  <input className={inputCls} disabled={!draft} value={q.question || ''}
                    onChange={(e) => patchQuiz(c.order, { ...q, question: e.target.value })} />
                </label>
                <span className="text-xs font-medium text-gray-600">
                  {t('admin.contracts.quizOptions')} — {t('admin.contracts.markCorrect')}
                </span>
                {opts.map((o, k) => (
                  <div key={k} className="flex items-center gap-2">
                    <input type="radio" name={`correct-${c.order}-${lang}`} disabled={!draft} checked={q.correct === k}
                      onChange={() => patchQuiz(c.order, { ...q, correct: k })} />
                    <input className={inputCls} disabled={!draft} value={o}
                      onChange={(e) => patchQuiz(c.order, { ...q, options: opts.map((x, j) => (j === k ? e.target.value : x)) })} />
                  </div>
                ))}
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">{t('admin.contracts.quizWhy')}</span>
                  <textarea rows={2} className={inputCls} disabled={!draft} value={q.why || ''}
                    onChange={(e) => patchQuiz(c.order, { ...q, why: e.target.value })} />
                </label>
                {c.quiz_generated_model && (
                  <p className="text-xs text-gray-400">{t('admin.contracts.draftedBy', { model: c.quiz_generated_model })}</p>
                )}
              </div>
            )}
          </div>
        )
      })}

      {draft
        ? <button type="button" onClick={save} disabled={saving} className={btnPrimary}>
            {saving ? t('admin.contracts.saving') : t('admin.contracts.save')}</button>
        : <p className="text-sm text-gray-500">{t('admin.contracts.notDraftMsg')}</p>}
    </div>
  )
}
