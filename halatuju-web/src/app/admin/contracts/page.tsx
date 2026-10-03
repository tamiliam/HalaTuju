'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { useProgrammeScope } from '@/lib/programmeScopeCore'
import {
  getContractTemplates, createContractTemplate, importContractDocx, putContractClauses,
  updateContractConfig,
  type ContractTemplateSummary, type ContractStatus,
} from '@/lib/admin-api'

// Contract templates list — a PROGRAMME-scope row since TD-229 (2026-10-03): the owner ruled on
// 2026-09-04 that the agreement is written PER GIFT, so the breadcrumb's gift says whose
// templates these are. super + org_admin only. New-version supports Start-blank, Upload or
// Copy-from a version IN THIS LIST — once a gift is chosen that is the gift's own versions only
// (a copy is a new, unvetted draft). Copying a schedule across gifts is ScheduleEditor's.
//
// ⚠ THE GIFT COMES FROM THE BREADCRUMB AND NOWHERE ELSE — the page has no picker of its own (the
// TD-241 rule for Payments: two controls answering "which gift" is two chances to write for the
// wrong one). It travels as `?programme=<code>`, which the server re-resolves INSIDE the caller's
// own organisation; with no gift chosen the list shows every gift's templates, each labelled,
// and New version waits for a gift rather than letting the server guess.

const STATUS_TONE: Record<ContractStatus, string> = {
  draft: 'bg-ground-100 text-ground-600',
  pending_deployment: 'bg-caution-100 text-caution-700',
  active: 'bg-positive-100 text-positive-700',
  archived: 'bg-ground-100 text-ground-500',
}

const inputCls = 'w-full px-3 py-2 border border-ground-300 rounded-lg focus:ring-2 focus:ring-info-500 focus:border-info-500'

export default function ContractsListPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()

  const allowed = canAccess('/admin/contracts', effectiveRole(role))

  const [templates, setTemplates] = useState<ContractTemplateSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [version, setVersion] = useState('')
  // Source: '' = start blank · 'upload' = populate from a .docx · a numeric id = copy that version.
  const [source, setSource] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The gift in the breadcrumb ('' = none chosen: several gifts, or not yet known).
  const { chosen: gift, programme: giftChoice } = useProgrammeScope()

  const load = () => {
    if (!token) return
    // ⚠ A REPLY FOR THE GIFT YOU LEFT IS DROPPED (the TD-298 shape): switching gift starts a new
    // read without cancelling the old, and the slower answer must not overwrite the newer.
    let current = true
    setLoading(true)
    getContractTemplates(gift || undefined, { token })
      .then((d) => { if (current) setTemplates(d.templates) })
      .catch(() => { if (current) setError(t('admin.contracts.actionFailed')) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }
  // `gift` IS A DEPENDENCY — switching gift in the breadcrumb must re-read the list.
  useEffect(load, [token, gift])   // eslint-disable-line react-hooks/exhaustive-deps

  if (role && !allowed) {
    return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const submitNew = async (e: React.FormEvent) => {
    e.preventDefault(); setError(null)
    if (source === 'upload' && !file) { setError(t('admin.contracts.uploadNeedsFile')); return }
    if (!gift) { setError(t('admin.contracts.error.programmeRequired')); return }
    setCreating(true)
    try {
      const body: Parameters<typeof createContractTemplate>[0] = { version: version.trim(), programme: gift }
      if (source && source !== 'upload') body.copy_from = Number(source)
      const created = await createContractTemplate(body, { token: token! })
      // Upload path: populate the new draft's clauses from the document (levels detected), then
      // land on the editor — that IS the review; nothing is live until vetting + deploy. A parse
      // failure still leaves a usable blank draft (the author imports/edits in the editor).
      if (source === 'upload' && file) {
        try {
          const { clauses, title, preamble, counterparty } = await importContractDocx(created.id, file, { token: token! })
          await putContractClauses(created.id, clauses.map((c) => ({
            level: c.level, heading_en: c.heading, body_en: c.body,
          })), { token: token! })
          // A brand-new draft is blank, so fill title/preamble + the counterparty party fields.
          const patch: Record<string, unknown> = {}
          if (title) patch.title_en = title
          if (preamble) patch.preamble_en = preamble
          if (counterparty?.name) patch.counterparty_name = counterparty.name
          if (counterparty?.nric) patch.counterparty_nric = counterparty.nric
          if (counterparty?.address) patch.counterparty_address = counterparty.address
          if (Object.keys(patch).length) await updateContractConfig(created.id, patch, { token: token! })
        } catch { /* soft-fail — blank draft created; author can import/hand-edit */ }
      }
      router.push(`/admin/contracts/${created.id}`)
    } catch (err) {
      // Map a known backend error code to friendly copy; fall back to the raw message.
      const code = (err as Error)?.message || ''
      const friendly: Record<string, string> = {
        version_too_long: t('admin.contracts.error.versionTooLong'),
        version_exists: t('admin.contracts.error.versionExists'),
        version_required: t('admin.contracts.error.versionRequired'),
        programme_required: t('admin.contracts.error.programmeRequired'),
      }
      setError(friendly[code] || code || t('admin.contracts.actionFailed'))
      setCreating(false)
    }
  }

  return (
    <div className="font-plex">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-ground-900">{t('admin.contracts.title')}</h1>
          <p className="text-sm text-ground-500 mt-1">{t('admin.contracts.subtitle')}</p>
        </div>
        <button type="button" onClick={() => setShowNew((s) => !s)}
          className="shrink-0 px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg font-medium hover:bg-brand-fill-hover">
          {t('admin.contracts.newVersion')}
        </button>
      </div>

      {error && <div className="rounded-lg p-3 my-4 bg-critical-50 border border-critical-200 text-critical-600 text-sm">{error}</div>}

      {showNew && (
        <form onSubmit={submitNew} className="mt-4 mb-6 bg-ground-0 rounded-xl border shadow-sm p-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <input className={inputCls} placeholder={t('admin.contracts.versionPlaceholder')}
              value={version} onChange={(e) => setVersion(e.target.value)} required maxLength={50} />
            <select className={inputCls} value={source}
              onChange={(e) => { setSource(e.target.value); if (e.target.value !== 'upload') setFile(null) }}>
              <option value="">{t('admin.contracts.startBlank')}</option>
              <option value="upload">{t('admin.contracts.uploadDoc')}</option>
              {templates.map((tm) => (
                <option key={tm.id} value={String(tm.id)}>{t('admin.contracts.copyFrom')} {tm.version}</option>
              ))}
            </select>
            {/* The gift this version is written for — the breadcrumb's, shown fixed. A super's
                organisation follows from the gift on the server. */}
            <input className={`${inputCls} bg-ground-50 text-ground-500`} disabled data-testid="contract-gift"
              value={giftChoice?.name || t('admin.contracts.error.programmeRequired')}
              title={t('admin.contracts.colGift')} />
          </div>
          {source === 'upload' && (
            <div className="rounded-lg border border-dashed border-ground-300 bg-ground-50 p-3">
              <input type="file" accept=".docx" className="text-sm text-ground-700"
                onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <p className="text-xs text-ground-400 mt-1">{t('admin.contracts.uploadDocHint')}</p>
            </div>
          )}
          <div className="flex gap-3">
            <button type="submit" disabled={creating}
              className="px-6 bg-brand-fill text-brand-fill-ink py-2.5 rounded-lg font-medium hover:bg-brand-fill-hover disabled:opacity-50">
              {creating ? t('admin.contracts.creating') : t('admin.contracts.create')}
            </button>
            <button type="button" onClick={() => setShowNew(false)}
              className="px-6 py-2.5 rounded-lg font-medium border border-ground-300 text-ground-700 hover:bg-ground-50">
              {t('admin.contracts.cancel')}
            </button>
          </div>
        </form>
      )}

      <TableFrame className="mt-4" minWidth={640} label={t('admin.contracts.title')}>
        <table className="w-full text-sm">
          <thead className="bg-ground-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.contracts.colVersion')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.contracts.colGift')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.contracts.colStatus')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.contracts.colLanguages')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.contracts.colVetted')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.contracts.colUpdated')}</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {templates.map((tm) => (
              <tr key={tm.id} className="hover:bg-info-50/40 cursor-pointer"
                onClick={() => router.push(`/admin/contracts/${tm.id}`)}>
                <td className="px-4 py-3 font-medium text-ground-900">{tm.version}</td>
                <td className="px-4 py-3 text-ground-600">
                  {tm.programme?.name ?? <span className="text-caution-700">{t('admin.contracts.noGift')}</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${STATUS_TONE[tm.status]}`}>
                    {t(`admin.contracts.status.${tm.status}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-ground-500 uppercase">{tm.languages_available.join(' · ')}</td>
                <td className="px-4 py-3 text-ground-500">{tm.vetted_by_name || '—'}</td>
                <td className="px-4 py-3 text-ground-500">{new Date(tm.updated_at).toLocaleDateString('en-GB')}</td>
              </tr>
            ))}
            {!loading && templates.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-ground-400">{t('admin.contracts.noTemplates')}</td></tr>
            )}
            {loading && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-ground-400">{t('admin.contracts.loading')}</td></tr>
            )}
          </tbody>
        </table>
      </TableFrame>
    </div>
  )
}
