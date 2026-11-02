'use client'

import { useState } from 'react'
import Toggle from '@/components/Toggle'
import { mytInstant, mytParts } from '@/components/announcements/AnnouncementForm'
import {
  createModule, lessonFileLink, removeLessonFile, updateModule, uploadLessonFile,
  type FileInfo, type ModuleAction, type ModuleAudience, type ModuleInput, type ModuleLimits, type ModuleRow,
  type TaskKind,
} from '@/lib/admin-api/development'
import { openSigned } from './shared'

const K = 'admin.development'
const TASKS: readonly TaskKind[] = ['none', 'reflection', 'upload']
/** The refusal codes the server sends that have their own words; anything else reads "could not save". */
const KNOWN = ['title_required', 'title_too_long', 'title_newline', 'summary_too_long', 'bad_audience', 'bad_publish_at',
  'bad_due_on', 'due_before_publish', 'remind_needs_due', 'bad_task_kind', 'prompt_required', 'prompt_too_long',
  'no_lessons', 'too_many_lessons', 'bad_lesson', 'bad_lessons', 'lesson_title_required', 'lesson_title_too_long',
  'lesson_title_newline', 'lesson_body_too_long', 'bad_video', 'video_too_long', 'video_or_file', 'task_locked',
  'started_locked', 'unsupported_format', 'file_too_large', 'upload_incomplete', 'storage_unavailable']
const FIELD = 'w-full rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-ground-900 disabled:bg-ground-50 disabled:text-ground-500'
const LABEL = 'flex flex-col gap-1 text-sm font-medium text-ground-700'
const LINK = 'inline-flex min-h-11 items-center text-sm font-medium text-primary-600 hover:underline disabled:opacity-50'
const PILL = 'min-h-11 rounded-full border px-4 text-sm'

type T = (k: string, vars?: Record<string, string>) => string
export type Done = 'published' | 'scheduled' | 'draft' | 'saved'
type Lesson = { id?: number; title: string; body: string; video_url: string; file: FileInfo | null }

export function words(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

function refusal(t: T, err: unknown): string {
  const e = err as { code?: string; body?: { detail?: number } }
  const code = e?.code ?? ''
  const place = typeof e?.body?.detail === 'number' ? ` ${t(`${K}.error.atLesson`, { n: String(e.body.detail + 1) })}` : ''
  return `${t(`${K}.error.${KNOWN.includes(code) ? code : 'generic'}`)}${place}`
}

function LessonEditor({ l, n, moduleId, limits, token, t, onChange, onDone, onError }: {
  l: Lesson; n: number; moduleId?: number; limits: ModuleLimits; token: string | null; t: T
  onChange: (l: Lesson) => void; onDone: () => void; onError: (text: string) => void
}) {
  const [uploading, setUploading] = useState(false)
  const attach = async (file: File | undefined) => {
    if (!file || !token || !moduleId || !l.id) return
    if (file.size > limits.file_bytes) { onError(t(`${K}.error.file_too_large`)); return }
    setUploading(true)
    try {
      const row = await uploadLessonFile(moduleId, l.id, file, { token })
      onChange({ ...l, file: row.lessons.find((x) => x.id === l.id)?.file ?? null })
    } catch (err) { onError(refusal(t, err)) } finally { setUploading(false) }
  }
  const detach = async () => {
    if (!token || !moduleId || !l.id) return
    try { await removeLessonFile(moduleId, l.id, { token }); onChange({ ...l, file: null }) }
    catch (err) { onError(refusal(t, err)) }
  }
  return (
    <div className="space-y-3 rounded-lg border border-info-300 bg-ground-0 p-4" data-testid={`lesson-edit-${n}`}>
      <label className={LABEL}>{t(`${K}.form.lessonTitle`)}
        <input value={l.title} maxLength={limits.lesson_title} data-testid={`lesson-title-${n}`} className={FIELD}
          onChange={(e) => onChange({ ...l, title: e.target.value })} />
      </label>
      <label className={LABEL}>{t(`${K}.form.lessonBody`)}
        <textarea value={l.body} maxLength={limits.lesson_body} rows={8} data-testid={`lesson-body-${n}`} className={FIELD}
          onChange={(e) => onChange({ ...l, body: e.target.value })} />
      </label>
      <label className={LABEL}>{t(`${K}.form.video`)}
        <input value={l.video_url} disabled={!!l.file} inputMode="url" placeholder="https://youtu.be/…"
          data-testid={`lesson-video-${n}`} className={FIELD} onChange={(e) => onChange({ ...l, video_url: e.target.value })} />
      </label>
      <div className="space-y-1 text-sm text-ground-700">
        <span className="font-medium">{t(`${K}.form.file`)}</span>
        {l.file ? (
          <span className="flex flex-wrap items-center gap-x-4">
            <span className="break-all">{l.file.name}</span>
            <button type="button" className={LINK} onClick={() => openSigned(
              () => lessonFileLink(moduleId as number, l.id as number, { token: token ?? undefined }), () => onError(t(`${K}.error.generic`)))}>
              {t(`${K}.form.fileOpen`)}</button>
            <button type="button" className={LINK} data-testid={`lesson-file-remove-${n}`} onClick={detach}>
              {t(`${K}.form.fileRemove`)}</button>
          </span>
        ) : !moduleId || !l.id ? (
          <p className="text-xs text-ground-600">{t(`${K}.form.fileSaveFirst`)}</p>
        ) : l.video_url.trim() ? (
          <p className="text-xs text-ground-600">{t(`${K}.form.fileOr`)}</p>
        ) : (
          <input type="file" accept="application/pdf,image/jpeg,image/png" disabled={uploading}
            data-testid={`lesson-file-${n}`} onChange={(e) => attach(e.target.files?.[0])} className="block w-full text-sm" />
        )}
        {uploading && <p className="text-xs text-ground-600" role="status">{t(`${K}.form.uploading`)}</p>}
      </div>
      <button type="button" onClick={onDone} className={LINK} data-testid={`lesson-done-${n}`}>{t(`${K}.form.doneLesson`)}</button>
    </div>
  )
}

/**
 * The New / Edit card on Programme → Development (the ModulesAdmin board): title, summary, who it is for, when it
 * is published, an optional due date, the lessons (1–20: a title, text, one video link OR one file), the task at
 * the end, and the two optional emails.
 *
 * ⚠ A LESSON'S FILE is attached to a SAVED lesson (it needs the lesson's id for its private key): save the
 * module (a draft is fine), then attach. The server reads the file's type and size from its bytes.
 * ⚠ ONCE A SCHOLAR HAS STARTED (`row.locked`) the task type, the audience and the publishing time are shown but
 * locked — the server refuses them too (`task_locked` / `started_locked`). Lessons and texts still change.
 */
export default function ModuleForm({ row, audiences, emailOn, limits, programme, token, t, onCancel, onSaved }: {
  row: ModuleRow | null
  audiences: ModuleAudience[]
  emailOn: boolean
  limits: ModuleLimits
  programme?: string
  token: string | null
  t: T
  onCancel: () => void
  onSaved: (row: ModuleRow, done: Done, keepOpen: boolean) => void
}) {
  const locked = !!row?.locked
  const live = !!row && (row.status === 'published' || row.status === 'archived')
  const when = mytParts(row?.publish_at ?? null)
  const [title, setTitle] = useState(row?.title ?? '')
  const [summary, setSummary] = useState(row?.summary ?? '')
  const [audience, setAudience] = useState(row?.programme?.code ?? '')
  const [later, setLater] = useState(!!row && row.status === 'scheduled')
  const [date, setDate] = useState(when.date)
  const [time, setTime] = useState(when.time || '09:00')
  const [due, setDue] = useState(row?.due_on ?? '')
  const [lessons, setLessons] = useState<Lesson[]>(row?.lessons.map((l) => ({ ...l })) ?? [{ title: '', body: '', video_url: '', file: null }])
  const [editingL, setEditingL] = useState<number | null>(row ? null : 0)
  const [task, setTask] = useState<TaskKind>(row?.task_kind ?? 'none')
  const [prompt, setPrompt] = useState(row?.task_prompt ?? '')
  const [emailPublish, setEmailPublish] = useState(row?.email_on_publish ?? false)
  const [remind, setRemind] = useState(row?.remind ?? false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const move = (i: number) => setLessons((ls) => {
    const next = [...ls]
    const [l] = next.splice(i, 1)
    next.splice(i - 1, 0, l)
    return next
  })

  const save = async (action: ModuleAction | 'edit') => {
    if (!token) return
    setError('')
    const at = later ? mytInstant(date, time) : null
    if (later && !at && !locked) { setError(t(`${K}.error.badTime`)); return }
    const payload: Partial<ModuleInput> = {
      title, summary, due_on: due || null, task_prompt: prompt, email_on_publish: emailPublish, remind: remind && !!due,
      lessons: lessons.map((l) => ({ ...(l.id ? { id: l.id } : {}), title: l.title.trim(), body: l.body,
        video_url: l.file ? '' : l.video_url.trim() })),
    }
    if (!locked) {
      payload.programme = audience || null
      payload.task_kind = task
      if (at && (!row || date !== when.date || time !== when.time || row.status === 'draft')) payload.publish_at = at
      if (!later && row && (row.status === 'draft' || row.status === 'scheduled')) payload.publish_now = true
    }
    if (action !== 'edit') payload.action = action
    setBusy(true)
    try {
      const saved = row ? await updateModule(row.id, payload, { token })
        : await createModule(payload as ModuleInput, programme, { token })
      const done: Done = action === 'edit' ? 'saved' : action === 'draft' ? 'draft'
        : saved.status === 'scheduled' ? 'scheduled' : 'published'
      // A new draft stays open, so its lessons can take files (they need the saved lesson ids).
      onSaved(saved, done, !row && action === 'draft')
    } catch (err) { setError(refusal(t, err)) } finally { setBusy(false) }
  }

  return (
    <section className="max-w-3xl space-y-4 rounded-xl border-2 border-info-500 bg-ground-0 p-5" data-testid="module-form">
      <h2 className="text-base font-semibold text-ground-900">{t(row ? `${K}.form.editTitle` : `${K}.form.newTitle`)}</h2>
      <label className={LABEL}>{t(`${K}.form.title`)}
        <input value={title} maxLength={limits.title} onChange={(e) => setTitle(e.target.value)} data-testid="module-title" className={FIELD} />
      </label>
      <label className={LABEL}>{t(`${K}.form.summary`)}
        <textarea value={summary} maxLength={limits.summary} rows={2} onChange={(e) => setSummary(e.target.value)}
          data-testid="module-summary" className={FIELD} />
      </label>
      <div className="flex flex-wrap gap-4">
        <label className={`${LABEL} min-w-[14rem] flex-1`}>{t(`${K}.form.for`)}
          <select value={audience} disabled={locked} onChange={(e) => setAudience(e.target.value)} data-testid="module-audience" className={FIELD}>
            {audiences.map((a) => (
              <option key={a.programme ?? ''} value={a.programme ?? ''}>
                {a.programme ? t(`${K}.forGift`, { name: a.name, count: String(a.count) }) : t(`${K}.forAll`, { count: String(a.count) })}
              </option>
            ))}
          </select>
        </label>
        <label className={`${LABEL} min-w-[12rem] flex-1`}>{t(`${K}.form.publish`)}
          <select value={later ? 'later' : 'now'} disabled={locked || live} onChange={(e) => setLater(e.target.value === 'later')}
            data-testid="module-when" className={FIELD}>
            <option value="now">{t(live ? `${K}.form.asIs` : `${K}.form.now`)}</option>
            <option value="later">{t(`${K}.form.later`)}</option>
          </select>
        </label>
        <label className={`${LABEL} min-w-[12rem] flex-1`}>{t(`${K}.form.due`)}
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} data-testid="module-due" className={FIELD} />
        </label>
      </div>
      {later && !locked && !live && (
        <div className="flex flex-wrap gap-4">
          <label className={LABEL}>{t(`${K}.form.date`)}
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="module-date" className={FIELD} />
          </label>
          <label className={LABEL}>{t(`${K}.form.time`)}
            <input value={time} inputMode="numeric" placeholder="09:00" onChange={(e) => setTime(e.target.value)}
              data-testid="module-time" className={`${FIELD} w-28`} />
          </label>
        </div>
      )}

      <h3 className="pt-2 text-[15px] font-semibold text-ground-900">{t(`${K}.form.lessons`)}</h3>
      <ol className="space-y-3" data-testid="module-lessons">
        {lessons.map((l, i) => (
          <li key={l.id ?? `new-${i}`}>
            {editingL === i ? (
              <LessonEditor l={l} n={i} moduleId={row?.id} limits={limits} token={token} t={t} onError={setError}
                onChange={(next) => setLessons((ls) => ls.map((x, j) => (j === i ? next : x)))}
                onDone={() => setEditingL(null)} />
            ) : (
              <div className="rounded-lg border border-ground-200 p-4" data-testid={`lesson-summary-${i}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <strong className="break-words text-sm text-ground-900">{i + 1}. {l.title || t(`${K}.form.untitled`)}</strong>
                  <span className="rounded-full bg-ground-100 px-2 py-0.5 text-xs text-ground-700">
                    {t(`${K}.form.kind.${l.file ? 'file' : l.video_url.trim() ? 'video' : 'text'}`)}
                  </span>
                </div>
                <p className="mt-1 break-words text-xs text-ground-600">
                  {[t(`${K}.form.words`, { count: String(words(l.body)) }), l.video_url.trim(), l.file?.name ?? '']
                    .filter(Boolean).join(' · ')}
                </p>
                <div className="flex flex-wrap gap-x-4">
                  <button type="button" className={LINK} data-testid={`lesson-edit-btn-${i}`} onClick={() => setEditingL(i)}>
                    {t(`${K}.form.edit`)}</button>
                  {i > 0 && <button type="button" className={LINK} data-testid={`lesson-up-${i}`}
                    onClick={() => { move(i); setEditingL(null) }}>{t(`${K}.form.moveUp`)}</button>}
                  <button type="button" className={LINK} data-testid={`lesson-remove-${i}`}
                    disabled={live && lessons.length === 1}
                    onClick={() => { setLessons((ls) => ls.filter((_x, j) => j !== i)); setEditingL(null) }}>
                    {t(`${K}.form.remove`)}</button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ol>
      {lessons.length < limits.lessons && (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" data-testid="module-add-lesson"
            onClick={() => { setLessons((ls) => [...ls, { title: '', body: '', video_url: '', file: null }]); setEditingL(lessons.length) }}
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800">{t(`${K}.form.addLesson`)}</button>
          <span className="text-xs text-ground-600">{t(`${K}.form.lessonHint`)}</span>
        </div>
      )}

      <h3 className="pt-2 text-[15px] font-semibold text-ground-900">{t(`${K}.form.task`)}</h3>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t(`${K}.form.task`)}>
        {TASKS.map((k) => (
          <button key={k} type="button" role="radio" aria-checked={task === k} disabled={locked && task !== k}
            onClick={() => setTask(k)} data-testid={`module-task-${k}`}
            className={`${PILL} ${task === k ? 'border-brand-shape bg-info-50 font-semibold text-info-800'
              : 'border-ground-300 bg-ground-0 text-ground-700'} disabled:opacity-50`}>
            {t(`${K}.form.taskKind.${k}`)}
          </button>
        ))}
      </div>
      {task !== 'none' && (
        <label className={LABEL}>{t(task === 'upload' ? `${K}.form.promptUpload` : `${K}.form.prompt`)}
          <textarea value={prompt} maxLength={limits.prompt} rows={2} onChange={(e) => setPrompt(e.target.value)}
            data-testid="module-prompt" className={FIELD} />
        </label>
      )}

      <div className="flex items-start gap-3">
        <Toggle on={emailPublish} onChange={setEmailPublish} label={t(`${K}.form.emailPublish`)} />
        <span className="text-sm text-ground-800">
          {t(`${K}.form.emailPublish`)}
          <span className="block text-xs text-ground-600">{t(emailOn ? `${K}.form.emailNote` : `${K}.form.emailOff`)}</span>
        </span>
      </div>
      <div className="flex items-start gap-3">
        <Toggle on={remind && !!due} onChange={(v) => setRemind(v && !!due)} label={t(`${K}.form.remind`)} />
        <span className="text-sm text-ground-800">
          {t(`${K}.form.remind`)}
          {!due && <span className="block text-xs text-ground-600">{t(`${K}.form.remindNeedsDue`)}</span>}
        </span>
      </div>

      {error && <p className="text-sm text-critical-600" role="alert" data-testid="module-error">{error}</p>}
      <div className="flex flex-wrap gap-2">
        {live ? (
          <button type="button" disabled={busy} onClick={() => save('edit')} data-testid="module-save"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink disabled:opacity-60">{t(`${K}.btn.save`)}</button>
        ) : (<>
          <button type="button" disabled={busy} onClick={() => save('publish')} data-testid="module-primary"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink disabled:opacity-60">
            {t(later ? `${K}.btn.schedule` : `${K}.btn.publish`)}</button>
          <button type="button" disabled={busy} onClick={() => save('draft')} data-testid="module-draft"
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800 disabled:opacity-60">
            {t(`${K}.btn.draft`)}</button>
        </>)}
        <button type="button" disabled={busy} onClick={onCancel}
          className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800">{t('common.cancel')}</button>
      </div>
      <p className="text-xs text-ground-600">{t(locked ? `${K}.form.lockedNote` : `${K}.form.lockNote`)}</p>
    </section>
  )
}
