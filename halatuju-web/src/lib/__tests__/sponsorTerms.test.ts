/**
 * The pure decisions behind the sponsor-terms panel.
 *
 * Most of this is bookkeeping. Three cases are not, and they are why the module exists rather than
 * living inline in the components: clearing a quiz flag must WIPE the answers (or the editor shows
 * one thing and saves another), a locale is only "translated" when every section carries it, and a
 * server error code must never reach the screen as a raw key path.
 */
import {
  blankSection, checkpointCount, isEditable, moveSection, quizComplete, renumber,
  sectionsNeedingWork, setQuizFlag, termsErrorKey, translationProgress,
} from '../sponsorTerms'
import type { SponsorTermsSection } from '../admin-api'

const sec = (over: Partial<SponsorTermsSection> = {}): SponsorTermsSection => ({
  ...blankSection(1),
  heading_en: 'Your gift is a gift',
  body_en: 'Nothing is repaid to you.',
  ...over,
})

const GOOD_QUIZ = {
  tag: 'Your gift', plain: 'A donation, not a loan.', question: 'What comes back to you?',
  options: ['The money', 'Nothing — it was a gift', 'A share of earnings'],
  correct: 1, why: 'Nothing is repaid.',
}

describe('isEditable', () => {
  it('allows a draft and refuses anything published', () => {
    expect(isEditable({ status: 'draft' })).toBe(true)
    expect(isEditable({ status: 'active' })).toBe(false)
    expect(isEditable({ status: 'archived' })).toBe(false)
    expect(isEditable(null)).toBe(false)
  })
})

describe('quizComplete', () => {
  it('accepts three options with an answer marked', () => {
    expect(quizComplete(GOOD_QUIZ)).toBe(true)
  })

  it('refuses two options, four options, or no answer', () => {
    expect(quizComplete({ ...GOOD_QUIZ, options: ['a', 'b'] })).toBe(false)
    expect(quizComplete({ ...GOOD_QUIZ, options: ['a', 'b', 'c', 'd'] })).toBe(false)
    expect(quizComplete({ ...GOOD_QUIZ, correct: undefined })).toBe(false)
  })

  it('refuses a blank option — a checkpoint with an empty answer is unanswerable', () => {
    expect(quizComplete({ ...GOOD_QUIZ, options: ['a', '   ', 'c'] })).toBe(false)
  })

  it('accepts answer index 0, which a falsy check would wrongly reject', () => {
    expect(quizComplete({ ...GOOD_QUIZ, correct: 0 })).toBe(true)
  })

  it('handles a missing payload', () => {
    expect(quizComplete(undefined)).toBe(false)
    expect(quizComplete({})).toBe(false)
  })
})

describe('setQuizFlag', () => {
  it('WIPES the answers when the flag is cleared', () => {
    // Otherwise the editor would show "no checkpoint" while still holding the answers, and the
    // save would silently discard work still visible on screen.
    const withQuiz = sec({ is_quiz_candidate: true, quiz_en: GOOD_QUIZ, quiz_generated_model: 'g' })
    const off = setQuizFlag(withQuiz, false)
    expect(off.is_quiz_candidate).toBe(false)
    expect(off.quiz_en).toEqual({})
    expect(off.quiz_generated_model).toBe('')
  })

  it('turning it on does not invent a payload', () => {
    const on = setQuizFlag(sec(), true)
    expect(on.is_quiz_candidate).toBe(true)
    expect(on.quiz_en).toEqual({})
  })
})

describe('sectionsNeedingWork', () => {
  it('names a section missing its English body', () => {
    const rows = renumber([sec(), sec({ body_en: '' })])
    expect(sectionsNeedingWork(rows)).toEqual([2])
  })

  it('names a checkpoint whose question is half-written', () => {
    const rows = renumber([sec({ is_quiz_candidate: true, quiz_en: { options: ['a', 'b'] } })])
    expect(sectionsNeedingWork(rows)).toEqual([1])
  })

  it('is empty when everything is complete', () => {
    const rows = renumber([sec(), sec({ is_quiz_candidate: true, quiz_en: GOOD_QUIZ })])
    expect(sectionsNeedingWork(rows)).toEqual([])
  })
})

describe('checkpointCount', () => {
  it('counts only checkpoints a sponsor could actually answer', () => {
    const rows = renumber([
      sec({ is_quiz_candidate: true, quiz_en: GOOD_QUIZ }),
      sec({ is_quiz_candidate: true, quiz_en: { options: ['a'] } }),   // half-written
      sec(),
    ])
    expect(checkpointCount(rows)).toBe(1)
  })
})

describe('translationProgress', () => {
  const intro = { title_ms: '', title_ta: '', intro_ms: '', intro_ta: '' }

  it('reports partial progress without calling it complete', () => {
    const rows = renumber([sec({ heading_ms: 'Satu', body_ms: 'Teks.' }), sec()])
    const p = translationProgress({ ...intro, title_ms: 'Tajuk', intro_ms: 'Ringkas.' }, rows)
    expect(p.ms).toEqual({ done: 1, total: 2, complete: false })
  })

  it('is complete only when the intro AND every section carry the locale', () => {
    // Mirrors languages_available on the server: a half-translated version is served in English,
    // because falling back mid-page reads as a bug to the person it happens to.
    const rows = renumber([sec({ heading_ms: 'Satu', body_ms: 'Teks.' })])
    expect(translationProgress({ ...intro, title_ms: 'T', intro_ms: 'R' }, rows).ms.complete)
      .toBe(true)
    expect(translationProgress(intro, rows).ms.complete).toBe(false)
  })

  it('counts nothing as complete when there are no sections at all', () => {
    expect(translationProgress({ ...intro, title_ms: 'T', intro_ms: 'R' }, []).ms.complete)
      .toBe(false)
  })
})

describe('moveSection', () => {
  const rows = renumber([sec({ heading_en: 'A' }), sec({ heading_en: 'B' }), sec({ heading_en: 'C' })])

  it('moves a section and renumbers so the display stays honest', () => {
    const moved = moveSection(rows, 2, -1)
    expect(moved.map((s) => s.heading_en)).toEqual(['A', 'C', 'B'])
    expect(moved.map((s) => s.order)).toEqual([1, 2, 3])
  })

  it('refuses to move past either end rather than throwing', () => {
    expect(moveSection(rows, 0, -1)).toBe(rows)
    expect(moveSection(rows, 2, 1)).toBe(rows)
  })

  it('does not mutate the caller array', () => {
    const before = rows.map((s) => s.heading_en)
    moveSection(rows, 0, 1)
    expect(rows.map((s) => s.heading_en)).toEqual(before)
  })
})

describe('termsErrorKey', () => {
  it('maps a known refusal to its own message', () => {
    expect(termsErrorKey('publish_forbidden'))
      .toBe('admin.sponsors.terms.error.publish_forbidden')
    expect(termsErrorKey('quiz_ai_unconfigured'))
      .toBe('admin.sponsors.terms.error.quiz_ai_unconfigured')
  })

  it('falls back for anything unmapped, so a raw code can never reach the screen', () => {
    expect(termsErrorKey('something_new')).toBe('admin.sponsors.terms.error.generic')
    expect(termsErrorKey(undefined)).toBe('admin.sponsors.terms.error.generic')
  })
})
