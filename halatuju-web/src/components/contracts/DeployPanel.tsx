'use client'

import { useState, useEffect, useCallback } from 'react'
import { useT } from '@/lib/i18n'
import {
  getContractValidation, recordContractVetting, submitContractTemplate,
  revertContractTemplate, deployContractTemplate,
  type ContractTemplateDetail, type ContractValidation,
} from '@/lib/admin-api'
import { inputCls, btnPrimary, btnGhost } from './shared'

// The Deploy tab — validation checklist + legal attestation + the lifecycle actions.
// draft: record vetting → Submit for deployment (enabled when validation passes).
// pending_deployment: Deploy (SUPER only; org_admin sees only Revert) or Return to draft.
// active/archived: read-only.
export default function DeployPanel(
  { template, token, onChange, isSuper, reload }: {
    template: ContractTemplateDetail; token: string; isSuper: boolean
    onChange: (t: ContractTemplateDetail) => void; reload: () => Promise<void>
  }) {
  const { t } = useT()
  const [val, setVal] = useState<ContractValidation | null>(null)
  const [vName, setVName] = useState(template.vetted_by_name || '')
  const [vOn, setVOn] = useState(template.vetted_on || '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const loadVal = useCallback(async () => {
    try { setVal(await getContractValidation(template.id, { token })) } catch { /* non-fatal */ }
  }, [template.id, token])
  useEffect(() => { loadVal() }, [loadVal, template.status])

  const run = async (fn: () => Promise<ContractTemplateDetail>) => {
    setBusy(true); setErr(null)
    try { onChange(await fn()); await reload(); await loadVal() }
    catch (e) { setErr((e as Error)?.message || t('admin.contracts.actionFailed')) }
    setBusy(false)
  }

  const draft = template.status === 'draft'
  const pending = template.status === 'pending_deployment'
  const active = template.status === 'active'

  return (
    <div className="space-y-6">
      {err && <div className="rounded-lg p-3 bg-red-50 border border-red-200 text-red-600 text-sm">{err}</div>}

      {/* Validation checklist */}
      <div className="bg-white rounded-xl border p-5">
        <div className="font-semibold text-gray-900 mb-3">{t('admin.contracts.validationChecklist')}</div>
        {!val ? <p className="text-sm text-gray-400">{t('admin.contracts.loading')}</p>
          : val.ok ? <p className="text-sm text-green-700">✓ {t('admin.contracts.allChecksPass')}</p>
          : (
            <>
              <p className="text-sm text-red-600 mb-2">{t('admin.contracts.issuesFound', { n: String(val.errors.length) })}</p>
              <ul className="space-y-1">
                {val.errors.map((e) => (
                  <li key={e.code} className="text-sm text-gray-700 flex items-center gap-2">
                    <span className="text-red-500">✗</span>{e.label}
                  </li>
                ))}
              </ul>
            </>
          )}
        {val && val.warnings.length > 0 && (
          <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 p-3">
            <div className="text-xs font-semibold text-amber-800 mb-1">{t('admin.contracts.warningsTitle')}</div>
            <ul className="space-y-1">
              {val.warnings.map((w) => <li key={w.code} className="text-sm text-amber-800">• {w.label}</li>)}
            </ul>
          </div>
        )}
      </div>

      {/* Legal attestation — draft only */}
      {draft && (
        <div className="bg-white rounded-xl border p-5 space-y-3">
          <div className="font-semibold text-gray-900">{t('admin.contracts.attestation')}</div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs font-medium text-gray-600">{t('admin.contracts.vettedByName')}</span>
              <input className={inputCls} value={vName} onChange={(e) => setVName(e.target.value)} />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-gray-600">{t('admin.contracts.vettedOn')}</span>
              <input type="date" className={inputCls} value={vOn || ''} onChange={(e) => setVOn(e.target.value)} />
            </label>
          </div>
          <button type="button" disabled={busy || !vName || !vOn} className={btnGhost}
            onClick={() => run(() => recordContractVetting(template.id, { vetted_by_name: vName, vetted_on: vOn }, { token }))}>
            {t('admin.contracts.recordVetting')}
          </button>
        </div>
      )}

      {/* Lifecycle actions */}
      <div className="flex flex-wrap gap-3">
        {draft && (
          <button type="button" disabled={busy || !val?.ok} className={btnPrimary}
            onClick={() => run(() => submitContractTemplate(template.id, { token }))}>
            {t('admin.contracts.submitForDeployment')}
          </button>
        )}
        {pending && (
          <>
            {isSuper && (
              <button type="button" disabled={busy} className={btnPrimary}
                onClick={() => run(() => deployContractTemplate(template.id, { token }))}>
                {t('admin.contracts.deploy')}
              </button>
            )}
            <button type="button" disabled={busy} className={btnGhost}
              onClick={() => run(() => revertContractTemplate(template.id, { token }))}>
              {t('admin.contracts.revert')}
            </button>
          </>
        )}
      </div>

      {pending && (
        <p className="text-xs text-gray-500">
          {isSuper ? t('admin.contracts.deployArchives') : t('admin.contracts.superOnlyDeploy')}
        </p>
      )}
      {active && <p className="text-sm text-green-700">{t('admin.contracts.deployed')}</p>}
    </div>
  )
}
