'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import {
  getContractTemplates, createContractTemplate, importContractDocx, putContractClauses,
  type ContractTemplateSummary, type ContractStatus,
} from '@/lib/admin-api'

// Contract templates list — reached from the Contracts card in Administration → Organisation
// (no top-level nav entry; the layout keeps "Administration" active). super + org_admin only.
// New-version supports Start-blank or Copy-from an existing version.

const STATUS_TONE: Record<ContractStatus, string> = {
  draft: 'bg-gray-100 text-gray-600',
  pending_deployment: 'bg-amber-100 text-amber-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-slate-100 text-slate-500',
}

const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

export default function ContractsListPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()

  const isSuper = !!(role?.is_super_admin || role?.role === 'super')
  const isOrgAdmin = role?.role === 'org_admin'
  const allowed = isSuper || isOrgAdmin

  const [templates, setTemplates] = useState<ContractTemplateSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [version, setVersion] = useState('')
  // Source: '' = start blank · 'upload' = populate from a .docx · a numeric id = copy that version.
  const [source, setSource] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [org, setOrg] = useState('')   // super only (org_admin uses own org)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    if (!token) return
    setLoading(true)
    getContractTemplates(undefined, { token })
      .then((d) => setTemplates(d.templates))
      .catch(() => setError(t('admin.contracts.actionFailed')))
      .finally(() => setLoading(false))
  }
  useEffect(load, [token])   // eslint-disable-line react-hooks/exhaustive-deps

  if (role && !allowed) {
    return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const submitNew = async (e: React.FormEvent) => {
    e.preventDefault(); setError(null)
    if (source === 'upload' && !file) { setError(t('admin.contracts.uploadNeedsFile')); return }
    setCreating(true)
    try {
      const body: Parameters<typeof createContractTemplate>[0] = { version: version.trim() }
      if (source && source !== 'upload') body.copy_from = Number(source)
      if (isSuper && org.trim()) body.organisation = org.trim()
      const created = await createContractTemplate(body, { token: token! })
      // Upload path: populate the new draft's clauses from the document (levels detected), then
      // land on the editor — that IS the review; nothing is live until vetting + deploy. A parse
      // failure still leaves a usable blank draft (the author imports/edits in the editor).
      if (source === 'upload' && file) {
        try {
          const { clauses } = await importContractDocx(created.id, file, { token: token! })
          await putContractClauses(created.id, clauses.map((c) => ({
            level: c.level, heading_en: c.heading, body_en: c.body,
          })), { token: token! })
        } catch { /* soft-fail — blank draft created; author can import/hand-edit */ }
      }
      router.push(`/admin/contracts/${created.id}`)
    } catch (err) {
      setError((err as Error)?.message || t('admin.contracts.actionFailed'))
      setCreating(false)
    }
  }

  return (
    <div className="max-w-5xl font-plex">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('admin.contracts.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('admin.contracts.subtitle')}</p>
        </div>
        <button type="button" onClick={() => setShowNew((s) => !s)}
          className="shrink-0 px-4 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700">
          {t('admin.contracts.newVersion')}
        </button>
      </div>

      {error && <div className="rounded-lg p-3 my-4 bg-red-50 border border-red-200 text-red-600 text-sm">{error}</div>}

      {showNew && (
        <form onSubmit={submitNew} className="mt-4 mb-6 bg-white rounded-xl border shadow-sm p-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <input className={inputCls} placeholder={t('admin.contracts.versionPlaceholder')}
              value={version} onChange={(e) => setVersion(e.target.value)} required />
            <select className={inputCls} value={source}
              onChange={(e) => { setSource(e.target.value); if (e.target.value !== 'upload') setFile(null) }}>
              <option value="">{t('admin.contracts.startBlank')}</option>
              <option value="upload">{t('admin.contracts.uploadDoc')}</option>
              {templates.map((tm) => (
                <option key={tm.id} value={String(tm.id)}>{t('admin.contracts.copyFrom')} {tm.version}</option>
              ))}
            </select>
            {isSuper && (
              <input className={inputCls} placeholder="Organisation code"
                value={org} onChange={(e) => setOrg(e.target.value)} />
            )}
          </div>
          {source === 'upload' && (
            <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3">
              <input type="file" accept=".docx" className="text-sm text-gray-700"
                onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <p className="text-xs text-gray-400 mt-1">{t('admin.contracts.uploadDocHint')}</p>
            </div>
          )}
          <div className="flex gap-3">
            <button type="submit" disabled={creating}
              className="px-6 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">
              {creating ? t('admin.contracts.creating') : t('admin.contracts.create')}
            </button>
            <button type="button" onClick={() => setShowNew(false)}
              className="px-6 py-2.5 rounded-lg font-medium border border-gray-300 text-gray-700 hover:bg-gray-50">
              {t('admin.contracts.cancel')}
            </button>
          </div>
        </form>
      )}

      <div className="bg-white rounded-lg shadow-sm border overflow-x-auto mt-4">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.contracts.colVersion')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.contracts.colStatus')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.contracts.colLanguages')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.contracts.colVetted')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.contracts.colUpdated')}</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {templates.map((tm) => (
              <tr key={tm.id} className="hover:bg-blue-50/40 cursor-pointer"
                onClick={() => router.push(`/admin/contracts/${tm.id}`)}>
                <td className="px-4 py-3 font-medium text-gray-900">{tm.version}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${STATUS_TONE[tm.status]}`}>
                    {t(`admin.contracts.status.${tm.status}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 uppercase">{tm.languages_available.join(' · ')}</td>
                <td className="px-4 py-3 text-gray-500">{tm.vetted_by_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{new Date(tm.updated_at).toLocaleDateString('en-GB')}</td>
              </tr>
            ))}
            {!loading && templates.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-gray-400">{t('admin.contracts.noTemplates')}</td></tr>
            )}
            {loading && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-gray-400">{t('admin.contracts.loading')}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
