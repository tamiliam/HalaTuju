/**
 * A3.16a / TD-362 / RD-06 — the mirrors OUTSIDE `src/lib` that the widened guard now finds.
 *
 * `codeStandards.test.ts` used to look for "mirror" claims in `src/lib` only. Screens and components
 * carry the same kind of claim ("mirrors the api's rule", "must match Consent.…"), and 20-odd of them
 * had nothing enforcing them. Each describe below reads the web source (these constants are not
 * exported — they live in a component) and the api's own source, and asserts both directions.
 * Every parse is sanity-checked, so a refactor that stops matching turns it RED, never into a no-op.
 *
 * ⚠ NO LOGIC IS CHANGED HERE. Where the two sides already differ, the difference is pinned as a
 * NAMED KNOWN EXCEPTION (asserted as it is today, reported, not fixed).
 */
import * as vm from 'vm'
import * as ts from 'typescript'
import { isQueryingLocked, QUERYING_LOCKED_STATES } from '@/lib/cockpitStages'
import { wizardComplete } from '@/lib/incomeWizard'
import { STAGES as WEB_STAGES } from '@/test/adminApplicationDetail'
import { pyChoiceValues, pySeq, readApi } from '@/test/apiSource'
import { readWeb } from '@/test/sourceGuard'

const web = (rel: string) => readWeb(rel, 'a mirrored constant that lives in a component, with no export')

/** `const NAME = [ 'a', 'b' ]` (optionally `as const`) → its strings. Throws if absent. */
function tsStrings(src: string, name: string): string[] {
  const m = src.match(new RegExp(`const\\s+${name}(?:\\s*:[^=]+)?\\s*=\\s*\\[([^\\]]*)\\]`))
  if (!m) throw new Error(`drift test: const ${name} not found`)
  const out = [...m[1].matchAll(/'([^']*)'/g)].map((x) => x[1])
  if (!out.length) throw new Error(`drift test: const ${name} holds no string literals`)
  return out
}

/** `const NAME = 123` → 123. Throws if absent. */
function tsNumber(src: string, name: string): number {
  const m = src.match(new RegExp(`const\\s+${name}\\s*=\\s*(\\d+)\\b`))
  if (!m) throw new Error(`drift test: const ${name} not found`)
  return Number(m[1])
}

/** `NAME = 123` at module level in a Python source → 123. */
function pyNumber(src: string, name: string): number {
  const m = src.match(new RegExp(`^${name}\\s*=\\s*(\\d+)\\b`, 'm'))
  if (!m) throw new Error(`drift test: ${name} not found in the api source`)
  return Number(m[1])
}

describe('org request urgency — requests/page.tsx vs org_requests.VALID_URGENCIES', () => {
  it('the same keys, in the same order', () => {
    const py = pySeq(readApi('apps/scholarship/org_requests.py'), 'VALID_URGENCIES')
    expect(py.length).toBeGreaterThanOrEqual(3)
    expect(tsStrings(web('src/app/admin/requests/page.tsx'), 'URGENCY_OPTIONS')).toEqual(py)
  })
})

describe('guardian relationship codes vs Consent.GUARDIAN_RELATIONSHIPS', () => {
  const py = pyChoiceValues(readApi('apps/scholarship/models/documents.py'), 'GUARDIAN_RELATIONSHIPS')
  it('parses (sanity)', () => expect(py.length).toBeGreaterThanOrEqual(7))
  it('the award page offers exactly the api codes', () => {
    expect(tsStrings(web('src/app/scholarship/award/page.tsx'), 'GUARDIAN_RELATIONSHIPS')).toEqual(py)
  })
  it('the consent form offers exactly the api codes', () => {
    expect(tsStrings(web('src/components/ScholarshipConsent.tsx'), 'GUARDIAN_RELATIONSHIPS')).toEqual(py)
  })
})

describe('apply-copy caps — ApplyCopyTab.tsx vs apply_copy.py', () => {
  const py = readApi('apps/scholarship/apply_copy.py')
  const tab = web('src/components/admin/ApplyCopyTab.tsx')
  it.each(['MAX_TITLE', 'MAX_INTRO', 'MAX_BULLET', 'MAX_BULLETS'])('%s is the api number', (name) => {
    expect(tsNumber(tab, name)).toBe(pyNumber(py, name))
  })
  it('the locales are the same three', () => {
    expect(tsStrings(tab, 'LOCALES')).toEqual(pySeq(py, 'LOCALES'))
  })
})

describe('STORY_TEXT_MAX — ScholarshipNextSteps.tsx vs the application serializer', () => {
  it('the same anti-spam ceiling', () => {
    const api = pyNumber(readApi('apps/scholarship/serializers/application.py'), 'STORY_TEXT_MAX')
    expect(api).toBeGreaterThan(0)
    expect(tsNumber(web('src/components/ScholarshipNextSteps.tsx'), 'STORY_TEXT_MAX')).toBe(api)
  })
})

describe('the clause editor — ClauseEditor.tsx vs the contracts package', () => {
  const editor = web('src/components/contracts/ClauseEditor.tsx')

  it('QUIZ_MAX_LEVEL is contracts.MAX_QUIZ_LEVEL', () => {
    expect(tsNumber(editor, 'QUIZ_MAX_LEVEL'))
      .toBe(pyNumber(readApi('apps/scholarship/contracts/numbering.py'), 'MAX_QUIZ_LEVEL'))
  })

  it('the "Insert variable" menu offers exactly CONTRACT_VARS, in order', () => {
    const vars = readApi('apps/scholarship/contracts/variables.py')
    const block = vars.slice(vars.indexOf('CONTRACT_VARS = ('), vars.indexOf('_VAR_RE'))
    const py = [...block.matchAll(/^\s*\(\s*'([a-z_]+)'/gm)].map((m) => m[1])
    expect(py.length).toBeGreaterThanOrEqual(12)
    const menu = editor.slice(editor.indexOf('const VARIABLES'), editor.indexOf('// The Clauses tab'))
    expect([...menu.matchAll(/token:\s*'\{\{([a-z_]+)\}\}'/g)].map((m) => m[1])).toEqual(py)
  })

  describe('resolveQuizFlags vs _resolve_quiz_flags', () => {
    const start = editor.indexOf('function resolveQuizFlags(')
    if (start < 0) throw new Error('drift test: function resolveQuizFlags not found')
    const body = editor.slice(start, editor.indexOf('\n}\n', start) + 3)
    const js = ts.transpileModule(body, { compilerOptions: { target: ts.ScriptTarget.ES2019 } }).outputText
    const sandbox = { QUIZ_MAX_LEVEL: tsNumber(editor, 'QUIZ_MAX_LEVEL') }
    const resolve = vm.runInNewContext(`${js}\nresolveQuizFlags`, sandbox) as
      (levels: number[], flags: boolean[]) => boolean[]

    it('both sides pop on same-or-shallower and cap at MAX_QUIZ_LEVEL (the shape is shared)', () => {
      const py = readApi('apps/scholarship/contracts/authoring.py')
      expect(py).toContain('while open_flagged_levels and open_flagged_levels[-1] >= level:')
      expect(py).toContain('level <= MAX_QUIZ_LEVEL')
      expect(body).toContain('openLevels[openLevels.length - 1] >= level')
      expect(body).toContain('level <= QUIZ_MAX_LEVEL')
    })

    it('the documented rules: level 2 never; ancestor wins; a sibling after the subtree is free again', () => {
      expect(resolve([0, 1, 2], [false, false, true])).toEqual([false, false, false])
      expect(resolve([0, 1], [true, true])).toEqual([true, false])
      expect(resolve([0, 1, 0, 1], [true, true, true, false])).toEqual([true, false, true, false])
      expect(resolve([0, 1, 1], [false, true, true])).toEqual([false, true, true])
    })
  })
})

describe('querying lock — cockpitStages.ts vs services/querying.py', () => {
  const py = readApi('apps/scholarship/services/querying.py')
  it('the same locked statuses', () => {
    const api = pySeq(py, 'QUERYING_LOCKED_STATUSES')
    expect(api.length).toBeGreaterThanOrEqual(9)
    expect([...QUERYING_LOCKED_STATES]).toEqual(api)
  })
  it('a submitted interview locks it too, on both sides', () => {
    expect(py).toContain("interview_sessions.filter(status='submitted')")
    expect(isQueryingLocked('profile_complete', 'submitted')).toBe(true)
    expect(isQueryingLocked('interviewing', undefined)).toBe(false)
  })
  it('a reopened decision unlocks it (the cockpit applies decisionReopened; the api checks the stamp)', () => {
    expect(py).toContain('application.decision_reopened_at is not None')
    expect(web('src/app/admin/scholarship/[id]/view/deriveCockpit.ts')).toContain('&& !decisionReopened')
  })
})

describe('has money gone out — WithdrawAwardCard.hasPaidTranche vs award_withdrawal.has_payments', () => {
  it('released or returned, on both sides', () => {
    const paid = pySeq(readApi('apps/scholarship/models/funding.py'), 'PAID', true)
    expect(paid).toEqual(['released'])
    expect(readApi('apps/scholarship/award_withdrawal.py'))
      .toContain("_PAID_OR_RETURNED = tuple(Disbursement.PAID) + ('returned',)")
    const card = web('src/app/admin/scholarship/[id]/view/WithdrawAwardCard.tsx')
    for (const s of [...paid, 'returned']) expect(card).toContain(`d.status === '${s}'`)
  })
})

describe('who may write on a case — view.tsx canWrite vs views_admin/base._can_review_app', () => {
  it('a qc holder writes on any case in scope; anyone else only on a case assigned to them', () => {
    const py = readApi('apps/scholarship/views_admin/base.py')
    const fn = py.slice(py.indexOf('def _can_review_app('), py.indexOf('def _require_app_write('))
    expect(fn).toContain("admin.has_perm('qc')")
    expect(fn).toContain('return app.assigned_to_id == admin.id')
    const view = web('src/app/admin/scholarship/[id]/view.tsx')
    expect(view).toContain("const canWrite = hasPerm(role, 'qc')")
    expect(view).toContain('app.assigned_to_id === (role?.admin_id ?? null)')
  })
})

describe('the income route switch — IncomeRouteSwitch.tsx vs wizardComplete (lib/incomeWizard.ts)', () => {
  it('the same completeness rule: STR needs an earner, salary needs at least one member', () => {
    const sw = web('src/components/IncomeRouteSwitch.tsx')
    expect(sw).toContain("const valid = route === 'str' ? !!earner : route === 'salary' ? members.length > 0 : false")
    expect(wizardComplete({ income_route: 'str', income_earner: 'father' })).toBe(true)
    expect(wizardComplete({ income_route: 'str', income_earner: '' })).toBe(false)
    expect(wizardComplete({ income_route: 'salary', income_working_members: ['mother'] })).toBe(true)
    expect(wizardComplete({ income_route: 'salary', income_working_members: [] })).toBe(false)
    expect(wizardComplete({ income_route: '' })).toBe(false)
  })
})

describe('the income wizard component — IncomeWizard.tsx', () => {
  const wiz = web('src/components/ScholarshipDocuments/IncomeWizard.tsx')

  it('the prefilled working members are persisted, as effective_working_members reconstructs them', () => {
    const rel = readApi('apps/scholarship/income_engine/relationships.py')
    const fn = rel.slice(rel.indexOf('def effective_working_members('), rel.indexOf('def member_relationship_status('))
    expect(fn).toContain('tagged_members')       // (1) the members the tagged documents name
    expect(fn).toContain('earning_members')      // (2) else the declared earners on the roster
    expect(wiz).toContain('income_working_members')
    expect(wiz).toMatch(/patch\.income_working_members\s*=/)
  })

  it("the card's slot match: (type, member) pair, or a legacy untagged copy for the STR-earner docs", () => {
    const cards = web('src/components/ScholarshipDocuments/cards.tsx')
    expect(cards).toContain("(d.household_member || '') === member || (legacyBlank && !(d.household_member || ''))")
    expect(wiz).toContain("(d.household_member || '') === slotMember || (isEarnerDoc && !(d.household_member || ''))")
    expect(wiz).toContain("const STR_EARNER_DOCS = new Set(['str', 'parent_ic', 'salary_slip', 'epf'])")
  })
})

describe('the test builder stage table — test/adminApplicationDetail.ts vs tests/factories.STAGES', () => {
  it('the same stages, in the same order', () => {
    const py = pySeq(readApi('apps/scholarship/tests/factories.py'), 'STAGES')
    expect(py.length).toBeGreaterThanOrEqual(14)
    expect([...WEB_STAGES]).toEqual(py)
  })
})

describe('the name, glued — ScholarshipConsent.tsx vs vision/names.py', () => {
  const consent = web('src/components/ScholarshipConsent.tsx')
  const names = readApi('apps/scholarship/vision/names.py')

  it('both reduce a name to its words glued back in order', () => {
    expect(consent).toContain(".split(/[^a-z]+/).filter(Boolean).join('')")
    expect(names).toContain("return ''.join(_fold_name_token(t) for t in toks) if fold else ''.join(toks)")
  })

  // KNOWN EXCEPTION D (not income, but a name gate): the api strips MORE noise before comparing —
  // bt / bte / anak / ak, the honorifics (sdri, encik, puan, dr, datuk …), a slash with stray spaces
  // ("A / P"), and a marker glued to a name ("LAKSMITHAA/P"). The web strips the original nine tokens
  // only. So a name the api reads as equal can read as unequal on the consent form. The web errs
  // towards "does not match" (the safe side). Owner decides whether to widen it; pinned as it is.
  it('KNOWN EXCEPTION D: the web strips fewer noise tokens than the api', () => {
    const web9 = consent.match(/const NAME_NOISE = \/\\b\(([^)]*)\)\\b\//)
    if (!web9) throw new Error('drift test: NAME_NOISE not found in ScholarshipConsent.tsx')
    expect(web9[1].split('|')).toEqual(['bin', 'binti', 'a\\/l', 'a\\/p', 'al', 'ap', 'd\\/o', 's\\/o', '@'])
    const from = names.indexOf('_NAME_NOISE = re.compile(')
    const apiNoise = names.slice(from, names.indexOf('flags=re.IGNORECASE', from))
    for (const tok of ['bt', 'bte', 'anak', 'ak', 'sdri', 'encik', 'datuk']) {
      expect(apiNoise).toMatch(new RegExp(`\\b${tok}\\b`))
    }
    expect(names).toContain('def _split_glued_markers(')
    expect(consent).not.toContain('_split_glued_markers')
  })
})
