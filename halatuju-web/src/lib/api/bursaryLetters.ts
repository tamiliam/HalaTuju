// Her letters on My Bursary (student maintenance S6b). Her OWN file only — the server 404s anything
// else. Imported by `components/bursary/BursaryLetters.tsx` only, so no other route carries it.
import { apiRequest } from './client'
import type { ApiOptions } from './client'

export type BursaryLetterState = 'withdrawn' | 'acknowledged' | 'overdue' | 'awaiting'

export interface BursaryLetter {
  id: number
  kind: 'general' | 'discipline' | 'suspension' | 'termination' | 'close_out'
  /** The PDF's language — English or Malay. */
  language: 'en' | 'ms'
  subject: string
  body: string
  issued_at: string
  response_due_on: string
  acknowledged_at: string | null
  withdrawn_at: string | null
  read: boolean
  state: BursaryLetterState
  has_pdf: boolean
}

export interface BursaryLetters {
  organisation: string
  letters: BursaryLetter[]
}

const BASE = '/api/v1/scholarship/bursary/letters/'

export async function getBursaryLetters(options?: ApiOptions): Promise<BursaryLetters> {
  return apiRequest(BASE, options)
}

export async function markLetterRead(id: number, options?: ApiOptions): Promise<BursaryLetter> {
  return apiRequest(`${BASE}${id}/read/`, { ...options, method: 'POST' })
}

/** "I have read this letter" — it does not mean she agrees. */
export async function acknowledgeLetter(id: number, options?: ApiOptions): Promise<BursaryLetter> {
  return apiRequest(`${BASE}${id}/acknowledge/`, { ...options, method: 'POST' })
}

/** A five-minute link to her letter's PDF, minted on her tap. */
export async function bursaryLetterPdf(id: number, options?: ApiOptions): Promise<{ url: string }> {
  return apiRequest(`${BASE}${id}/pdf/`, options)
}
