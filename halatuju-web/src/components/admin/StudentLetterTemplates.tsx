'use client'

import { useCallback, useEffect, useState } from 'react'
import TemplateEditor from '@/components/emails/TemplateEditor'
import {
  getLetterTemplates, saveLetterTemplate,
  type LetterLanguage, type LetterTemplateRow, type LetterTemplatesPayload,
} from '@/lib/admin-api/letters'

const PREFIX = 'admin.orgSettings.studentComms'
const L = `${PREFIX}.letters`
const KINDS = ['general', 'discipline', 'termination', 'suspension', 'close_out'] as const
const KNOWN_ERRORS = ['unknown_placeholders', 'banned_phrase', 'empty', 'subject_too_long', 'unknown_template',
  'subject_newline', 'body_too_long']   // S6b review 7
type T = (key: string, params?: Record<string, string>) => string
type EditorRow = Omit<LetterTemplateRow, 'kind'> & { kind: string }

/**
 * Student communications → Letters (S6b; the CommsLetters board): the organisation's wording for the
 * five letters, ONE row per kind with a chip per PDF language (English, Malay — the PDF cannot shape
 * Tamil), and "Edit wording" opening a tab per language in the shared `TemplateEditor`. A language
 * without the organisation's own row reads "Platform default"; "Use the default" deletes the row.
 * The notice email beside them ("A letter has been issued") is a catalogue row of its own, locked.
 */
export default function StudentLetterTemplates({ org, token, t }: { org?: string; token: string | null; t: T }) {
  const [data, setData] = useState<LetterTemplatesPayload | null>(null)
  const [failed, setFailed] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const [lang, setLang] = useState<LetterLanguage>('en')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!token) return
    getLetterTemplates(org, { token }).then((d) => { setData(d); setFailed(false) }).catch(() => setFailed(true))
  }, [org, token])
  useEffect(() => { load() }, [load])

  if (failed) return <p className="px-4 py-3 text-sm text-critical-600 sm:px-5">{t(`${L}.loadError`)}</p>
  if (!data) return null

  const row = (kind: string, language: string) => data.templates.find((x) => x.kind === kind && x.language === language)
  const save = async (key: string, patch: { subject: string; body: string }) => {
    const [kind, language] = key.split('.')
    const next = await saveLetterTemplate({ kind, language, ...patch }, org, { token: token! })
    setData(next)
    const saved = next.templates.find((x) => x.key === key) as LetterTemplateRow
    const editorRow: EditorRow = { ...saved, kind: saved.key }
    return editorRow
  }
  const reset = async (tpl: LetterTemplateRow) => {
    setBusy(true)
    try { setData(await saveLetterTemplate({ kind: tpl.kind, language: tpl.language, reset: true }, org, { token: token! })) }
    catch { setFailed(true) } finally { setBusy(false) }
  }
  const errorKey = (code: string | undefined) => `${PREFIX}.error.${code && KNOWN_ERRORS.includes(code) ? code : 'generic'}`

  return (
    <div data-testid="letter-templates">
      <p className="border-t px-4 py-2 text-xs text-ground-500 sm:px-5" data-testid="letter-response-days">
        {t(`${L}.responseDays`, { days: String(data.response_days) })}
      </p>
      <ul className="divide-y divide-ground-100 border-t">
        {KINDS.map((kind) => {
          const editing = open === kind
          const tpl = row(kind, lang)
          return (
            <li key={kind} className="px-4 py-4 sm:px-5" data-testid={`letter-template-${kind}`}>
              <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
                <div className="min-w-0 flex-1 sm:pl-[60px]">
                  <p className="font-medium text-ground-900">{t(`${L}.kind.${kind}`)}</p>
                  <p className="mt-0.5 text-sm text-ground-500">{t(`${L}.when.${kind}`)}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span className="text-xs text-ground-500">{t(`${L}.pdf`)}</span>
                  {(['en', 'ms'] as const).map((l) => {
                    const own = !!row(kind, l)?.customised
                    return (
                      <span key={l} data-customised={own ? 'true' : 'false'}
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${own
                          ? 'bg-info-100 text-info-700' : 'border border-ground-200 text-ground-500'}`}>
                        {t(`${PREFIX}.chip.${l}`)}
                      </span>
                    )
                  })}
                  <button type="button" onClick={() => { setOpen(editing ? null : kind); setLang('en') }}
                    className="ml-2 text-sm font-medium text-primary-600 hover:underline">
                    {t(editing ? 'common.cancel' : `${PREFIX}.edit`)}
                  </button>
                </div>
              </div>
              {editing && tpl && (
                <div className="mt-3 rounded-xl border border-ground-200 sm:ml-[60px]">
                  <div role="tablist" className="flex gap-1 border-b px-3 pt-2">
                    {(['en', 'ms'] as const).map((l) => (
                      <button key={l} type="button" role="tab" aria-selected={lang === l} onClick={() => setLang(l)}
                        data-testid={`letter-template-tab-${kind}.${l}`}
                        className={`-mb-px rounded-t-lg border px-3 py-1.5 text-sm ${lang === l
                          ? 'border-ground-200 border-b-ground-0 bg-ground-0 font-medium text-ground-900'
                          : 'border-transparent text-ground-500 hover:text-ground-800'}`}>
                        {t(`${L}.tab.${l}`)}
                      </button>
                    ))}
                  </div>
                  <div className="p-3 sm:p-4" role="tabpanel">
                    <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${tpl.customised
                        ? 'bg-info-100 text-info-700' : 'bg-ground-100 text-ground-600'}`}>
                        {t(tpl.customised ? `${PREFIX}.customised` : `${PREFIX}.default`)}
                      </span>
                      {tpl.customised && (
                        <button type="button" onClick={() => reset(tpl)} disabled={busy}
                          className="text-ground-600 hover:underline disabled:opacity-50">{t(`${PREFIX}.reset`)}</button>
                      )}
                    </div>
                    <TemplateEditor<EditorRow> key={tpl.key} template={{ ...tpl, kind: tpl.key }} prefix={PREFIX}
                      onSave={save} errorKey={errorKey} onSaved={() => setOpen(null)} onCancel={() => setOpen(null)} t={t} />
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
