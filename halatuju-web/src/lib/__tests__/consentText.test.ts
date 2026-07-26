/**
 * Consent text guards — `2026-draft-7`.
 *
 * ONE consent version is displayed to everyone, by owner decision 2026-07-26: both the form and the
 * read-only "What you agreed to" panel render the current wording, so a student who consented under
 * an earlier version sees today's text. Per-version archived bodies were built and then removed as
 * complexity that buys a panel nuance rather than a real protection (see TD-166). The RECORD is
 * unaffected — `Consent.version` still stores what each person agreed to.
 *
 * These tests pin the properties of the live text that are easy to break by accident.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

type Consent = { text: string; textMinor: string; archive?: unknown }
const LOCALES: Record<string, Consent> = {
  en: (en.scholarship as never as { consent: Consent }).consent,
  ms: (ms.scholarship as never as { consent: Consent }).consent,
  ta: (ta.scholarship as never as { consent: Consent }).consent,
}

describe('consent text (draft-7)', () => {
  it('is a single version — no per-version archive in the catalogues', () => {
    // Guards the 2026-07-26 decision. An archive block reappearing means someone started
    // reintroducing per-version display; that needs an owner decision, not a quiet edit.
    for (const c of Object.values(LOCALES)) expect(c.archive).toBeUndefined()
  })

  it('states what a sponsor sees during sponsorship — the draft-7 widening', () => {
    expect(LOCALES.en.text).toContain('During sponsorship')
    expect(LOCALES.en.textMinor).toContain('During sponsorship')
    expect(LOCALES.ms.text).toContain('Semasa penajaan')
    expect(LOCALES.ta.text).toContain('ஆதரவு வழங்கப்படும்போது')
  })

  it('keeps both absolutes in every language', () => {
    // Identity and documents are the promises draft-7 must not weaken while it widens.
    const NEVER: Record<string, string[]> = {
      en: ['NRIC', 'documents'], ms: ['NRIC', 'dokumen'], ta: ['NRIC', 'ஆவணங்க'],
    }
    for (const [loc, c] of Object.entries(LOCALES)) {
      for (const needle of NEVER[loc]) {
        expect(c.text).toContain(needle)
        expect(c.textMinor).toContain(needle)
      }
    }
  })

  it('uses a literal bullet — the renderer has no markdown lists', () => {
    // ScholarshipConsent.renderRich handles ONLY **bold**; it preserves newlines, so `•` renders as
    // a bullet where a markdown `- ` would print a hyphen to the student.
    for (const c of Object.values(LOCALES)) {
      expect(c.text).toContain('\n• ')
      expect(c.textMinor).toContain('\n• ')
      expect(c.text).not.toMatch(/\n- /)
      expect(c.textMinor).not.toMatch(/\n- /)
    }
  })

  it('uses only placeholders the component actually supplies', () => {
    // An unknown placeholder is left untouched by interpolateMessage — it would render as a raw
    // `{token}` in a legal text shown to a student.
    const ALLOWED = new Set(['student_name', 'student_nric', 'he_or_she', 'his_or_her',
                             'him_or_her', 'programmeName'])
    for (const c of Object.values(LOCALES)) {
      for (const body of [c.text, c.textMinor]) {
        // exec loop, not matchAll: this project's tsconfig has no downlevelIteration.
        const re = /\{([a-zA-Z_]+)\}/g
        let m: RegExpExecArray | null
        while ((m = re.exec(body)) !== null) expect(ALLOWED.has(m[1])).toBe(true)
      }
    }
  })

  it('the parent version speaks in the guardian voice and protects them too', () => {
    expect(LOCALES.en.textMinor).toContain('parent or guardian')
    expect(LOCALES.en.textMinor).toContain('nor ours')      // the guardian's own details
    expect(LOCALES.en.text).toContain("nor my parents'")    // the student's version protects theirs
  })
})
