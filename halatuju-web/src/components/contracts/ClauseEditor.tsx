'use client'

import { useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  putContractClauses, importContractDocx,
  type ContractTemplateDetail, type ContractClauseData,
} from '@/lib/admin-api'
import { CLocale, LangTabs, inputCls, btnPrimary, btnGhost } from './shared'

type Draft = Partial<ContractClauseData>
const EMPTY: Draft = {
  heading_en: '', heading_ms: '', heading_ta: '', body_en: '', body_ms: '', body_ta: '',
  is_quiz_candidate: false, quiz_en: {}, quiz_ms: {}, quiz_ta: {},
}

// The Clauses tab — ordered clause list (heading/body per language) + the Word import:
// import-docx PROPOSES clauses, the author REVIEWS them, and only on Accept do they
// replace the draft's clauses (the file is never retained).
export default function ClauseEditor(
  { template, token, onChange }: {
    template: ContractTemplateDetail; token: string
    onChange: (t: ContractTemplateDetail) => void
  }) {
  const { t } = useT()
  const draft = template.status === 'draft'
  const [lang, setLang] = useState<CLocale>('en')
  const [clauses, setClauses] = useState<Draft[]>(template.clauses.map((c) => ({ ...c })))
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  // Word import
  const fileRef = useRef<HTMLInputElement>(null)
  const [importing, setImporting] = useState(false)
  const [proposed, setProposed] = useState<Array<{ heading: string; body: string }> | null>(null)

  const set = (i: number, k: keyof ContractClauseData, v: unknown) =>
    setClauses((prev) => prev.map((c, j) => (j === i ? { ...c, [k]: v } : c)))
  const hk = `heading_${lang}` as keyof ContractClauseData
  const bk = `body_${lang}` as keyof ContractClauseData

  const persist = async (list: Draft[]) => {
    setSaving(true); setErr(null); setMsg(null)
    try {
      const updated = await putContractClauses(template.id, list, { token })
      onChange(updated); setClauses(updated.clauses.map((c) => ({ ...c }))); setMsg(t('admin.contracts.saved'))
    } catch (e) {
      setErr((e as Error)?.message || t('admin.contracts.actionFailed'))
    }
    setSaving(false)
  }

  const onImport = async (file: File) => {
    setImporting(true); setErr(null); setProposed(null)
    try {
      const { clauses: got } = await importContractDocx(template.id, file, { token })
      setProposed(got)
    } catch {
      setErr(t('admin.contracts.importFailed'))   // graceful degradation → edit by hand
    }
    setImporting(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const acceptImport = async () => {
    if (!proposed) return
    const list: Draft[] = proposed.map((c) => ({ ...EMPTY, heading_en: c.heading, body_en: c.body }))
    setProposed(null)
    await persist(list)
  }

  return (
    <div className="space-y-5">
      {err && <div className="rounded-lg p-3 bg-red-50 border border-red-200 text-red-600 text-sm">{err}</div>}
      {msg && <div className="rounded-lg p-3 bg-green-50 border border-green-200 text-green-700 text-sm">{msg}</div>}

      {draft && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <LangTabs value={lang} onChange={setLang} />
          <div className="flex items-center gap-2">
            <input ref={fileRef} type="file" accept=".docx" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onImport(f) }} />
            <button type="button" onClick={() => fileRef.current?.click()} disabled={importing} className={btnGhost}>
              {importing ? t('admin.contracts.importing') : t('admin.contracts.importDocx')}
            </button>
          </div>
        </div>
      )}
      {draft && <p className="text-xs text-gray-400">{t('admin.contracts.importHint')}</p>}

      {/* Word-import review-before-accept */}
      {proposed && (
        <div className="rounded-xl border-2 border-blue-300 bg-blue-50/40 p-5 space-y-3">
          <div className="font-semibold text-gray-900">{t('admin.contracts.importReviewTitle')}</div>
          <p className="text-sm text-gray-600">{t('admin.contracts.importReviewHint')}</p>
          <ol className="space-y-2 list-decimal pl-5 max-h-80 overflow-y-auto">
            {proposed.map((c, i) => (
              <li key={i} className="text-sm">
                <span className="font-semibold">{c.heading || '—'}</span>
                <div className="text-gray-600 whitespace-pre-wrap">{c.body}</div>
              </li>
            ))}
          </ol>
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={acceptImport} disabled={saving} className={btnPrimary}>
              {t('admin.contracts.importAccept')}</button>
            <button type="button" onClick={() => setProposed(null)} className={btnGhost}>
              {t('admin.contracts.importDiscard')}</button>
          </div>
        </div>
      )}

      {clauses.map((c, i) => (
        <div key={i} className="bg-white rounded-xl border p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-400">{i + 1}</span>
            {draft && (
              <button type="button" onClick={() => setClauses((prev) => prev.filter((_, j) => j !== i))}
                className="text-xs text-red-600 hover:text-red-800">{t('admin.contracts.remove')}</button>
            )}
          </div>
          <input className={inputCls} disabled={!draft} placeholder={t('admin.contracts.heading')}
            value={String(c[hk] || '')} onChange={(e) => set(i, hk, e.target.value)} />
          <textarea rows={3} className={inputCls} disabled={!draft} placeholder={t('admin.contracts.body')}
            value={String(c[bk] || '')} onChange={(e) => set(i, bk, e.target.value)} />
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" disabled={!draft} checked={!!c.is_quiz_candidate}
              onChange={(e) => set(i, 'is_quiz_candidate', e.target.checked)} />
            {t('admin.contracts.useForQuiz')}
          </label>
        </div>
      ))}
      {clauses.length === 0 && <p className="text-sm text-gray-400">{t('admin.contracts.noClauses')}</p>}

      {draft && (
        <div className="flex gap-3">
          <button type="button" onClick={() => setClauses((prev) => [...prev, { ...EMPTY }])} className={btnGhost}>
            {t('admin.contracts.addClause')}</button>
          <button type="button" onClick={() => persist(clauses)} disabled={saving} className={btnPrimary}>
            {saving ? t('admin.contracts.saving') : t('admin.contracts.saveClauses')}</button>
        </div>
      )}
      {!draft && <p className="text-sm text-gray-500">{t('admin.contracts.notDraftMsg')}</p>}
    </div>
  )
}
