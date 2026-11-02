'use client'

import { useEffect, useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  getMyModule, getMyModules, lessonFileUrl, markLessonRead, myTaskFileUrl, sendReflection, sendTaskFile,
  type MyModule, type MyModuleCard,
} from '@/lib/api/bursaryGrowth'
import { linkify } from './BursaryNews'

const P = 'bursaryTabs.growth'
/** ⚠ ONE BOX LEVEL ON A PHONE (mobile standard, rule 15): below `sm` a module is a full-width section (no border,
 *  no radius, the page's 16 px gutter kept inside); from `sm` it is a card. Nothing inside is a bordered box. */
const SECTION = '-mx-4 bg-ground-0 px-4 py-5 sm:mx-0 sm:rounded-2xl sm:p-5 sm:shadow-sm'
const PRIMARY = 'h-12 w-full rounded-lg bg-brand-fill text-base font-semibold text-brand-fill-ink disabled:opacity-60'
const LINK = 'inline-flex min-h-11 items-center text-sm font-medium text-primary-600 hover:underline'
const FIELD = 'w-full rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-base text-ground-900'
const KNOWN = ['text_required', 'text_too_long', 'lessons_first', 'reviewed', 'module_closed', 'unsupported_format',
  'file_too_large', 'upload_incomplete']
const MAX_BYTES = 10 * 1024 * 1024

type T = (k: string, vars?: Record<string, string>) => string

function errorWords(t: T, err: unknown): string {
  const code = (err as { code?: string })?.code ?? ''
  return t(`${P}.error.${KNOWN.includes(code) ? code : 'generic'}`)
}

/** Open a signed link in a new tab: the tab is opened on the tap (so no blocker stops it), then pointed. */
async function openSigned(get: () => Promise<{ url: string }>, onFail: () => void) {
  const tab = typeof window !== 'undefined' ? window.open('', '_blank') : null
  try {
    const { url } = await get()
    if (tab) tab.location.href = url
  } catch { tab?.close(); onFail() }
}

function videoHost(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return '' }
}

export function lineOf(t: T, m: Pick<MyModuleCard, 'due_on' | 'lessons' | 'task_kind'>): string {
  const lessons = t(m.lessons === 1 ? `${P}.oneLesson` : `${P}.lessons`, { count: String(m.lessons) })
  return [m.due_on ? t(`${P}.due`, { date: formatDate(m.due_on) }) : t(`${P}.noDue`),
    m.task_kind === 'none' ? lessons : t(`${P}.withTask`, { lessons, task: t(`${P}.task.${m.task_kind}`) })].join(' · ')
}

function Card({ m, org, t, onOpen }: { m: MyModuleCard; org: string; t: T; onOpen: () => void }) {
  const pct = m.lessons ? Math.round((m.read / m.lessons) * 100) : 0
  return (
    <section className={SECTION} data-testid={`module-${m.id}`}>
      <h2 className="break-words text-[17px] font-semibold text-ground-900">{m.title}</h2>
      <p className="mt-1 text-xs text-ground-600">{lineOf(t, m)}</p>
      {m.summary && <p className="mt-2 whitespace-pre-line break-words text-[15px] text-ground-700">{m.summary}</p>}
      {m.done ? (
        <p className="mt-2 text-sm text-ground-700" data-testid={`module-done-${m.id}`}>
          <span className="font-semibold text-positive-700">{t(`${P}.done`)}</span>
          {m.reviewed ? ` · ${t(`${P}.reviewed`, { org })}` : ''}
        </p>
      ) : (
        <div role="img" aria-label={t(`${P}.readOf`, { read: String(m.read), count: String(m.lessons) })}
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-ground-200">
          <div className="h-full bg-brand-fill" style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-x-3 text-xs text-ground-600">
        {!m.done && <span>{t(`${P}.readOf`, { read: String(m.read), count: String(m.lessons) })}</span>}
        <button type="button" onClick={onOpen} className={LINK} data-testid={`module-open-${m.id}`}>
          {t(m.done || !m.can_act ? `${P}.open` : m.started ? `${P}.continue` : `${P}.start`)}
        </button>
      </div>
    </section>
  )
}

function Task({ m, org, token, t, onSaved }: {
  m: MyModule; org: string; token: string | null; t: T; onSaved: (m: MyModule, toDo: number) => void
}) {
  const task = m.task
  const [text, setText] = useState(task.text)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const kind = task.kind as 'reflection' | 'upload'

  const send = async () => {
    if (!token) return
    setError('')
    if (kind === 'reflection' && !text.trim()) { setError(t(`${P}.error.text_required`)); return }
    if (kind === 'upload' && file && file.size > MAX_BYTES) { setError(t(`${P}.error.file_too_large`)); return }
    setBusy(true)
    try {
      const r = kind === 'reflection' ? await sendReflection(m.id, text.trim(), { token })
        : await sendTaskFile(m.id, file as File, { token })
      setFile(null)
      onSaved(r.module, r.to_do)
    } catch (err) { setError(errorWords(t, err)) } finally { setBusy(false) }
  }

  return (
    <section className={SECTION} data-testid="module-task">
      <h3 className="text-[17px] font-semibold text-ground-900">{t(`${P}.taskTitle.${kind}`)}</h3>
      {task.prompt && <p className="mt-1 whitespace-pre-line break-words text-[15px] text-ground-700">{task.prompt}</p>}
      {task.reviewed_at && (
        <p className="mt-2 text-sm text-positive-700" data-testid="module-reviewed">
          {t(`${P}.reviewedOn`, { date: formatDate(task.reviewed_at) })}
          {task.comment && <span className="block whitespace-pre-line break-words text-ground-800">
            {t(`${P}.comment`, { org, comment: task.comment })}</span>}
        </p>
      )}
      {task.file && (
        <button type="button" className={LINK} data-testid="module-my-file"
          onClick={() => openSigned(() => myTaskFileUrl(m.id, { token: token ?? undefined }), () => setError(t(`${P}.error.generic`)))}>
          {t(`${P}.yourFile`, { name: task.file.name })}
        </button>
      )}
      {!task.can_change ? (
        kind === 'reflection' && task.text
          ? <p className="mt-2 whitespace-pre-line break-words text-[15px] text-ground-900">{task.text}</p>
          : !task.sent_at && m.can_act && <p className="mt-2 text-sm text-ground-600">{t(`${P}.lessonsFirst`)}</p>
      ) : (
        <div className="mt-3 space-y-3">
          {kind === 'reflection' ? (
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} maxLength={5000}
              aria-label={t(`${P}.taskTitle.reflection`)} data-testid="module-reflection" className={FIELD} />
          ) : (
            <label className="block text-sm text-ground-700">{t(`${P}.chooseFile`)}
              <input type="file" accept="application/pdf,image/jpeg,image/png" data-testid="module-file"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-1 block w-full text-sm" />
            </label>
          )}
          {error && <p className="text-sm text-critical-600" role="alert" data-testid="module-error">{error}</p>}
          <button type="button" disabled={busy || (kind === 'upload' && !file)} onClick={send} className={PRIMARY}
            data-testid="module-send">
            {t(task.sent_at ? `${P}.change.${kind}` : `${P}.send.${kind}`)}
          </button>
          <p className="text-xs text-ground-600">{t(`${P}.who`, { org })}</p>
        </div>
      )}
      {task.sent_at && (
        <p className="mt-2 text-xs text-ground-600" role="status" data-testid="module-sent">
          {t(`${P}.sent`, { date: formatDate(task.sent_at) })}
        </p>
      )}
      {!task.can_change && error && <p className="mt-2 text-sm text-critical-600" role="alert">{error}</p>}
    </section>
  )
}

function Opened({ id, org, token, t, onBack, onCount }: {
  id: number; org: string; token: string | null; t: T; onBack: () => void; onCount: (n: number) => void
}) {
  const [m, setM] = useState<MyModule | null>(null)
  const [at, setAt] = useState(0)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const top = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!token) return
    let live = true
    getMyModule(id, { token })
      .then((d) => {
        if (!live) return
        setM(d)
        const first = d.lessons.findIndex((l) => !l.read)
        setAt(first === -1 ? d.lessons.length : first)   // the task when every lesson is read
      })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [id, token])

  const go = (n: number) => { setAt(n); setError(''); top.current?.scrollIntoView?.({ block: 'start' }) }
  const back = (
    <button type="button" onClick={onBack} className={LINK} data-testid="module-back">← {t(`${P}.back`)}</button>
  )
  if (failed) return <div>{back}<p className="text-sm text-critical-600" role="alert">{t(`${P}.loadFailed`)}</p></div>
  if (!m) return back

  const lesson = m.lessons[at]
  const last = at === m.lessons.length - 1
  const markRead = async () => {
    if (!token || !lesson) return
    setBusy(true); setError('')
    try {
      const r = await markLessonRead(m.id, lesson.id, { token })
      setM(r.module); onCount(r.to_do)
      go(at + 1)
    } catch (err) { setError(errorWords(t, err)) } finally { setBusy(false) }
  }

  return (
    <div ref={top} className="space-y-4" data-testid={`module-opened-${m.id}`}>
      {back}
      {!m.can_act && <p className="text-sm text-ground-600">{t(`${P}.readOnly`)}</p>}
      {lesson ? (
        <section className={SECTION} data-testid={`lesson-${lesson.id}`}>
          <p className="text-xs text-ground-600">{t(`${P}.lessonOf`, { n: String(at + 1), count: String(m.lessons.length) })}</p>
          <h2 className="mt-1 break-words text-lg font-semibold text-ground-900">{lesson.title}</h2>
          {lesson.video_url && (
            <a href={lesson.video_url} target="_blank" rel="noopener noreferrer" data-testid="lesson-video"
              className="mt-2 flex min-h-14 items-center gap-2 text-[15px] font-medium text-primary-600 underline">
              ▶ {t(`${P}.watch`)} <span className="text-xs text-ground-600 no-underline">{videoHost(lesson.video_url)}</span>
            </a>
          )}
          {lesson.file && (
            <button type="button" className={LINK} data-testid="lesson-file"
              onClick={() => openSigned(() => lessonFileUrl(m.id, lesson.id, { token: token ?? undefined }), () => setError(t(`${P}.error.generic`)))}>
              {t(`${P}.openFile`, { name: lesson.file.name })}
            </button>
          )}
          {lesson.body && (
            <p className="mt-3 whitespace-pre-line break-words text-[15px] leading-relaxed text-ground-800">{linkify(lesson.body)}</p>
          )}
          {error && <p className="mt-3 text-sm text-critical-600" role="alert" data-testid="module-error">{error}</p>}
          <div className="mt-4 space-y-2">
            {m.can_act && !lesson.read ? (
              <button type="button" disabled={busy} onClick={markRead} className={PRIMARY} data-testid="lesson-read">
                {t(last ? `${P}.markLast` : `${P}.markRead`)}
              </button>
            ) : (
              <button type="button" onClick={() => go(at + 1)} className={PRIMARY} data-testid="lesson-next">
                {t(last ? (m.task.kind === 'none' ? `${P}.back` : `${P}.toTask`) : `${P}.next`)}
              </button>
            )}
            {at > 0 && <button type="button" onClick={() => go(at - 1)} className={LINK}>{t(`${P}.prev`)}</button>}
          </div>
        </section>
      ) : (
        <>
          {m.done && <p className="text-sm font-semibold text-positive-700" data-testid="module-finished">{t(`${P}.finished`)}</p>}
          {m.task.kind !== 'none' && <Task m={m} org={org} token={token} t={t} onSaved={(next, n) => { setM(next); onCount(n) }} />}
          {m.lessons.length > 0 && (
            <button type="button" onClick={() => go(m.lessons.length - 1)} className={LINK}>{t(`${P}.prev`)}</button>
          )}
        </>
      )}
    </div>
  )
}

/**
 * Her Growth tab on My Bursary (student maintenance S10; the owner-approved ModuleStudent board): development
 * modules, each with a progress bar; open one → ONE lesson at a time, "I have read this — next lesson" (marks it
 * read, idempotent), then the task (a reflection or a file); she can change it until staff mark it reviewed,
 * then sees their comment.
 *
 * ⚠ WHAT SHE SEES IS THE SERVER'S ALLOWLIST (`development.student_modules` / `student_module`). Optional — never
 * touches money, standing or eligibility. A file opens through a 300-second signed link fetched on the tap.
 * Phone-first (rule 15): sections on a phone, 44 px targets, 16 px fields. Words: `bursaryTabs.growth`.
 */
export default function BursaryGrowth({ token, onCount }: { token: string | null; onCount?: (n: number) => void }) {
  const { t } = useT()
  const [items, setItems] = useState<MyModuleCard[] | null>(null)
  const [org, setOrg] = useState('')
  const [failed, setFailed] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [reload, setReload] = useState(0)
  const told = useRef(onCount)
  told.current = onCount

  useEffect(() => {
    if (!token) return
    let live = true
    getMyModules({ token })
      .then((d) => { if (live) { setItems(d.modules); setOrg(d.organisation); setFailed(false) } })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [token, reload])

  if (failed) return <p className="text-sm text-critical-600">{t(`${P}.loadFailed`)}</p>
  if (open !== null) {
    return <Opened id={open} org={org} token={token} t={t} onCount={(n) => told.current?.(n)}
      onBack={() => { setOpen(null); setReload((n) => n + 1) }} />
  }
  if (!items) return null
  if (items.length === 0) {
    return <p className={`${SECTION} text-sm text-ground-600`} data-testid="growth-empty">{t(`${P}.empty`)}</p>
  }
  return (
    <>
      {items.map((m) => <Card key={m.id} m={m} org={org} t={t} onOpen={() => setOpen(m.id)} />)}
      <p className="px-1 text-xs text-ground-600">{t(`${P}.footnote`)}</p>
    </>
  )
}
