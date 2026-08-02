'use client'

import { useEffect, useState } from 'react'
import {
  getReviewerEmails, updatePartnerEmail,
  type PartnerEmailTemplate, type PartnerEmailsPayload,
} from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'
import { REVIEWER_EMAIL_KINDS } from '@/lib/partnerComms'
import PartnerTemplateEditor from '@/components/sources/PartnerTemplateEditor'
import { Toggle } from '@/components/sources/shared'

// The Emails tab on Organisation → Reviewers: the five emails our own volunteers receive.
//
// ⚠ ALL FIVE ARE SENDING TODAY. They were hard-coded prose until request #10; the switches here
// are real, so turning one off genuinely stops it. The card says so out loud rather than letting
// an org_admin discover it by silence — this is the opposite of the Sources card, where nothing
// sends yet and the honest note is that no partner has an address on file.
//
// Deliberately leaner than `PartnerEmailsCard`: no "who qualifies" panel. The recipient of a
// reviewer email is the reviewer the case belongs to, so there is no reachability question to
// answer — everyone on the Reviewers table has an email or they could not have signed in.

export default function ReviewerEmailsCard({ token, t }: {
  token: string | null
  t: (key: string, params?: Record<string, string>) => string
}) {
  const [data, setData] = useState<PartnerEmailsPayload | null>(null)
  const [openKind, setOpenKind] = useState<string | null>(null)
  const [busyKind, setBusyKind] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    getReviewerEmails({ token })
      .then(setData)
      .catch(() => setError(t('admin.reviewers.emails.loadError')))
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) {
    return error ? (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">{error}</div>
    ) : null
  }

  const replace = (updated: PartnerEmailTemplate) =>
    setData({ ...data, templates: data.templates.map((x) => (x.kind === updated.kind ? updated : x)) })

  const toggle = async (tpl: PartnerEmailTemplate) => {
    setBusyKind(tpl.kind)
    setError(null)
    // Optimistic, then reconciled from the response — the same pattern the sibling card uses.
    replace({ ...tpl, enabled: !tpl.enabled })
    try {
      replace(await updatePartnerEmail(tpl.kind, { enabled: !tpl.enabled }, { token: token! }))
    } catch {
      replace(tpl)
      setError(t('admin.actionFailed'))
    }
    setBusyKind(null)
  }

  // Fixed order, from the list — not the payload's, so the screen reads the same every time.
  const ordered = REVIEWER_EMAIL_KINDS
    .map((k) => data.templates.find((x) => x.kind === k))
    .filter((x): x is PartnerEmailTemplate => !!x)

  return (
    <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
      <div className="px-4 sm:px-5 py-4 border-b">
        <h2 className="font-semibold text-gray-900">{t('admin.reviewers.emails.title')}</h2>
        <p className="text-sm text-gray-500 mt-1 max-w-3xl">
          {t('admin.reviewers.emails.subtitle')}
        </p>
        {/* The one thing a reader must not get wrong: these are live. */}
        <p className="text-sm text-amber-700 mt-2 max-w-3xl">
          {t('admin.reviewers.emails.liveNote')}
        </p>
      </div>

      {error && (
        <div className="px-4 sm:px-5 py-3 text-sm text-red-600 border-b">{error}</div>
      )}

      <ul className="divide-y divide-gray-100">
        {ordered.map((tpl) => (
          <li key={tpl.kind} className="px-4 sm:px-5 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium text-gray-900">
                  {t(`admin.reviewers.emails.kind.${tpl.kind}`)}
                </p>
                <p className="text-sm text-gray-500 mt-0.5">
                  {t(`admin.reviewers.emails.when.${tpl.kind}`)}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {tpl.last_sent_at
                    ? t('admin.reviewers.emails.lastSent', { date: formatDate(tpl.last_sent_at) })
                    : t('admin.reviewers.emails.neverSent')}
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button type="button" onClick={() => setOpenKind(openKind === tpl.kind ? null : tpl.kind)}
                  className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline">
                  {t(openKind === tpl.kind ? 'common.cancel' : 'admin.reviewers.emails.edit')}
                </button>
                <Toggle on={tpl.enabled} disabled={busyKind === tpl.kind}
                  label={t(`admin.reviewers.emails.kind.${tpl.kind}`)}
                  onClick={() => { void toggle(tpl) }} />
              </div>
            </div>
            {openKind === tpl.kind && (
              <div className="mt-4">
                <PartnerTemplateEditor
                  template={tpl} token={token} t={t}
                  onSaved={(updated) => { replace(updated); setOpenKind(null) }}
                  onCancel={() => setOpenKind(null)}
                />
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
