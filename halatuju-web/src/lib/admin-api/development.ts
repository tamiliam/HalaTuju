/**
 * Programme → Development (student maintenance S10, 2026-11-02): an organisation's development modules, each
 * module's Progress (per scholar), its CSV, the review, a lesson's file, and the scholar file's Growth tab.
 * Every rule is the server's (`apps/scholarship/development.py`): who may make one, who sees it, the task-type
 * lock at the first start, the files (typed by their bytes, private, short signed links), the emails. The
 * screens offer Delete / Archive / Remind only where the server's row says so.
 */
import { API_BASE, adminFetch, adminMutate, giftQuery } from './client'
import type { ApiOptions } from './client'

export type ModuleStatus = 'draft' | 'scheduled' | 'published' | 'archived'
export type ModuleAction = 'publish' | 'draft'
export type TaskKind = 'none' | 'reflection' | 'upload'
export type ProgressBucket = 'to_review' | 'done' | 'in_progress' | 'not_started'

export interface FileInfo {
  name: string
  type: string
  size: number
}

export interface LessonInput {
  /** Absent for a new lesson; an existing lesson keeps its id (her reads follow the id). */
  id?: number
  title: string
  body: string
  video_url: string
}

export interface LessonRow extends LessonInput {
  id: number
  file: FileInfo | null
}

export interface ModuleRow {
  id: number
  title: string
  summary: string
  /** The server's word: `scheduled` is read from `publish_at`. */
  status: ModuleStatus
  /** null = every scholar of the organisation. */
  programme: { code: string; name: string } | null
  publish_at: string | null
  due_on: string | null
  task_kind: TaskKind
  task_prompt: string
  lessons: LessonRow[]
  audience_count: number
  started_count: number
  done_count: number
  to_review_count: number
  email_on_publish: boolean
  remind: boolean
  published_emailed_at: string | null
  reminded_at: string | null
  author: { email: string; name: string; role: string }
  created_at: string
  /** Somebody started: the task type, audience and publishing time are fixed. */
  locked: boolean
  can_delete: boolean
  can_archive: boolean
  can_restore: boolean
}

export interface ModuleAudience {
  programme: string | null
  name: string
  count: number
}

export interface ModuleLimits {
  title: number
  summary: number
  lesson_title: number
  lesson_body: number
  lessons: number
  prompt: number
  file_bytes: number
}

export interface ModulesPayload {
  organisation: { code: string; name: string }
  modules: ModuleRow[]
  counts: Record<'published' | 'scheduled' | 'draft' | 'archived', number>
  audiences: ModuleAudience[]
  /** The organisation's "A new module" student email is switched on (Student communications). */
  email_switch_on: boolean
  limits: ModuleLimits
}

export interface ModuleInput {
  title: string
  summary: string
  programme: string | null
  /** ISO date-time; omitted / null = now. */
  publish_at?: string | null
  /** "Now" on a draft or a scheduled one: the server sets the time to now. */
  publish_now?: boolean
  due_on: string | null
  task_kind: TaskKind
  task_prompt: string
  email_on_publish: boolean
  remind: boolean
  lessons: LessonInput[]
  action?: ModuleAction
}

export interface ProgressRow {
  application_id: number
  name: string
  mentor: string
  bucket: Exclude<ProgressBucket, 'to_review'>
  to_review: boolean
  read: number
  lessons: number
  started_at: string | null
  task_sent_at: string | null
  task_text: string
  task_file: FileInfo | null
  reviewed_at: string | null
  reviewed_by: string
  review_comment: string
  /** Past the due date and not done — staff and the mentor only, never money. */
  late: boolean
}

export interface ModuleProgress {
  module: ModuleRow
  email_switch_on?: boolean
  rows: ProgressRow[]
  counts: Record<ProgressBucket, number>
  can_remind: boolean
}

/** A scholar's modules, as the scholar file's Growth tab and the mentor's page read them. */
export interface WorkRow {
  id: number
  title: string
  status: ModuleStatus
  due_on: string | null
  task_kind: TaskKind
  lessons: number
  read: number
  done: boolean
  late: boolean
  task_sent_at: string | null
  task_text: string
  /** `url` only on the mentor's page (a short signed link). */
  task_file: { name: string; type: string; url?: string | null } | null
  reviewed_at: string | null
  review_comment: string
}

const BASE = '/api/v1/admin/scholarship/development/'

export async function getModules(programme?: string, options?: ApiOptions) {
  return adminFetch<ModulesPayload>(`${BASE}${giftQuery(programme)}`, options)
}

/** Refusals arrive as `code` (+ `detail`: the lesson's place for a lesson error). */
export async function createModule(data: ModuleInput, programme?: string, options?: ApiOptions) {
  return adminMutate<ModuleRow>(`${BASE}${giftQuery(programme)}`, 'POST', data, options)
}

/** From the first start: 409 `task_locked` / `started_locked` for the fixed parts. */
export async function updateModule(id: number, data: Partial<ModuleInput>, options?: ApiOptions) {
  return adminMutate<ModuleRow>(`${BASE}${id}/`, 'PATCH', data, options)
}

/** Only while nobody has started (409 `archive_instead`). */
export async function deleteModule(id: number, options?: ApiOptions) {
  return adminMutate<void>(`${BASE}${id}/`, 'DELETE', null, options)
}

export async function archiveModule(id: number, options?: ApiOptions) {
  return adminMutate<ModuleRow>(`${BASE}${id}/archive/`, 'POST', null, options)
}

export async function getModuleProgress(id: number, options?: ApiOptions) {
  return adminFetch<ModuleProgress>(`${BASE}${id}/progress/`, options)
}

/** The same reminder as the hourly job, now, to each scholar not done and not yet reminded (never twice). */
export async function remindModule(id: number, options?: ApiOptions) {
  return adminMutate<Omit<ModuleProgress, 'module'> & { sent: number }>(`${BASE}${id}/remind/`, 'POST', null, options)
}

export async function reviewTask(id: number, applicationId: number, comment: string, options?: ApiOptions) {
  return adminMutate<Omit<ModuleProgress, 'module'>>(
    `${BASE}${id}/progress/${applicationId}/review/`, 'POST', { comment }, options)
}

/** A short signed link to one scholar's uploaded task. */
export async function taskFileLink(id: number, applicationId: number, options?: ApiOptions) {
  return adminFetch<{ url: string; expires_in: number }>(`${BASE}${id}/progress/${applicationId}/file/`, options)
}

/** A short signed link to a lesson's file. */
export async function lessonFileLink(id: number, lessonId: number, options?: ApiOptions) {
  return adminFetch<{ url: string; expires_in: number }>(`${BASE}${id}/lessons/${lessonId}/file/`, options)
}

/** The whole lesson-file chain: sign → PUT the bytes straight to Storage → record (the server reads the bytes
 *  for the type and size). Returns the module's refreshed row. */
export async function uploadLessonFile(id: number, lessonId: number, file: File, options?: ApiOptions) {
  const url = `${BASE}${id}/lessons/${lessonId}/file/`
  const signed = await adminMutate<{ upload_url: string; storage_path: string }>(
    `${url}sign/`, 'POST', { size: file.size }, options)
  const resp = await fetch(signed.upload_url, {
    method: 'PUT', body: file,
    headers: { 'Content-Type': file.type || 'application/octet-stream', 'x-upsert': 'true' },
  })
  if (!resp.ok) throw Object.assign(new Error(`Upload failed: ${resp.status}`), { code: 'upload_failed' })
  return adminMutate<ModuleRow>(url, 'POST', { storage_path: signed.storage_path, original_filename: file.name }, options)
}

export async function removeLessonFile(id: number, lessonId: number, options?: ApiOptions) {
  return adminMutate<ModuleRow>(`${BASE}${id}/lessons/${lessonId}/file/`, 'DELETE', null, options)
}

/** The CSV (auth header required), as text for a client-side download. */
export async function fetchModuleCsv(id: number, options?: ApiOptions): Promise<string> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${BASE}${id}/csv/`, { headers })
  if (!res.ok) throw new Error(`CSV download failed: ${res.status}`)
  return res.text()
}

export async function getScholarGrowth(id: number, options?: ApiOptions) {
  return adminFetch<{ modules: WorkRow[] }>(`/api/v1/admin/scholarship/scholars/${id}/development/`, options)
}
