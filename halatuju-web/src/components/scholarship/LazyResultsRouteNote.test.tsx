/** @jest-environment jsdom */
/**
 * TD-773: Step 3's results notes. What each draws (which one shows is `lib/__tests__/resultsRouteNote.test.ts`), and the
 * words themselves: the English is the owner's text, word for word, and every language names the
 * card's real "Results wrong? Edit them" link, so the note can never point at a link that is not there.
 */
import { render, screen } from '@testing-library/react'

import LazyResultsRouteNote from './LazyResultsRouteNote'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (p?.link ? `${k}|${p.link}` : k),
    locale: 'en',
  }),
}))

describe('LazyResultsRouteNote: what it draws', () => {
  it('the warning: a caution box with the title, both lines and the real link name; no button', async () => {
    render(<LazyResultsRouteNote kind="needsPostSpm" />)
    const box = await screen.findByText('documentsTab.resultsNote.postSpmTitle')
    const note = box.closest('[data-results-note="needsPostSpm"]') as HTMLElement
    expect(note.className).toContain('bg-caution-50')
    expect(note.querySelector('svg')).not.toBeNull()
    expect(screen.getByText('documentsTab.resultsNote.postSpmBody')).toBeTruthy()
    expect(screen.getByText('documentsTab.resultsNote.postSpmAdd|scholarship.apply.resultsWrong')).toBeTruthy()
    expect(note.querySelector('button, a')).toBeNull()
  })

  it('the PNGK hint: a small blue note', async () => {
    render(<LazyResultsRouteNote kind="pngkOnly" />)
    const p = await screen.findByText('documentsTab.resultsNote.pngkOnly')
    expect(p.className).toContain('bg-info-50')
  })
})

describe('the words', () => {
  type Cat = { documentsTab: { resultsNote: Record<string, string> }; scholarship: { apply: { resultsWrong: string } } }
  const note = (c: unknown) => (c as Cat).documentsTab.resultsNote

  it("the English is the owner's text", () => {
    const n = note(en)
    expect(n.postSpmTitle).toBe('This gift needs results from after SPM')
    expect(n.postSpmBody).toBe('This gift is for students who already have STPM, Matriculation, Asasi or Diploma '
      + 'results. We only have your SPM results.')
    expect(n.postSpmAdd.replace('{link}', (en as unknown as Cat).scholarship.apply.resultsWrong)).toBe(
      'If you have these results, add them by clicking the “Results wrong? Edit them” link above. '
      + 'If you do not have them yet, this gift is not for you this time.')
    expect(n.pngkOnly).toBe('For this gift, we check your PNGK, not your SPM grades.')
    expect(n.cgpaOnly).toBeUndefined()
  })

  it.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s: every note is there and the link is named by its key', (_l, c) => {
    const n = note(c)
    for (const k of ['postSpmTitle', 'postSpmBody', 'postSpmAdd', 'pngkOnly']) expect(n[k]).toBeTruthy()
    expect(n.cgpaOnly).toBeUndefined()
    expect(n.postSpmAdd).toContain('“{link}”')
  })
})
