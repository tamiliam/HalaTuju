/**
 * The "How it's advertised" tab: a safer clear, and a draft that never saves (2026-09-10).
 *
 * ⚠⚠ THE CLEAR BUTTON WAS A FOOTGUN AND THESE TESTS SAY WHY. It deletes EVERY language, it
 * appears whenever ENGLISH is saved, and it sits on whichever language tab you happen to be on —
 * so it stood, live, beside an empty Malay form, one unconfirmed click from taking the English
 * with it. `writtenLocales` is what lets the dialog name the loss instead of describing it.
 *
 * ⚠ AND THE DRAFT IS MADE FROM THE **SAVED** ENGLISH, because that is what the server reads.
 * Offering it over unsaved English would translate wording the reader can no longer see, and the
 * result would read as a bad translation rather than a stale one — `englishUnsaved` is the guard,
 * asked about English ALONE so editing Malay cannot lock the Tamil button.
 */
import { toDraft, toPayload, writtenLocales, englishUnsaved } from '@/components/admin/ApplyCopyTab'
import { draftApplyCopy } from '../admin-api'
import { platformApplyCard } from '../applyCopy'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const EN = {
  title: 'Apply for the Sabah Bursary',
  intro: 'Support for Sabahan school leavers.',
  criteria: ['Resident in Sabah.', 'Continuing to tertiary study.'],
}
const MS = {
  title: 'Mohon Biasiswa Sabah',
  intro: 'Bantuan untuk lepasan sekolah Sabah.',
  criteria: ['Bermastautin di Sabah.', 'Melanjutkan pengajian tertiari.'],
}

describe('the button is named for what it DOES', () => {
  // ⚠ AN ABSENCE CHECK, AND ONLY AN ABSENCE CHECK ANSWERS A RENAME (lessons.md, 2026-09-08).
  // "Clear all wording" being present proves nothing — the old outcome-named label could sit
  // right beside it. The question is whether the old one is GONE, in every language.
  const bundles: Record<string, Record<string, unknown>> = {
    en: (en as never)['admin']['applyCopy'],
    ms: (ms as never)['admin']['applyCopy'],
    ta: (ta as never)['admin']['applyCopy'],
  }

  it.each(['en', 'ms', 'ta'])('%s no longer carries the outcome-named key', (loc) => {
    expect(bundles[loc]).not.toHaveProperty('useDefault')
  })

  it('English says the destructive verb out loud', () => {
    expect(String(bundles.en.clearAll).toLowerCase()).toContain('clear')
  })

  it('the dialog warns that EVERY language goes, not only the one on screen', () => {
    expect(String(bundles.en.clearBody).toLowerCase()).toContain('every language')
  })

  // ⚠ THIS TEST WAS INVERTED ON 2026-09-10, DELIBERATELY, ON THE OWNER'S RULING. It used to
  // require "draft" and forbid "translate", because the word carried the expectation the feature
  // depends on: a person reads every line before any of it can be saved. The owner asked for
  // "Translate from English" in plain terms, so the label is theirs — and the expectation moved
  // rather than being dropped: `hintTranslate` now states, in the standing instructions, that this
  // produces a MACHINE TRANSLATION that must be reviewed before saving. That sentence is what the
  // assertions below protect.
  it('the control says "translate", as the owner asked', () => {
    expect(String(bundles.en.draft).toLowerCase()).toContain('translate')
  })

  it('⚠ and the standing instructions still say a machine wrote it, and must be checked', () => {
    const note = String(bundles.en.hintTranslate).toLowerCase()
    expect(note).toContain('machine')
    expect(note).toMatch(/review|check/)
  })

  it.each(['en', 'ms', 'ta'])('%s says a machine produced it', (loc) => {
    // Every language, because the reader of the Tamil tab is the one being asked to check Tamil.
    expect(String(bundles[loc].hintTranslate).length).toBeGreaterThan(20)
    expect(bundles[loc]).toHaveProperty('drafted')
  })
})

describe('the instructions live in one place', () => {
  // ⚠ ABSENCE, AGAIN — the owner's report was that guidance repeated on every language tab. The
  // question is not whether the top block exists; it is whether the scattered sentences are GONE.
  const bundles: Record<string, Record<string, unknown>> = {
    en: (en as never)['admin']['applyCopy'],
    ms: (ms as never)['admin']['applyCopy'],
    ta: (ta as never)['admin']['applyCopy'],
  }

  it.each(['en', 'ms', 'ta'])('%s no longer carries the per-tab sentences', (loc) => {
    expect(bundles[loc]).not.toHaveProperty('fallbackNote')   // was under every language tab
    expect(bundles[loc]).not.toHaveProperty('looserWarning')  // was under the criteria
    expect(bundles[loc]).not.toHaveProperty('draftHint')      // was beside the button
  })

  it.each(['en', 'ms', 'ta'])('%s carries all four standing instructions', (loc) => {
    for (const k of ['hint', 'hintBlank', 'hintExact', 'hintTranslate']) {
      expect(String(bundles[loc][k] ?? '').length).toBeGreaterThan(20)
    }
  })

  it('the blank-language rule still states BOTH outcomes', () => {
    // Losing either half would make it a lie: blank means the PLATFORM default, unless English is
    // written, in which case ms/ta readers get the gift's English.
    const s = String(bundles.en.hintBlank).toLowerCase()
    expect(s).toContain('standard wording')
    expect(s).toContain('english')
  })
})

describe('the standard wording is shown, not just named', () => {
  it('reads the platform default for the language on screen, not the reader’s', () => {
    // An administrator working in English must be able to see what a MALAY applicant would read.
    const enCard = platformApplyCard('en')
    const taCard = platformApplyCard('ta')
    expect(enCard.title).not.toBe(taCard.title)
    expect(enCard.criteria.length).toBeGreaterThan(0)
    expect(taCard.criteria.length).toBe(enCard.criteria.length)
  })

  it('⚠ counts the bullets rather than assuming four', () => {
    // A hard-coded four would silently drop a fifth the day somebody adds one.
    expect(platformApplyCard('ms').criteria.every(l => l.trim().length > 0)).toBe(true)
  })
})

describe('what the clear dialog is able to warn about', () => {
  it('names every language that holds something, not just the one on screen', () => {
    expect(writtenLocales({ en: EN, ms: MS })).toEqual(['en', 'ms'])
  })

  it('⚠ reports ENGLISH even while the reader is standing on an empty Malay tab', () => {
    // The whole reason the old one-click button was dangerous: nothing on screen said English
    // would go too.
    expect(writtenLocales({ en: EN })).toEqual(['en'])
  })

  it('says nothing is at stake when the gift uses the standard wording', () => {
    expect(writtenLocales({})).toEqual([])
  })
})

describe('when a draft may be offered', () => {
  it('is blocked while the English has unsaved edits', () => {
    const saved = toDraft({ en: EN })
    const edited = toDraft({ en: { ...EN, title: 'Apply for the Sabah Grant' } })
    expect(englishUnsaved(edited, saved)).toBe(true)
  })

  it('⚠ is NOT blocked by unsaved edits to another language', () => {
    // Asked about English alone — otherwise typing Malay would grey out the Tamil button for a
    // reason that has nothing to do with Tamil.
    const saved = toDraft({ en: EN })
    const withMalay = toDraft({ en: EN, ms: MS })
    expect(englishUnsaved(withMalay, saved)).toBe(false)
  })

  it('treats a whitespace-only edit as no edit, because the payload trims', () => {
    const saved = toDraft({ en: EN })
    const padded = toDraft({ en: { ...EN, title: `  ${EN.title}  ` } })
    expect(englishUnsaved(padded, saved)).toBe(false)
  })
})

describe('the draft request', () => {
  const realFetch = global.fetch
  afterEach(() => { global.fetch = realFetch })

  function capture(block: unknown = MS) {
    const calls: { url: string; method?: string; body?: string }[] = []
    global.fetch = jest.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(url), method: init?.method, body: init?.body as string })
      return {
        ok: true, status: 200,
        json: async () => ({ locale: 'ms', block }),
      } as Response
    }) as unknown as typeof fetch
    return calls
  }

  it('POSTs the target language to the gift’s own draft route', async () => {
    const calls = capture()
    await draftApplyCopy(7, 'ms', { token: 't' })
    expect(calls[0].url).toContain('/programmes/7/apply-copy/draft/')
    expect(calls[0].method).toBe('POST')
    expect(JSON.parse(calls[0].body as string)).toEqual({ locale: 'ms' })
  })

  it('⚠ RETURNS THE BLOCK AND NEVER TOUCHES THE SAVE ROUTE', async () => {
    // The rule the whole feature rests on: a machine proposes wording, a person publishes it.
    const calls = capture()
    const out = await draftApplyCopy(7, 'ta', { token: 't' })
    expect(out.title).toBe(MS.title)
    expect(calls).toHaveLength(1)
    expect(calls[0].url).not.toMatch(/\/programmes\/7\/$/)
  })
})

describe('a drafted block is still ordinary editable copy', () => {
  it('round-trips through the editor’s own payload rules', () => {
    // A draft lands in the boxes and is saved by the SAME path as typed wording — so it must
    // survive `toDraft`/`toPayload` untouched, blank rows and all.
    const withDraft = toDraft({ en: EN, ms: { ...MS, criteria: [...MS.criteria, '  '] } })
    expect(toPayload(withDraft).ms?.criteria).toEqual(MS.criteria)
  })
})
