/**
 * Regression (T5c P5 hotfix): the Organisation Overview row kept the old label "Programmes" after the
 * new Programmes landing row was added, so the sidebar showed two rows with the same name.
 * For every role and locale, no group may repeat a label; no two rows may share a chord.
 */
import { NAV_ITEMS, ROLE_NAMES, visibleNav, NO_PROBES } from './navigation'
import en from '../messages/en.json'
import ms from '../messages/ms.json'
import ta from '../messages/ta.json'

const LOCALES: Record<string, unknown> = { en, ms, ta }

function lookup(messages: unknown, key: string): string | undefined {
  let cur: unknown = messages
  for (const part of key.split('.')) {
    if (cur && typeof cur === 'object') cur = (cur as Record<string, unknown>)[part]
    else return undefined
  }
  return typeof cur === 'string' ? cur : undefined
}

describe('sidebar labels', () => {
  for (const [locale, messages] of Object.entries(LOCALES)) {
    for (const role of ROLE_NAMES) {
      it(`no repeated label within a group: ${role} / ${locale}`, () => {
        const groups = visibleNav({ role, probes: NO_PROBES })
        for (const g of groups) {
          const labels = g.items.map((i) => lookup(messages, i.labelKey))
          labels.forEach((l, n) => expect(l).toBeTruthy())
          expect(new Set(labels).size).toBe(labels.length)
        }
      })
    }
  }

  it('no two rows share a shortcut chord', () => {
    const chords = NAV_ITEMS.map((i) => i.chord).filter(Boolean)
    expect(new Set(chords).size).toBe(chords.length)
  })
})
