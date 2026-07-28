/**
 * Client-side sorting and paging (2026-07-28).
 *
 * Most of this is arithmetic. Three cases are not, and they are the reason the module exists
 * rather than an inline `.sort()`: money arrives as a STRING, a null date means *unknown* rather
 * than *oldest*, and a page number can outlive the list it points into.
 */
import {
  DEFAULT_PAGE_SIZE, PAGINATION_MIN_ROWS, byDate, byNumber, byText, nextSort, pageOf,
  shouldPaginate, sortIndicator, sortRows, totalPages,
} from '../tableView'

describe('shouldPaginate', () => {
  it('stays hidden at ten rows and appears at eleven (owner: only above 10)', () => {
    expect(shouldPaginate(PAGINATION_MIN_ROWS)).toBe(false)
    expect(shouldPaginate(PAGINATION_MIN_ROWS + 1)).toBe(true)
  })

  it('stays hidden when everything fits one page, whatever the threshold', () => {
    // 40 rows at 50 per page is one page — a footer there is furniture.
    expect(shouldPaginate(40, 50)).toBe(false)
    expect(shouldPaginate(40, 25)).toBe(true)
  })

  it('is hidden for the production sponsor tables that have not grown yet', () => {
    expect(shouldPaginate(9)).toBe(false)     // sponsors
    expect(shouldPaginate(8)).toBe(false)     // people invited
    expect(shouldPaginate(1)).toBe(false)     // wallet credits
    expect(shouldPaginate(38)).toBe(true)     // one sponsor's sponsorship history
  })
})

describe('pageOf', () => {
  const rows = Array.from({ length: 38 }, (_, i) => i + 1)

  it('slices the requested page', () => {
    expect(pageOf(rows, 1, 10)[0]).toBe(1)
    expect(pageOf(rows, 4, 10)).toEqual([31, 32, 33, 34, 35, 36, 37, 38])
  })

  it('clamps a page that outlived its list rather than blanking the table', () => {
    // Filtering the sponsors list while on page 3 must not show an empty body.
    expect(pageOf(rows, 99, 10)).toEqual(pageOf(rows, 4, 10))
    expect(pageOf(rows, 0, 10)).toEqual(pageOf(rows, 1, 10))
  })

  it('handles an empty list', () => {
    expect(pageOf([], 1, 10)).toEqual([])
    expect(totalPages(0, 10)).toBe(1)
  })
})

describe('byNumber', () => {
  it('sorts money as a NUMBER, not as the string the API sends', () => {
    // The trap: '9000.00' > '20000.00' as text. Plausible-looking and wrong.
    expect(byNumber('9000.00', '20000.00')).toBeLessThan(0)
    expect(['9000.00', '20000.00', '100000.00'].sort(byNumber))
      .toEqual(['9000.00', '20000.00', '100000.00'])
  })

  it('treats a blank or dash as zero rather than NaN', () => {
    expect(byNumber('', '1')).toBeLessThan(0)
    expect(byNumber(null, 0)).toBe(0)
    expect(byNumber('not a number', 0)).toBe(0)
  })
})

describe('byText', () => {
  it('compares case-insensitively, so "chong lee ai" files with the Chongs', () => {
    expect(byText('chong lee ai', 'Chong Lee Min')).toBeLessThan(0)
  })

  it('puts a blank name last in both directions', () => {
    expect(byText('', 'Aisha')).toBeGreaterThan(0)
    expect(byText('Aisha', '')).toBeLessThan(0)
  })
})

describe('byDate + sortRows: unknown stays at the bottom', () => {
  type Row = { name: string; seen: string | null }
  const rows: Row[] = [
    { name: 'old', seen: '2026-06-01T00:00:00Z' },
    { name: 'never', seen: null },
    { name: 'recent', seen: '2026-07-27T00:00:00Z' },
  ]
  const cmp = (a: Row, b: Row) => byDate(a.seen, b.seen)
  const unknown = (r: Row) => !r.seen

  it('keeps a sponsor with NO SIGN-IN RECORDED last when sorted newest-first', () => {
    expect(sortRows(rows, cmp, 'desc', unknown).map((r) => r.name))
      .toEqual(['recent', 'old', 'never'])
  })

  it('keeps them last when sorted oldest-first too — "unknown" is not "longest ago"', () => {
    // Without the unknown-test a null would read as 1970 and claim nine sponsors were last here
    // before the programme existed. The column has only recorded since 2026-07-27.
    expect(sortRows(rows, cmp, 'asc', unknown).map((r) => r.name))
      .toEqual(['old', 'recent', 'never'])
  })
})

describe('nextSort', () => {
  it('flips direction on the same column', () => {
    expect(nextSort({ key: 'name', dir: 'asc' }, 'name')).toEqual({ key: 'name', dir: 'desc' })
    expect(nextSort({ key: 'name', dir: 'desc' }, 'name')).toEqual({ key: 'name', dir: 'asc' })
  })

  it('starts a new column at its own preferred direction', () => {
    expect(nextSort({ key: 'name', dir: 'desc' }, 'given', 'desc'))
      .toEqual({ key: 'given', dir: 'desc' })
  })
})

describe('sortIndicator', () => {
  it('marks only the active column', () => {
    expect(sortIndicator(true, 'asc')).toBe('▲')
    expect(sortIndicator(true, 'desc')).toBe('▼')
    expect(sortIndicator(false, 'asc')).toBe('')
  })
})

describe('defaults', () => {
  it('pages at ten, matching the threshold', () => {
    // If these disagreed, a table could pass the threshold and still show one page.
    expect(DEFAULT_PAGE_SIZE).toBe(PAGINATION_MIN_ROWS)
  })
})
