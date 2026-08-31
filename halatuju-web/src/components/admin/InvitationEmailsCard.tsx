'use client'

import { useEffect, useState } from 'react'
import {
  getInvitationEmails,
  type PartnerEmailTemplate, type PartnerEmailsPayload,
} from '@/lib/admin-api'
import PartnerTemplateEditor from '@/components/sources/PartnerTemplateEditor'

/**
 * The Emails tab on Organisation → Invitations: the four invitation emails, editable.
 *
 * One per group on the page — admin, reviewer, source, sponsor — since 2026-08-04. Which letter a
 * staff invite actually reads is decided SERVER-SIDE from the same role map that groups the tables
 * (`emails._invite_kind_for_role`); nothing here picks it, so this list cannot disagree with what
 * sends.
 *
 * ⚠ **NO SWITCH, AND THAT IS THE ONE DIFFERENCE FROM EVERY OTHER EMAIL CARD.** Owner's decision,
 * 2026-08-04. Turning an invitation email off would mean pressing "Send invite" still creates the
 * account and still issues the temporary password — and simply tells nobody, with nothing to report
 * the silence. Wording is the organisation's; whether an invitation is delivered is not a setting.
 * The server agrees: `emails._invite_render` never reads `enabled`.
 *
 * ⚠ **THE SIGN-IN PARAGRAPH IS NOT EDITABLE AND THAT IS WHY THIS IS SAFE.** `{access}` is a
 * structural block carrying the temporary password and its three shapes (a fresh password / sign in
 * with Google / you already have an account). The editor refuses a save that has dropped it, and
 * the sender falls back to the built-in letter if a stored body somehow renders without it.
 */
export default function InvitationEmailsCard({ token, t }: {
  token: string | null
  t: (key: string, params?: Record<string, string>) => string
}) {
  const [data, setData] = useState<PartnerEmailsPayload | null>(null)
  const [openKind, setOpenKind] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    getInvitationEmails({ token })
      .then(setData)
      .catch(() => setError(t('admin.invitations.emails.loadError')))
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) {
    return error ? (
      <div className="rounded-lg border border-critical-200 bg-critical-50 p-4 text-sm text-critical-600">{error}</div>
    ) : null
  }

  const replace = (updated: PartnerEmailTemplate) =>
    setData({ ...data, templates: data.templates.map((x) => (x.kind === updated.kind ? updated : x)) })

  return (
    <div className="overflow-hidden rounded-xl border bg-ground-0 shadow-sm">
      <div className="border-b px-4 py-4 sm:px-5">
        <h2 className="font-semibold text-ground-900">{t('admin.invitations.emails.title')}</h2>
        <p className="mt-1 max-w-3xl text-sm text-ground-500">
          {t('admin.invitations.emails.subtitle')}
        </p>
        {/* The two things a reader must not get wrong, said once each. `accessLocked` scopes
            itself ("where a letter hands somebody an account") rather than being repeated on the
            three rows it happens to apply to. */}
        <p className="mt-2 max-w-3xl text-sm text-caution-700">
          {t('admin.invitations.emails.alwaysSends')}
        </p>
        <p className="mt-1.5 max-w-3xl text-sm text-caution-700">
          {t('admin.invitations.emails.accessLocked')}
        </p>
      </div>

      <ul className="divide-y divide-ground-100">
        {data.templates.map((tpl) => (
          <li key={tpl.kind} className="px-4 py-4 sm:px-5">
            <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ground-900">
                  {t(`admin.invitations.emails.kind.${tpl.kind}`)}
                </p>
                <p className="mt-0.5 text-sm text-ground-500">
                  {t(`admin.invitations.emails.when.${tpl.kind}`)}
                </p>
                {/* ⚠ NOTHING PER-ROW BEYOND ITS OWN NAME AND WHEN IT SENDS (owner, 2026-08-04).
                    The locked-access note used to repeat on three of the four rows, and the source
                    row said it was unsent twice over — once in its description and once in a note
                    of its own. Both facts are now stated ONCE, in the header. A caveat repeated
                    down a list stops being read. */}
              </div>
              <button type="button"
                onClick={() => setOpenKind(openKind === tpl.kind ? null : tpl.kind)}
                className="shrink-0 text-sm font-medium text-info-600 hover:text-info-700 hover:underline">
                {t(openKind === tpl.kind ? 'common.cancel' : 'admin.reviewers.emails.edit')}
              </button>
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
