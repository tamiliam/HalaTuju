'use client'

import { useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  putContractClauses, importContractDocx, updateContractConfig,
  type ContractTemplateDetail, type ContractClauseData,
} from '@/lib/admin-api'
import { clauseNumbers, normaliseLevels, canIndent, canOutdent } from '@/lib/clauseNumbering'
import { CLocale, LangTabs, inputCls, btnPrimary, btnGhost } from './shared'

// `_showH` / `_showB` are transient UI flags: force an empty heading/body box open (a field
// with content shows automatically). They ride on the draft object so they survive reorder/indent,
// and are stripped before save (never sent to the API).
type Draft = Partial<ContractClauseData> & { _showH?: boolean; _showB?: boolean }
const EMPTY: Draft = {
  level: 0, heading_en: '', heading_ms: '', heading_ta: '', body_en: '', body_ms: '', body_ta: '',
  is_quiz_candidate: false, quiz_en: {}, quiz_ms: {}, quiz_ta: {},
}

// Merge variables the "Insert variable" menu offers — mirrors contracts.CONTRACT_VARS on the
// backend (which does the actual substitution at render time). Tokens are language-neutral;
// the descriptions are author hints about the English-authoritative merge fields, so they are
// kept here in English rather than translated (the tokens fill in identically in every locale).
const VARIABLES: Array<{ token: string; desc: string }> = [
  { token: '{{student_name}}', desc: "The student's full name" },
  { token: '{{student_nric}}', desc: "The student's NRIC" },
  { token: '{{guarantor_name}}', desc: 'Parent / guardian name' },
  { token: '{{guarantor_relationship}}', desc: 'Guarantor relationship (e.g. father)' },
  { token: '{{donor_name}}', desc: 'Donor / sponsor name' },
  { token: '{{donor_nric}}', desc: 'Donor / counterparty NRIC' },
  { token: '{{donor_address}}', desc: 'Donor / counterparty address' },
  { token: '{{amount}}', desc: 'Bursary amount' },
  { token: '{{institution}}', desc: 'Institution name' },
  { token: '{{course}}', desc: 'Course / programme name' },
  { token: '{{commencement_date}}', desc: 'Course commencement date' },
  { token: '{{progress_standard}}', desc: 'Academic progress standard' },
]

// The Clauses tab — a 3-level hierarchy (clause 1. / sub 1.1 / sub-sub i)) with Indent/Outdent,
// move, insert-between, and the Word import. Numbers are COMPUTED from the level run
// (clauseNumbers) — never typed. Levels are kept normalised in state (no skipping) so what shows
// is what saves; only a top-level clause carries a comprehension quiz. A clause body supports
// **bold** and {{variable}} tokens (resolved in the rendered agreement). import-docx PROPOSES
// clauses + a title/preamble for review before they replace the draft (the file is never retained).
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
  const topRef = useRef<HTMLDivElement>(null)   // scroll target for the save banner
  // Word import
  const fileRef = useRef<HTMLInputElement>(null)
  const [importing, setImporting] = useState(false)
  const [proposed, setProposed] = useState<Array<{ heading: string; body: string; level: number }> | null>(null)
  const [proposedTitle, setProposedTitle] = useState('')
  const [proposedPreamble, setProposedPreamble] = useState('')
  const [proposedParty, setProposedParty] = useState<{ name?: string; nric?: string; address?: string }>({})
  // Body toolbar (bold / insert-variable) — operates on the focused clause's textarea.
  const bodyRefs = useRef<Record<number, HTMLTextAreaElement | null>>({})
  const [varMenu, setVarMenu] = useState<number | null>(null)

  const hk = `heading_${lang}` as keyof ContractClauseData
  const bk = `body_${lang}` as keyof ContractClauseData

  const levels = clauses.map((c) => c.level ?? 0)
  const numbers = clauseNumbers(levels)

  // Field edits don't touch structure.
  const set = (i: number, k: keyof ContractClauseData, v: unknown) =>
    setClauses((prev) => prev.map((c, j) => (j === i ? { ...c, [k]: v } : c)))

  // A heading/body box shows when it has content in ANY language, or was opened via its "+" chip.
  const hasHeading = (c: Draft) => !!(c.heading_en || c.heading_ms || c.heading_ta) || !!c._showH
  const hasBody = (c: Draft) => !!(c.body_en || c.body_ms || c.body_ta) || !!c._showB
  const showField = (i: number, key: '_showH' | '_showB') =>
    setClauses((prev) => prev.map((c, j) => (j === i ? { ...c, [key]: true } : c)))

  // Rewrite a body field then restore the caret (so bold/insert feel in-place).
  const editBody = (i: number, value: string, caret: number) => {
    set(i, bk, value)
    requestAnimationFrame(() => {
      const el = bodyRefs.current[i]
      if (el) { el.focus(); el.setSelectionRange(caret, caret) }
    })
  }

  // Wrap the current selection (or a placeholder) in **…**.
  const wrapBold = (i: number) => {
    const el = bodyRefs.current[i]
    const val = String(clauses[i][bk] || '')
    const s = el ? el.selectionStart : val.length
    const e = el ? el.selectionEnd : val.length
    const sel = val.slice(s, e) || 'bold text'
    editBody(i, `${val.slice(0, s)}**${sel}**${val.slice(e)}`, s + 2 + sel.length + 2)
  }

  // Drop a {{variable}} token at the cursor.
  const insertVar = (i: number, tokenText: string) => {
    const el = bodyRefs.current[i]
    const val = String(clauses[i][bk] || '')
    const pos = el ? el.selectionStart : val.length
    editBody(i, `${val.slice(0, pos)}${tokenText}${val.slice(pos)}`, pos + tokenText.length)
    setVarMenu(null)
  }

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
  // Insert a blank clause directly below clause i, at the SAME level (renumbers automatically).
  const insertAfter = (i: number) => setStructural([
    ...clauses.slice(0, i + 1), { ...EMPTY, level: clauses[i].level ?? 0 }, ...clauses.slice(i + 1),
  ])

  const persist = async (list: Draft[]) => {
    setSaving(true); setErr(null); setMsg(null)
    try {
      // Strip the transient UI flags before the save (they are not model fields).
      const clean = list.map(({ _showH, _showB, ...c }) => c)
      const updated = await putContractClauses(template.id, clean, { token })
      onChange(updated); setClauses(updated.clauses.map((c) => ({ ...c }))); setMsg(t('admin.contracts.saved'))
    } catch (e) {
      setErr((e as Error)?.message || t('admin.contracts.actionFailed'))
    }
    setSaving(false)
    // Scroll the "Saved" (or error) banner into view — the Save buttons sit far below the fold.
    requestAnimationFrame(() => topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  const onImport = async (file: File) => {
    setImporting(true); setErr(null); setProposed(null)
    try {
      const { clauses: got, title, preamble, counterparty } = await importContractDocx(template.id, file, { token })
      setProposed(got); setProposedTitle(title || ''); setProposedPreamble(preamble || '')
      setProposedParty(counterparty || {})
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
    // Fill BLANK title/preamble/party fields from the document — never overwrite the author's own.
    const patch: Record<string, unknown> = {}
    if (proposedTitle && !template.title_en) patch.title_en = proposedTitle
    if (proposedPreamble && !template.preamble_en) patch.preamble_en = proposedPreamble
    if (proposedParty.name && !template.counterparty_name) patch.counterparty_name = proposedParty.name
    if (proposedParty.nric && !template.counterparty_nric) patch.counterparty_nric = proposedParty.nric
    if (proposedParty.address && !template.counterparty_address) patch.counterparty_address = proposedParty.address
    if (Object.keys(patch).length) {
      try { onChange(await updateContractConfig(template.id, patch, { token })) } catch { /* clauses already saved */ }
    }
  }

  const iconBtn = 'w-7 h-7 inline-flex items-center justify-center rounded-md border border-gray-200 text-gray-500 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-30 disabled:hover:bg-transparent'
  const toolBtn = 'h-7 px-2 inline-flex items-center gap-1 rounded-md border border-gray-200 text-gray-600 hover:bg-blue-50 hover:text-blue-700 text-xs font-semibold'

  return (
    <div className="space-y-5">
      <div ref={topRef} className="scroll-mt-4" />
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
          {(proposedTitle || proposedPreamble) && (
            <div className="rounded-lg bg-white border border-blue-200 p-3 space-y-2 text-sm">
              {proposedTitle && (<div>
                <span className="text-[11px] uppercase tracking-wide font-semibold text-blue-700">{t('admin.contracts.importTitleLabel')}</span>
                <div className="text-gray-800">{proposedTitle}</div></div>)}
              {proposedPreamble && (<div>
                <span className="text-[11px] uppercase tracking-wide font-semibold text-blue-700">{t('admin.contracts.importPreambleLabel')}</span>
                <div className="text-gray-600 whitespace-pre-wrap">{proposedPreamble}</div></div>)}
              <p className="text-[11px] text-gray-400">{t('admin.contracts.importFillNote')}</p>
            </div>
          )}
          {(() => { const pn = clauseNumbers(proposed.map((c) => c.level ?? 0)); return (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {proposed.map((c, i) => {
                const top = (c.level ?? 0) === 0
                // Mirror the rendered document: number + heading + body inline; bold ONLY the
                // top level; no "—" placeholder when a clause legitimately has no heading.
                return (
                  <div key={i} className="text-sm" style={{ paddingLeft: `${(c.level ?? 0) * 22}px` }}>
                    <span className={`font-mono text-blue-700 mr-2 ${top ? 'font-semibold' : ''}`}>{pn[i]}</span>
                    {c.heading && <span className={top ? 'font-semibold' : ''}>{c.heading} </span>}
                    <span className="text-gray-600 whitespace-pre-wrap">{c.body}</span>
                  </div>
                )
              })}
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
            {/* Number sits to the LEFT of the boxes (1. [box]); only the fields in use are shown. */}
            <div className="flex gap-2">
              <span className="font-mono text-xs font-bold text-blue-700 tabular-nums shrink-0 w-12 text-right pt-2.5">{numbers[i]}</span>
              <div className="flex-1 min-w-0 space-y-2">
                {hasHeading(c) && (
                  <input className={inputCls} disabled={!draft} placeholder={t('admin.contracts.heading')}
                    value={String(c[hk] || '')} onChange={(e) => set(i, hk, e.target.value)} />
                )}
                {hasBody(c) && (
                  <textarea rows={3} className={inputCls} disabled={!draft} placeholder={t('admin.contracts.body')}
                    ref={(el) => { bodyRefs.current[i] = el }}
                    value={String(c[bk] || '')} onChange={(e) => set(i, bk, e.target.value)} />
                )}
                {!hasHeading(c) && !hasBody(c) && (
                  <p className="text-xs text-gray-300 py-2">{t('admin.contracts.emptyClauseHint')}</p>
                )}
              </div>
            </div>
            {/* Bottom row: quiz control (top-level only) on the left; field-adders, text tools and
                the clause controls on the bottom-right, split by a separator. */}
            <div className="flex items-center justify-between gap-2 pt-1">
              <div className="min-w-0">
                {level === 0 && (
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input type="checkbox" disabled={!draft} checked={!!c.is_quiz_candidate}
                      onChange={(e) => set(i, 'is_quiz_candidate', e.target.checked)} />
                    {t('admin.contracts.useForQuiz')}
                  </label>
                )}
              </div>
              {draft && (
                <div className="flex items-center gap-1 shrink-0">
                  {!hasHeading(c) && (
                    <button type="button" onClick={() => showField(i, '_showH')} className={toolBtn}>
                      ＋ {t('admin.contracts.heading')}</button>
                  )}
                  {hasBody(c) ? (
                    <>
                      <button type="button" title={t('admin.contracts.bold')} onClick={() => wrapBold(i)}
                        className={toolBtn}><span className="font-bold">B</span></button>
                      <div className="relative">
                        <button type="button" onClick={() => setVarMenu(varMenu === i ? null : i)} className={toolBtn}>
                          ＋ {t('admin.contracts.insertVariable')} <span className="text-[10px]">▾</span></button>
                        {varMenu === i && (
                          <div className="absolute z-10 bottom-9 right-0 w-80 max-h-56 overflow-auto rounded-lg border border-gray-300 bg-white shadow-xl p-1.5">
                            <div className="px-2 py-1 text-[11px] uppercase tracking-wide text-gray-400 font-semibold">{t('admin.contracts.variableMenuHint')}</div>
                            {VARIABLES.map((v) => (
                              <button key={v.token} type="button" onClick={() => insertVar(i, v.token)}
                                className="w-full flex items-center justify-between gap-3 px-2 py-1.5 rounded-md hover:bg-blue-50 text-left">
                                <code className="text-xs text-blue-800 bg-blue-50 border border-blue-200 rounded px-1.5 py-0.5 whitespace-nowrap">{v.token}</code>
                                <span className="text-[11px] text-gray-500 text-right">{v.desc}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <button type="button" onClick={() => showField(i, '_showB')} className={toolBtn}>
                      ＋ {t('admin.contracts.body')}</button>
                  )}
                  <span className="w-px h-5 bg-gray-200 mx-1" aria-hidden="true" />
                  <button type="button" title={t('admin.contracts.insertBelow')} onClick={() => insertAfter(i)}
                    className="w-7 h-7 inline-flex items-center justify-center rounded-md border border-emerald-200 text-emerald-600 bg-emerald-50 hover:bg-emerald-100 font-bold">＋</button>
                  <button type="button" title={t('admin.contracts.outdent')} onClick={() => outdent(i)} disabled={!canOutdent(levels, i)} className={iconBtn}>←</button>
                  <button type="button" title={t('admin.contracts.indent')} onClick={() => indent(i)} disabled={!canIndent(levels, i)} className={iconBtn}>→</button>
                  <button type="button" title={t('admin.contracts.moveUp')} onClick={() => move(i, -1)} disabled={i === 0} className={iconBtn}>↑</button>
                  <button type="button" title={t('admin.contracts.moveDown')} onClick={() => move(i, 1)} disabled={i === clauses.length - 1} className={iconBtn}>↓</button>
                  <button type="button" title={t('admin.contracts.remove')} onClick={() => remove(i)}
                    className="w-7 h-7 inline-flex items-center justify-center rounded-md border border-transparent text-gray-400 hover:bg-red-50 hover:text-red-600">🗑</button>
                </div>
              )}
            </div>
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
