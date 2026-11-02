'use client'

import { useState } from 'react'
import Toggle from '@/components/Toggle'
import { mytInstant, mytParts } from '@/components/announcements/AnnouncementForm'
import {
  createSurvey, updateSurvey,
  type QuestionKind, type SurveyAction, type SurveyAudience, type SurveyInput, type SurveyLimits,
  type SurveyQuestionInput, type SurveyRow,
} from '@/lib/admin-api'

const K = 'admin.surveys'
export const KINDS: readonly QuestionKind[] = ['one', 'many', 'rating', 'yes_no', 'short', 'long']
const CHOICE: readonly QuestionKind[] = ['one', 'many']
/** The refusal codes the server sends that have their own words; anything else reads "could not save". */
const KNOWN = ['title_required', 'title_too_long', 'title_newline', 'intro_too_long', 'bad_audience', 'bad_opens_at',
  'bad_closes_at', 'closes_at_past', 'closes_before_opens', 'no_questions', 'too_many_questions', 'bad_question_kind',
  'question_required', 'question_too_long', 'question_newline', 'hint_too_long', 'options_count', 'option_required',
  'option_too_long', 'option_duplicate', 'bad_options', 'questions_locked', 'answered_locked']
const FIELD = 'w-full rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-ground-900 disabled:bg-ground-50 disabled:text-ground-500'
const LABEL = 'flex flex-col gap-1 text-sm font-medium text-ground-700'
const LINK = 'inline-flex min-h-11 items-center text-sm font-medium text-primary-600 hover:underline disabled:opacity-50'

type T = (k: string, vars?: Record<string, string>) => string
export type Done = 'published' | 'scheduled' | 'draft' | 'saved'

export function blankQuestion(kind: QuestionKind = 'one'): SurveyQuestionInput {
  return { kind, text: '', hint: '', required: true, mentor_only: false, options: CHOICE.includes(kind) ? ['', ''] : [] }
}

/** The question as the server takes it: options only for a choice question, trimmed, empty lines dropped. */
export function cleanQuestion(q: SurveyQuestionInput): SurveyQuestionInput {
  return {
    kind: q.kind, text: q.text.trim(), hint: q.hint.trim(), required: q.required, mentor_only: q.mentor_only,
    options: CHOICE.includes(q.kind) ? q.options.map((o) => o.trim()).filter(Boolean) : [],
  }
}

function QuestionEditor({ q, n, limits, t, onChange, onDone }: {
  q: SurveyQuestionInput; n: number; limits: SurveyLimits; t: T
  onChange: (q: SurveyQuestionInput) => void; onDone: () => void
}) {
  const choice = CHOICE.includes(q.kind)
  return (
    <div className="space-y-3 rounded-lg border border-info-300 bg-ground-0 p-4" data-testid={`survey-qedit-${n}`}>
      <div className="flex flex-wrap gap-3">
        <label className={`${LABEL} min-w-[12rem] flex-1`}>{t(`${K}.form.questionType`)}
          <select value={q.kind} data-testid={`survey-qkind-${n}`} className={FIELD}
            onChange={(e) => {
              const kind = e.target.value as QuestionKind
              onChange({ ...q, kind, options: CHOICE.includes(kind) ? (q.options.length ? q.options : ['', '']) : [] })
            }}>
            {KINDS.map((k) => <option key={k} value={k}>{t(`${K}.kind.${k}`)}</option>)}
          </select>
        </label>
      </div>
      <label className={LABEL}>{t(`${K}.form.questionText`)}
        <input value={q.text} maxLength={limits.question} data-testid={`survey-qtext-${n}`} className={FIELD}
          onChange={(e) => onChange({ ...q, text: e.target.value })} />
      </label>
      <label className={LABEL}>{t(`${K}.form.hint`)}
        <input value={q.hint} maxLength={limits.hint} className={FIELD} placeholder={q.kind === 'rating' ? t(`${K}.form.hintRating`) : ''}
          onChange={(e) => onChange({ ...q, hint: e.target.value })} />
      </label>
      {choice && (
        <label className={LABEL}>{t(`${K}.form.options`, { max: String(limits.options) })}
          <textarea rows={Math.max(3, q.options.length)} data-testid={`survey-qoptions-${n}`} className={FIELD}
            value={q.options.join('\n')} onChange={(e) => onChange({ ...q, options: e.target.value.split('\n') })} />
        </label>
      )}
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        <span className="flex items-center gap-3 text-sm text-ground-800">
          <Toggle on={q.required} onChange={(v) => onChange({ ...q, required: v })} label={t(`${K}.form.required`)} />
          {t(`${K}.form.required`)}
        </span>
        <span className="flex items-center gap-3 text-sm text-ground-800">
          <Toggle on={q.mentor_only} onChange={(v) => onChange({ ...q, mentor_only: v })} label={t(`${K}.form.mentorOnly`)} />
          {t(`${K}.form.mentorOnly`)}
        </span>
      </div>
      <button type="button" onClick={onDone} className={LINK} data-testid={`survey-qdone-${n}`}>{t(`${K}.form.doneQuestion`)}</button>
    </div>
  )
}

/**
 * The New / Edit card on Programme → Surveys (the SurveysAdmin board): title, introduction, who it is for,
 * when it opens and closes, the questions (up to 30, six types), and the two optional emails.
 *
 * ⚠ ONCE ANYBODY HAS ANSWERED (`row.locked`) the questions, the audience and the opening time are shown but
 * locked — the server refuses them too (`questions_locked` / `answered_locked`) — so answers stay
 * comparable. The title, the introduction, the closing date and the email choices can still change.
 */
export default function SurveyForm({ row, audiences, emailOn, limits, programme, token, t, onCancel, onSaved }: {
  row: SurveyRow | null
  audiences: SurveyAudience[]
  emailOn: boolean
  limits: SurveyLimits
  programme?: string
  token: string | null
  t: T
  onCancel: () => void
  onSaved: (row: SurveyRow, done: Done) => void
}) {
  const locked = !!row?.locked
  const published = !!row && row.status !== 'draft'
  const opens = mytParts(row?.opens_at ?? null)
  const closes = mytParts(row?.closes_at ?? null)
  const [title, setTitle] = useState(row?.title ?? '')
  const [intro, setIntro] = useState(row?.intro ?? '')
  const [audience, setAudience] = useState(row?.programme?.code ?? '')
  const [later, setLater] = useState(!!row && row.status === 'scheduled')
  const [openDate, setOpenDate] = useState(opens.date)
  const [openTime, setOpenTime] = useState(opens.time || '09:00')
  const [closeDate, setCloseDate] = useState(closes.date)
  const [closeTime, setCloseTime] = useState(closes.time || '23:59')
  const [questions, setQuestions] = useState<SurveyQuestionInput[]>(
    row?.questions.map(({ id: _id, ...q }) => q) ?? [blankQuestion()])
  const [editingQ, setEditingQ] = useState<number | null>(row ? null : 0)
  const [emailOnOpen, setEmailOnOpen] = useState(row?.email_on_open ?? false)
  const [remind, setRemind] = useState(row?.remind ?? false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const move = (i: number, by: number) => setQuestions((qs) => {
    const next = [...qs]
    const [q] = next.splice(i, 1)
    next.splice(i + by, 0, q)
    return next
  })

  const save = async (action: SurveyAction | 'edit') => {
    if (!token) return
    setError('')
    const closesAt = mytInstant(closeDate, closeTime)
    const opensAt = later ? mytInstant(openDate, openTime) : null
    if (!closesAt || (later && !opensAt && !locked)) { setError(t(`${K}.error.badTime`)); return }
    // ⚠ A DATE IS SENT ONLY WHEN IT CHANGED: the boxes hold minutes, a stored time may hold seconds ("Close
    // now"), and a closed survey's unchanged past closing date must not read as a new one in the past.
    const payload: Partial<SurveyInput> = { title, intro, email_on_open: emailOnOpen, remind }
    if (!row || closeDate !== closes.date || closeTime !== closes.time) payload.closes_at = closesAt
    if (!locked) {
      payload.programme = audience || null
      payload.questions = questions.map(cleanQuestion)
      if (opensAt && (!row || openDate !== opens.date || openTime !== opens.time || row.status === 'draft')) {
        payload.opens_at = opensAt
      }
      // Review 4: "Now" on a draft or a scheduled one is said OUTRIGHT — sending no time kept the one an
      // earlier save left, so a draft saved for later published as scheduled.
      if (!later && row && (row.status === 'draft' || row.status === 'scheduled')) payload.opens_now = true
    }
    if (action !== 'edit') payload.action = action
    setBusy(true)
    try {
      const saved = row
        ? await updateSurvey(row.id, payload, { token })
        : await createSurvey(payload as SurveyInput, programme, { token })
      onSaved(saved, action === 'edit' ? 'saved' : action === 'draft' ? 'draft'
        : saved.status === 'scheduled' ? 'scheduled' : 'published')
    } catch (err) {
      const e = err as { code?: string; body?: { detail?: number } }
      const code = e?.code ?? ''
      const place = typeof e?.body?.detail === 'number' ? ` ${t(`${K}.error.atQuestion`, { n: String(e.body.detail + 1) })}` : ''
      setError(`${t(`${K}.error.${KNOWN.includes(code) ? code : 'generic'}`)}${place}`)
    } finally { setBusy(false) }
  }

  return (
    <section className="max-w-3xl space-y-4 rounded-xl border-2 border-info-500 bg-ground-0 p-5" data-testid="survey-form">
      <h2 className="text-base font-semibold text-ground-900">{t(row ? `${K}.form.editTitle` : `${K}.form.newTitle`)}</h2>
      <label className={LABEL}>{t(`${K}.form.title`)}
        <input value={title} maxLength={limits.title} onChange={(e) => setTitle(e.target.value)}
          data-testid="survey-title" className={FIELD} />
      </label>
      <label className={LABEL}>{t(`${K}.form.intro`)}
        <textarea value={intro} maxLength={limits.intro} rows={2} onChange={(e) => setIntro(e.target.value)}
          data-testid="survey-intro" className={FIELD} />
      </label>

      <div className="flex flex-wrap gap-4">
        <label className={`${LABEL} min-w-[14rem] flex-1`}>{t(`${K}.form.for`)}
          <select value={audience} disabled={locked} onChange={(e) => setAudience(e.target.value)}
            data-testid="survey-audience" className={FIELD}>
            {audiences.map((a) => (
              <option key={a.programme ?? ''} value={a.programme ?? ''}>
                {a.programme ? t(`${K}.forGift`, { name: a.name, count: String(a.count) })
                  : t(`${K}.forAll`, { count: String(a.count) })}
              </option>
            ))}
          </select>
        </label>
        <label className={`${LABEL} min-w-[14rem] flex-1`}>{t(`${K}.form.opens`)}
          <select value={later ? 'later' : 'now'} disabled={locked || (published && row?.status !== 'scheduled')}
            onChange={(e) => setLater(e.target.value === 'later')} data-testid="survey-when" className={FIELD}>
            <option value="now">{t(published ? `${K}.form.asIs` : `${K}.form.now`)}</option>
            <option value="later">{t(`${K}.form.later`)}</option>
          </select>
        </label>
      </div>
      {later && !locked && (
        <div className="flex flex-wrap gap-4">
          <label className={LABEL}>{t(`${K}.form.openDate`)}
            <input type="date" value={openDate} onChange={(e) => setOpenDate(e.target.value)}
              data-testid="survey-open-date" className={FIELD} />
          </label>
          <label className={LABEL}>{t(`${K}.form.time`)}
            <input value={openTime} inputMode="numeric" placeholder="09:00" onChange={(e) => setOpenTime(e.target.value)}
              data-testid="survey-open-time" className={`${FIELD} w-28`} />
          </label>
        </div>
      )}
      <div className="flex flex-wrap gap-4">
        <label className={LABEL}>{t(`${K}.form.closeDate`)}
          <input type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)}
            data-testid="survey-close-date" className={FIELD} />
        </label>
        <label className={LABEL}>{t(`${K}.form.time`)}
          <input value={closeTime} inputMode="numeric" placeholder="23:59" onChange={(e) => setCloseTime(e.target.value)}
            data-testid="survey-close-time" className={`${FIELD} w-28`} />
        </label>
      </div>

      <h3 className="pt-2 text-[15px] font-semibold text-ground-900">{t(`${K}.form.questions`)}</h3>
      <ol className="space-y-3" data-testid="survey-questions">
        {questions.map((q, i) => (
          <li key={i}>
            {editingQ === i && !locked ? (
              <QuestionEditor q={q} n={i} limits={limits} t={t}
                onChange={(next) => setQuestions((qs) => qs.map((x, j) => (j === i ? next : x)))}
                onDone={() => setEditingQ(null)} />
            ) : (
              <div className="rounded-lg border border-ground-200 p-4" data-testid={`survey-qsummary-${i}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <strong className="break-words text-sm text-ground-900">{i + 1}. {q.text || t(`${K}.form.untitled`)}</strong>
                  <span className="rounded-full bg-ground-100 px-2 py-0.5 text-xs text-ground-700">{t(`${K}.kind.${q.kind}`)}</span>
                </div>
                {CHOICE.includes(q.kind) && (
                  <p className="mt-1 break-words text-xs text-ground-600">{q.options.filter(Boolean).join(' · ')}</p>
                )}
                <p className="mt-1 text-xs text-ground-600">
                  {[t(q.required ? `${K}.form.required` : `${K}.form.optional`), q.hint,
                    q.mentor_only ? t(`${K}.form.mentorOnlyShort`) : ''].filter(Boolean).join(' · ')}
                </p>
                {!locked && (
                  <div className="flex flex-wrap gap-x-4">
                    <button type="button" className={LINK} data-testid={`survey-qedit-btn-${i}`}
                      onClick={() => setEditingQ(i)}>{t(`${K}.form.edit`)}</button>
                    {i > 0 && <button type="button" className={LINK} data-testid={`survey-qup-${i}`}
                      onClick={() => { move(i, -1); setEditingQ(null) }}>{t(`${K}.form.moveUp`)}</button>}
                    <button type="button" className={LINK} data-testid={`survey-qremove-${i}`}
                      // Review 1: a published survey keeps at least one question (the server says no_questions).
                      disabled={published && questions.length === 1}
                      onClick={() => { setQuestions((qs) => qs.filter((_x, j) => j !== i)); setEditingQ(null) }}>
                      {t(`${K}.form.remove`)}
                    </button>
                  </div>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>
      {!locked && questions.length < limits.questions && (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" data-testid="survey-add-question"
            onClick={() => { setQuestions((qs) => [...qs, blankQuestion()]); setEditingQ(questions.length) }}
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800">
            {t(`${K}.form.addQuestion`)}
          </button>
          <span className="text-xs text-ground-600">{t(`${K}.form.types`)}</span>
        </div>
      )}

      <div className="flex items-start gap-3">
        <Toggle on={emailOnOpen} onChange={setEmailOnOpen} label={t(`${K}.form.emailOpen`)} />
        <span className="text-sm text-ground-800">
          {t(`${K}.form.emailOpen`)}
          <span className="block text-xs text-ground-600">{t(emailOn ? `${K}.form.emailNote` : `${K}.form.emailOff`)}</span>
        </span>
      </div>
      <div className="flex items-start gap-3">
        <Toggle on={remind} onChange={setRemind} label={t(`${K}.form.remind`)} />
        <span className="text-sm text-ground-800">{t(`${K}.form.remind`)}</span>
      </div>

      {error && <p className="text-sm text-critical-600" role="alert" data-testid="survey-error">{error}</p>}
      <div className="flex flex-wrap gap-2">
        {published ? (
          <button type="button" disabled={busy} onClick={() => save('edit')} data-testid="survey-save"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink disabled:opacity-60">
            {t(`${K}.btn.save`)}
          </button>
        ) : (<>
          <button type="button" disabled={busy} onClick={() => save('publish')} data-testid="survey-primary"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink disabled:opacity-60">
            {t(later ? `${K}.btn.schedule` : `${K}.btn.publish`)}
          </button>
          <button type="button" disabled={busy} onClick={() => save('draft')} data-testid="survey-draft"
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800 disabled:opacity-60">
            {t(`${K}.btn.draft`)}
          </button>
        </>)}
        <button type="button" disabled={busy} onClick={onCancel}
          className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800">
          {t('common.cancel')}
        </button>
      </div>
      <p className="text-xs text-ground-600">{t(locked ? `${K}.form.lockedNote` : `${K}.form.lockNote`)}</p>
    </section>
  )
}
