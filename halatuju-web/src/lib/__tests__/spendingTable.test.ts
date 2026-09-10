/**
 * The spending screen's comparators (S6, 2026-09-11).
 *
 * ⚠ Every test here is written from a way the naive version is WRONG for this data, not from the
 * shape of the code. Sorting is the part of a table that fails quietly: a wrong order still looks
 * like a table, and nobody reports it.
 */
import {
  MERCHANT_SORT_LABEL, STUDENT_SORT_LABEL, merchantFirstDir, shopsWithUnplacedMoney,
  sortMerchants, sortStudents, studentFirstDir, type MerchantSortKey, type StudentSortKey,
} from '../spendingTable'
import type { SpendingMerchantRow, SpendingStudentRow } from '../admin-api'

const shop = (over: Partial<SpendingMerchantRow>): SpendingMerchantRow => ({
  merchant: 'A SHOP', category: 'food', decided_by: 'rule', visits: 1,
  total: '10.00', last_seen: '2026-08-01', held_back: 0, ...over,
})

const student = (over: Partial<SpendingStudentRow>): SpendingStudentRow => ({
  application_id: 1, name: 'Aisyah', payments: 1, spent: '10.00', unplaced: '0.00', ...over,
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

  test('a student with no name recorded sorts LAST, both directions', () => {
    const rows = [student({ application_id: 1, name: '' }),
                  student({ application_id: 2, name: 'Aisyah' })]
    expect(sortStudents(rows, 'name', 'asc').map((r) => r.application_id)).toEqual([2, 1])
    expect(sortStudents(rows, 'name', 'desc').map((r) => r.application_id)).toEqual([2, 1])
  })
})

describe('every column can be sorted and every column has a name', () => {
  // ⚠ A column added to the table without a comparator or without a label is invisibly broken:
  // the header renders, the click does nothing, or the header reads as a raw dotted key. These
  // two lists are the only place that pairing is written down, so they are asserted complete.
  const MERCHANT_KEYS: MerchantSortKey[] =
    ['shop', 'countedAs', 'decidedBy', 'visits', 'total', 'lastSeen']
  const STUDENT_KEYS: StudentSortKey[] = ['name', 'payments', 'spent', 'unplaced']

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
