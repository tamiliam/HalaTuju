'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import {
  getStudentEmails, saveStudentEmail, setStudentEmailSwitch,
  type StudentEmailRow as Row, type StudentEmailTemplate, type StudentEmailsPayload, type StudentEmailsSaved,
} from '@/lib/admin-api'
import StudentEmailRow from './StudentEmailRow'
import StudentLetterTemplates from './StudentLetterTemplates'
import type { EditorRow } from './StudentEmailLanguages'

const PREFIX = 'admin.orgSettings.studentComms'

/**
 * Organisation → Settings → Student communications — EVERY email a student receives, from applying
 * to the end of her file, under headings (student maintenance S6a; owner rulings 2026-10-30, layout A).
 *
 * One row per email (the reviewer panel's shape, `ReviewerEmailsCard`): the switch where the owner
 * ruled it safe, else a lock with the server's reason; when it is sent; last sent; one chip per
 * language. The organisation-worded ones (Results) open an editor with a tab per language — the
 * shared `TemplateEditor`, keyed on `kind.language`; the others show their wording read-only.
 *
 * ⚠ THE PAGE DECIDES NOTHING. Whether a row is switchable, why it is locked, and whether a platform
 * flag holds it back all arrive from `student_email_catalogue`; the switch endpoint refuses a locked
 * email on its own (lessons, 2026-10-30: a rule written twice has a copy nobody sees break).
 */
export default function StudentCommsTab() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<StudentEmailsPayload | null>(null)
  const [org, setOrg] = useState<string | undefined>(undefined)
  const [orgChoices, setOrgChoices] = useState<string[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [switchError, setSwitchError] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!token) return
    getStudentEmails(org, { token })
      .then((d) => { setData(d); setOrgChoices(null); setLoadError(false) })
      .catch((e) => {
        const err = e as Error & { body?: { code?: string; organisations?: string[] } }
        if (err.body?.code === 'organisation_required' && Array.isArray(err.body.organisations)) {
          setOrgChoices(err.body.organisations)
        } else {
          setLoadError(true)
        }
      })
  }, [token, org])
  useEffect(() => { load() }, [load])

  /** Set ONE row's switch, leaving every other row as it now stands (review L5: a failure used to
   *  restore the whole page from a stale copy, undoing a neighbour's switch that had succeeded). */
  const setRow = (key: string, enabled: boolean) =>
    setData((cur) => cur && { ...cur, catalogue: cur.catalogue.map((r) => (r.key === key ? { ...r, enabled } : r)) })

  const toggle = async (row: Row) => {
    setBusy(row.key)
    setSwitchError(false)
    setRow(row.key, !row.enabled)                       // optimistic
    try {
      const done = await setStudentEmailSwitch(row.key, !row.enabled, org, { token: token! })
      setRow(done.key, done.enabled)                    // the server's answer for this row
    } catch {
      setRow(row.key, row.enabled)                      // back to what it was — this row only
      setSwitchError(true)
    } finally { setBusy(null) }
  }

  /** A save answers with the wording only; the rest of the page (last sent, switches) stays. */
  const keepWording = (saved: StudentEmailsSaved) =>
    setData((cur) => cur && { ...cur, enabled: saved.enabled, templates: saved.templates })

  const save = async (key: string, patch: { subject: string; body: string }) => {
    const [kind, language] = key.split('.')
    const next = await saveStudentEmail({ kind, language, ...patch }, org, { token: token! })
    keepWording(next)
    const tpl = next.templates.find((x) => x.key === key) as StudentEmailTemplate
    const editorRow: EditorRow = { ...tpl, kind: tpl.key }
    return editorRow
  }

  const reset = async (tpl: StudentEmailTemplate) => {
    setBusy(tpl.key)
    try {
      keepWording(await saveStudentEmail({ kind: tpl.kind, language: tpl.language, reset: true }, org, { token: token! }))
    } catch {
      setLoadError(true)
    } finally { setBusy(null) }
  }

  return (
    <div className="mt-6">
      <p className="text-sm text-ground-600 max-w-3xl">{t(`${PREFIX}.subtitle`)}</p>
      <p className="mt-2 text-sm text-caution-700 max-w-3xl">{t(`${PREFIX}.switchNote`)}</p>
      {/* Review L3: switching back on is not a fresh start — it reaches everyone now due. */}
      <p className="mt-1 text-sm text-ground-600 max-w-3xl" data-testid="student-comms-switch-back">
        {t(`${PREFIX}.switchBackNote`)}
      </p>
      {loadError && <p className="mt-3 text-sm text-critical-600">{t(`${PREFIX}.loadError`)}</p>}
      {switchError && <p className="mt-3 text-sm text-critical-600">{t(`${PREFIX}.switchFailed`)}</p>}
      {orgChoices && (
        <div className="mt-4 rounded-xl border border-ground-200 bg-ground-0 p-4">
          <p className="text-sm font-medium text-ground-800">{t('admin.orgSettings.config.organisationRequired')}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {orgChoices.map((code) => (
              <button key={code} type="button" onClick={() => setOrg(code)}
                className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm hover:bg-ground-50">{code}</button>
            ))}
          </div>
        </div>
      )}
      {data && data.groups.map((group) => {
        const rows = data.catalogue.filter((r) => r.group === group)
        if (rows.length === 0) return null
        return (
          <section key={group} className="mt-5 overflow-hidden rounded-2xl border border-ground-200 bg-ground-0 shadow-sm"
            data-testid={`student-comms-group-${group}`}>
            <div className="border-b px-4 py-3 sm:px-5">
              <h2 className="font-semibold text-ground-900">{t(`${PREFIX}.group.${group}`)}</h2>
              {/* The Results emails sit under one platform switch; say plainly which way it is set. */}
              {group === 'results' && (
                <p className={`mt-2 rounded-lg border p-2.5 text-sm ${data.enabled
                  ? 'border-positive-200 bg-positive-50 text-positive-800'
                  : 'border-caution-200 bg-caution-50 text-caution-800'}`} data-testid="student-comms-switch">
                  {t(data.enabled ? `${PREFIX}.on` : `${PREFIX}.off`)}
                </p>
              )}
            </div>
            <ul className="divide-y divide-ground-100">
              {rows.map((row) => (
                <StudentEmailRow key={row.key} row={row}
                  templates={data.templates.filter((x) => x.kind === row.key)}
                  open={open === row.key} onOpen={() => setOpen(open === row.key ? null : row.key)}
                  busy={busy} onToggle={() => { void toggle(row) }}
                  onSave={save} onReset={(tpl) => { void reset(tpl) }} t={t} />
              ))}
            </ul>
            {/* S6b: the letters' own wording sits under the same heading as the notice email. */}
            {group === 'letters' && <StudentLetterTemplates org={org} token={token} t={t} />}
          </section>
        )
      })}
    </div>
  )
}
