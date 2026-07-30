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
 * helper would not have caught it — the helper was fine, it simply had one caller. So the assertion
 * here is deliberately a STATIC SOURCE check over both files: it fails when a surface exists that
 * takes screenshots and does not accept them the two other ways.
 *
 * If a THIRD surface ever accepts screenshots, add it to SURFACES. That is the point.
 */
import * as fs from 'fs'
import * as path from 'path'

import { imagesFrom, namedForPaste } from '@/lib/screenshotInput'

const ROOT = path.join(__dirname, '..', '..')

const SURFACES = [
  { label: 'request detail (uploads immediately)', file: 'components/OrgRequestAttachments.tsx' },
  { label: 'request create form (stages files)', file: 'app/admin/requests/page.tsx' },
]

const read = (rel: string) => fs.readFileSync(path.join(ROOT, rel), 'utf8')

describe('every screenshot surface accepts paste and drop', () => {
  for (const { label, file } of SURFACES) {
    describe(label, () => {
      const src = read(file)

      it('handles paste somewhere that can actually RECEIVE it', () => {
        /*
         * ⚠ THIS ASSERTION WAS WRONG ONCE, and the wrong version passed.
         *
         * It used to be `expect(src).toMatch(/onPaste=/)` — which proved a handler was ATTACHED,
         * not that it could ever FIRE. Both surfaces put `onPaste` on a plain <div>. A paste event
         * is dispatched at the FOCUSED element and bubbles UPWARD; an unfocused div with no
         * tabIndex is never on that path. So paste was dead on both surfaces while this test was
         * green and the hint text promised the feature. The owner reported it — for the third time
         * on the same feature.
         *
         * A source-shape check cannot know about focus. What it CAN pin is the mechanism we chose
         * because of it: listen on the document, filter to files, and clean up on unmount.
         */
        expect(src).toMatch(/document\.addEventListener\('paste'/)
        expect(src).toMatch(/document\.removeEventListener\('paste'/)
        expect(src).toMatch(/clipboardData/)
        // A dead div-level handler must not linger beside the live one, or a paste inside the
        // panel is handled twice and uploads the same image twice.
        expect(src).not.toMatch(/onPaste=/)
      })

      it('leaves a TEXT paste completely alone', () => {
        // The price of listening document-wide: Ctrl+V into any field must be untouched. So the
        // handler body must BAIL OUT on a fileless clipboard BEFORE it calls preventDefault.
        const bodyStart = src.indexOf('(e: ClipboardEvent) => {')
        expect(bodyStart).toBeGreaterThan(-1)
        const body = src.slice(bodyStart, src.indexOf("document.addEventListener('paste'", bodyStart))

        const guardAt = body.search(/if \([^)]*(?:!files\.length|length === 0)[^)]*\) return/)
        const preventAt = body.indexOf('preventDefault')
        expect(guardAt).toBeGreaterThan(-1)
        expect(preventAt).toBeGreaterThan(guardAt)
      })

      it('handles drag-and-drop', () => {
        expect(src).toMatch(/onDrop=/)
        expect(src).toMatch(/onDragOver=/)
        expect(src).toMatch(/dataTransfer/)
      })

      it('routes through the SHARED filter rather than its own copy', () => {
        // The duplication is what allowed the two surfaces to drift apart in the first place.
        expect(src).toContain("from '@/lib/screenshotInput'")
        expect(src).toMatch(/imagesFrom\(/)
        // No local re-implementation of "is it an image".
        expect(src).not.toMatch(/filter\(\(f\) => f\.type\.startsWith\('image\//)
      })

      it('offers a VISIBLE drop zone, not just a link and a promise', () => {
        /*
         * The third shape of the same mistake. First the handler was missing on one surface; then
         * it was attached where it could never fire; then it fired but there was nothing on screen
         * to aim a drag at — a text link plus hint copy saying "you can also paste or drag an image
         * in", with the wrapper collapsing to the height of the link. The owner asked whether a
         * surface had been built at all. It had not.
         *
         * A drop zone must be a TARGET BEFORE the drag begins: real padding, a dashed edge, and a
         * state change while a file is over it. Asserting the copy alone is what let a promise
         * ship without the thing it promised.
         */
        expect(src).toMatch(/border-dashed/)          // it looks like a drop target at rest
        expect(src).toMatch(/py-6/)                   // it has height to aim at
        expect(src).toContain('attachments.dropZone') // it says what you can do
        expect(src).toMatch(/dragging\s*\n?\s*\?/)    // and it reacts while a file is over it
      })
    })
  }
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
