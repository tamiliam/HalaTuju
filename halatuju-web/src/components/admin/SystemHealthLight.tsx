'use client'

import { useCallback, useEffect, useState } from 'react'

import { tOr, useT } from '@/lib/i18n'
import { getSystemHealth, type HealthRow, type HealthStatus, type SystemHealth } from '@/lib/admin-api'
import { Menu } from '@/components/admin/Menu'
import { Icon } from '@/components/admin/icons'

/**
 * The System health light (owner-approved Stitch design, 2026-10-28): a small round light in the top
 * bar and, on click, a panel of five rows — Gemini, Vision, email, the scheduled jobs and the AI
 * credit. SUPER ADMINS ONLY: `AppShell` mounts this for a super and for nobody else, so no other
 * admin's browser ever asks for it (the endpoint refuses them too).
 *
 * Two owner changes from the mock: the light shows the WORST row's colour (computed here, from the
 * rows), and there is NO "View logs" link.
 *
 * It fetches on mount, every `HEALTH_POLL_MS` while the shell is mounted (the light's colour needs
 * it), and again each time the panel opens. A failed fetch keeps the last answer on screen.
 */

export const HEALTH_POLL_MS = 5 * 60 * 1000

const RANK: Record<HealthStatus, number> = { green: 0, amber: 1, red: 2 }

/** The worst status among the rows — what the light shows. Null before the first answer. */
export function worstStatus(rows: HealthRow[] | undefined): HealthStatus | null {
  if (!rows?.length) return null
  return rows.reduce<HealthStatus>((w, r) => (RANK[r.status] > RANK[w] ? r.status : w), 'green')
}

/** The runtime-built key families, listed so the i18n guard can hold each one to a real string. */
export const HEALTH_LINE_CODES: Record<string, string[]> = {
  read: ['ok', 'idle', 'failures', 'down'],
  email: ['ok', 'no_record', 'recent_failure', 'failing', 'no_success'],
  cron: ['ok', 'waiting', 'late', 'missed', 'never', 'errored', 'errored_twice'],
  credit: ['ok', 'payment_error', 'recovered'],
}
export const HEALTH_ROW_KEYS = ['gemini', 'vision', 'email', 'cron', 'credit'] as const
export const HEALTH_UNITS = ['minutes', 'hours', 'days'] as const
export const HEALTH_CADENCES = ['every15', 'hourly', 'daily', 'weekly', 'monthly', 'yearly'] as const

const DOT: Record<HealthStatus | 'unknown', string> = {
  green: 'bg-positive-500',
  amber: 'bg-caution-500 ring-4 ring-caution-500/25',
  red: 'bg-critical-500 ring-4 ring-critical-500/25',
  unknown: 'bg-ground-300',
}
const PILL: Record<HealthStatus, string> = {
  green: 'bg-positive-50 text-positive-700',
  amber: 'bg-caution-50 text-caution-800',
  red: 'bg-critical-50 text-critical-700',
}
const ROW_TINT: Record<HealthStatus, string> = { green: '', amber: 'bg-caution-50', red: 'bg-critical-50' }
const LINE_INK: Record<HealthStatus, string> = {
  green: 'text-ground-500', amber: 'text-caution-700', red: 'text-critical-700',
}

type T = (key: string, params?: Record<string, string>) => string

const HHMM = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
const DAY_MONTH = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

/** "last OK 14:05", "last OK yesterday 23:10", "last OK 21 Oct". */
export function lastOkText(t: T, iso: string | null, now: Date = new Date()): string {
  if (!iso) return t('admin.systemHealth.lastOkNone')
  const at = new Date(iso)
  if (sameDay(at, now)) return t('admin.systemHealth.lastOk', { time: HHMM.format(at) })
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (sameDay(at, yesterday)) return t('admin.systemHealth.lastOkYesterday', { time: HHMM.format(at) })
  return t('admin.systemHealth.lastOk', { time: DAY_MONTH.format(at) })
}

/** The row's one plain-English line, from the server's code + params. */
export function lineText(t: T, row: HealthRow): string {
  const group = row.key === 'gemini' || row.key === 'vision' ? 'read' : row.key
  const p = { ...row.params }
  if (p.job) p.job = tOr(t, `admin.systemHealth.job.${p.job}`, p.job)
  if (p.unit) p.age = t(`admin.systemHealth.unit.${p.unit}`, { n: p.amount ?? '' })
  if (p.cadence) p.cadence = t(`admin.systemHealth.cadence.${p.cadence}`)
  return tOr(t, `admin.systemHealth.line.${group}.${row.code}`, row.code, p)
}

function checkedText(t: T, iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 60000))
  if (minutes < 1) return t('admin.systemHealth.subtitleNow')
  if (minutes === 1) return t('admin.systemHealth.subtitleOne')
  return t('admin.systemHealth.subtitle', { n: String(minutes) })
}

function Dot({ status, size = 'h-2.5 w-2.5' }: { status: HealthStatus | 'unknown'; size?: string }) {
  return <span aria-hidden data-status={status} className={`inline-block shrink-0 rounded-full ${size} ${DOT[status]}`} />
}

/** The panel's body. Mounted only while the menu is open, so its mount IS "the panel opened". */
function HealthPanel({ health, loading, failed, onOpen, onRefresh }: {
  health: SystemHealth | null
  loading: boolean
  failed: boolean
  onOpen: () => void
  onRefresh: () => void
}) {
  const { t } = useT()
  useEffect(() => { onOpen() }, [onOpen])
  const status = worstStatus(health?.rows)

  return (
    <div data-testid="system-health-panel">
      <div className="flex items-start justify-between gap-2 px-3 pb-2 pt-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-[13px] font-semibold text-ground-900">{t('admin.systemHealth.title')}</p>
            {status && (
              <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${PILL[status]}`}>
                {t(`admin.systemHealth.overall.${status}`)}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[11px] text-ground-400">
            {health ? checkedText(t, health.checked_at) : t('admin.systemHealth.loading')}
          </p>
        </div>
        {/* ⚠ stopPropagation: the menu closes on any click inside its panel. ⚠ Never `disabled`
            while loading: a click on a disabled button still bubbles to that closing handler in
            React, so the panel would shut instead of refreshing. A second check is harmless. */}
        <button
          type="button"
          role="menuitem"
          data-menuitem
          aria-label={t('admin.systemHealth.refresh')}
          title={t('admin.systemHealth.refresh')}
          aria-busy={loading}
          onClick={(e) => { e.stopPropagation(); onRefresh() }}
          className="rounded-lg p-1.5 text-ground-500 transition-colors hover:bg-primary-50 hover:text-primary-700"
        >
          <Icon name="refresh" size={15} className={loading ? 'animate-spin' : undefined} />
        </button>
      </div>

      {failed && (
        <p className="mx-3 mb-1 rounded-lg bg-caution-50 px-3 py-2 text-[11.5px] text-caution-800">
          {t('admin.systemHealth.error')}
        </p>
      )}

      <ul className="space-y-0.5">
        {(health?.rows ?? []).map((row) => (
          <li key={row.key} data-testid={`health-row-${row.key}`} data-status={row.status}
            className={`flex items-start gap-2.5 rounded-lg px-3 py-2 ${ROW_TINT[row.status]}`}>
            <span className="pt-[5px]"><Dot status={row.status} size="h-2 w-2" /></span>
            <span className="min-w-0 flex-1">
              <span className="block text-[12.5px] font-medium text-ground-900">
                {tOr(t, `admin.systemHealth.row.${row.key}`, row.key)}
              </span>
              <span className={`block text-[11.5px] leading-snug ${LINE_INK[row.status]}`}>{lineText(t, row)}</span>
            </span>
            <span className="shrink-0 whitespace-nowrap pt-0.5 text-[10.5px] text-ground-400">
              {lastOkText(t, row.last_ok_at)}
            </span>
          </li>
        ))}
      </ul>

      <div className="my-1 h-px bg-ground-100" role="separator" />
      <p className="px-3 pb-1 text-[11px] leading-relaxed text-ground-400">{t('admin.systemHealth.footer')}</p>
    </div>
  )
}

export function SystemHealthLight({ token }: { token: string | null | undefined }) {
  const { t } = useT()
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async (fresh = false) => {
    if (!token) return
    setLoading(true)
    try {
      setHealth(await getSystemHealth(fresh, { token }))
      setFailed(false)
    } catch {
      setFailed(true)            // keep the last answer; the panel says it could not check
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (!token) return
    void load()
    const id = setInterval(() => { void load() }, HEALTH_POLL_MS)
    return () => clearInterval(id)
  }, [token, load])

  const onOpen = useCallback(() => { void load() }, [load])
  const onRefresh = useCallback(() => { void load(true) }, [load])

  const status = worstStatus(health?.rows)
  const label = t('admin.systemHealth.open', {
    status: t(`admin.systemHealth.overall.${status ?? 'unknown'}`),
  })

  return (
    <Menu
      label={label}
      width="w-[340px] max-w-[calc(100vw-16px)]"
      trigger={
        <span data-testid="system-health-light" data-status={status ?? 'unknown'}
          className="grid h-[22px] w-[22px] place-items-center rounded-full border border-ground-200 bg-ground-0">
          <Dot status={status ?? 'unknown'} />
        </span>
      }
    >
      <HealthPanel health={health} loading={loading} failed={failed} onOpen={onOpen} onRefresh={onRefresh} />
    </Menu>
  )
}
