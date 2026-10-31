/**
 * The My activity card's pure rules (`lib/profileActivity.ts`, common profile S5): the day groups,
 * the sentence split, the subject's words (a visible label verbatim; otherwise OUR neutral word —
 * never the server's English one), the links, and the grey second line.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import { interpolateMessage } from '@/lib/branding'
import type { ActivityItem } from '@/lib/admin-api'
import {
  dayGroup, groupByDay, rowContext, sentenceParts, subjectHref, subjectText,
} from '@/lib/profileActivity'

const tIn = (messages: object) => (key: string, vars?: Record<string, string>) => {
  const v = key.split('.').reduce<unknown>((c, k) => (c && typeof c === 'object' ? (c as Record<string, unknown>)[k] : undefined), messages)
  return typeof v === 'string' ? interpolateMessage(v, vars) : key
}
const t = tIn(en)
// Wednesday 28 October 2026, 10:00 local.
const NOW = new Date(2026, 9, 28, 10, 0)
const at = (y: number, m: number, d: number, h = 9, min = 5) => new Date(y, m - 1, d, h, min).toISOString()
const row = (over: Partial<ActivityItem> = {}): ActivityItem => ({
  id: 1, verb: 'verdict_recorded', kind: 'students', created_at: at(2026, 10, 28), backfilled: false,
  subject: { type: 'application', state: 'visible', label: 'Aisyah', id: 104 }, meta: {}, ...over,
})

describe('day groups', () => {
  it('today, this week (since Monday), earlier', () => {
    expect(dayGroup(at(2026, 10, 28, 0, 0), NOW)).toBe('today')
    expect(dayGroup(at(2026, 10, 27, 23, 59), NOW)).toBe('week')
    expect(dayGroup(at(2026, 10, 26, 0, 0), NOW)).toBe('week')        // Monday
    expect(dayGroup(at(2026, 10, 25, 23, 59), NOW)).toBe('earlier')   // Sunday before
  })
  it('a moment ahead of the viewer’s clock is today; nonsense is earlier', () => {
    expect(dayGroup(at(2026, 10, 29), NOW)).toBe('today')
    expect(dayGroup('not a date', NOW)).toBe('earlier')
  })
  it('on a Monday the week starts today', () => {
    const monday = new Date(2026, 9, 26, 8, 0)
    expect(dayGroup(at(2026, 10, 25, 22, 0), monday)).toBe('earlier')
  })
  it('groups keep the server order and never repeat a heading in a run', () => {
    const rows = [row({ id: 3 }), row({ id: 2, created_at: at(2026, 10, 27) }),
      row({ id: 1, created_at: at(2026, 9, 1) })]
    expect(groupByDay(rows, NOW).map((g) => [g.group, g.rows.map((r) => r.id)]))
      .toEqual([['today', [3]], ['week', [2]], ['earlier', [1]]])
  })
})

describe('the sentence and its subject', () => {
  it('splits around {subject}, or keeps the whole sentence', () => {
    expect(sentenceParts('Recorded a verdict for {subject}')).toEqual(['Recorded a verdict for ', ''])
    expect(sentenceParts('Signed in for the first time')).toEqual(['Signed in for the first time', null])
  })
  it('a visible name is shown verbatim; a reference carries its kind', () => {
    expect(subjectText({ type: 'application', state: 'visible', label: 'Aisyah binti Ali', id: 4 }, t)).toBe('Aisyah binti Ali')
    expect(subjectText({ type: 'payment_run', state: 'visible', label: 'PR-2026-10-01-01', id: 9 }, t))
      .toBe('payment run PR-2026-10-01-01')
  })
  it('hidden and removed use OUR words, never the server label', () => {
    expect(subjectText({ type: 'application', state: 'hidden', label: 'SERVER WORD', id: null }, t)).toBe('a student')
    expect(subjectText({ type: 'application', state: 'removed', label: 'SERVER WORD', id: null }, t)).toBe('a student (removed)')
    expect(subjectText({ type: 'new_kind', state: 'removed', label: 'SERVER WORD', id: null }, t)).toBe('something (removed)')
    expect(subjectText(null, t)).toBe('something')
  })
  it('TD-445: a visible subject with no name takes OUR translated word, and a student stays linked', () => {
    const nameless = { type: 'application', state: 'visible' as const, label: null, id: 104 }
    expect(subjectText(nameless, t)).toBe('a student')
    expect(subjectText(nameless, tIn(ms))).toBe('seorang pelajar')
    expect(subjectHref(nameless)).toBe('/admin/scholarship/104')
    const invitation = { type: 'invitation', state: 'visible' as const, label: null, id: 7 }
    expect(subjectText(invitation, t)).toBe('someone')
    expect(subjectText(invitation, tIn(ms))).toBe('seseorang')
    expect(subjectText({ type: 'payment_run', state: 'visible', label: null, id: 9 }, t)).toBe('a payment run')
  })
  it('links only a visible student or payment run', () => {
    expect(subjectHref({ type: 'application', state: 'visible', label: 'A', id: 4 })).toBe('/admin/scholarship/4')
    expect(subjectHref({ type: 'payment_run', state: 'visible', label: 'PR', id: 9 })).toBe('/admin/payments/9')
    expect(subjectHref({ type: 'invoice', state: 'visible', label: 'INV-1', id: 2 })).toBeNull()
    expect(subjectHref({ type: 'application', state: 'hidden', label: 'a student', id: null })).toBeNull()
    expect(subjectHref({ type: 'application', state: 'removed', label: 'x', id: 4 })).toBeNull()
    expect(subjectHref(null)).toBeNull()
  })
})

describe('the grey second line', () => {
  it('today: the time; before today: the date and time', () => {
    expect(rowContext(row(), NOW, t)).toBe('09:05')
    expect(rowContext(row({ created_at: at(2026, 10, 2, 14, 30) }), NOW, t)).toBe('02/10/2026 14:30')
  })
  it('a payment run signature says which part; an unknown code adds nothing', () => {
    const signed = row({ verb: 'payment_run_signed', meta: { role: 'checker' } })
    expect(rowContext(signed, NOW, t)).toBe('09:05 · as the checker')
    expect(rowContext({ ...signed, meta: { role: 'boss' } }, NOW, t)).toBe('09:05')
    expect(rowContext({ ...signed, verb: 'org_request_approved' }, NOW, t)).toBe('09:05')
  })
})
