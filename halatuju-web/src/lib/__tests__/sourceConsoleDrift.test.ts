/**
 * THE DRIFT TEST for `lib/sourceConsole.ts` (source sign-in, 2026-10-30) — the stage keys and the
 * checklist part names a source console screen labels are the SERVER'S vocabulary:
 *
 *   * `SOURCE_STAGES` = the keys of `partner_comms.STAGE_LINES`, in email order (the server serves
 *     `source_console.STAGES`, which IS that table) — a stage the server adds and the web lacks
 *     would reach the filter and the tiles as a raw key, and the tiles would stop adding up;
 *   * the part names = `source_console.PARTS`' second column.
 *
 * Every one of them must also have its words in all three locales.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import {
  SOURCE_STAGES, contractStageKey, levelLabelKey, partLabel, refusalKey, stageLabelKey,
} from '@/lib/sourceConsole'
import { readApi } from '@/test/apiSource'

const block = (src: string, name: string) => {
  const start = src.indexOf(`${name} = (`)
  expect(start).toBeGreaterThan(-1)
  return src.slice(start, src.indexOf('\n)', start))
}

const stageLines = [...block(readApi('apps/scholarship/partner_comms.py'), 'STAGE_LINES')
  .matchAll(/\(\s*'(\w+)',\s*\(/g)].map((m) => m[1])
const parts = [...block(readApi('apps/scholarship/source_console.py'), 'PARTS')
  .matchAll(/\('\w+',\s*'(\w+)'\)/g)].map((m) => m[1])

const resolve = (cat: unknown, key: string) =>
  key.split('.').reduce<unknown>((node, k) => (node as Record<string, unknown> | undefined)?.[k], cat)

describe('the source console vocabulary vs the server', () => {
  test('the parse found the real tables (parse sanity)', () => {
    expect(stageLines.length).toBe(7)
    expect(parts).toContain('guardian_documents')
  })

  test('SOURCE_STAGES is STAGE_LINES, in the same order', () => {
    expect([...SOURCE_STAGES]).toEqual(stageLines)
  })

  test.each([['en', en], ['ms', ms], ['ta', ta]])('every stage, part and level has words in %s', (_l, cat) => {
    for (const s of stageLines) expect(typeof resolve(cat, stageLabelKey(s))).toBe('string')
    const t = (k: string) => (typeof resolve(cat, k) === 'string' ? (resolve(cat, k) as string) : k)
    for (const p of parts) expect(partLabel(t, p)).not.toBe(`admin.sourceConsole.part.${p}`)
    for (const lv of ['spm', 'stpm', 'matric', 'asasi', 'diploma', '']) {
      expect(typeof resolve(cat, levelLabelKey(lv))).toBe('string')
    }
    for (const code of ['not_ready', 'already_witnessed', 'contract_not_live', 'confirm_required',
      'name_required', 'name_too_long', 'not_found', 'source_unavailable', 'surprise']) {
      expect(typeof resolve(cat, refusalKey('witness', code))).toBe('string')
    }
  })
})

/**
 * Review L9: the refusal codes the witness POST and the profile PATCH can answer, and the contract
 * statuses `BursaryAgreement.status` can derive, read off the api's own source. A code the server
 * adds would otherwise reach the screen as "We could not … Try again"; a status, as a raw key.
 */
describe('the refusals and contract statuses vs the server', () => {
  const views = readApi('apps/scholarship/views_admin/source_console.py')
  const classBody = (name: string) => {
    const start = views.indexOf(`class ${name}(`)
    expect(start).toBeGreaterThan(-1)
    const next = views.indexOf('\nclass ', start + 1)
    return views.slice(start, next === -1 ? undefined : next)
  }
  const codes = (src: string) => [...src.matchAll(/_error\('(\w+)'/g)].map((m) => m[1])
  // Shared by every view: a switched-off source or user, and an out-of-scope id.
  const base = codes(classBody('_SourceConsoleBase'))
  // `bad_request` (a body that is not a JSON object) is a client bug, never a person's: generic words.
  const worded = (list: string[]) => [...new Set(list)].filter((c) => c !== 'bad_request')

  test('the parse found the real refusals (parse sanity)', () => {
    expect(base).toEqual(expect.arrayContaining(['source_unavailable', 'not_found']))
    expect(codes(classBody('AdminSourceWitnessView'))).toContain('contract_not_live')
  })

  test('every witness refusal has words of its own', () => {
    for (const code of worded([...base, ...codes(classBody('AdminSourceWitnessView'))])) {
      expect(refusalKey('witness', code)).toBe(`admin.sourceConsole.witness.error.${code}`)
    }
  })

  test('every profile refusal has words of its own', () => {
    for (const code of worded([...base.filter((c) => c !== 'not_found'),
      ...codes(classBody('AdminSourceProfileView'))])) {
      expect(refusalKey('profile', code)).toBe(`admin.sourceConsole.profile.error.${code}`)
    }
  })

  test('every contract status has words, in all three locales', () => {
    const model = readApi('apps/scholarship/models/agreements.py')
    const prop = model.slice(model.indexOf('def status(self):'))
    const statuses = [...prop.split(/\r?\n\s*\r?\n/)[0].matchAll(/return '(\w+)'/g)].map((m) => m[1])
    expect(statuses).toEqual(['executed', 'countersigned', 'binds', 'student_signed', 'draft'])
    for (const cat of [en, ms, ta]) {
      for (const s of [...statuses, null]) expect(typeof resolve(cat, contractStageKey(s as never))).toBe('string')
    }
  })
})
