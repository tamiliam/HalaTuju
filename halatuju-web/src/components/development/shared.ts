/**
 * What the Development pages share (student maintenance S10), kept apart so the Progress page's chunk does not
 * carry the list and its form.
 */
import type { ModuleRow } from '@/lib/admin-api/development'

/** The roles the server lets in (`development.may_make`); the screens refuse the rest and call nothing. */
export const MAKER_ROLES = ['super', 'org_admin', 'admin']
const K = 'admin.development'

type T = (k: string, vars?: Record<string, string>) => string

export function audienceLabel(t: T, row: Pick<ModuleRow, 'programme' | 'audience_count'>): string {
  const count = String(row.audience_count)
  return row.programme ? t(`${K}.forGift`, { name: row.programme.name, count }) : t(`${K}.forAll`, { count })
}

/** "3 lessons + a written reflection". */
export function contentsLabel(t: T, row: Pick<ModuleRow, 'lessons' | 'task_kind'>): string {
  const n = row.lessons.length
  const lessons = t(n === 1 ? `${K}.oneLesson` : `${K}.lessons`, { count: String(n) })
  return row.task_kind === 'none' ? lessons : `${lessons} + ${t(`${K}.task.${row.task_kind}`)}`
}

/** A page link that keeps the chosen gift (`?programme=`) — Sprint 9's, ONE home. */
export { giftHref } from '@/components/surveys/shared'

/** Open a signed link in a new tab: the tab opens on the tap (no blocker stops it), then is pointed. */
export async function openSigned(get: () => Promise<{ url: string }>, onFail: () => void) {
  const tab = typeof window !== 'undefined' ? window.open('', '_blank') : null
  try {
    const { url } = await get()
    if (tab) tab.location.href = url
  } catch { tab?.close(); onFail() }
}
