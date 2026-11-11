/**
 * A3.16a / TD-362 — the three income mirrors in `incomeWizard.ts`, guarded against the api's own
 * source: the document plan (`salary_member_blocks` + `income_requirements`), the member roster and
 * relationship-document tables, and the patronymic connector list.
 *
 * ⚠ THIS GUARD BLESSES NOTHING. The income rule has eleven homes that disagree (TD-262) and the
 * owner has not ruled. Where the two sides ALREADY differ, the difference is pinned below as a
 * NAMED KNOWN EXCEPTION, asserted as it is today. When the owner rules and one side moves, the
 * exception test turns red; delete it (or flip it) with the ruling. Nothing here changes income logic.
 */
import {
  hasPatronymic, incomeRequirements, MEMBER_ORDER, relationshipDocFor, salaryMemberBlocks,
  type WorkingMember,
} from '@/lib/incomeWizard'
import { pySeq, readApi } from '@/test/apiSource'

const ADVICE = readApi('apps/scholarship/income_engine/advice.py')
const RELATIONSHIPS = readApi('apps/scholarship/income_engine/relationships.py')
const NAME_ORDER = readApi('apps/scholarship/name_order.py')

/** The text of one top-level `def` — up to the next top-level def or section rule. */
function pyBody(src: string, name: string): string {
  const start = src.indexOf(`\ndef ${name}(`)
  if (start < 0) throw new Error(`drift test: def ${name} not found`)
  const rest = src.slice(start + 1)
  const end = rest.slice(1).search(/\n(?:def |# ──|_[A-Z_]+ =)/)
  return end < 0 ? rest : rest.slice(0, end + 1)
}

/** The `(doc, tag)` pairs of one list assignment inside a body: tag is `m` (the member) or `''`. */
function pairs(body: string, assign: string): string[][] {
  const m = body.match(new RegExp(`${assign}\\s*\\+?=\\s*\\[([^\\]]*)\\]`))
  if (!m) throw new Error(`drift test: ${assign} not found`)
  return [...m[1].matchAll(/\(\s*'([a-z_]+)'\s*,\s*(m|'')\s*\)/g)].map((x) => [x[1], x[2]])
}

describe('salary_member_blocks (income_engine/advice.py) — the per-member document plan', () => {
  const body = pyBody(ADVICE, 'salary_member_blocks')

  it('parses (sanity: the pairs are really read)', () => {
    expect(pairs(body, 'compulsory').length).toBeGreaterThanOrEqual(1)
    expect(pairs(body, 'optional').length).toBeGreaterThanOrEqual(2)
  })

  it('every member: compulsory IC first (tagged), optional slip + EPF (tagged) — both sides', () => {
    const pyCompulsory = pairs(body, 'compulsory').map(([d]) => d)
    const pyOptional = pairs(body, 'optional').map(([d]) => d)
    expect(pyCompulsory).toEqual(['parent_ic'])
    for (const b of salaryMemberBlocks([...MEMBER_ORDER])) {
      expect(b.compulsory[0]).toEqual({ docType: pyCompulsory[0], member: b.member })
      expect(b.optional).toEqual(pyOptional.map((d) => ({ docType: d, member: b.member })))
    }
  })

  it('the relationship document is appended to compulsory UNTAGGED, from relationship_doc_for', () => {
    expect(body).toMatch(/compulsory\.append\(\(rel,\s*''\)\)/)
    for (const b of salaryMemberBlocks([...MEMBER_ORDER])) {
      const rel = relationshipDocFor(b.member)
      expect(b.relDoc).toBe(rel)
      expect(b.compulsory.slice(1)).toEqual(rel ? [{ docType: rel, member: '' }] : [])
    }
  })

  it('blocks come out in the roster order, de-duplicated, ignoring garbage — as the api does', () => {
    expect(body).toContain('for m in _MEMBER_ORDER')
    const web = salaryMemberBlocks(['sister', 'father', 'father', 'cousin' as WorkingMember]).map((b) => b.member)
    expect(web).toEqual(['father', 'sister'])
  })
})

describe('the roster tables (income_engine/relationships.py)', () => {
  it('_MEMBER_ORDER is MEMBER_ORDER', () => {
    const py = pySeq(RELATIONSHIPS, '_MEMBER_ORDER')
    expect(py.length).toBeGreaterThanOrEqual(5)
    expect([...MEMBER_ORDER]).toEqual(py)
  })

  it('_RELATIONSHIP_DOC is relationshipDocFor, member by member', () => {
    const m = RELATIONSHIPS.match(/_RELATIONSHIP_DOC\s*=\s*\{([^}]*)\}/)
    if (!m) throw new Error('drift test: _RELATIONSHIP_DOC not found')
    const py = Object.fromEntries([...m[1].matchAll(/'([a-z_]+)'\s*:\s*'([a-z_]+)'/g)].map((x) => [x[1], x[2]]))
    expect(Object.keys(py).length).toBeGreaterThanOrEqual(2)
    for (const member of MEMBER_ORDER) expect(relationshipDocFor(member)).toBe(py[member] ?? '')
    expect(relationshipDocFor('')).toBe('')
    expect(relationshipDocFor(null)).toBe('')
  })

  it('_PATRONYMIC_MEMBERS is the set whose relationship needs no document', () => {
    const m = RELATIONSHIPS.match(/_PATRONYMIC_MEMBERS\s*=\s*\{([^}]*)\}/)
    if (!m) throw new Error('drift test: _PATRONYMIC_MEMBERS not found')
    const py = [...m[1].matchAll(/'([a-z_]+)'/g)].map((x) => x[1]).sort()
    expect(py.length).toBeGreaterThanOrEqual(3)
    const web = MEMBER_ORDER.filter((x) => !relationshipDocFor(x)).sort()
    expect(web).toEqual(py)
  })
})

describe('income_requirements (income_engine/advice.py) vs incomeRequirements', () => {
  const body = pyBody(ADVICE, 'income_requirements')

  it('the salary route: no flat compulsory, the two household bills optional', () => {
    expect(body).toMatch(/'compulsory':\s*\[\],\s*'optional':\s*\['water_bill',\s*'electricity_bill'\]/)
    const r = incomeRequirements({ income_route: 'salary', income_working_members: ['father'] })
    expect(r.compulsory).toEqual([])
    expect(r.optional).toEqual(['water_bill', 'electricity_bill'])
  })

  it('the STR route: earner IC, relationship doc, STR; optional bills + slip + EPF', () => {
    expect(body).toMatch(/compulsory\s*=\s*\['parent_ic'\]/)
    expect(body).toMatch(/compulsory\.append\('str'\)/)
    const py = body.match(/optional\s*\+=\s*\[([^\]]*)\]/)
    if (!py) throw new Error('drift test: optional += not found')
    const optional = [...py[1].matchAll(/'([a-z_]+)'/g)].map((x) => x[1])
    expect(optional.length).toBeGreaterThanOrEqual(4)
    const r = incomeRequirements({ income_route: 'str', income_earner: 'mother' })
    expect(r.compulsory).toEqual(['parent_ic', 'birth_certificate', 'str'])
    expect(r.optional).toEqual(optional)
  })

  it('the blank route: only the earner IC stands', () => {
    expect(incomeRequirements({}).compulsory).toEqual(['parent_ic'])
    expect(incomeRequirements({}).optional).toEqual([])
  })

  // KNOWN EXCEPTION A (TD-262, owner ruling pending): the web offers an OPTIONAL household birth
  // certificate when the student's name is a mononym; the api's income_requirements has no such
  // option (it never sees the name). Asserted as it is TODAY, not blessed.
  it('KNOWN EXCEPTION A: the mononym birth-certificate option exists on the web only', () => {
    expect(body).not.toMatch(/patronymic|mononym/i)
    expect(body).not.toContain("optional.append('birth_certificate')")
    const web = incomeRequirements(
      { income_route: 'salary', income_working_members: ['father'] }, { studentHasPatronymic: false })
    expect(web.optional).toContain('birth_certificate')
  })

  // KNOWN EXCEPTION B (TD-262): the api reads the members through effective_working_members (it
  // falls back to the tagged documents / family roster when the wizard answer was not saved);
  // the web reads only the answer it is handed.
  it('KNOWN EXCEPTION B: the api reads members through effective_working_members, the web does not', () => {
    expect(body).toContain('salary_member_blocks(effective_working_members(application))')
    expect(pyBody(RELATIONSHIPS, 'effective_working_members')).toMatch(/tagged_members|earning_members/)
    expect(salaryMemberBlocks(undefined)).toEqual([])
  })
})

describe('patronymic connectors (name_order.CONNECTOR_RE vs incomeWizard PATRONYMIC_RE)', () => {
  const re = NAME_ORDER.match(/CONNECTOR_RE\s*=\s*re\.compile\(\s*r'\\b\(\?:([^']*)\)\\b'/)
  if (!re) throw new Error('drift test: CONNECTOR_RE not found')
  // split on the top-level bars only (the ANAK branch holds a bar inside its group)
  const alternatives = re[1].split(/\|(?![^(]*\))/)

  it('parses (sanity: the connector list is really read)', () => {
    expect(alternatives.length).toBeGreaterThanOrEqual(8)
    expect(RELATIONSHIPS).toContain('_PATRONYMIC_RE = CONNECTOR_RE')
  })

  // One name per api alternative (a literal rendering of each regex branch).
  const SAMPLE: Record<string, string> = {
    'anak(?:\\s+(?:lelaki|perempuan))?': 'MARY ANAK JOHNNY',
    'ak': 'MARY AK JOHNNY',
    'bin': 'AHMAD BIN ALI',
    'binti': 'SITI BINTI ALI',
    'bte': 'SITI BTE ALI',
    'bt': 'SITI BT ALI',
    'a\\s*/\\s*[lp]': 'RAJU A/L MURUGAN',
    's\\s*/\\s*o': 'RAJU S/O MURUGAN',
    'd\\s*/\\s*o': 'DIVYA D/O MURUGAN',
  }
  // KNOWN EXCEPTION C (TD-262 / TD-408): the api's ONE connector list gained bare ANAK / AK and
  // BT / BTE at TD-408; the web's list did not. A name carrying only those reads as "no patronymic"
  // on the web. The web also still accepts "@", which the api does not. Pinned as they are today.
  const API_ONLY = new Set(['anak(?:\\s+(?:lelaki|perempuan))?', 'ak', 'bte', 'bt'])

  it('every api connector is in the sample table (a new connector must be classified here)', () => {
    for (const alt of alternatives) expect(Object.keys(SAMPLE)).toContain(alt)
  })

  it('every shared connector is a patronymic on both sides', () => {
    for (const alt of alternatives.filter((a) => !API_ONLY.has(a))) {
      expect(hasPatronymic(SAMPLE[alt])).toBe(true)
    }
  })

  it('KNOWN EXCEPTION C: ANAK / AK / BT / BTE are connectors on the api only; "@" on the web only', () => {
    for (const alt of API_ONLY) expect(hasPatronymic(SAMPLE[alt])).toBe(false)
    expect(alternatives.join('|')).not.toContain('@')
    expect(hasPatronymic('MOHD @ ALI')).toBe(true)
  })

  it('a mononym carries none, on both sides', () => {
    expect(hasPatronymic('DIVIYA')).toBe(false)
    expect(hasPatronymic('')).toBe(false)
  })
})
