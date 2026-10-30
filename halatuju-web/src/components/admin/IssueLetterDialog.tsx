'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  issueLetter, previewLetter,
  type AdminLetter, type LetterKind, type LetterLanguage, type LetterPreview, type ScholarLetters,
} from '@/lib/admin-api/letters'

const P = 'admin.scholars.letters'
const ALL_KINDS: readonly LetterKind[] = ['general', 'discipline', 'close_out', 'suspension', 'termination']
const CONFIRM: readonly LetterKind[] = ['discipline', 'termination']
const DOCS_ONLY: readonly LetterKind[] = ['suspension', 'termination']
const KNOWN = ['forbidden', 'file_closed', 'confirm_mismatch', 'clause_required', 'clause_too_long', 'note_too_long',
  'pdf_failed', 'storage_failed']

/**
 * "Issue a letter" (S6b; the LettersAdmin board's six steps): kind, PDF language, the fill-ins, the
 * DRAFT preview of the letter and of the email she gets, the documents-only line for suspension and
 * termination, and the typed full name for discipline and termination.
 *
 * ⚠ The preview is the SERVER's render (`letters.preview`), so what is shown is what is issued. The
 * typed name is checked here only to enable the button; the server checks it again and refuses a
 * mismatch (`confirm_mismatch`). Kinds this officer may not issue are not offered (`can_issue`).
 */
export default function IssueLetterDialog({ id, token, data, onCancel, onIssued }: {
  id: number
  token: string | null
  data: ScholarLetters
  onCancel: () => void
  onIssued: (letter: AdminLetter) => void
}) {
  const { t } = useT()
  const [kind, setKind] = useState<LetterKind>(data.can_issue[0] ?? 'general')
  const [language, setLanguage] = useState<LetterLanguage>(data.default_language)
  const [clause, setClause] = useState('')
  const [note, setNote] = useState('')
  const [preview, setPreview] = useState<LetterPreview | null>(null)
  const [previewError, setPreviewError] = useState('')
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const say = (e: unknown) => {
    const code = (e as { code?: string })?.code || ''
    return t(`${P}.error.${KNOWN.includes(code) ? code : 'generic'}`)
  }

  useEffect(() => {
    if (!token) return
    let live = true
    const timer = setTimeout(() => {
      previewLetter(id, { kind, language, clause, note }, { token })
        .then((p) => { if (live) { setPreview(p); setPreviewError('') } })
        .catch((e) => { if (live) { setPreview(null); setPreviewError(say(e)) } })
    }, 350)
    return () => { live = false; clearTimeout(timer) }
  }, [id, token, kind, language, clause, note]) // eslint-disable-line react-hooks/exhaustive-deps -- `say` only maps a code to words; the draft re-renders on its own fields

  const needsName = CONFIRM.includes(kind)
  const norm = (s: string) => s.trim().split(/\s+/).join(' ').toLocaleLowerCase()
  const nameOk = !needsName || (!!data.student_name && norm(typed) === norm(data.student_name))

  async function issue() {
    if (!token || !preview || !nameOk) return
    setBusy(true); setError('')
    try {
      onIssued(await issueLetter(id, { kind, language, clause, note, confirm_name: typed }, { token }))
    } catch (e) { setError(say(e)) } finally { setBusy(false) }
  }

  const input = 'h-10 rounded-lg border border-ground-300 px-3 text-sm'
  return (
    <section aria-label={t(`${P}.issue`)} data-testid="issue-letter"
      className="space-y-4 rounded-xl border-2 border-primary-500 bg-ground-0 p-4 sm:p-5">
      <h2 className="text-lg font-semibold text-ground-900">{t(`${P}.issue`)}</h2>

      <fieldset>
        <legend className="mb-1.5 text-sm font-semibold text-ground-700">{t(`${P}.dialog.kind`)}</legend>
        <div className="flex flex-wrap gap-4 text-sm">
          {ALL_KINDS.filter((k) => data.can_issue.includes(k)).map((k) => (
            <label key={k} className="flex items-center gap-1.5">
              <input type="radio" name="letter-kind" checked={kind === k} onChange={() => setKind(k)} />
              {t(`${P}.kind.${k}`)}
            </label>
          ))}
        </div>
        {!data.can_issue.includes('termination') && !data.file_closed && (
          <p className="mt-1 text-xs text-ground-500">{t(`${P}.dialog.seniorOnly`)}</p>
        )}
      </fieldset>

      <div className="flex flex-wrap gap-4">
        <label className="flex flex-col gap-1 text-sm font-semibold text-ground-700">
          {t(`${P}.dialog.language`)}
          <select value={language} onChange={(e) => setLanguage(e.target.value as LetterLanguage)} className={input}>
            <option value="en">{t(`${P}.lang.en`)}</option>
            <option value="ms">{t(`${P}.lang.ms`)}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold text-ground-700">
          {t(`${P}.dialog.clause`)}
          <input value={clause} onChange={(e) => setClause(e.target.value)} maxLength={40} className={`${input} w-28`} />
        </label>
        <label className="flex min-w-0 flex-1 basis-72 flex-col gap-1 text-sm font-semibold text-ground-700">
          {t(`${P}.dialog.note`)}
          <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} rows={2}
            className="rounded-lg border border-ground-300 px-3 py-2 text-sm font-normal" />
        </label>
        <div className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ground-700">{t(`${P}.dialog.replyBy`)}</span>
          <span className="flex h-10 items-center text-ground-700" data-testid="letter-reply-by">
            {preview ? t(`${P}.dialog.replyByValue`, { date: formatDate(preview.response_due_on),
              days: String(data.response_days) }) : '—'}
          </span>
        </div>
      </div>
      <p className="text-xs text-ground-500">{t(`${P}.dialog.wordingWhere`)}</p>

      {previewError && <p className="text-sm text-critical-600" data-testid="letter-preview-error">{previewError}</p>}
      {preview && (
        <div className="flex flex-wrap gap-4">
          <div className="min-w-0 flex-1 basis-80 space-y-2 rounded-lg border bg-ground-50 p-4" data-testid="letter-preview">
            <span className="inline-block rounded border border-critical-200 px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-critical-700">
              {t(`${P}.dialog.draft`)}
            </span>
            <p className="text-sm font-semibold text-ground-900">{preview.subject}</p>
            <p className="whitespace-pre-wrap text-sm text-ground-700">{preview.body}</p>
          </div>
          <div className="min-w-0 flex-1 basis-80 space-y-2 rounded-lg border bg-ground-50 p-4" data-testid="letter-email-preview">
            <p className="text-sm font-semibold text-ground-900">
              {t(`${P}.dialog.emailPreview`, { language: t(`${P}.emailLang.${preview.email.language}`) })}
            </p>
            <p className="text-sm text-ground-800">{preview.email.subject}</p>
            <p className="whitespace-pre-wrap text-sm text-ground-700">{preview.email.body}</p>
          </div>
        </div>
      )}

      {DOCS_ONLY.includes(kind) && (
        <p className="rounded-lg bg-caution-50 px-3 py-2 text-sm text-caution-800" data-testid="letter-docs-only">
          {t(`${P}.dialog.documentsOnly`)}
        </p>
      )}
      {needsName && (
        <label className="flex max-w-md flex-col gap-1 text-sm font-semibold text-ground-700">
          {t(`${P}.dialog.typeName`)}
          <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={data.student_name}
            className={`${input} font-normal`} data-testid="letter-confirm-name" />
        </label>
      )}
      {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={issue} disabled={busy || !preview || !nameOk}
          className="h-11 rounded-lg bg-primary-600 px-4 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50">
          {busy ? t('common.loading') : t(`${P}.dialog.issueAndEmail`)}
        </button>
        <button type="button" onClick={onCancel} className="h-11 rounded-lg border border-ground-300 px-4 text-sm">
          {t('common.cancel')}
        </button>
      </div>
    </section>
  )
}
