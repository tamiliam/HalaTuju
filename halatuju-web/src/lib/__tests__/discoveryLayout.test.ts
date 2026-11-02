/**
 * Static guard: student discovery on a phone (Mobile M3) — the course search, the course pages, the
 * saved list, the report and the shared footer.
 *
 * The failures it prevents.
 *   - The STPM stream page put 240 schools in a 600 px box with its own scroll: on a phone the thumb
 *     scrolled the box, not the page, and was trapped. A fixed-pixel `max-h-[…px]` scroll box on a
 *     course page is refused here (on a phone the page scrolls; nothing scrolls inside it).
 *   - Save sat in the sidebar card, which a phone draws LAST: 6,800 px down on a diploma with 18
 *     colleges. The phone now saves from a sticky bar that clears the home bar.
 *   - A `truncate` school name set the column's width and pushed the STPM page 8 px past a 375 px
 *     screen: every phone-ordered section is `min-w-0`.
 *   - The search filters filled a phone's first screen; they now live in a sheet below `md`.
 *   - Footer links were 18-20 px tall; the saved list's compare tick box was desktop-only and
 *     explained only by a hover `title=`.
 *
 * What this proves: the classes and structure that do those things are still there. What it does
 * NOT prove: that anything fits — jsdom cannot lay out a page. mobile-check measures that in a real
 * browser (the live course pages, and the sandbox: search-filters, saved-list, saved-compare, report)
 * at 360 and 390 in all three languages.
 */
import { readWeb } from '@/test/sourceGuard'

const COURSE_PAGES = {
  'src/app/course/[id]/page.tsx': readWeb('src/app/course/[id]/page.tsx', 'the SPM / pre-U course page'),
  'src/app/stpm/[id]/page.tsx': readWeb('src/app/stpm/[id]/page.tsx', 'the STPM degree course page'),
}
const COURSE_PARTS = {
  ...COURSE_PAGES,
  'src/components/CourseDetailShared.tsx': readWeb('src/components/CourseDetailShared.tsx', 'the course pages\' shared pieces'),
  'src/components/RequirementsCard.tsx': readWeb('src/components/RequirementsCard.tsx', 'the entry requirements card'),
  'src/components/CareerPathways.tsx': readWeb('src/components/CareerPathways.tsx', 'the careers card'),
  'src/components/course/PreUInstitutions.tsx': readWeb('src/components/course/PreUInstitutions.tsx',
    'the Form Six schools and matriculation colleges (the 600 px box lived here)'),
}
const classes = (s: string) => s.split(/\s+/)

describe('the course pages on a phone (Mobile M3)', () => {
  it.each(Object.entries(COURSE_PARTS))('%s has no fixed-pixel inner scroll box', (_f, src) => {
    // A `max-h-[600px]` (any px) box: whether or not it also scrolls today, it is the trap's shape.
    expect(src.match(/max-h-\[\d+px\]/g) ?? []).toEqual([])
    expect(src.match(/className="[^"]*\boverflow-y-(auto|scroll)\b[^"]*"/g) ?? []).toEqual([])
  })

  it.each(Object.entries(COURSE_PAGES))('%s dissolves its columns on a phone and orders every section', (_f, src) => {
    // Rule 15 (M4b): no gap on a phone — the sections are divided by their own hairlines.
    expect(src).toMatch(/className="flex flex-col md:grid md:grid-cols-3 md:gap-8"/)
    const cols = src.match(/className="(contents [^"]+)"/g) ?? []
    expect(cols.length).toBe(2)
    for (const c of cols) expect(c).toMatch(/\bmd:block\b/)
    const items = Array.from(src.matchAll(/className="(order-\d [^"]*)"/g), (m) => m[1])
    expect(items.length).toBeGreaterThanOrEqual(6)
    for (const item of items) expect(classes(item)).toEqual(expect.arrayContaining(['min-w-0', 'md:order-none']))
    // Quick facts first, then the entry requirements.
    expect(src.indexOf('order-1 ')).toBeGreaterThan(-1)
    expect(src.indexOf('order-2 ')).toBeGreaterThan(-1)
  })

  it.each(Object.entries(COURSE_PAGES))('%s saves from the sticky phone bar', (_f, src) => {
    expect(src).toMatch(/<CourseSaveBar isSaved=\{isSaved\} onSave=\{handleSave\} \/>/)
  })

  it('the Save bar is sticky, phone-only, clears the home bar and tells the toast its height', () => {
    const shared = COURSE_PARTS['src/components/CourseDetailShared.tsx']
    const bar = shared.slice(shared.indexOf('export function CourseSaveBar'))
    const cls = bar.match(/data-testid="course-save-bar"\s+className="([^"]+)"/)
    expect(cls).not.toBeNull()
    expect(classes(cls![1])).toEqual(expect.arrayContaining(['sticky', 'bottom-0', 'md:hidden',
      'pb-[max(0.75rem,env(safe-area-inset-bottom))]']))
    expect(bar).toMatch(/useBottomBarInset\(bar\)/)
    expect(bar).toMatch(/min-h-12/)
    // The sidebar's Save button is the desktop's only.
    const actions = shared.slice(shared.indexOf('export function CourseActions'), shared.indexOf('export function CourseSaveBar'))
    expect(actions).toMatch(/className=\{`hidden md:block w-full min-h-11/)
  })

  it('the toast rises above a sticky bottom bar', () => {
    const toast = readWeb('src/components/Toast.tsx', 'the toast container')
    expect(toast).toMatch(/bottom-\[calc\(max\(1rem,env\(safe-area-inset-bottom\)\)\+var\(--bottom-bar,0px\)\)\]/)
  })
})

describe('the course search on a phone (Mobile M3)', () => {
  const search = readWeb('src/app/search/page.tsx', 'the course search page')

  it('a phone gets the Filters button and the sheet; the pills are the desktop\'s', () => {
    expect(search).toMatch(/onClick=\{\(\) => setFiltersOpen\(true\)\}/)
    const button = search.match(/aria-haspopup="dialog"\s+className="([^"]+)"/)
    expect(button).not.toBeNull()
    expect(classes(button![1])).toEqual(expect.arrayContaining(['md:hidden', 'h-12', 'shrink-0']))
    expect(search).toMatch(/\{\/\* Filter row \*\/\}\s*<div className="flex flex-wrap items-center gap-2">\s*\{\/\*[^*]*\*\/\}\s*<div className="hidden md:contents">/)
    expect(search).toMatch(/<SearchFilterSheet\b/)
    // Mounted with the page, never behind an import(): it is a phone's only way to filter.
    expect(search).not.toMatch(/import\(\s*['"]@\/components\/search\/SearchFilterSheet/)
    expect(search).toMatch(/^import SearchFilterSheet/m)
  })

  it('the search box can shrink beside the button (one row at 360 in Tamil)', () => {
    expect(search).toMatch(/<div className="mb-3 flex gap-2">\s*<div className="relative min-w-0 flex-1">/)
  })

  it('the picked filters wrap as 44 px chips, never a sideways strip', () => {
    const list = search.match(/aria-label=\{t\('discovery\.activeFilters'\)\} className="([^"]+)"/)
    expect(list).not.toBeNull()
    expect(classes(list![1])).toEqual(expect.arrayContaining(['flex', 'flex-wrap', 'md:hidden']))
    expect(classes(list![1])).not.toContain('overflow-x-auto')
    expect(search).toMatch(/aria-label=\{t\('discovery\.removeFilter', \{ name: p\.label \}\)\}\s+className="inline-flex min-h-11/)
  })
})

describe('saved courses on a phone (Mobile M3)', () => {
  const card = readWeb('src/components/saved/SavedCourseCard.tsx', 'one saved course')
  const page = readWeb('src/app/saved/page.tsx', 'the saved courses page')

  it('the compare tick box is on every width, with its word beside it — no hover title', () => {
    expect(card + page).not.toMatch(/\stitle=["{]/)
    expect(card + page).not.toMatch(/hidden md:flex/)
    expect(card).toMatch(/<label className="[^"]*\bmin-h-11\b[^"]*">\s*<input type="checkbox"[\s\S]*?\{t\('discovery\.compareSelect'\)\}\s*<\/label>/)
  })

  it('the status pills wrap and are 44 px', () => {
    expect(card).toMatch(/<div className="mt-3 flex flex-wrap items-center gap-2">/)
    expect(card).toMatch(/const pill = 'inline-flex min-h-11 /)
  })

  it('no compare word is hard-coded Malay any more — on the page or in the compare component', () => {
    // The compare words moved into SavedCompare.tsx; a guard that read only the page could never see
    // them come back (M3 review).
    const compare = readWeb('src/components/saved/SavedCompare.tsx', 'the saved-course compare')
    for (const malay of ['Bandingkan', 'Batal', 'Perbandingan Kursus', 'Kembali ke senarai', 'kursus dipilih', '/bln', 'Temuduga']) {
      expect(page).not.toContain(malay)
      expect(compare).not.toContain(malay)
    }
  })
})

describe('the report and the footer (Mobile M3)', () => {
  it('the report page keeps its header while loading and on an error', () => {
    const page = readWeb('src/app/report/[id]/page.tsx', 'the report page')
    const header = page.indexOf('<AppHeader />')
    expect(header).toBeGreaterThan(-1)
    expect(header).toBeLessThan(page.indexOf('{loading ?'))
    const view = readWeb('src/components/ReportView.tsx', 'the report view')
    expect(view).toMatch(/className="btn-primary min-h-11/)
    expect(view).toMatch(/px-4 pt-4 sm:px-6/)
    expect(view).toMatch(/p-4 sm:p-8/)
  })

  it('every footer link is a 44 px row', () => {
    const footer = readWeb('src/components/AppFooter.tsx', 'the shared footer')
    // 44 × 44: a short word ("About", "பற்றி") is narrower than 44 px, so the row has a minimum WIDTH too.
    expect(footer).toMatch(/const LINK = 'inline-flex min-h-11 min-w-11 /)
    // Ten list links and buttons share LINK; the bottom bar's Contact link carries its own 44 px.
    expect(footer.match(/className=\{LINK\}/g)?.length).toBe(10)
    expect(footer.match(/<(Link|button)\b/g)?.length).toBe(11)
    expect(footer).toMatch(/<Link href="\/contact" className="inline-flex min-h-11 min-w-11 /)
    expect(footer).not.toMatch(/className="text-sm text-ground-(500|600) hover:text-ground-900"/)
  })
})
