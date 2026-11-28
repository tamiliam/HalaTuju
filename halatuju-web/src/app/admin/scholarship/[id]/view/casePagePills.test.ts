/**
 * THE CASE PAGE'S TEXT PILLS FOLLOW THE PHONE PILL STANDARD (editor fixes, 27 Nov 2026).
 *
 * On a phone a text pill — a status badge, a tag, a Pass / Fail choice — is a softly squared label
 * (`rounded-md`, from `@/lib/phonePill`), not a fully round end. Every `rounded-full` on the admin
 * case page (this route, the source drawer it opens and the interview card it lazy-loads) must carry
 * a phone pill class on the same line, unless it is one of the icon-only or truly circular shapes
 * named in ALLOWED below (dots, the ≠ mark, a calendar day). A new rounded-full text pill without a
 * phone pill class fails here; so does an ALLOWED entry that no longer matches anything (stale).
 * The exact per-file PHONE_PILL counts stay in rule 17's ledger (`src/lib/__tests__/mobileStandard.test.ts`);
 * this sweep only catches a NEW rounded-full text pill the ledger cannot see.
 */
import fs from 'fs'
import path from 'path'

const SRC = path.resolve(__dirname, '..', '..', '..', '..', '..')   // halatuju-web/src
const CASE_DIR = path.join(SRC, 'app', 'admin', 'scholarship', '[id]')
const SOURCE_DIR = path.join(SRC, 'components', 'source')
const EXTRA = [path.join(SRC, 'components', 'admin', 'InterviewScheduleCard.tsx')]

/** Icon-only / circular shapes that stay rounded-full on a phone: file (from src), a snippet of the
 *  line, how many lines it matches, and why. */
const ALLOWED: { file: string; snippet: string; count: number; why: string }[] = [
  { file: 'app/admin/scholarship/[id]/view/shared.tsx', snippet: 'h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full', count: 1,
    why: 'DiffMarker: the ≠ icon mark, a circle' },
  { file: 'app/admin/scholarship/[id]/view/VerificationVerdict.tsx', snippet: 'h-2 w-2 rounded-full', count: 2,
    why: 'tone dots (aria-hidden)' },
  { file: 'components/admin/InterviewScheduleCard.tsx', snippet: 'h-1.5 w-1.5 rounded-full', count: 2, why: 'slot dots' },
  { file: 'components/admin/InterviewScheduleCard.tsx', snippet: 'h-1 w-1 rounded-full', count: 1, why: 'a day-has-slots dot' },
  { file: 'components/admin/InterviewScheduleCard.tsx', snippet: 'h-9 w-9 items-center justify-center rounded-full', count: 1,
    why: 'a calendar day cell, a circle by design' },
]

function sources(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) return sources(p)
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : []
  })
}

const rel = (p: string) => path.relative(SRC, p).split(path.sep).join('/')
const isComment = (l: string) => /^\s*(\/\/|\*|\/\*|\{\/\*)/.test(l)

function roundedLines(): { file: string; line: string }[] {
  return [...sources(CASE_DIR), ...sources(SOURCE_DIR), ...EXTRA].flatMap((p) =>
    fs.readFileSync(p, 'utf8').split(/\r?\n/)
      .filter((l) => l.includes('rounded-full') && !isComment(l))
      .map((line) => ({ file: rel(p), line: line.trim() })))
}

describe('case page text pills on a phone', () => {
  const lines = roundedLines()

  it('scans the real case page', () => {
    expect(lines.length).toBeGreaterThan(20)
    expect(lines.some((l) => l.file.endsWith('view/FactsInDoubt.tsx'))).toBe(true)
  })

  it('every rounded-full text pill carries a phone pill class', () => {
    const offenders = lines.filter(({ file, line }) =>
      !/PHONE_PILL|max-md:rounded-md/.test(line)
      && !ALLOWED.some((a) => a.file === file && line.includes(a.snippet)))
    expect(offenders).toEqual([])
  })

  it('every allowed icon-only shape still exists (no stale entries)', () => {
    for (const a of ALLOWED) {
      const hits = lines.filter((l) => l.file === a.file && l.line.includes(a.snippet))
      expect([a.file, a.snippet, hits.length]).toEqual([a.file, a.snippet, a.count])
    }
  })
})
