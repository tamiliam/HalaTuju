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

  // The fields this form can change — ONE list, used both to build the save and to decide whether
  // there is anything to save (request #6). Two lists would drift, and the failure would be silent
  // in the worse direction: a field editable but not counted leaves Save dead on a real edit.
  const patchOf = (x: ContractTemplateDetail) => ({
    title_en: x.title_en, title_ms: x.title_ms, title_ta: x.title_ta,
    preamble_en: x.preamble_en, preamble_ms: x.preamble_ms, preamble_ta: x.preamble_ta,
    progress_standard_en: x.progress_standard_en, progress_standard_ms: x.progress_standard_ms,
    progress_standard_ta: x.progress_standard_ta,
    counterparty_name: x.counterparty_name, counterparty_title: x.counterparty_title,
    counterparty_nric: x.counterparty_nric, counterparty_address: x.counterparty_address,
    counterparty_notify_emails: x.counterparty_notify_emails,
    parent_role: x.parent_role, witness_policy: x.witness_policy,
  })

  const dirty = JSON.stringify(patchOf(f)) !== JSON.stringify(patchOf(template))

  const save = async () => {
    setSaving(true); setMsg(null); setErr(null)
    try {
      const patch = patchOf(f)
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
      <p className="text-xs text-info-700 bg-info-50 rounded-lg px-3 py-2">{t('admin.contracts.englishAuthoritative')}</p>
      {err && <div className="rounded-lg p-3 bg-critical-50 border border-critical-200 text-critical-600 text-sm">{err}</div>}
      {msg && <div className="rounded-lg p-3 bg-positive-50 border border-positive-200 text-positive-700 text-sm">{msg}</div>}

      <div className="flex justify-end"><LangTabs value={lang} onChange={setLang} /></div>

      <div className="bg-ground-0 rounded-xl border p-5 space-y-4">
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.titleLabel')}</span>
          <input className={inputCls} disabled={!draft} value={String(f[L('title')] || '')}
            onChange={(e) => set(L('title'), e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.preamble')}</span>
          <textarea rows={3} className={inputCls} disabled={!draft} value={String(f[L('preamble')] || '')}
            onChange={(e) => set(L('preamble'), e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.progressStandard')}</span>
          <textarea rows={2} className={inputCls} disabled={!draft} value={String(f[L('progress_standard')] || '')}
            onChange={(e) => set(L('progress_standard'), e.target.value)} />
        </label>
      </div>

      <div className="bg-ground-0 rounded-xl border p-5 grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.counterpartyName')}</span>
          <input className={inputCls} disabled={!draft} value={f.counterparty_name}
            onChange={(e) => set('counterparty_name', e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.counterpartyTitle')}</span>
          <input className={inputCls} disabled={!draft} value={f.counterparty_title}
            onChange={(e) => set('counterparty_title', e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.counterpartyNric')}</span>
          <input className={inputCls} disabled={!draft} value={f.counterparty_nric}
            onChange={(e) => set('counterparty_nric', e.target.value)} />
        </label>
        <label className="block sm:col-span-2">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.counterpartyAddress')}</span>
          <textarea rows={2} className={inputCls} disabled={!draft} value={f.counterparty_address || ''}
            onChange={(e) => set('counterparty_address', e.target.value)} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.notifyEmails')}</span>
          <input className={inputCls} disabled={!draft}
            value={(f.counterparty_notify_emails || []).join(', ')}
            onChange={(e) => set('counterparty_notify_emails',
              e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.parentRole')}</span>
          <select className={inputCls} disabled={!draft} value={f.parent_role}
            onChange={(e) => set('parent_role', e.target.value)}>
            <option value="co_signer_all">{t('admin.contracts.coSignerAll')}</option>
            <option value="minor_only">{t('admin.contracts.minorOnly')}</option>
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ground-600">{t('admin.contracts.witnessPolicy')}</span>
          <select className={inputCls} disabled={!draft} value={f.witness_policy}
            onChange={(e) => set('witness_policy', e.target.value)}>
            <option value="none">{t('admin.contracts.witness.none')}</option>
            <option value="optional">{t('admin.contracts.witness.optional')}</option>
            <option value="required">{t('admin.contracts.witness.required')}</option>
          </select>
        </label>
      </div>

      {draft
        ? <button type="button" onClick={save} disabled={saving || !dirty}
            title={dirty ? undefined : t('common.nothingToSave')} className={btnPrimary}>
            {saving ? t('admin.contracts.saving') : t('admin.contracts.save')}</button>
        : <p className="text-sm text-ground-500">{t('admin.contracts.notDraftMsg')}</p>}
    </div>
  )
}
