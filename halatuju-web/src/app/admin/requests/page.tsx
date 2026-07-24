'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import {
  getOrgRequests, createOrgRequest, type OrgRequestDetail,
} from '@/lib/admin-api'
import {
  REQUEST_STATUSES, statusLabelKey, statusTone, kindLabelKey, hasUnansweredQuestions,
  REQUEST_COMPONENT_PARENTS, requestSubComponents, componentLabelKey,
} from '@/lib/requestStatus'

// The Requests-space landing: a rate-card panel (bugs free · the adjudication rule · features
// quoted in hours with the owner's approval), a submit form (org_admin), and the org's request
// list. Ships dark behind REQUESTS_ENABLED — a 404 from the API means the feature is off; the
// Administration hub card is hidden by the same probe, so a stray visit lands gracefully.

const errText = (t: (k: string) => string, code?: string) => {
  const known = ['bug_is_free', 'bad_hours', 'reason_required', 'triage_ai_unconfigured',
    'triage_ai_unavailable', 'ai_limit_reached']
  return code && known.includes(code) ? t(`admin.requests.error.${code}`) : t('admin.requests.error.generic')
}

// Optional urgency keys (mirror org_requests.VALID_URGENCIES). Components come from the
// two-level REQUEST_COMPONENT_TREE (parent surface → optional B40 sub-component).
const URGENCY_OPTIONS = ['blocking', 'important', 'nice_to_have']

export default function AdminRequestsPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const isSuper = !!(role?.is_super_admin || role?.role === 'super')
  const isOrgAdmin = role?.role === 'org_admin'

  const [requests, setRequests] = useState<OrgRequestDetail[]>([])
  const [statusF, setStatusF] = useState('')
  const [loading, setLoading] = useState(true)
  const [dark, setDark] = useState(false)
  const [error, setError] = useState('')

  // Submit form (org_admin)
  const [kind, setKind] = useState<'bug' | 'feature'>('bug')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  // Two-level component: `component` is the parent surface; `subComponent` is the optional
  // B40 sub-component VALUE (only when parent = applications). The stored value is the sub when
  // one is picked, else the parent (PathwayPicker's parent→child pattern; child cleared on change).
  const [component, setComponent] = useState('')
  const [subComponent, setSubComponent] = useState('')
  const [urgency, setUrgency] = useState('')
  const [steps, setSteps] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    getOrgRequests(statusF ? { status: statusF } : undefined, { token })
      .then((d) => { setRequests(d.requests); setDark(false) })
      .catch((e) => {
        // A 404 = the feature is dark (REQUESTS_ENABLED off) — show the coming-soon shell.
        if ((e as { status?: number })?.status === 404 || /404/.test(String(e))) setDark(true)
        else setError(t('admin.requests.error.generic'))
      })
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, statusF])

  useEffect(() => { load() }, [load])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setBusy(true); setError('')
    try {
      // The effective component: a chosen B40 sub-component wins over the bare parent.
      const effectiveComponent = component === 'applications' && subComponent ? subComponent : component
      await createOrgRequest({
        kind, title, description,
        component: effectiveComponent, urgency,
        // Steps only make sense for a bug — never send them for a feature.
        steps_to_reproduce: kind === 'bug' ? steps : '',
      }, { token })
      setTitle(''); setDescription(''); setKind('bug')
      setComponent(''); setSubComponent(''); setUrgency(''); setSteps('')
      load()
    } catch (err) {
      setError(errText(t, (err as { code?: string })?.code))
    } finally {
      setBusy(false)
    }
  }

  if (dark) {
    return <p className="text-gray-500">{t('admin.requests.list.empty')}</p>
  }

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900">{t('admin.requests.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-6">{t('admin.requests.subtitle')}</p>

      {/* Rate card */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-5 mb-6">
        <h2 className="font-semibold text-gray-900 mb-2">{t('admin.requests.rateCard.title')}</h2>
        <ul className="space-y-1.5 text-sm text-gray-700">
          {(['bugReports', 'bugDefinition', 'featureDefinition', 'quotations'] as const).map((item) => (
            <li key={item}>
              • <strong>{t(`admin.requests.rateCard.${item}Label`)}</strong>{' '}
              {t(`admin.requests.rateCard.${item}`)}
            </li>
          ))}
        </ul>
      </div>

      {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-600 p-3 mb-4">{error}</div>}

      {/* Submit form — org_admin only (the owner triages, never submits to itself) */}
      {isOrgAdmin && (
        <form onSubmit={submit} className="bg-white rounded-xl border shadow-sm p-6 space-y-4 mb-8">
          <h2 className="font-semibold text-gray-900">{t('admin.requests.form.title')}</h2>
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">{t('admin.requests.form.kind')}</p>
            <div className="flex gap-2">
              {(['bug', 'feature'] as const).map((k) => (
                <button key={k} type="button" onClick={() => setKind(k)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    kind === k ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>
                  {t(kindLabelKey(k))}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.form.titleLabel')}</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200}
              placeholder={t('admin.requests.form.titlePlaceholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.form.descriptionLabel')}</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} required rows={4}
              placeholder={t('admin.requests.form.descriptionPlaceholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.form.component')}</label>
              <select value={component}
                onChange={(e) => { setComponent(e.target.value); setSubComponent('') }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                <option value="">—</option>
                {REQUEST_COMPONENT_PARENTS.map((c) => <option key={c} value={c}>{t(componentLabelKey(c))}</option>)}
              </select>
              {/* B40 sub-component — only when the parent surface has children (applications). */}
              {requestSubComponents(component).length > 0 && (
                <select key={component} value={subComponent} onChange={(e) => setSubComponent(e.target.value)}
                  className="mt-2 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                  <option value="">{t('admin.requests.form.subComponentAll')}</option>
                  {requestSubComponents(component).map((c) => (
                    <option key={c} value={c}>{t(componentLabelKey(c))}</option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.form.urgency')}</label>
              <select value={urgency} onChange={(e) => setUrgency(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                <option value="">—</option>
                {URGENCY_OPTIONS.map((u) => <option key={u} value={u}>{t(`admin.requests.urgency.${u}`)}</option>)}
              </select>
            </div>
          </div>
          {/* Steps to reproduce — only meaningful for a bug. */}
          {kind === 'bug' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('admin.requests.form.stepsLabel')}</label>
              <textarea value={steps} onChange={(e) => setSteps(e.target.value)} rows={3}
                placeholder={t('admin.requests.form.stepsPlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
          )}
          <button type="submit" disabled={busy || !title.trim() || !description.trim()}
            className="px-6 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">
            {busy ? t('admin.requests.form.submitting') : t('admin.requests.form.submit')}
          </button>
        </form>
      )}

      {/* Filter + list */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select value={statusF} onChange={(e) => setStatusF(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.requests.list.filterAll')}</option>
          {REQUEST_STATUSES.map((s) => <option key={s} value={s}>{t(statusLabelKey(s))}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>
      ) : requests.length === 0 ? (
        <div className="text-center text-gray-500 mt-8">{t('admin.requests.list.empty')}</div>
      ) : (
        <div className="space-y-2">
          {requests.map((r) => {
            const needsAnswer = isOrgAdmin && hasUnansweredQuestions(r.clarifications)
            return (
              <Link key={r.id} href={`/admin/requests/${r.id}`}
                className="block bg-white rounded-xl border hover:border-blue-300 hover:bg-blue-50/40 transition-colors p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-gray-900 truncate">{r.title}</span>
                      <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">{t(kindLabelKey(r.kind))}</span>
                      {needsAnswer && (
                        <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">{t('admin.requests.list.answerNeeded')}</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {isSuper && r.organisation_name ? `${r.organisation_name} · ` : ''}
                      {t('admin.requests.list.submittedBy', { name: r.submitted_by_name })} · {formatDate(r.created_at)}
                    </div>
                  </div>
                  <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-semibold ${statusTone(r.status)}`}>
                    {t(statusLabelKey(r.status))}
                  </span>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
