/**
 * The spending screen's comparators (S6, 2026-09-11).
 *
 * ⚠ Every test here is written from a way the naive version is WRONG for this data, not from the
 * shape of the code. Sorting is the part of a table that fails quietly: a wrong order still looks
 * like a table, and nobody reports it.
 */
import {
  MERCHANT_SORT_LABEL, STUDENT_SORT_LABEL, filterMerchants, filterStudents,
  merchantFirstDir, shopsWithUnplacedMoney,
  sortMerchants, sortStudents, studentFirstDir, type MerchantSortKey, type StudentSortKey,
} from '../spendingTable'
import type { SpendingMerchantRow, SpendingStudentRow } from '../admin-api'

const shop = (over: Partial<SpendingMerchantRow>): SpendingMerchantRow => ({
  merchant: 'A SHOP', category: 'food', decided_by: 'rule', visits: 1,
  total: '10.00', last_seen: '2026-08-01', held_back: 0, decided_at: '2026-08-02T00:00:00Z',
  ...over,
})

const student = (over: Partial<SpendingStudentRow>): SpendingStudentRow => ({
  application_id: 1, name: 'Aisyah', transactions: 1, spent: '10.00', unplaced: '0.00',
  paid: '200.00', balance: '190.00', ...over,
})

const LABELS = { food: 'Food & drink', groceries: 'Groceries', unsorted: 'Not yet sorted' }

describe('sorting the shops', () => {
  test('MONEY SORTS AS A NUMBER — the string order would put RM900 above RM2,000', () => {
    // ⚠ THE ONE THAT MATTERS. The API sends money as a 2-decimal string; comparing those as text
    // ranks '900.00' above '2000.00' because '9' > '2'. It looks like a sorted table.
    const rows = [shop({ merchant: 'SMALL', total: '900.00' }),
                  shop({ merchant: 'BIG', total: '2000.00' })]
    expect(sortMerchants(rows, 'total', 'desc', LABELS).map((r) => r.merchant))
      .toEqual(['BIG', 'SMALL'])
  })

  test('"counted as" sorts by the words on screen, not the code behind them', () => {
    // `groceries` < `unsorted` as codes AND 'Groceries' < 'Not yet sorted' as labels, so a code
    // sort would pass by luck. `food` is the discriminator: the code sorts FIRST, the label LAST.
    const rows = [shop({ merchant: 'C', category: 'food' }),
                  shop({ merchant: 'A', category: 'groceries' }),
                  shop({ merchant: 'B', category: 'unsorted' })]
    expect(sortMerchants(rows, 'countedAs', 'asc', LABELS).map((r) => r.category))
      .toEqual(['food', 'groceries', 'unsorted'])
    const RENAMED = { food: 'Zebra food', groceries: 'Groceries', unsorted: 'Not yet sorted' }
    expect(sortMerchants(rows, 'countedAs', 'asc', RENAMED).map((r) => r.category))
      .toEqual(['groceries', 'unsorted', 'food'])
  })

  test('"how we decided" ranks by how settled the answer is, not A to Z', () => {
    const rows = [shop({ merchant: 'D', decided_by: 'ai' }),
                  shop({ merchant: 'A', decided_by: 'owner' }),
                  shop({ merchant: 'E', decided_by: '' }),
                  shop({ merchant: 'B', decided_by: 'rule' })]
    expect(sortMerchants(rows, 'decidedBy', 'asc', LABELS).map((r) => r.decided_by))
      .toEqual(['owner', 'rule', 'ai', ''])
    // Descending is the queue an officer actually wants: the least settled at the top.
    expect(sortMerchants(rows, 'decidedBy', 'desc', LABELS).map((r) => r.decided_by))
      .toEqual(['', 'ai', 'rule', 'owner'])
  })

  test('a shop never seen sorts LAST whichever way the date column points', () => {
    // A null `last_seen` means NO RECORD, not "longest ago". Flipping the column must not drag
    // the unknowns to the top and claim they are the most recent.
    const rows = [shop({ merchant: 'NEVER', last_seen: null }),
                  shop({ merchant: 'OLD', last_seen: '2026-01-01' }),
                  shop({ merchant: 'NEW', last_seen: '2026-08-30' })]
    expect(sortMerchants(rows, 'lastSeen', 'desc', LABELS).map((r) => r.merchant))
      .toEqual(['NEW', 'OLD', 'NEVER'])
    expect(sortMerchants(rows, 'lastSeen', 'asc', LABELS).map((r) => r.merchant))
      .toEqual(['OLD', 'NEW', 'NEVER'])
  })

  test('two shops on the same total keep the order the server sent them in', () => {
    // Correcting one shop re-fetches the WHOLE list, so ties must not reshuffle themselves while
    // somebody is working down the page. `Array.sort` is stable and the server's own order is
    // deterministic (`-total`, then name), so preserving the incoming order is enough — no
    // second sort key is needed, and adding one would only be another thing to get wrong.
    const rows = [shop({ merchant: 'ZAINAB STALL', total: '50.00' }),
                  shop({ merchant: 'ADAM STALL', total: '50.00' })]
    expect(sortMerchants(rows, 'total', 'desc', LABELS).map((r) => r.merchant))
      .toEqual(['ZAINAB STALL', 'ADAM STALL'])
    expect(sortMerchants(rows, 'total', 'desc', LABELS))
      .toEqual(sortMerchants(rows, 'total', 'desc', LABELS))
  })

  test('it never mutates the list it was given', () => {
    const rows = [shop({ merchant: 'B' }), shop({ merchant: 'A' })]
    sortMerchants(rows, 'shop', 'asc', LABELS)
    expect(rows.map((r) => r.merchant)).toEqual(['B', 'A'])
  })
})

describe('which shops the Unsorted tab lists', () => {
  test('it takes the never-sorted, the honestly-unplaceable, and the ceiling-held', () => {
    const rows = [
      shop({ merchant: 'PLACED', category: 'food', held_back: 0 }),
      shop({ merchant: 'NEVER SORTED', category: '', held_back: 0 }),
      shop({ merchant: 'UNPLACEABLE', category: 'unsorted', held_back: 0 }),
      shop({ merchant: 'CEILING HELD', category: 'food', held_back: 3 }),
    ]
    expect(shopsWithUnplacedMoney(rows).map((r) => r.merchant))
      .toEqual(['NEVER SORTED', 'UNPLACEABLE', 'CEILING HELD'])
  })

  test('⚠ A CEILING-HELD SHOP IS NOT DROPPED FOR LOOKING PLACED', () => {
    // Its category reads `food`, so a filter written only on the category hides it — and with it
    // the six real payments (RM424) the RM20 ceiling holds back on production. That money IS
    // unplaced; the shop merely does not look it.
    expect(shopsWithUnplacedMoney([shop({ category: 'food', held_back: 6 })])).toHaveLength(1)
  })
})

describe('sorting the students', () => {
  test('spent and not-yet-sorted both sort as money', () => {
    const rows = [student({ name: 'Small', spent: '900.00', unplaced: '900.00' }),
                  student({ name: 'Big', spent: '2000.00', unplaced: '2000.00' })]
    expect(sortStudents(rows, 'spent', 'desc').map((r) => r.name)).toEqual(['Big', 'Small'])
    expect(sortStudents(rows, 'unplaced', 'desc').map((r) => r.name)).toEqual(['Big', 'Small'])
  })

  test('⚠ A BALANCE SORTS AS A SIGNED NUMBER — it is the one column that goes below zero', () => {
    // Comparing money as text files '-40.00' next to '4.00' and looks almost right. Every other
    // money column on this screen is non-negative, so this is the only place it can bite.
    // ⚠ 9 AND 100 ARE THE DISCRIMINATOR, and the first version of this test lacked them:
    // with only -40, 0 and 10 the text order and the number order AGREE, so a `byText`
    // comparator passed the bite-check. As text, '100.00' < '9.00'.
    const rows = [student({ name: 'Over', balance: '-40.00' }),
                  student({ name: 'Small', balance: '9.00' }),
                  student({ name: 'Big', balance: '100.00' }),
                  student({ name: 'Flat', balance: '0.00' })]
    expect(sortStudents(rows, 'balance', 'asc').map((r) => r.name))
      .toEqual(['Over', 'Flat', 'Small', 'Big'])
    expect(sortStudents(rows, 'balance', 'desc').map((r) => r.name))
      .toEqual(['Big', 'Small', 'Flat', 'Over'])
  })

  test('the balance column opens SMALLEST first; the other money columns open largest', () => {
    expect(studentFirstDir('balance')).toBe('asc')
    expect(studentFirstDir('spent')).toBe('desc')
    expect(studentFirstDir('unplaced')).toBe('desc')
  })

  test('a student with no name recorded sorts LAST, both directions', () => {
    const rows = [student({ application_id: 1, name: '' }),
                  student({ application_id: 2, name: 'Aisyah' })]
    expect(sortStudents(rows, 'name', 'asc').map((r) => r.application_id)).toEqual([2, 1])
    expect(sortStudents(rows, 'name', 'desc').map((r) => r.application_id)).toEqual([2, 1])
  })
})

describe('searching and filtering the shops', () => {
  const rows = [
    shop({ merchant: '99 SPEEDMART', category: 'groceries', decided_by: 'rule' }),
    shop({ merchant: 'SHOPEE MARKETPLACE', category: 'unsorted', decided_by: 'ai' }),
    shop({ merchant: 'APAM BALIK SELAYANG', category: 'food', decided_by: '' }),
  ]

  test('the search ignores case and surrounding spaces, because people paste', () => {
    expect(filterMerchants(rows, { query: '  ShOpEe ' }).map((r) => r.merchant))
      .toEqual(['SHOPEE MARKETPLACE'])
  })

  test('an empty or blank search changes nothing', () => {
    expect(filterMerchants(rows, {})).toHaveLength(3)
    expect(filterMerchants(rows, { query: '   ' })).toHaveLength(3)
  })

  test('it matches ANYWHERE in the name, not just the start', () => {
    // Shop names arrive as Vircle wrote them, so the distinctive word is often in the middle.
    expect(filterMerchants(rows, { query: 'balik' }).map((r) => r.merchant))
      .toEqual(['APAM BALIK SELAYANG'])
  })

  test('the category filter treats a BLANK category as unsorted, exactly like the screen does', () => {
    // A never-sorted row renders under "Not yet sorted"; a filter that disagreed with the label
    // in front of the reader would look broken while being technically defensible.
    const blank = [shop({ merchant: 'NEVER', category: '' })]
    expect(filterMerchants(blank, { category: 'unsorted' })).toHaveLength(1)
  })

  test('⚠ "not decided" is a CHOOSABLE state, not the absence of a choice', () => {
    // The blank rung means the sorter has not reached this shop. A dropdown cannot offer '' as a
    // value without it reading as the "any" option, so `none` names it — in the filter and in the
    // pill alike.
    expect(filterMerchants(rows, { decidedBy: 'none' }).map((r) => r.merchant))
      .toEqual(['APAM BALIK SELAYANG'])
    expect(filterMerchants(rows, { decidedBy: '' })).toHaveLength(3)
  })

  test('filters combine — search AND category AND how it was decided', () => {
    expect(filterMerchants(rows, { query: 'shop', category: 'unsorted', decidedBy: 'ai' }))
      .toHaveLength(1)
    expect(filterMerchants(rows, { query: 'shop', category: 'food', decidedBy: 'ai' }))
      .toHaveLength(0)
  })

  test('it never mutates the list it was given', () => {
    const before = rows.map((r) => r.merchant)
    filterMerchants(rows, { query: 'speed' })
    expect(rows.map((r) => r.merchant)).toEqual(before)
  })
})

describe('searching and filtering the students', () => {
  const rows = [
    student({ application_id: 1, name: 'NURUL TEST', unplaced: '20.00' }),
    student({ application_id: 2, name: 'AMIR TEST', unplaced: '0.00' }),
  ]

  test('the search is by name, case-insensitively', () => {
    expect(filterStudents(rows, { query: 'amir' }).map((r) => r.application_id)).toEqual([2])
  })

  test('⚠ "ONLY UNSORTED" COMPARES A NUMBER — the money is a STRING and "0.00" IS TRUTHY', () => {
    // This is the whole test. `if (r.unplaced)` keeps a student with exactly zero unsorted money,
    // so the filter appears to do nothing at all — and the reason is invisible in the code.
    expect(filterStudents(rows, { onlyUnplaced: true }).map((r) => r.application_id)).toEqual([1])
  })

  test('off by default, and combinable with the search', () => {
    expect(filterStudents(rows, {})).toHaveLength(2)
    expect(filterStudents(rows, { query: 'test', onlyUnplaced: true })).toHaveLength(1)
  })
})

describe('every column can be sorted and every column has a name', () => {
  // ⚠ A column added to the table without a comparator or without a label is invisibly broken:
  // the header renders, the click does nothing, or the header reads as a raw dotted key. These
  // two lists are the only place that pairing is written down, so they are asserted complete.
  const MERCHANT_KEYS: MerchantSortKey[] =
    ['shop', 'countedAs', 'decidedBy', 'visits', 'total', 'lastSeen', 'decidedAt']
  const STUDENT_KEYS: StudentSortKey[] =
    ['name', 'transactions', 'spent', 'unplaced', 'balance']

  test('shops', () => {
    expect(Object.keys(MERCHANT_SORT_LABEL).sort()).toEqual([...MERCHANT_KEYS].sort())
    MERCHANT_KEYS.forEach((k) => {
      expect(typeof merchantFirstDir(k)).toBe('string')
      expect(sortMerchants([shop({})], k, 'asc', LABELS)).toHaveLength(1)
    })
  })

  test('students', () => {
    expect(Object.keys(STUDENT_SORT_LABEL).sort()).toEqual([...STUDENT_KEYS].sort())
    STUDENT_KEYS.forEach((k) => {
      expect(typeof studentFirstDir(k)).toBe('string')
      expect(sortStudents([student({})], k, 'asc')).toHaveLength(1)
    })
  })
})
