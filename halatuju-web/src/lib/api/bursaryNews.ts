// Her News tab on My Bursary (student maintenance S8). Her OWN file only — the server 404s anything else.
// Imported by `components/bursary/BursaryNews.tsx` only, so no other route carries it.
import { apiRequest } from './client'
import type { ApiOptions } from './client'

/** One announcement as the server lets her see it (`announcements.student_payload`, an allowlist): never
 *  who wrote it, who else it is for, or anything about the email. */
export interface NewsItem {
  id: number
  title: string
  /** Plain text with line breaks; links are made clickable on screen. */
  body: string
  pinned: boolean
  published_at: string
  edited_at: string | null
  /** Her tab has not shown it yet. */
  new: boolean
}

export interface BursaryNews {
  organisation: string
  announcements: NewsItem[]
}

export async function getBursaryNews(options?: ApiOptions): Promise<BursaryNews> {
  return apiRequest('/api/v1/scholarship/bursary/news/', options)
}

/** Her tab showed these. The server records only the ones she may see; answers how many are still unread. */
export async function markNewsRead(ids: number[], options?: ApiOptions): Promise<{ marked: number; unread: number }> {
  return apiRequest('/api/v1/scholarship/bursary/news/read/', { ...options, method: 'POST', body: JSON.stringify({ ids }) })
}
