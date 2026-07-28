'use client'

import { useRef, useState } from 'react'
import { insertPlaceholder } from '@/lib/partnerComms'

// The wording editor for ONE editable email, shared by the partner and sponsor families
// (generalised 2026-07-28, when sponsor comms became the second family to need it).
//
// It expands INSIDE its row in the card — the same idiom as the Organisations table, so a page has
// one way of editing things rather than two. Left: subject, body, placeholder chips. Right: what
// the recipient receives, rendered the way the email shell will render it. Save/Cancel at the foot.
//
// Everything family-specific arrives as a prop: the SAVE call, the error-code→copy mapper, and the
// i18n prefix. The alternative was a second 135-line copy of this file, and a duplicated component
// is where the next fix lands in one place and not the other.

const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

/** The minimum shape an editable template must have, whichever family it belongs to. */
export interface EditableTemplate {
  kind: string
  subject: string
  body: string
  placeholders: string[]
}

/** Preview the stored body the way the email shell will: blank-line-separated paragraphs, with
 *  placeholders left visible so the admin can see exactly where each detail lands. */
function Preview({ subject, body }: { subject: string; body: string }) {
  const blocks = body.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean)
  return (
    <div className="rounded-lg border bg-gray-50 p-4">
      <p className="pb-2.5 mb-3 border-b border-dashed border-gray-300 text-xs text-gray-500">
        {subject}
      </p>
      <div className="rounded-xl border bg-white p-4 text-sm leading-relaxed text-gray-700 space-y-3">
        {blocks.map((b, i) => <p key={i} className="whitespace-pre-wrap">{b}</p>)}
      </div>
    </div>
  )
}

export default function TemplateEditor<T extends EditableTemplate>({
  template, prefix, onSave, errorKey, onSaved, onCancel, t,
}: {
  template: T
  /** i18n namespace for this family's editor copy, e.g. `admin.sources.emails`. */
  prefix: string
  /** Persist the edit. Family-specific because each has its own endpoint. */
  onSave: (kind: string, patch: { subject: string; body: string }) => Promise<T>
  /** Map a server error code to a copy key under `prefix` (or a full key). */
  errorKey: (code: string | undefined) => string
  onSaved: (updated: T) => void
  onCancel: () => void
  t: (key: string, params?: Record<string, string>) => string
}) {
  const [subject, setSubject] = useState(template.subject)
  const [body, setBody] = useState(template.body)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bodyRef = useRef<HTMLTextAreaElement | null>(null)

  const dirty = subject !== template.subject || body !== template.body

  const dropIn = (token_: string) => {
    const area = bodyRef.current
    const at = area?.selectionStart ?? body.length
    const { value, caret } = insertPlaceholder(body, token_, at)
    setBody(value)
    // Restore the caret after React re-renders, so a second chip lands where the first left off.
    requestAnimationFrame(() => {
      if (!area) return
      area.focus()
      area.setSelectionRange(caret, caret)
    })
  }

  const save = async () => {
    setBusy(true); setError(null)
    try {
      onSaved(await onSave(template.kind, { subject, body }))
    } catch (err) {
      // Both refusals carry their offending items — the unknown tokens or the banned phrases — so
      // the message can name them instead of telling the admin to go and find them.
      const code = (err as { code?: string })?.code
      const detail = (err as { body?: { placeholders?: string[]; phrases?: string[] } })?.body
      const list = (detail?.placeholders || detail?.phrases || []).join(', ')
      setError(list ? t(errorKey(code), { list }) : t(errorKey(code)))
    }
    setBusy(false)
  }

  return (
    <div className="border-t border-dashed bg-white">
      <div className="grid lg:grid-cols-2">
        <div className="p-4 lg:p-5 space-y-3 min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
            {t(`${prefix}.editLabel`)}
          </p>
          <label className="block">
            <span className="block text-sm text-gray-600 mb-1">{t(`${prefix}.subject`)}</span>
            <input className={inputCls} value={subject} onChange={(e) => setSubject(e.target.value)} />
          </label>
          <label className="block">
            <span className="block text-sm text-gray-600 mb-1">{t(`${prefix}.body`)}</span>
            <textarea ref={bodyRef} rows={11} spellCheck={false}
              className={`${inputCls} font-mono text-xs leading-relaxed`}
              value={body} onChange={(e) => setBody(e.target.value)} />
          </label>
          <div>
            <p className="text-xs text-gray-400 mb-1.5">{t(`${prefix}.placeholderHint`)}</p>
            <div className="flex flex-wrap gap-1.5">
              {template.placeholders.map((p) => (
                <button key={p} type="button" onClick={() => dropIn(`{${p}}`)}
                  className="rounded border border-gray-200 bg-blue-50 px-1.5 py-0.5 font-mono text-[11px] text-blue-700 hover:border-blue-500">
                  {`{${p}}`}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="p-4 lg:p-5 space-y-3 min-w-0 border-t lg:border-t-0 lg:border-l">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
            {t(`${prefix}.previewLabel`)}
          </p>
          <Preview subject={subject} body={body} />
          <p className="text-xs text-gray-400">{t(`${prefix}.note.${template.kind}`)}</p>
        </div>
      </div>

      {error && (
        <div className="mx-4 lg:mx-5 mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4 border-t px-4 lg:px-5 py-3">
        <span className="mr-auto text-xs text-gray-400">{t(`${prefix}.sharedNote`)}</span>
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700">
          {t('admin.sources.cancel')}
        </button>
        <button type="button" onClick={save} disabled={busy || !dirty}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {busy ? t('admin.sources.saving') : t('admin.sources.save')}
        </button>
      </div>
    </div>
  )
}
