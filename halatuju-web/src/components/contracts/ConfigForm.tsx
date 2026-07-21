'use client'

import { useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import { updateContractConfig, type ContractTemplateDetail } from '@/lib/admin-api'
import { CLocale, LangTabs, inputCls, btnPrimary } from './shared'

// The Config tab — localised title/preamble/progress (en authoritative) + party/flow config.
// Draft-only: inputs disable once the version leaves draft (the service also refuses).
export default function ConfigForm(
  { template, token, onChange }: {
    template: ContractTemplateDetail; token: string
    onChange: (t: ContractTemplateDetail) => void
  }) {
  const { t } = useT()
  const draft = template.status === 'draft'
  const [lang, setLang] = useState<CLocale>('en')
  const [f, setF] = useState({ ...template })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const topRef = useRef<HTMLDivElement>(null)

  const set = (k: keyof ContractTemplateDetail, v: unknown) => setF((prev) => ({ ...prev, [k]: v }))
  const L = (base: string) => `${base}_${lang}` as keyof ContractTemplateDetail

  const save = async () => {
    setSaving(true); setMsg(null); setErr(null)
    try {
      const patch = {
        title_en: f.title_en, title_ms: f.title_ms, title_ta: f.title_ta,
        preamble_en: f.preamble_en, preamble_ms: f.preamble_ms, preamble_ta: f.preamble_ta,
        progress_standard_en: f.progress_standard_en, progress_standard_ms: f.progress_standard_ms,
        progress_standard_ta: f.progress_standard_ta,
        counterparty_name: f.counterparty_name, counterparty_title: f.counterparty_title,
        counterparty_nric: f.counterparty_nric, counterparty_address: f.counterparty_address,
        counterparty_notify_emails: f.counterparty_notify_emails,
        parent_role: f.parent_role, witness_policy: f.witness_policy,
      }
      const updated = await updateContractConfig(template.id, patch, { token })
      onChange(updated); setF({ ...updated }); setMsg(t('admin.contracts.saved'))
    } catch (e) {
      setErr((e as Error)?.message || t('admin.contracts.actionFailed'))
    }
    setSaving(false)
    requestAnimationFrame(() => topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  return (
    <div className="space-y-6">
      <div ref={topRef} className="scroll-mt-4" />
      <p className="text-xs text-blue-700 bg-blue-50 rounded-lg px-3 py-2">{t('admin.contracts.englishAuthoritative')}</p>
      {err && <div className="rounded-lg p-3 bg-red-50 border border-red-200 text-red-600 text-sm">{err}</div>}
      {msg && <div className="rounded-lg p-3 bg-green-50 border border-green-200 text-green-700 text-sm">{msg}</div>}

      <div className="flex justify-end"><LangTabs value={lang} onChange={setLang} /></div>

      <div className="bg-white rounded-xl border p-5 space-y-4">
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.titleLabel')}</span>
          <input className={inputCls} disabled={!draft} value={String(f[L('title')] || '')}
            onChange={(e) => set(L('title'), e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.preamble')}</span>
          <textarea rows={3} className={inputCls} disabled={!draft} value={String(f[L('preamble')] || '')}
            onChange={(e) => set(L('preamble'), e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.progressStandard')}</span>
          <textarea rows={2} className={inputCls} disabled={!draft} value={String(f[L('progress_standard')] || '')}
            onChange={(e) => set(L('progress_standard'), e.target.value)} />
        </label>
      </div>

      <div className="bg-white rounded-xl border p-5 grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.counterpartyName')}</span>
          <input className={inputCls} disabled={!draft} value={f.counterparty_name}
            onChange={(e) => set('counterparty_name', e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.counterpartyTitle')}</span>
          <input className={inputCls} disabled={!draft} value={f.counterparty_title}
            onChange={(e) => set('counterparty_title', e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.counterpartyNric')}</span>
          <input className={inputCls} disabled={!draft} value={f.counterparty_nric}
            onChange={(e) => set('counterparty_nric', e.target.value)} />
        </label>
        <label className="block sm:col-span-2">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.counterpartyAddress')}</span>
          <textarea rows={2} className={inputCls} disabled={!draft} value={f.counterparty_address || ''}
            onChange={(e) => set('counterparty_address', e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.notifyEmails')}</span>
          <input className={inputCls} disabled={!draft}
            value={(f.counterparty_notify_emails || []).join(', ')}
            onChange={(e) => set('counterparty_notify_emails',
              e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.parentRole')}</span>
          <select className={inputCls} disabled={!draft} value={f.parent_role}
            onChange={(e) => set('parent_role', e.target.value)}>
            <option value="co_signer_all">{t('admin.contracts.coSignerAll')}</option>
            <option value="minor_only">{t('admin.contracts.minorOnly')}</option>
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600">{t('admin.contracts.witnessPolicy')}</span>
          <select className={inputCls} disabled={!draft} value={f.witness_policy}
            onChange={(e) => set('witness_policy', e.target.value)}>
            <option value="none">{t('admin.contracts.witness.none')}</option>
            <option value="optional">{t('admin.contracts.witness.optional')}</option>
            <option value="required">{t('admin.contracts.witness.required')}</option>
          </select>
        </label>
      </div>

      {draft
        ? <button type="button" onClick={save} disabled={saving} className={btnPrimary}>
            {saving ? t('admin.contracts.saving') : t('admin.contracts.save')}</button>
        : <p className="text-sm text-gray-500">{t('admin.contracts.notDraftMsg')}</p>}
    </div>
  )
}
