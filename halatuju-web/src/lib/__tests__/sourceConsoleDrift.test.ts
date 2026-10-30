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
import { SOURCE_STAGES, levelLabelKey, partLabel, refusalKey, stageLabelKey } from '@/lib/sourceConsole'
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
