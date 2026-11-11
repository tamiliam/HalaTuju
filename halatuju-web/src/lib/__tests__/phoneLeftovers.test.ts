/**
 * Phone layout leftovers (A4.3): TD-453 (hover only where a device can hover), TD-464 (the shared selects are 44 px
 * on a phone; mobile-check skips a fixed bar's children), TD-466 (the SPM grade picker is wide enough for "Grade").
 */
import { readWeb, walkFloor, WEB_ROOT } from '@/test/sourceGuard'
import * as path from 'path'

const HOVER_REVEAL = /group-hover[^\s"'`]*:(block|flex|inline|grid|opacity-100|visible)|hover:(block|flex|visible|opacity-100)|peer-hover[^\s"'`]*:(block|flex|visible|opacity-100)/

describe('TD-453 hoverOnlyWhenSupported', () => {
  it('the Tailwind flag is on', () => {
    expect(readWeb('tailwind.config.ts', 'the flag lives here')).toMatch(/hoverOnlyWhenSupported:\s*true/)
  })

  it('the only hover:opacity-100 / group-hover reveals left are harmless: the always-visible toast dismiss and the admin rail chip (desktop; opens on focus too)', () => {
    const files = walkFloor(path.join(WEB_ROOT, 'src'), 600, 'a walk that found nothing would pass for ever',
      { exts: ['.ts', '.tsx'] })
    const rels = files.map((f) => path.relative(WEB_ROOT, f).split(path.sep).join('/'))
    const hits = rels.filter((rel) => !/(__tests__\/|\.test\.tsx?$)/.test(rel))
      .filter((rel) => HOVER_REVEAL.test(readWeb(rel, 'sweep for hover-only reveals')))
    expect(hits).toEqual(['src/components/Toast.tsx', 'src/components/admin/Sidebar.tsx'])
  })
})

describe('TD-464 shared selects and the fixed-bar rule', () => {
  it('Language and Theme selects are 44 px below md', () => {
    for (const f of ['LanguageSelector', 'ThemeSelector']) {
      expect(readWeb(`src/components/${f}.tsx`, 'a shared select')).toMatch(/<select[\s\S]*?max-md:min-h-11/)
    }
  })

  it('mobile-check names the widest element outside a fixed ancestor, not just outside a fixed element', () => {
    const m = readWeb('mobile-check/measure.ts', 'the widest-element walk')
    expect(m).toMatch(/const insideFixed = /)
    expect(m).toMatch(/if \(insideFixed\(el\) \|\| insideSideScroller\(el\)\) continue/)
  })
})

describe('TD-466 grade picker', () => {
  it('the SPM grade pickers are w-24 (w-20 clipped "Grade" at 16 px text)', () => {
    const s = readWeb('src/components/SpmResultsBlock.tsx', 'the grade pickers')
    expect(s).not.toMatch(/min-h-11 w-20 /)
    expect(s.match(/min-h-11 w-24 flex-shrink-0/g)).toHaveLength(3)
  })
})

describe('TD-450 (3) the Sheet clears the notch in landscape', () => {
  it('its title row, body and footer use .sheet-pad-x, which pads by the left and right safe areas', () => {
    const s = readWeb('src/components/Sheet.tsx', 'the sheet is fixed, so the body insets do not reach it')
    expect(s.match(/sheet-pad-x/g)).toHaveLength(3)
    const css = readWeb('src/app/globals.css', 'the class lives here')
    expect(css).toMatch(/\.sheet-pad-x \{[^}]*max\(1\.25rem, env\(safe-area-inset-left\)\)[^}]*max\(1\.25rem, env\(safe-area-inset-right\)\)/)
  })
})
