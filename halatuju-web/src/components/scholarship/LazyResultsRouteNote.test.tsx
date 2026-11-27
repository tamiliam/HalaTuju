/** @jest-environment jsdom */
/**
 * TD-773: Step 3's results notes. Which note shows (`resultsRouteNote`), what each draws, and the
 * words themselves: the English is the owner's text, word for word, and every language names the
 * card's real "Results wrong? Edit them" link, so the note can never point at a link that is not there.
 */
import { render, screen } from '@testing-library/react'

import LazyResultsRouteNote, { resultsRouteNote } from './LazyResultsRouteNote'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (p?.link ? `${k}|${p.link}` : k),
    locale: 'en',
  }),
}))

describe('resultsRouteNote: which note Step 3 shows', () => {
  const KINDS = ['spm', 'stpm', 'matric', 'asasi', 'diploma'] as const

  it('post_spm: the warning to an SPM-only holder, nothing to a post-SPM holder', () => {
    expect(resultsRouteNote('post_spm', 'spm', true)).toBe('needsPostSpm')
    for (const k of KINDS.filter((x) => x !== 'spm')) expect(resultsRouteNote('post_spm', k, true)).toBeNull()
  })

  it('both: the PNGK hint for STPM, the overall CGPA hint for Matriculation / Asasi / Diploma, none for SPM', () => {
    expect(resultsRouteNote('both', 'stpm', true)).toBe('pngkOnly')
    for (const k of ['matric', 'asasi', 'diploma']) expect(resultsRouteNote('both', k, true)).toBe('cgpaOnly')
    expect(resultsRouteNote('both', 'spm', true)).toBeNull()
  })

  it("spm, either, no rule and an unread answer show nothing, whatever the results", () => {
    for (const routes of ['spm', 'either', null, undefined] as const) {
      for (const k of KINDS) expect(resultsRouteNote(routes, k, true)).toBeNull()
    }
  })

  it('no results yet: nothing (the card already asks for them)', () => {
    expect(resultsRouteNote('post_spm', 'spm', false)).toBeNull()
    expect(resultsRouteNote('both', 'stpm', false)).toBeNull()
    expect(resultsRouteNote('post_spm', null, false)).toBeNull()
  })
})

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

  it.each(['pngkOnly', 'cgpaOnly'] as const)('the %s hint: a small blue note', async (kind) => {
    render(<LazyResultsRouteNote kind={kind} />)
    const p = await screen.findByText(`documentsTab.resultsNote.${kind}`)
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
    expect(n.pngkOnly).toBe('For this gift, we look at your PNGK only. Your SPM grades do not count.')
  })

  it.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s: every note is there and the link is named by its key', (_l, c) => {
    const n = note(c)
    for (const k of ['postSpmTitle', 'postSpmBody', 'postSpmAdd', 'pngkOnly', 'cgpaOnly']) expect(n[k]).toBeTruthy()
    expect(n.postSpmAdd).toContain('“{link}”')
  })
})
