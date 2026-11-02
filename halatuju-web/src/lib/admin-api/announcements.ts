/**
 * Programme → Announcements (student maintenance S8, 2026-11-01): an organisation's news to its scholars.
 * Every rule is the server's (`apps/scholarship/announcements.py`): who may post, who sees one, what may
 * change once it is out, and the email. The screen offers Delete / Withdraw only where the row says so.
 */
import { adminFetch, adminMutate, giftQuery } from './client'
import type { ApiOptions } from './client'

export type AnnouncementStatus = 'draft' | 'scheduled' | 'published' | 'withdrawn'
export type AnnouncementAction = 'publish' | 'schedule' | 'draft'

export interface AnnouncementRow {
  id: number
  title: string
  body: string
  /** The server's word: a scheduled one whose time has passed already reads `published`. */
  status: AnnouncementStatus
  pinned: boolean
  /** null = every scholar of the organisation. */
  programme: { code: string; name: string } | null
  /** The scholars who may see it now ("M" in "read N of M"). */
  audience_count: number
  read_count: number
  email_requested: boolean
  emailed_at: string | null
  emailed_count: number
  /** The job found the organisation's "Announcement" email switched off: nobody was emailed. */
  email_switched_off: boolean
  publish_at: string | null
  published_at: string | null
  edited_at: string | null
  withdrawn_at: string | null
  author: { email: string; name: string; role: string }
  created_at: string
  can_delete: boolean
  can_withdraw: boolean
}

export interface AnnouncementAudience {
  /** A gift code, or null for every scholar. */
  programme: string | null
  name: string
  count: number
}

export interface AnnouncementsPayload {
  organisation: { code: string; name: string }
  announcements: AnnouncementRow[]
  counts: Record<AnnouncementStatus, number>
  audiences: AnnouncementAudience[]
  /** The organisation's "Announcement" student email is switched on (Student communications). */
  email_switch_on: boolean
  limits: { title: number; body: number }
}

export interface AnnouncementInput {
  title: string
  body: string
  programme: string | null
  pinned: boolean
  email: boolean
  action: AnnouncementAction
  /** ISO date-time, for `schedule`. */
  publish_at?: string
}

const BASE = '/api/v1/admin/scholarship/announcements/'

export async function getAnnouncements(programme?: string, options?: ApiOptions) {
  return adminFetch<AnnouncementsPayload>(`${BASE}${giftQuery(programme)}`, options)
}

/** Refusals arrive as `code`: `title_required`, `title_too_long`, `title_newline`, `body_required`,
 *  `body_too_long`, `bad_audience`, `bad_publish_at`, `publish_at_past`, `bad_action`, `programme_required`. */
export async function createAnnouncement(data: AnnouncementInput, programme?: string, options?: ApiOptions) {
  return adminMutate<AnnouncementRow>(`${BASE}${giftQuery(programme)}`, 'POST', data, options)
}

/** Once it is out only `title`, `body` and `pinned` may change (409 `published_locked` otherwise). */
export async function updateAnnouncement(id: number, data: Partial<AnnouncementInput>, options?: ApiOptions) {
  return adminMutate<AnnouncementRow>(`${BASE}${id}/`, 'PATCH', data, options)
}

/** A draft or a scheduled one only (409 `withdraw_instead` once it is out). */
export async function deleteAnnouncement(id: number, options?: ApiOptions) {
  return adminMutate<void>(`${BASE}${id}/`, 'DELETE', null, options)
}

export async function withdrawAnnouncement(id: number, options?: ApiOptions) {
  return adminMutate<AnnouncementRow>(`${BASE}${id}/withdraw/`, 'POST', null, options)
}
