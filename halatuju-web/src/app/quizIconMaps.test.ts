/**
 * TD-705: every icon name a quiz's data uses must have an emoji in that quiz page's ICON_EMOJI map,
 * else the card shows the fallback question mark. The python data files and the tsx pages are read as
 * text (no import), so the two sides cannot drift apart unnoticed. Also fails on a map name the data
 * never uses, so the STPM list cannot grow dead entries again.
 */
import { readFileSync } from 'fs'
import { join } from 'path'

const read = (rel: string) => readFileSync(join(__dirname, rel), 'utf8')

function dataIcons(pyFile: string): string[] {
  const src = read(`../../../halatuju_api/apps/courses/${pyFile}`)
  return Array.from(new Set(Array.from(src.matchAll(/['"]icon['"]\s*:\s*['"]([a-z_]+)['"]/g), (m) => m[1])))
}

function mapIcons(tsxFile: string): string[] {
  const src = read(tsxFile)
  const start = src.indexOf('const ICON_EMOJI')
  const body = src.slice(start, src.indexOf('\n}\n', start))
  const noComments = body.replace(/\/\/.*$/gm, '')
  return Array.from(noComments.matchAll(/\b([a-z_]+):\s*'/g), (m) => m[1])
}

describe.each([
  ['main quiz', 'quiz_data.py', 'quiz/page.tsx'],
  ['STPM quiz', 'stpm_quiz_data.py', 'stpm/quiz/page.tsx'],
])('%s icons', (_label, pyFile, tsxFile) => {
  const used = dataIcons(pyFile)
  const mapped = mapIcons(tsxFile)

  it('finds the icon names in the data and the map (the readers work)', () => {
    expect(used.length).toBeGreaterThan(30)
    expect(mapped.length).toBeGreaterThan(30)
  })

  it('has an emoji for every icon name the data uses', () => {
    expect(used.filter((n) => !mapped.includes(n))).toEqual([])
  })

  it('has no map entry the data never uses', () => {
    expect(mapped.filter((n) => !used.includes(n))).toEqual([])
  })
})
