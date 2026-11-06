// Her Growth tab on My Bursary (student maintenance S10): development modules. Her OWN file only — the server
// 404s anything else. Imported by `components/bursary/BursaryGrowth.tsx` only, so no other route carries it.
import { apiRequest } from './client'
import type { ApiOptions } from './client'
import { uploadContentType } from '../uploadContentType'

export type TaskKind = 'none' | 'reflection' | 'upload'

export interface MyFile {
  name: string
  type: string
  size: number
}

/** One module on her list (`development.student_modules`, an allowlist). */
export interface MyModuleCard {
  id: number
  title: string
  summary: string
  due_on: string | null
  task_kind: TaskKind
  lessons: number
  read: number
  done: boolean
  started: boolean
  /** Live and her file in maintenance: she may read on and send her task. */
  can_act: boolean
  task_sent_at: string | null
  reviewed: boolean
}

export interface MyLesson {
  id: number
  title: string
  body: string
  video_url: string
  file: MyFile | null
  read: boolean
}

export interface MyTask {
  kind: TaskKind
  prompt: string
  text: string
  file: MyFile | null
  sent_at: string | null
  reviewed_at: string | null
  /** Staff's comment, once they marked it reviewed. */
  comment: string
  can_change: boolean
}

export interface MyModule {
  id: number
  title: string
  summary: string
  due_on: string | null
  can_act: boolean
  done: boolean
  lessons: MyLesson[]
  task: MyTask
}

const BASE = '/api/v1/scholarship/bursary/growth/'

export async function getMyModules(options?: ApiOptions): Promise<{ organisation: string; modules: MyModuleCard[] }> {
  return apiRequest(BASE, options)
}

export async function getMyModule(id: number, options?: ApiOptions): Promise<MyModule> {
  return apiRequest(`${BASE}${id}/`, options)
}

/** "I have read this" (idempotent). 409 `module_closed`. */
export async function markLessonRead(id: number, lessonId: number, options?: ApiOptions):
  Promise<{ module: MyModule; to_do: number }> {
  return apiRequest(`${BASE}${id}/lessons/${lessonId}/read/`, { ...options, method: 'POST', body: '{}' })
}

/** A 300-second link to a lesson's file. */
export async function lessonFileUrl(id: number, lessonId: number, options?: ApiOptions): Promise<{ url: string }> {
  return apiRequest(`${BASE}${id}/lessons/${lessonId}/file/`, options)
}

/** A 300-second link to HER uploaded task. */
export async function myTaskFileUrl(id: number, options?: ApiOptions): Promise<{ url: string }> {
  return apiRequest(`${BASE}${id}/task/file/`, options)
}

/** Send (or change) her reflection. 409 `lessons_first` / `reviewed` / `module_closed`. */
export async function sendReflection(id: number, text: string, options?: ApiOptions):
  Promise<{ module: MyModule; to_do: number }> {
  return apiRequest(`${BASE}${id}/task/`, { ...options, method: 'POST', body: JSON.stringify({ text }) })
}

/** Her file: sign → PUT the bytes straight to Storage → record (the server reads the bytes for the type and the
 *  size, and refuses `unsupported_format` / `file_too_large`). */
export async function sendTaskFile(id: number, file: File, options?: ApiOptions):
  Promise<{ module: MyModule; to_do: number }> {
  const signed: { upload_url: string; storage_path: string } = await apiRequest(
    `${BASE}${id}/task/sign/`, { ...options, method: 'POST', body: JSON.stringify({ size: file.size }) })
  const resp = await fetch(signed.upload_url, {
    method: 'PUT', body: file,
    headers: { 'Content-Type': uploadContentType(file) },   // no upsert: signed without it (S10 review)
  })
  if (!resp.ok) throw Object.assign(new Error(`Upload failed: ${resp.status}`), { code: 'upload_incomplete' })
  return apiRequest(`${BASE}${id}/task/`, {
    ...options, method: 'POST',
    body: JSON.stringify({ storage_path: signed.storage_path, original_filename: file.name }),
  })
}
