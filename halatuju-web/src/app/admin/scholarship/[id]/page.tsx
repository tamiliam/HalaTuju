'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import {
  getScholarshipApplication,
  generateSponsorProfile,
  saveSponsorProfile,
  publishSponsorProfile,
  verifyAcceptApplication,
  setMentoringCandidate,
  addReferee,
  deleteReferee,
  type AdminScholarshipDetail,
  type AdminSponsorProfile,
} from '@/lib/admin-api'

const EMPTY_REFEREE = { name: '', role: '', relationship: '', phone: '', email: '' }

const VERIFY_ITEMS = ['nric', 'name', 'results', 'document'] as const

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-gray-400 uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-gray-800">{value === null || value === undefined || value === '' ? '—' : value}</dd>
    </div>
  )
}

export default function AdminScholarshipDetailPage() {
  const params = useParams()
  const id = Number(params?.id)
  const { token } = useAdminAuth()
  const { t } = useT()
  const [app, setApp] = useState<AdminScholarshipDetail | null>(null)
  const [profile, setProfile] = useState<AdminSponsorProfile | null>(null)
  const [markdown, setMarkdown] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [checklist, setChecklist] = useState<Record<string, boolean>>({})
  const [refForm, setRefForm] = useState({ ...EMPTY_REFEREE })

  useEffect(() => {
    if (!token || !id) return
    getScholarshipApplication(id, { token })
      .then((d) => {
        setApp(d)
        setProfile(d.sponsor_profile)
        setMarkdown(d.sponsor_profile?.current_markdown || '')
      })
      .catch(() => setError(t('admin.scholarship.loadFailed')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  const doGenerate = async () => {
    if (!token) return
    setBusy('gen'); setError('')
    try {
      const p = await generateSponsorProfile(id, { token })
      setProfile(p); setMarkdown(p.current_markdown || p.draft_markdown)
    } catch { setError(t('admin.scholarship.genError')) } finally { setBusy('') }
  }

  const doSave = async () => {
    if (!token) return
    setBusy('save'); setError('')
    try {
      const p = await saveSponsorProfile(id, { edited_markdown: markdown, status: 'approved' }, { token })
      setProfile(p)
    } catch { setError(t('admin.scholarship.saveError')) } finally { setBusy('') }
  }

  const doPublish = async () => {
    if (!token) return
    setBusy('pub'); setError('')
    try {
      const p = await publishSponsorProfile(id, { token })
      setProfile(p)
    } catch { setError(t('admin.scholarship.publishError')) } finally { setBusy('') }
  }

  const doVerifyAccept = async () => {
    if (!token) return
    setBusy('verify'); setError('')
    try {
      setApp(await verifyAcceptApplication(id, checklist, { token }))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.acceptError'))
    } finally { setBusy('') }
  }

  const toggleMentoring = async (value: boolean) => {
    if (!token) return
    setBusy('mentor'); setError('')
    try {
      setApp(await setMentoringCandidate(id, value, { token }))
    } catch { setError(t('admin.scholarship.mentorError')) } finally { setBusy('') }
  }

  const refreshApp = async () => {
    if (!token) return
    setApp(await getScholarshipApplication(id, { token }))
  }

  const doAddReferee = async () => {
    if (!token || !refForm.name.trim()) return
    setBusy('ref'); setError('')
    try {
      await addReferee(id, refForm, { token })
      setRefForm({ ...EMPTY_REFEREE })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  const doDeleteReferee = async (refId: number) => {
    if (!token) return
    setBusy('ref'); setError('')
    try {
      await deleteReferee(id, refId, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  if (error && !app) return <div className="text-red-600 mt-8">{error}</div>
  if (!app) return <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>

  return (
    <div className="space-y-6">
      <Link href="/admin/scholarship" className="text-sm text-blue-600 hover:underline">‹ {t('admin.scholarship.back')}</Link>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl sm:text-2xl font-bold">{app.name || '—'}</h1>
        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">{app.status}</span>
        {app.bucket && <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">Bucket {app.bucket}</span>}
      </div>

      {/* Applicant + intake */}
      <div className="bg-white rounded-xl border p-4">
        <h2 className="font-semibold mb-3">{t('admin.scholarship.applicant')}</h2>
        <dl className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Field label={t('admin.scholarship.school')} value={app.school} />
          <Field label={t('admin.scholarship.qualification')} value={app.qualification?.toUpperCase()} />
          <Field label="SPM A" value={app.spm_a_count} />
          <Field label="STPM PNGK" value={app.stpm_pngk} />
          <Field label={t('admin.scholarship.income')} value={app.household_income ? `RM${app.household_income}` : null} />
          <Field label="STR" value={app.receives_str ? 'Yes' : 'No'} />
          <Field label={t('admin.scholarship.pathway')} value={app.intended_pathway} />
        </dl>
        {app.shortlist_reason && <p className="text-xs text-amber-700 mt-3">{app.shortlist_reason}</p>}
      </div>

      {/* Deeper info + funding */}
      <div className="bg-white rounded-xl border p-4 space-y-2">
        <Field label={t('admin.scholarship.aspirations')} value={app.aspirations} />
        <Field label={t('admin.scholarship.justification')} value={app.justification} />
        {app.funding_need && <Field label={t('admin.scholarship.funding')} value={`RM${app.funding_need.total}`} />}
      </div>

      {/* Documents / referees / consent */}
      <div className="bg-white rounded-xl border p-4">
        <h3 className="font-semibold text-sm mb-2">{t('admin.scholarship.documents')} ({app.documents.length})</h3>
        <ul className="text-sm text-gray-600 space-y-1">
          {app.documents.map((d) => (
            <li key={d.id}>
              {d.doc_type}: {d.download_url
                ? <a href={d.download_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{d.original_filename || 'view'}</a>
                : (d.original_filename || '—')}{' '}
              <span className="text-gray-400">[{d.verification_status}]</span>
            </li>
          ))}
          {app.documents.length === 0 && <li className="text-gray-400">{t('admin.scholarship.none')}</li>}
        </ul>

        <h3 className="font-semibold text-sm mt-4 mb-1">{t('admin.scholarship.referees')}</h3>
        <p className="text-xs text-gray-400 mb-2">{t('admin.scholarship.refHint')}</p>
        <ul className="text-sm text-gray-600 space-y-1">
          {app.referees.map((r) => (
            <li key={r.id} className="flex items-start justify-between gap-2">
              <span>
                {r.name}{r.role ? ` (${r.role})` : ''}{r.relationship ? ` · ${r.relationship}` : ''}
                {r.phone ? ` — ${r.phone}` : ''}{r.email ? ` · ${r.email}` : ''}
              </span>
              <button onClick={() => doDeleteReferee(r.id)} disabled={!!busy}
                className="text-red-500 hover:underline text-xs shrink-0 disabled:opacity-50">
                {t('admin.scholarship.refRemove')}
              </button>
            </li>
          ))}
          {app.referees.length === 0 && <li className="text-gray-400">{t('admin.scholarship.none')}</li>}
        </ul>
        {/* Add referee (coordinator records it at verify-&-accept) */}
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input value={refForm.name} onChange={(e) => setRefForm((f) => ({ ...f, name: e.target.value }))}
            placeholder={t('admin.scholarship.refName')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.role} onChange={(e) => setRefForm((f) => ({ ...f, role: e.target.value }))}
            placeholder={t('admin.scholarship.refRole')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.relationship} onChange={(e) => setRefForm((f) => ({ ...f, relationship: e.target.value }))}
            placeholder={t('admin.scholarship.refRelationship')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.phone} onChange={(e) => setRefForm((f) => ({ ...f, phone: e.target.value }))}
            placeholder={t('admin.scholarship.refPhone')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.email} onChange={(e) => setRefForm((f) => ({ ...f, email: e.target.value }))}
            placeholder={t('admin.scholarship.refEmail')} className="border rounded-lg px-2 py-1 text-sm sm:col-span-2" />
        </div>
        <button onClick={doAddReferee} disabled={!!busy || !refForm.name.trim()}
          className="mt-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
          {busy === 'ref' ? t('admin.scholarship.refAdding') : t('admin.scholarship.refAdd')}
        </button>

        <h3 className="font-semibold text-sm mt-4 mb-2">{t('admin.scholarship.consent')}</h3>
        <p className="text-sm text-gray-600">
          {app.consents.some((c) => c.is_active) ? t('admin.scholarship.consentGiven') : t('admin.scholarship.consentNone')}
        </p>
      </div>

      {/* Verify & accept (human gate — locks the NRIC, advances → accepted) */}
      <div className="bg-white rounded-xl border p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{t('admin.scholarship.verifyTitle')}</h2>
          {app.nric_verified && (
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
              {t('admin.scholarship.nricLocked')}
            </span>
          )}
        </div>

        {app.status === 'accepted' ? (
          <p className="text-sm text-gray-600">
            {t('admin.scholarship.acceptedBy')} {app.verified_by || '—'}
            {app.verified_at ? ` · ${new Date(app.verified_at).toLocaleDateString()}` : ''}
          </p>
        ) : app.status === 'shortlisted' ? (
          <>
            <p className="text-sm text-gray-500">{t('admin.scholarship.verifyHint')}</p>
            <div className="space-y-2">
              {VERIFY_ITEMS.map((key) => (
                <label key={key} className="flex items-start gap-2 text-sm text-gray-700">
                  <input type="checkbox" className="mt-1" checked={!!checklist[key]}
                    onChange={(e) => setChecklist((c) => ({ ...c, [key]: e.target.checked }))} />
                  <span>
                    {t(`admin.scholarship.check_${key}`)}
                    {key === 'nric' && <span className="ml-1 font-mono text-gray-500">{app.nric || '—'}</span>}
                    {key === 'name' && <span className="ml-1 text-gray-500">{app.name || '—'}</span>}
                  </span>
                </label>
              ))}
            </div>
            <button onClick={doVerifyAccept}
              disabled={!!busy || !VERIFY_ITEMS.every((k) => checklist[k])}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50">
              {busy === 'verify' ? t('admin.scholarship.accepting') : t('admin.scholarship.verifyAccept')}
            </button>
          </>
        ) : (
          <p className="text-sm text-gray-400">{t('admin.scholarship.notShortlisted')}</p>
        )}

        <label className="mt-2 flex items-center gap-2 border-t pt-3 text-sm text-gray-700">
          <input type="checkbox" checked={app.mentoring_candidate} disabled={!!busy}
            onChange={(e) => toggleMentoring(e.target.checked)} />
          {t('admin.scholarship.mentoring')}
        </label>
      </div>

      {/* AI sponsor profile */}
      <div className="bg-white rounded-xl border p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{t('admin.scholarship.profileTitle')}</h2>
          {profile && <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">{profile.status}</span>}
        </div>

        {!profile ? (
          <button onClick={doGenerate} disabled={busy === 'gen'} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
            {busy === 'gen' ? t('admin.scholarship.generating') : t('admin.scholarship.generate')}
          </button>
        ) : (
          <>
            <textarea
              value={markdown} onChange={(e) => setMarkdown(e.target.value)} rows={14}
              className="w-full border rounded-lg p-3 font-mono text-sm"
            />
            <p className="text-xs text-gray-400">{t('admin.scholarship.model')}: {profile.model_used || '—'}</p>
            <div className="flex flex-wrap gap-2">
              <button onClick={doGenerate} disabled={!!busy} className="px-3 py-2 border rounded-lg text-sm disabled:opacity-50">
                {busy === 'gen' ? t('admin.scholarship.generating') : t('admin.scholarship.regenerate')}
              </button>
              <button onClick={doSave} disabled={!!busy} className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
                {busy === 'save' ? t('admin.scholarship.saving') : t('admin.scholarship.save')}
              </button>
              <button onClick={doPublish} disabled={!!busy} className="px-3 py-2 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50">
                {busy === 'pub' ? t('admin.scholarship.publishing') : t('admin.scholarship.publish')}
              </button>
            </div>
          </>
        )}
        {error && <p className="text-red-600 text-sm">{error}</p>}
      </div>
    </div>
  )
}
