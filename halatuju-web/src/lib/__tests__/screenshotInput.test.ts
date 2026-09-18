/**
 * Guardrail: a screenshot can be PASTED or DRAGGED into every surface that accepts one.
 *
 * Why this test exists. Paste and drag-and-drop shipped on 2026-07-30 into
 * `components/OrgRequestAttachments.tsx` — the request DETAIL page — and the plan named only that
 * file. The request CREATE form has its own screenshot block (it stages `File` objects, because
 * there is no request id to upload against until the request exists) and kept accepting uploads
 * alone. The owner had to report the same missing feature twice, on the surface where a screenshot
 * most naturally starts life: you take it, then you describe the bug.
 *
 * The mistake was one of SCOPE, not implementation: I searched for the attachments *component*,
 * found one, and never asked where else a screenshot enters the system. A unit test of the shared
 * helper would not have caught it — the helper was fine, it simply had one caller.
 *
 * ⚠ **WHAT THIS FILE KEPT, AND WHAT IT GAVE AWAY (code health H6).** The half worth keeping is the
 * DISK WALK: only reading the tree can answer "is there a surface nobody thought about?", and that
 * question is the whole reason the defect happened. The half it gave away is every claim about
 * what a paste DOES — because a source-shape check cannot see focus, and that is not hypothetical:
 * this file once asserted `onPaste=` was attached, went green, and the feature was dead on BOTH
 * surfaces, because a paste is dispatched at the FOCUSED element and bubbles upward while the
 * handler sat on an unfocusable <div>. Those claims now live in mounts:
 *
 *   * `src/components/OrgRequestAttachments.paste.test.tsx`  — the detail page
 *   * `src/app/admin/requests/page.paste.test.tsx`           — the create form
 *
 * So the rule enforced below is: **every surface that imports the shared helper is named here, and
 * every named surface has a rendered test of its own.** A third surface cannot appear with only a
 * source guard behind it.
 */
import { File as NodeFile } from 'node:buffer'
import * as fs from 'fs'
import * as path from 'path'

import { imagesFrom, namedForPaste } from '@/lib/screenshotInput'

// ⚠ `File` IS A BROWSER GLOBAL, AND ONLY NODE 20+ HAS IT. The production image — and so the deploy
// gate — runs Node 18, where a bare `new File(...)` is a ReferenceError. This suite passed on every
// dev box (Node 24) and failed the first time it ran where the app is built (code health H2,
// 2026-09-18). `node:buffer` has exported `File` since 18.13, so borrow it when the global is absent.
if (typeof (globalThis as { File?: unknown }).File === 'undefined') {
  (globalThis as { File?: unknown }).File = NodeFile
}

const SRC = path.join(__dirname, '..', '..')

/**
 * The surfaces, and the RENDERED test that proves each one works. Paths are relative to `src/`.
 * Adding a surface without a rendered test fails below; so does adding one and forgetting this
 * list, because the list is checked against the disk.
 */
const SURFACES = [
  {
    label: 'request detail (uploads immediately)',
    file: 'components/OrgRequestAttachments.tsx',
    renderedTest: 'components/OrgRequestAttachments.paste.test.tsx',
  },
  {
    label: 'request create form (stages files)',
    file: 'app/admin/requests/page.tsx',
    renderedTest: 'app/admin/requests/page.paste.test.tsx',
  },
]

/** Every `.ts`/`.tsx` under `src/`, tests excluded — the haystack the walk searches. */
function walk(dir: string, acc: string[]): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name !== 'node_modules') walk(full, acc)
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
      acc.push(full)
    }
  }
  return acc
}

/** Relative to `src/`, forward slashes always, so a path written here on Windows is the same
 *  string the Linux gate computes. */
const rel = (file: string) => path.relative(SRC, file).split(path.sep).join('/')

/** Every non-test file that routes a screenshot through the shared filter. `screenshotInput.ts`
 *  is the helper itself, not a surface. */
const found = walk(SRC, [])
  .filter((f) => rel(f) !== 'lib/screenshotInput.ts')
  .filter((f) => fs.readFileSync(f, 'utf8').includes("from '@/lib/screenshotInput'"))
  .map(rel)
  .sort()

describe('no screenshot surface goes unnoticed', () => {
  it('the walk actually read the tree (the floor)', () => {
    // A path change that matched nothing would make the assertion below vacuously true, which is
    // exactly the failure this whole file exists to prevent.
    expect(walk(SRC, []).length).toBeGreaterThan(200)
    expect(found.length).toBeGreaterThan(0)
  })

  it('⚠ EVERY SURFACE ON DISK IS NAMED HERE — a third one cannot appear quietly', () => {
    expect(found).toEqual(SURFACES.map((s) => s.file).sort())
  })

  it.each(SURFACES)('$label has a RENDERED test, not a source guard', ({ renderedTest }) => {
    // The claim a text scan cannot make: that a paste from where a person is actually typing
    // reaches this surface. Each named file mounts its surface and dispatches one.
    expect(fs.existsSync(path.join(SRC, renderedTest))).toBe(true)
  })

  it.each(SURFACES)('$label routes through the SHARED filter, not its own copy', ({ file }) => {
    // The duplication is what allowed the two surfaces to drift apart in the first place. This
    // one claim stays structural because it is about WHERE the rule lives, not about behaviour —
    // two correct copies would pass every rendered test and still be the original defect.
    const src = fs.readFileSync(path.join(SRC, file), 'utf8')
    expect(src).toMatch(/imagesFrom\(/)
    expect(src).not.toMatch(/filter\(\(f\) => f\.type\.startsWith\('image\//)
  })
})

describe('namedForPaste', () => {
  it('names a clipboard image, which arrives with none', () => {
    const pasted = new File([new Uint8Array([1, 2, 3])], '', { type: 'image/png' })
    const named = namedForPaste(pasted)
    expect(named.name).toMatch(/^screenshot-\d+\.png$/)
    expect(named.type).toBe('image/png')
  })

  it('leaves a picked file alone', () => {
    const picked = new File([new Uint8Array([1])], 'bug.png', { type: 'image/png' })
    expect(namedForPaste(picked)).toBe(picked)
  })

  it('normalises jpeg to jpg so the caption reads like a filename', () => {
    const pasted = new File([new Uint8Array([1])], '', { type: 'image/jpeg' })
    expect(namedForPaste(pasted).name).toMatch(/\.jpg$/)
  })

  it('falls back to png when the clipboard gives no usable subtype', () => {
    const pasted = new File([new Uint8Array([1])], '', { type: 'image/' })
    expect(namedForPaste(pasted).name).toMatch(/\.png$/)
  })
})

describe('imagesFrom', () => {
  const asList = (files: File[]) => files as unknown as FileList

  it('keeps images and drops everything else — a drop carries anything', () => {
    const list = asList([
      new File([new Uint8Array([1])], 'shot.png', { type: 'image/png' }),
      new File([new Uint8Array([1])], 'notes.pdf', { type: 'application/pdf' }),
      new File([new Uint8Array([1])], 'data.csv', { type: 'text/csv' }),
    ])
    const out = imagesFrom(list)
    expect(out.map((f) => f.name)).toEqual(['shot.png'])
  })

  it('names every image it returns', () => {
    const list = asList([new File([new Uint8Array([1])], '', { type: 'image/png' })])
    expect(imagesFrom(list)[0].name).not.toBe('')
  })

  it('is safe on null and empty — paste fires with no files at all', () => {
    expect(imagesFrom(null)).toEqual([])
    expect(imagesFrom(undefined)).toEqual([])
    expect(imagesFrom(asList([]))).toEqual([])
  })
})
