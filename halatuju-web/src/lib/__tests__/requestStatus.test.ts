/**
 * Guardrail for the Requests-space status vocabulary + action rules (Sprint 15), mirroring
 * applicationStatus.test.ts:
 *
 * 1. Label parity — every status / kind / lane has a key in en / ms / ta, and the status block
 *    holds NO key that isn't a known status.
 * 2. Tone coverage — statusTone returns a non-default tone for every known status.
 * 3. No regrowth — neither requests page carries a local status→label or status→colour map.
 * 4. requestActionsFor mirrors org_requests.TRANSITIONS (the buttons a page shows must match the
 *    server's from-status rules — a spot-check across the flow).
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import {
  REQUEST_STATUSES, statusLabelKey, statusTone, hasStatusTone,
  kindLabelKey, laneLabelKey, requestActionsFor, hasUnansweredQuestions,
} from '@/lib/requestStatus'

const DEFAULT_TONE = 'bg-gray-100 text-gray-600'
const block = (m: unknown, key: string): Record<string, string> =>
  key.split('.').reduce<Record<string, unknown>>(
    (o, k) => (o[k] as Record<string, unknown>), m as Record<string, unknown>) as Record<string, string>

describe('requestStatus vocabulary', () => {
  test('statusLabelKey / kindLabelKey / laneLabelKey wrap the canonical prefixes', () => {
    expect(statusLabelKey('quoted')).toBe('admin.requests.status.quoted')
    expect(kindLabelKey('bug')).toBe('admin.requests.kind.bug')
    expect(laneLabelKey('sprint')).toBe('admin.requests.lane.sprint')
  })

  describe.each([['en', en], ['ms', ms], ['ta', ta]])('%s labels', (_lang, m) => {
    test('every status has a label; no unknown status leaks in', () => {
      const b = block(m, 'admin.requests.status')
      expect(REQUEST_STATUSES.filter((s) => !b[s])).toEqual([])
      expect(Object.keys(b).filter((k) => (REQUEST_STATUSES as readonly string[]).indexOf(k) < 0)).toEqual([])
    })
    test('kind + lane labels present', () => {
      expect(block(m, 'admin.requests.kind').bug).toBeTruthy()
      expect(block(m, 'admin.requests.kind').feature).toBeTruthy()
      expect(block(m, 'admin.requests.lane').small_change).toBeTruthy()
      expect(block(m, 'admin.requests.lane').sprint).toBeTruthy()
    })
  })

  test('every status has an explicit tone', () => {
    expect(REQUEST_STATUSES.filter((s) => !hasStatusTone(s))).toEqual([])
  })

  test('statusTone falls back to grey for an unknown status', () => {
    expect(statusTone('nonsense')).toBe(DEFAULT_TONE)
  })

  test('neither requests page regrows a local status map', () => {
    const screens = [
      path.join(__dirname, '..', '..', 'app', 'admin', 'requests', 'page.tsx'),
      path.join(__dirname, '..', '..', 'app', 'admin', 'requests', '[id]', 'page.tsx'),
    ]
    const BANNED = /STATUS_LABELS|STATUS_TONE|statusBadge/
    expect(screens.filter((f) => BANNED.test(fs.readFileSync(f, 'utf8')))).toEqual([])
  })
})

describe('requestActionsFor mirrors the transition matrix', () => {
  test('org_admin answers only when a question waits (submitted/triaged)', () => {
    expect(requestActionsFor('org_admin', 'submitted', '', true)).toContain('answer')
    expect(requestActionsFor('org_admin', 'submitted', '', false)).not.toContain('answer')
    expect(requestActionsFor('org_admin', 'quoted', '', true)).not.toContain('answer')
  })

  test('org_admin quote responses (accept/defer/modify/withdraw)', () => {
    expect(requestActionsFor('org_admin', 'quoted', 'feature', false).sort())
      .toEqual(['accept', 'defer', 'modify', 'withdraw'].sort())
    // deferred: accept + modify (+withdraw), no defer
    const d = requestActionsFor('org_admin', 'deferred', 'feature', false)
    expect(d).toEqual(expect.arrayContaining(['accept', 'modify', 'withdraw']))
    expect(d).not.toContain('defer')
  })

  test('org_admin has no owner actions', () => {
    const a = requestActionsFor('org_admin', 'triaged', 'feature', false)
    expect(a).not.toContain('quote')
    expect(a).not.toContain('triage')
  })

  test('super: triage from submitted; quote a triaged feature; schedule a triaged bug', () => {
    expect(requestActionsFor('super', 'submitted', '', false)).toEqual(
      expect.arrayContaining(['triage', 'decline', 'ai_rerun']))
    expect(requestActionsFor('super', 'triaged', 'feature', false)).toContain('quote')
    expect(requestActionsFor('super', 'triaged', 'feature', false)).not.toContain('schedule')
    expect(requestActionsFor('super', 'triaged', 'bug', false)).toContain('schedule')
    expect(requestActionsFor('super', 'triaged', 'bug', false)).not.toContain('quote')
  })

  test('super: requote a deferred, schedule an approved, done a scheduled', () => {
    expect(requestActionsFor('super', 'deferred', 'feature', false)).toContain('requote')
    expect(requestActionsFor('super', 'approved', 'feature', false)).toContain('schedule')
    expect(requestActionsFor('super', 'scheduled', 'feature', false)).toEqual(['done'])
  })

  test('terminal statuses offer nothing', () => {
    expect(requestActionsFor('super', 'done', '', false)).toEqual([])
    expect(requestActionsFor('super', 'declined', '', false)).toEqual([])
    expect(requestActionsFor('org_admin', 'done', '', false)).toEqual([])
  })
})

describe('hasUnansweredQuestions', () => {
  test('true only when a question has no answer', () => {
    expect(hasUnansweredQuestions([{ question: 'Q?', answer: null }])).toBe(true)
    expect(hasUnansweredQuestions([{ question: 'Q?', answer: 'A' }])).toBe(false)
    expect(hasUnansweredQuestions([{ history: 'x' }])).toBe(false)
    expect(hasUnansweredQuestions(null)).toBe(false)
  })
})
