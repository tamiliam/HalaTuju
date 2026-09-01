'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { inputCls } from '@/components/contracts/shared'
import { STATUS_TONE, termsErrorKey } from '@/lib/sponsorTerms'
import {
  createSponsorTerms, getSponsorTermsList, importSponsorTermsDocx, putSponsorTermsSections,
  updateSponsorTermsIntro,
  type SponsorTermsListPayload,
} from '@/lib/admin-api'

/**
 * The versions table, adopting the Contract Templates layout (owner, 2026-07-28).
 *
 * A row opens `/admin/sponsors/terms/<id>` — a nested route, so it resolves to the Sponsors nav
 * item by longest match and needs no registry entry, exactly as `/admin/contracts/9` does.
 *
 * The fifth column is **Published by**, not the contracts screen's "Vetted by": that column exists
 * because a lawyer signs off a contract template, and the owner decided against a lawyer pass for
 * the sponsor terms. A column that could only ever show an em-dash is worse than one that reports
 * who made a version binding.
 */
export default function SponsorTermsCard({ token, t }: {
  token: string | null
  t: (k: string, p?: Record<string, string>) => string
}) {
  const router = useRouter()
  const [data, setData] = useState<SponsorTermsListPayload | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [version, setVersion] = useState('')
  // '' = start blank · 'upload' = populate from a .docx · a numeric id = copy that version.
  const [source, setSource] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(() => {
    if (!token) return
    getSponsorTermsList({ token })
      .then(setData)
      .catch(() => setError(t('admin.sponsors.terms.loadError')))
  }, [token, t])

  useEffect(() => { load() }, [load])

  const submitNew = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setNotice('')
    if (source === 'upload' && !file) {
      setError(t('admin.sponsors.terms.uploadNeedsFile'))
      return
    }
    setBusy(true)
    try {
      const created = await createSponsorTerms({
        version: version.trim(),
        ...(source && source !== 'upload' ? { copy_from: Number(source) } : {}),
      }, { token: token! })

      if (source === 'upload' && file) {
        setNotice(t('admin.sponsors.terms.importing'))
        try {
          const proposal = await importSponsorTermsDocx(created.id, file, { token: token! })
          await putSponsorTermsSections(created.id, proposal.sections, { token: token! })
          const patch: Record<string, string> = {}
          if (proposal.title) patch.title_en = proposal.title
          if (proposal.intro) patch.intro_en = proposal.intro
          if (Object.keys(patch).length) {
            await updateSponsorTermsIntro(created.id, patch, { token: token! })
          }
        } catch {
          // Soft-fail, as the contract importer does: the draft exists and is usable, so land the
          // author in the editor to hand-write rather than losing the version they just named.
        }
      }
      router.push(`/admin/sponsors/terms/${created.id}`)
    } catch (err) {
      setError(t(termsErrorKey((err as { code?: string })?.code)))
      setBusy(false)
    }
  }

  if (!data) return <p className="text-sm text-ground-500 py-8 text-center">{t('common.loading')}</p>

  return (
    <div className="max-w-5xl">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <h2 className="text-xl font-bold text-ground-900">{t('admin.sponsors.terms.title')}</h2>
          <p className="text-sm text-ground-500 mt-1">{t('admin.sponsors.terms.subtitle')}</p>
        </div>
        <button type="button" onClick={() => setShowNew((s) => !s)}
          className="shrink-0 px-4 py-2.5 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700">
          {t('admin.sponsors.terms.newVersion')}
        </button>
      </div>

      {!data.active_version && (
        <div className="rounded-xl border border-caution-200 bg-caution-50 p-4 text-sm text-caution-900 mt-4">
          <p className="font-semibold">{t('admin.sponsors.terms.noneActiveTitle')}</p>
          <p className="mt-1">{t('admin.sponsors.terms.noneActiveBody')}</p>
        </div>
      )}

      {error && (
        <div className="rounded-lg p-3 my-4 bg-critical-50 border border-critical-200 text-critical-600 text-sm">
          {error}
        </div>
      )}
      {notice && <p className="text-sm text-ground-500 my-2">{notice}</p>}

      {showNew && (
        <form onSubmit={submitNew} className="mt-4 mb-6 bg-ground-0 rounded-xl border shadow-sm p-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <input className={inputCls} required maxLength={50} value={version}
              placeholder={t('admin.sponsors.terms.newVersionPh')}
              onChange={(e) => setVersion(e.target.value)} />
            <select className={inputCls} value={source}
              onChange={(e) => { setSource(e.target.value); if (e.target.value !== 'upload') setFile(null) }}>
              <option value="">{t('admin.sponsors.terms.startBlank')}</option>
              <option value="upload">{t('admin.sponsors.terms.uploadDoc')}</option>
              {data.versions.map((v) => (
                <option key={v.id} value={String(v.id)}>
                  {t('admin.sponsors.terms.copyFrom')} {v.version}
                </option>
              ))}
            </select>
          </div>
          {source === 'upload' && (
            <div className="rounded-lg border border-dashed border-ground-300 bg-ground-50 p-3">
              <input type="file" accept=".docx" className="text-sm text-ground-700"
                onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <p className="text-xs text-ground-500 mt-1">{t('admin.sponsors.terms.uploadHint')}</p>
            </div>
          )}
          <div className="flex gap-3">
            <button type="submit" disabled={busy || !version.trim()}
              className="px-6 py-2.5 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50">
              {busy ? t('admin.sponsors.terms.creating') : t('admin.sponsors.terms.create')}
            </button>
            <button type="button" onClick={() => setShowNew(false)}
              className="px-6 py-2.5 rounded-lg font-medium border border-ground-300 text-ground-700 hover:bg-ground-50">
              {t('admin.sponsors.terms.cancel')}
            </button>
          </div>
        </form>
      )}

      <div className="bg-ground-0 rounded-lg shadow-sm border overflow-x-auto mt-4">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-ground-50 border-b">
            <tr>
              {(['colVersion', 'colStatus', 'colLanguages', 'colPublishedBy', 'colUpdated'] as const)
                .map((c) => (
                  <th key={c} className="text-left px-4 py-3 font-medium text-ground-600">
                    {t(`admin.sponsors.terms.${c}`)}
                  </th>
                ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.versions.map((v) => (
              <tr key={v.id} className="hover:bg-info-50/40 cursor-pointer"
                onClick={() => router.push(`/admin/sponsors/terms/${v.id}`)}>
                <td className="px-4 py-3 font-medium text-ground-900">{v.version}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                    STATUS_TONE[v.status] || STATUS_TONE.archived}`}>
                    {t(`admin.sponsors.terms.status.${v.status}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-ground-500 uppercase">
                  {v.languages_available.join(' · ')}
                </td>
                <td className="px-4 py-3 text-ground-500">{v.published_by_email || '—'}</td>
                <td className="px-4 py-3 text-ground-500">
                  {new Date(v.updated_at).toLocaleDateString('en-GB')}
                </td>
              </tr>
            ))}
            {data.versions.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-ground-400">
                {t('admin.sponsors.terms.noVersions')}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
