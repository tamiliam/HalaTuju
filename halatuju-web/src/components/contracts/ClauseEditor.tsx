'use client'

import { useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  putContractClauses, importContractDocx,
  type ContractTemplateDetail, type ContractClauseData,
} from '@/lib/admin-api'
import { clauseNumbers, normaliseLevels, canIndent, canOutdent } from '@/lib/clauseNumbering'
import { CLocale, LangTabs, inputCls, btnPrimary, btnGhost } from './shared'

type Draft = Partial<ContractClauseData>
const EMPTY: Draft = {
  level: 0, heading_en: '', heading_ms: '', heading_ta: '', body_en: '', body_ms: '', body_ta: '',
  is_quiz_candidate: false, quiz_en: {}, quiz_ms: {}, quiz_ta: {},
}

// The Clauses tab — a 3-level hierarchy (clause 1. / sub 1.1 / sub-sub i)) with Indent/Outdent,
// move, and the Word import. Numbers are COMPUTED from the level run (clauseNumbers) — never typed.
// Levels are kept normalised in state (no skipping) so what shows is what saves; only a top-level
// clause carries a comprehension quiz. import-docx PROPOSES clauses (with levels) for review before
// they replace the draft (the file is never retained).
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
  const [proposed, setProposed] = useState<Array<{ heading: string; body: string; level: number }> | null>(null)

  const hk = `heading_${lang}` as keyof ContractClauseData
  const bk = `body_${lang}` as keyof ContractClauseData

  const levels = clauses.map((c) => c.level ?? 0)
  const numbers = clauseNumbers(levels)

  // Field edits don't touch structure.
  const set = (i: number, k: keyof ContractClauseData, v: unknown) =>
    setClauses((prev) => prev.map((c, j) => (j === i ? { ...c, [k]: v } : c)))

  // Any STRUCTURAL change re-normalises the levels (no skipping) and clears the quiz flag on any
  // clause that is no longer top-level — so the displayed numbers + quiz controls always match
  // what will be saved.
  const setStructural = (list: Draft[]) => {
    const lv = normaliseLevels(list.map((c) => c.level ?? 0))
    setClauses(list.map((c, i) => (lv[i] === 0
      ? { ...c, level: 0 }
      : { ...c, level: lv[i], is_quiz_candidate: false })))
  }

  const indent = (i: number) => { if (canIndent(levels, i)) setStructural(clauses.map((c, j) => j === i ? { ...c, level: (c.level ?? 0) + 1 } : c)) }
  const outdent = (i: number) => { if (canOutdent(levels, i)) setStructural(clauses.map((c, j) => j === i ? { ...c, level: (c.level ?? 0) - 1 } : c)) }
  const move = (i: number, d: -1 | 1) => {
    const j = i + d
    if (j < 0 || j >= clauses.length) return
    const next = clauses.slice()
    ;[next[i], next[j]] = [next[j], next[i]]
    setStructural(next)
  }
  const remove = (i: number) => setStructural(clauses.filter((_, j) => j !== i))
  const add = () => setStructural([...clauses, { ...EMPTY }])

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
    const list: Draft[] = proposed.map((c) => ({ ...EMPTY, level: c.level ?? 0, heading_en: c.heading, body_en: c.body }))
    setProposed(null)
    await persist(list)
  }

  const iconBtn = 'w-7 h-7 inline-flex items-center justify-center rounded-md border border-gray-200 text-gray-500 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-30 disabled:hover:bg-transparent'

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
      {draft && <p className="text-xs text-gray-400">{t('admin.contracts.hierarchyHint')}</p>}

      {/* Word-import review-before-accept (indented to show the detected levels) */}
      {proposed && (
        <div className="rounded-xl border-2 border-blue-300 bg-blue-50/40 p-5 space-y-3">
          <div className="font-semibold text-gray-900">{t('admin.contracts.importReviewTitle')}</div>
          <p className="text-sm text-gray-600">{t('admin.contracts.importReviewHint')}</p>
          {(() => { const pn = clauseNumbers(proposed.map((c) => c.level ?? 0)); return (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {proposed.map((c, i) => (
                <div key={i} className="text-sm" style={{ paddingLeft: `${(c.level ?? 0) * 22}px` }}>
                  <span className="font-mono font-semibold text-blue-700 mr-2">{pn[i]}</span>
                  <span className="font-semibold">{c.heading || '—'}</span>
                  <div className="text-gray-600 whitespace-pre-wrap">{c.body}</div>
                </div>
              ))}
            </div>
          ) })()}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={acceptImport} disabled={saving} className={btnPrimary}>
              {t('admin.contracts.importAccept')}</button>
            <button type="button" onClick={() => setProposed(null)} className={btnGhost}>
              {t('admin.contracts.importDiscard')}</button>
          </div>
        </div>
      )}

      {clauses.map((c, i) => {
        const level = c.level ?? 0
        return (
          <div key={i} className="bg-white rounded-xl border p-4 space-y-2"
            style={{ marginLeft: `${level * 28}px` }}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs font-bold text-blue-700 tabular-nums">{numbers[i]}</span>
              {draft && (
                <div className="flex items-center gap-1">
                  <button type="button" title={t('admin.contracts.outdent')} onClick={() => outdent(i)} disabled={!canOutdent(levels, i)} className={iconBtn}>←</button>
                  <button type="button" title={t('admin.contracts.indent')} onClick={() => indent(i)} disabled={!canIndent(levels, i)} className={iconBtn}>→</button>
                  <button type="button" title={t('admin.contracts.moveUp')} onClick={() => move(i, -1)} disabled={i === 0} className={iconBtn}>↑</button>
                  <button type="button" title={t('admin.contracts.moveDown')} onClick={() => move(i, 1)} disabled={i === clauses.length - 1} className={iconBtn}>↓</button>
                  <button type="button" title={t('admin.contracts.remove')} onClick={() => remove(i)}
                    className="w-7 h-7 inline-flex items-center justify-center rounded-md border border-transparent text-gray-400 hover:bg-red-50 hover:text-red-600">🗑</button>
                </div>
              )}
            </div>
            <input className={inputCls} disabled={!draft} placeholder={t('admin.contracts.heading')}
              value={String(c[hk] || '')} onChange={(e) => set(i, hk, e.target.value)} />
            <textarea rows={3} className={inputCls} disabled={!draft} placeholder={t('admin.contracts.body')}
              value={String(c[bk] || '')} onChange={(e) => set(i, bk, e.target.value)} />
            {level === 0 ? (
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" disabled={!draft} checked={!!c.is_quiz_candidate}
                  onChange={(e) => set(i, 'is_quiz_candidate', e.target.checked)} />
                {t('admin.contracts.useForQuiz')}
              </label>
            ) : (
              <p className="text-xs text-gray-400">{t('admin.contracts.subclauseQuizNote')}</p>
            )}
          </div>
        )
      })}
      {clauses.length === 0 && <p className="text-sm text-gray-400">{t('admin.contracts.noClauses')}</p>}

      {draft && (
        <div className="flex gap-3">
          <button type="button" onClick={add} className={btnGhost}>
            {t('admin.contracts.addClause')}</button>
          <button type="button" onClick={() => persist(clauses)} disabled={saving} className={btnPrimary}>
            {saving ? t('admin.contracts.saving') : t('admin.contracts.saveClauses')}</button>
        </div>
      )}
      {!draft && <p className="text-sm text-gray-500">{t('admin.contracts.notDraftMsg')}</p>}
    </div>
  )
}
