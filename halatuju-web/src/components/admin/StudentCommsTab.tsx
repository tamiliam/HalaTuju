'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import TemplateEditor from '@/components/emails/TemplateEditor'
import { getStudentEmails, saveStudentEmail, type StudentEmailTemplate, type StudentEmailsPayload } from '@/lib/admin-api'

const PREFIX = 'admin.orgSettings.studentComms'
const KNOWN_ERRORS = ['unknown_placeholders', 'banned_phrase', 'empty', 'subject_too_long', 'unknown_template']
/** The editor keys a row on `kind`; here that is `kind.language` (the row's `key`). */
type EditorRow = Omit<StudentEmailTemplate, 'kind'> & { kind: string }

/**
 * Organisation → Settings → Student communications (student maintenance S4b): the organisation's
 * wording for the three emails a FUNDED student receives about her results — due, overdue, and an
 * officer's query — each in English, Malay and Tamil (the student is written to in her language).
 *
 * A row is the platform's default until the organisation saves its own; "Use the default" deletes
 * the organisation's wording. The editor is the shared `TemplateEditor` (the partner and sponsor
 * families' own), keyed on `kind.language`.
 *
 * ⚠ THE SWITCH IS THE PLATFORM'S, NOT A ROW'S. While `MAINTENANCE_REMINDERS_ENABLED` is off nothing is
 * sent, and the header says so — a page of editable letters must not read as letters that go out.
 */
export default function StudentCommsTab() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<StudentEmailsPayload | null>(null)
  const [org, setOrg] = useState<string | undefined>(undefined)
  const [orgChoices, setOrgChoices] = useState<string[] | null>(null)
  const [loadError, setLoadError] = useState(false)
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

  const save = async (key: string, patch: { subject: string; body: string }) => {
    const [kind, language] = key.split('.')
    const next = await saveStudentEmail({ kind, language, ...patch }, org, { token: token! })
    setData(next)
    const row = next.templates.find((x) => x.key === key) as StudentEmailTemplate
    return { ...row, kind: row.key }
  }

  const reset = async (tpl: StudentEmailTemplate) => {
    setBusy(tpl.key)
    try {
      setData(await saveStudentEmail({ kind: tpl.kind, language: tpl.language, reset: true }, org, { token: token! }))
      setOpen(null)
    } catch {
      setLoadError(true)
    } finally { setBusy(null) }
  }

  const errorKey = (code: string | undefined) =>
    `${PREFIX}.error.${code && KNOWN_ERRORS.includes(code) ? code : 'generic'}`

  return (
    <div className="mt-6">
      <p className="text-sm text-ground-600">{t(`${PREFIX}.subtitle`)}</p>
      {data && (
        <p className={`mt-3 rounded-lg border p-3 text-sm ${data.enabled
          ? 'border-positive-200 bg-positive-50 text-positive-800'
          : 'border-caution-200 bg-caution-50 text-caution-800'}`} data-testid="student-comms-switch">
          {t(data.enabled ? `${PREFIX}.on` : `${PREFIX}.off`)}
        </p>
      )}
      {loadError && <p className="mt-3 text-sm text-critical-600">{t(`${PREFIX}.loadError`)}</p>}
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
      {data && (['results_due', 'results_overdue', 'result_queried'] as const).map((kind) => (
        <section key={kind} className="mt-5 overflow-hidden rounded-2xl border border-ground-200 bg-ground-0 shadow-sm">
          <div className="border-b px-4 py-4 sm:px-5">
            <h2 className="font-semibold text-ground-900">{t(`${PREFIX}.kind.${kind}`)}</h2>
            <p className="mt-0.5 text-sm text-ground-500">{t(`${PREFIX}.when.${kind}`)}</p>
          </div>
          <ul className="divide-y divide-ground-100">
            {data.templates.filter((x) => x.kind === kind).map((tpl) => (
              <li key={tpl.key} className="px-4 py-3 sm:px-5" data-testid={`student-email-${tpl.key}`}>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span className="w-20 text-sm font-medium text-ground-800">{t(`${PREFIX}.language.${tpl.language}`)}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-ground-600">{tpl.subject}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${tpl.customised
                    ? 'bg-info-100 text-info-700' : 'bg-ground-100 text-ground-600'}`}>
                    {t(tpl.customised ? `${PREFIX}.customised` : `${PREFIX}.default`)}
                  </span>
                  {tpl.customised && (
                    <button type="button" onClick={() => reset(tpl)} disabled={busy === tpl.key}
                      className="text-sm text-ground-600 hover:underline disabled:opacity-50">
                      {t(`${PREFIX}.reset`)}
                    </button>
                  )}
                  <button type="button" onClick={() => setOpen(open === tpl.key ? null : tpl.key)}
                    className="text-sm font-medium text-primary-600 hover:underline">
                    {t(open === tpl.key ? 'common.cancel' : `${PREFIX}.edit`)}
                  </button>
                </div>
                {open === tpl.key && (
                  <div className="mt-3">
                    <TemplateEditor<EditorRow>
                      template={{ ...tpl, kind: tpl.key }}
                      prefix={PREFIX}
                      onSave={save}
                      errorKey={errorKey}
                      onSaved={() => setOpen(null)}
                      onCancel={() => setOpen(null)}
                      t={t}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
