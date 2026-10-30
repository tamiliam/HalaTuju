'use client'

import { useState } from 'react'
import TemplateEditor from '@/components/emails/TemplateEditor'
import type { StudentEmailLanguage, StudentEmailRow as Row, StudentEmailTemplate } from '@/lib/admin-api'

const PREFIX = 'admin.orgSettings.studentComms'
const KNOWN_ERRORS = ['unknown_placeholders', 'banned_phrase', 'empty', 'subject_too_long', 'unknown_template']
type T = (key: string, params?: Record<string, string>) => string
/** The editor keys a row on `kind`; here that is `kind.language` (the template's `key`). */
export type EditorRow = Omit<StudentEmailTemplate, 'kind'> & { kind: string }

/**
 * One email's wording, one TAB PER LANGUAGE (S6a, the owner's "more compactly"): three rows per
 * email became one row and this panel. An organisation-worded email edits each language in the
 * shared `TemplateEditor` ("Use the default" deletes that language's wording); any other shows the
 * sending module's own text, read-only, tokens in place.
 */
export default function StudentEmailLanguages({ row, templates, busy, onSave, onReset, onDone, t }: {
  row: Row
  templates: StudentEmailTemplate[]
  busy: string | null
  onSave: (key: string, patch: { subject: string; body: string }) => Promise<EditorRow>
  onReset: (tpl: StudentEmailTemplate) => void
  onDone: () => void
  t: T
}) {
  const langs = (['en', 'ms', 'ta'] as const).filter((l) =>
    row.editable ? templates.some((x) => x.language === l) : !!row.wording[l])
  const [lang, setLang] = useState<StudentEmailLanguage>(langs[0] ?? 'en')
  const tpl = templates.find((x) => x.language === lang)
  const shown = row.wording[lang]
  const errorKey = (code: string | undefined) =>
    `${PREFIX}.error.${code && KNOWN_ERRORS.includes(code) ? code : 'generic'}`

  return (
    <div className="rounded-xl border border-ground-200">
      <div role="tablist" aria-label={t(`${PREFIX}.kind.${row.key}`)} className="flex gap-1 border-b px-3 pt-2">
        {langs.map((l) => {
          const own = templates.some((x) => x.language === l && x.customised)
          return (
            <button key={l} type="button" role="tab" aria-selected={lang === l} onClick={() => setLang(l)}
              data-testid={`student-email-tab-${row.key}.${l}`}
              className={`-mb-px rounded-t-lg border px-3 py-1.5 text-sm ${lang === l
                ? 'border-ground-200 border-b-ground-0 bg-ground-0 font-medium text-ground-900'
                : 'border-transparent text-ground-500 hover:text-ground-800'}`}>
              {t(`${PREFIX}.language.${l}`)}{own && <span className="ml-1 text-info-600" aria-hidden="true">●</span>}
            </button>
          )
        })}
      </div>
      <div className="p-3 sm:p-4" role="tabpanel">
        {row.editable && tpl ? (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
              <span className={`rounded-full px-2 py-0.5 text-xs ${tpl.customised
                ? 'bg-info-100 text-info-700' : 'bg-ground-100 text-ground-600'}`}>
                {t(tpl.customised ? `${PREFIX}.customised` : `${PREFIX}.default`)}
              </span>
              {tpl.customised && (
                <button type="button" onClick={() => onReset(tpl)} disabled={busy === tpl.key}
                  className="text-ground-600 hover:underline disabled:opacity-50">
                  {t(`${PREFIX}.reset`)}
                </button>
              )}
            </div>
            <TemplateEditor<EditorRow> key={tpl.key}
              template={{ ...tpl, kind: tpl.key }}
              prefix={PREFIX}
              onSave={onSave}
              errorKey={errorKey}
              onSaved={onDone}
              onCancel={onDone}
              t={t}
            />
          </>
        ) : shown ? (
          <div>
            <p className="mb-2 text-xs text-ground-500">{t(`${PREFIX}.wordingNote`)}</p>
            <p className="text-sm text-ground-700 break-words">
              <span className="text-ground-400">{t(`${PREFIX}.subject`)}: </span>{shown.subject}
            </p>
            <pre className="mt-2 whitespace-pre-wrap break-words rounded-lg border bg-ground-50 p-3 font-sans text-sm text-ground-700">
              {shown.body}
            </pre>
          </div>
        ) : null}
      </div>
    </div>
  )
}
