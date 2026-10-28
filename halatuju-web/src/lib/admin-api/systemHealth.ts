import { adminFetch, type ApiOptions } from './client'

/**
 * The admin System health light (2026-10-28) — SUPER ADMINS ONLY; every other admin gets 403, and
 * the shell never calls this for them. Each row carries a machine `code` + `params`; the words are
 * `admin.systemHealth.line.<group>.<code>` in the reader's language.
 */
export type HealthStatus = 'green' | 'amber' | 'red'
export type HealthRowKey = 'gemini' | 'vision' | 'email' | 'cron' | 'credit'

export interface HealthRow {
  key: HealthRowKey
  status: HealthStatus
  code: string
  params: Record<string, string>
  /** ISO time of the last success seen, or null. */
  last_ok_at: string | null
}

export interface SystemHealth {
  overall: HealthStatus
  checked_at: string
  rows: HealthRow[]
}

/** `fresh` (the panel's refresh button) skips the server's 60-second cache. */
export async function getSystemHealth(fresh = false, options?: ApiOptions): Promise<SystemHealth> {
  return adminFetch(`/api/v1/admin/scholarship/system-health/${fresh ? '?fresh=1' : ''}`, options)
}
