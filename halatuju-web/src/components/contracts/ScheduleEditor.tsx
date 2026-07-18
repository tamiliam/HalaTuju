'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { putContractSchedule, type ContractTemplateDetail, type ContractScheduleRowData } from '@/lib/admin-api'
import { btnPrimary } from './shared'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const CELLS = 18   // offsets 0..17 — covers the 17-month STPM span (Jul→Nov across two years)

// The Schedule tab — real BrightPath data (RM200, per-pathway start months, a two-academic-year
// month grid → paid_offsets), each row's total live-checked against the award amount. The backend
// re-validates S3/S4 on deploy.
function expectedTotal(pathway: string, variant: string): number {
  if (pathway === 'stpm') return variant === 'continuing' ? 1000 : 3000
  return 2000
}

export default function ScheduleEditor(
  { template, token, onChange }: {
    template: ContractTemplateDetail; token: string
    onChange: (t: ContractTemplateDetail) => void
  }) {
  const { t } = useT()
  const draft = template.status === 'draft'
  const [rows, setRows] = useState<ContractScheduleRowData[]>(template.schedule.map((r) => ({ ...r })))
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const setRow = (i: number, patch: Partial<ContractScheduleRowData>) =>
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  const toggle = (i: number, offset: number) => {
    if (!draft) return
    const r = rows[i]
    const set = new Set(r.paid_offsets)
    if (set.has(offset)) set.delete(offset); else set.add(offset)
    setRow(i, { paid_offsets: Array.from(set).sort((a, b) => a - b) })
  }

  const save = async () => {
    setSaving(true); setErr(null); setMsg(null)
    try {
      const updated = await putContractSchedule(template.id, rows, { token })
      onChange(updated); setRows(updated.schedule.map((r) => ({ ...r }))); setMsg(t('admin.contracts.saved'))
    } catch (e) {
      setErr((e as Error)?.message || t('admin.contracts.actionFailed'))
    }
    setSaving(false)
  }

  return (
    <div className="space-y-5">
      {err && <div className="rounded-lg p-3 bg-red-50 border border-red-200 text-red-600 text-sm">{err}</div>}
      {msg && <div className="rounded-lg p-3 bg-green-50 border border-green-200 text-green-700 text-sm">{msg}</div>}

      <div className="space-y-4">
        {rows.map((r, i) => {
          const monthly = Number(r.monthly_amount) || 0
          const total = r.paid_offsets.length * monthly
          const expected = expectedTotal(r.pathway, r.variant)
          const ok = total === expected
          return (
            <div key={`${r.pathway}-${r.variant}`} className="bg-white rounded-xl border p-4">
              <div className="flex flex-wrap items-center gap-3 mb-3">
                <span className="font-semibold text-gray-900">{r.label_en || r.pathway}</span>
                {r.variant && <span className="text-xs text-gray-400">({r.variant})</span>}
                <label className="text-xs text-gray-500 flex items-center gap-1 ml-auto">
                  {t('admin.contracts.schedMonthly')}
                  <input type="number" disabled={!draft} value={monthly}
                    onChange={(e) => setRow(i, { monthly_amount: e.target.value })}
                    className="w-20 px-2 py-1 border rounded text-sm disabled:bg-gray-50" />
                </label>
                <label className="text-xs text-gray-500 flex items-center gap-1">
                  {t('admin.contracts.schedStart')}
                  <input type="number" min={1} max={12} disabled={!draft} value={r.start_month}
                    onChange={(e) => setRow(i, { start_month: Number(e.target.value) })}
                    className="w-14 px-2 py-1 border rounded text-sm disabled:bg-gray-50" />
                </label>
              </div>

              <div className="flex flex-wrap gap-1">
                {Array.from({ length: CELLS }, (_, off) => {
                  const paid = r.paid_offsets.includes(off)
                  const abs = (r.start_month - 1) + off
                  const month = MONTHS[abs % 12]
                  const year2 = abs >= 12
                  return (
                    <button key={off} type="button" onClick={() => toggle(i, off)} disabled={!draft}
                      title={`${month}${year2 ? ' (Y2)' : ''}`}
                      className={`w-10 h-9 rounded text-[10px] font-medium border ${
                        paid ? 'bg-green-100 border-green-400 text-green-800'
                             : 'bg-gray-50 border-gray-200 text-gray-400'} ${year2 ? 'ring-1 ring-inset ring-blue-100' : ''}`}>
                      {month}
                    </button>
                  )
                })}
              </div>

              <div className="mt-3 text-sm flex items-center gap-2">
                <span className="text-gray-500">{t('admin.contracts.schedMonths')}: {r.paid_offsets.length}</span>
                <span className="text-gray-500">· {t('admin.contracts.schedTotal')}: RM{total}</span>
                {ok
                  ? <span className="text-green-700">✓ {t('admin.contracts.schedMatches')} (RM{expected})</span>
                  : <span className="text-red-600">✗ {t('admin.contracts.schedMismatch')} (RM{expected})</span>}
              </div>
            </div>
          )
        })}
      </div>

      {draft
        ? <button type="button" onClick={save} disabled={saving} className={btnPrimary}>
            {saving ? t('admin.contracts.saving') : t('admin.contracts.save')}</button>
        : <p className="text-sm text-gray-500">{t('admin.contracts.notDraftMsg')}</p>}
    </div>
  )
}
