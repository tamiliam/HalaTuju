'use client'

import { useEffect, useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  getMySurveys, sendMyAnswers, type MySurvey, type SurveyAnswer, type SurveyQuestion,
} from '@/lib/api/bursarySurveys'

const P = 'bursaryTabs.surveys'
/** ⚠ ONE BOX LEVEL ON A PHONE (mobile standard, rule 15 — Mobile M4): below `sm` a survey is a full-width
 *  section (no border, no radius, the page's 16 px gutter kept inside); from `sm` it is a card. Nothing
 *  inside it is a bordered box — the controls are buttons, the notes are coloured text. */
const SECTION = '-mx-4 bg-ground-0 px-4 py-5 sm:mx-0 sm:rounded-2xl sm:p-5 sm:shadow-sm'
const CHOICE = 'flex min-h-11 items-center gap-3 text-[15px] text-ground-800'
const FIELD = 'w-full rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-base text-ground-900'
const KNOWN = ['required', 'bad_answer', 'answer_too_long', 'survey_closed']

type T = (k: string, vars?: Record<string, string>) => string
type Draft = Record<string, SurveyAnswer | undefined>

function empty(v: SurveyAnswer | undefined): boolean {
  return v === undefined || v === '' || (Array.isArray(v) && v.length === 0)
}

/** Her answer as words (the read-only view). */
export function answerText(t: T, q: SurveyQuestion, v: SurveyAnswer | undefined): string {
  if (empty(v)) return t(`${P}.noAnswer`)
  if (q.kind === 'yes_no') return t(v ? `${P}.yes` : `${P}.no`)
  if (Array.isArray(v)) return v.join(', ')
  return String(v)
}

function Question({ q, n, value, onChange, t, error }: {
  q: SurveyQuestion; n: number; value: SurveyAnswer | undefined; onChange: (v: SurveyAnswer | undefined) => void
  t: T; error: boolean
}) {
  const name = `q-${q.id}`
  const label = `${n}. ${q.text}${q.required ? ' *' : ''}`
  return (
    <fieldset className="space-y-2" data-testid={`survey-q-${q.id}`} aria-invalid={error || undefined}>
      <legend className="break-words text-[15px] font-semibold text-ground-900">{label}</legend>
      {q.hint && <p className="text-xs text-ground-600">{q.hint}</p>}
      {q.kind === 'one' && q.options.map((o) => (
        <label key={o} className={CHOICE}>
          <input type="radio" name={name} checked={value === o} onChange={() => onChange(o)} className="h-5 w-5" />
          <span className="break-words">{o}</span>
        </label>
      ))}
      {q.kind === 'many' && q.options.map((o) => {
        const list = Array.isArray(value) ? value : []
        return (
          <label key={o} className={CHOICE}>
            <input type="checkbox" checked={list.includes(o)} className="h-5 w-5"
              onChange={(e) => onChange(e.target.checked ? [...list, o] : list.filter((x) => x !== o))} />
            <span className="break-words">{o}</span>
          </label>
        )
      })}
      {q.kind === 'rating' && (
        <div className="flex gap-2" role="radiogroup" aria-label={q.text}>
          {[1, 2, 3, 4, 5].map((r) => (
            <button key={r} type="button" role="radio" aria-checked={value === r} onClick={() => onChange(r)}
              data-testid={`${name}-rate-${r}`}
              className={`h-12 w-12 rounded-lg border text-base font-medium ${value === r
                ? 'border-brand-shape bg-brand-fill text-brand-fill-ink' : 'border-ground-300 bg-ground-0 text-ground-800'}`}>
              {r}
            </button>
          ))}
        </div>
      )}
      {q.kind === 'yes_no' && (
        <div className="flex gap-2" role="radiogroup" aria-label={q.text}>
          {[true, false].map((b) => (
            <button key={String(b)} type="button" role="radio" aria-checked={value === b} onClick={() => onChange(b)}
              data-testid={`${name}-${b ? 'yes' : 'no'}`}
              className={`h-11 min-w-[5.5rem] rounded-lg border px-4 text-base font-medium ${value === b
                ? 'border-brand-shape bg-brand-fill text-brand-fill-ink' : 'border-ground-300 bg-ground-0 text-ground-800'}`}>
              {t(b ? `${P}.yes` : `${P}.no`)}
            </button>
          ))}
        </div>
      )}
      {q.kind === 'short' && (
        <input value={typeof value === 'string' ? value : ''} maxLength={300} aria-label={q.text}
          onChange={(e) => onChange(e.target.value)} data-testid={`${name}-text`} className={FIELD} />
      )}
      {q.kind === 'long' && (
        <textarea value={typeof value === 'string' ? value : ''} maxLength={3000} rows={4} aria-label={q.text}
          onChange={(e) => onChange(e.target.value)} data-testid={`${name}-text`} className={FIELD} />
      )}
      {error && <p className="text-sm text-critical-600" role="alert">{t(`${P}.needThis`)}</p>}
    </fieldset>
  )
}

function SurveyCard({ s, org, token, t, onSent }: {
  s: MySurvey; org: string; token: string | null; t: T; onSent: (s: MySurvey | null, toAnswer: number) => void
}) {
  const [draft, setDraft] = useState<Draft>(s.answers)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [missing, setMissing] = useState<number | null>(null)
  const [saved, setSaved] = useState(false)
  const until = formatDate(s.closes_at)

  const send = async () => {
    if (!token) return
    setError(''); setSaved(false)
    const first = s.questions.find((q) => q.required && empty(draft[String(q.id)]))
    if (first) { setMissing(first.id); setError(t(`${P}.error.required`)); return }
    setMissing(null)
    const answers: Record<string, SurveyAnswer> = {}
    for (const q of s.questions) {
      const v = draft[String(q.id)]
      if (!empty(v)) answers[String(q.id)] = typeof v === 'string' ? v.trim() : v as SurveyAnswer
    }
    setBusy(true)
    try {
      const r = await sendMyAnswers(s.id, answers, { token })
      setSaved(true)
      onSent(r.survey, r.to_answer)
    } catch (err) {
      const e = err as { code?: string; fieldErrors?: { detail?: number } }
      const code = e?.code ?? ''
      if (typeof e?.fieldErrors?.detail === 'number') setMissing(e.fieldErrors.detail)
      setError(t(`${P}.error.${KNOWN.includes(code) ? code : 'generic'}`))
    } finally { setBusy(false) }
  }

  return (
    <section className={SECTION} data-testid={`survey-${s.id}`}>
      <h2 className="break-words text-[17px] font-semibold text-ground-900">{s.title}</h2>
      <p className="mt-1 text-xs text-ground-600">
        {[s.status === 'open' ? t(`${P}.openUntil`, { date: until }) : t(`${P}.closed`, { date: until }),
          t(s.questions.length === 1 ? `${P}.oneQuestion` : `${P}.questions`, { count: String(s.questions.length) }),
          s.answered_at ? t(`${P}.answered`, { date: formatDate(s.updated_at ?? s.answered_at) }) : '']
          .filter(Boolean).join(' · ')}
      </p>
      {s.intro && <p className="mt-2 whitespace-pre-line break-words text-[15px] text-ground-700">{s.intro}</p>}

      {s.can_answer ? (
        <div className="mt-5 space-y-6">
          {s.questions.map((q, i) => (
            <Question key={q.id} q={q} n={i + 1} value={draft[String(q.id)]} t={t} error={missing === q.id}
              onChange={(v) => { setDraft((d) => ({ ...d, [String(q.id)]: v })); setSaved(false) }} />
          ))}
          {error && <p className="text-sm text-critical-600" role="alert" data-testid="survey-error">{error}</p>}
          {saved && (
            <p className="text-sm font-medium text-positive-700" role="status" data-testid="survey-saved">
              {t(`${P}.thanks`, { date: until })}
            </p>
          )}
          <button type="button" disabled={busy} onClick={send} data-testid="survey-send"
            className="h-12 w-full rounded-lg bg-brand-fill text-base font-semibold text-brand-fill-ink disabled:opacity-60">
            {t(s.answered_at ? `${P}.change` : `${P}.send`)}
          </button>
          <p className="text-xs text-ground-600">{t(`${P}.who`, { org, date: until })}</p>
        </div>
      ) : (
        <div className="mt-4 space-y-3" data-testid={`survey-readonly-${s.id}`}>
          <h3 className="text-sm font-semibold text-ground-800">{t(`${P}.yourAnswers`)}</h3>
          {s.questions.map((q, i) => (
            <div key={q.id}>
              <p className="break-words text-sm text-ground-700">{i + 1}. {q.text}</p>
              <p className="whitespace-pre-line break-words text-[15px] font-medium text-ground-900">
                {answerText(t, q, s.answers[String(q.id)])}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

/**
 * Her Surveys tab on My Bursary (student maintenance S9; the owner-approved SurveyStudent board).
 *
 * ⚠ WHAT SHE SEES IS THE SERVER'S ALLOWLIST (`surveys.student_payload`): her questions and her own answers.
 * Open surveys first; she can send and CHANGE her answers until it closes; after that (or once her file is
 * closed) a read-only "Your answers". Phone-first: 44 px choices, five 48 px rating buttons, 16 px fields.
 * The tab's red number follows the server's `to_answer` after each send. Words: `bursaryTabs.surveys`.
 */
export default function BursarySurveys({ token, onCount }: { token: string | null; onCount?: (n: number) => void }) {
  const { t } = useT()
  const [items, setItems] = useState<MySurvey[] | null>(null)
  const [org, setOrg] = useState('')
  const [failed, setFailed] = useState(false)
  const told = useRef(onCount)
  told.current = onCount

  useEffect(() => {
    if (!token) return
    let live = true
    getMySurveys({ token })
      .then((d) => { if (live) { setItems(d.surveys); setOrg(d.organisation); setFailed(false) } })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [token])

  if (failed) return <p className="text-sm text-critical-600">{t(`${P}.loadFailed`)}</p>
  if (!items) return null
  if (items.length === 0) {
    return <p className={`${SECTION} text-sm text-ground-600`} data-testid="surveys-empty">{t(`${P}.empty`)}</p>
  }
  return (
    <>
      {items.map((s) => (
        <SurveyCard key={s.id} s={s} org={org} token={token} t={t}
          onSent={(next, toAnswer) => {
            if (next) setItems((list) => (list ?? []).map((x) => (x.id === next.id ? next : x)))
            told.current?.(toAnswer)
          }} />
      ))}
      <p className="px-1 text-xs text-ground-600">{t(`${P}.footnote`)}</p>
    </>
  )
}
