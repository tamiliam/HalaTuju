/**
 * THE DRIFT TEST for `REQUEST_COMPONENT_TREE` in `requestStatus.ts` — named by its `drift-test:`
 * markers (code health H10). The sibling of H9's `requestStatusDrift`, and the last two entries
 * that file still owed the ledger.
 *
 * The component is the Bugzilla-style scoping on a request — *which console surface is this about?*
 * The api clamps anything outside `VALID_COMPONENTS` to `''` **silently** (`_clean_choice`; there
 * is no DB CHECK and no error), so a value the picker offers and the server does not know is not a
 * 400 anybody sees: it is a request that arrives with its component quietly blanked. That is the
 * failure this pair has to prevent, and it is exactly the kind nothing else would notice.
 *
 * Characterised first (the H8 rule): the parents compared in order, the children per parent, and
 * the flattened value set — the shape `_clean_choice` actually tests against — on the untouched
 * tree. They AGREE.
 */
import {
  REQUEST_COMPONENT_TREE, REQUEST_COMPONENT_PARENTS, REQUEST_COMPONENT_VALUES,
  requestSubComponents, componentLabelKey,
} from '@/lib/requestStatus'
import { readApi, readApiTree } from '@/test/apiSource'

// ⚠ `models.py` became the PACKAGE `models/` at code health H15 (2026-09-20). Walked rather than
// pointed at `models/org_requests.py`, because the error message below promises the tree is where
// `REQUEST_COMPONENT_TREE` must be a module-level dict — and a second copy appearing in another
// module is exactly the drift this file exists to catch.
const MODELS = 'apps/scholarship/models'
const SERVICE = 'apps/scholarship/org_requests.py'
const modelsSrc = readApiTree(MODELS, 15)
const serviceSrc = readApi(SERVICE)

/** `REQUEST_COMPONENT_TREE = {'parent': ('sub', …), 'other': (), …}` — parents in order. */
const backendTree = (() => {
  const block = modelsSrc.match(/^REQUEST_COMPONENT_TREE\s*=\s*\{[\s\S]*?^\}/m)
  if (!block) {
    throw new Error(
      `drift test: REQUEST_COMPONENT_TREE is no longer a module-level dict in ${MODELS}. The `
      + 'component vocabulary has moved — follow it, never delete the assertion.')
  }
  const out: Record<string, string[]> = {}
  for (const m of block[0].matchAll(/'([a-z_]+)'\s*:\s*\(([\s\S]*?)\)/g)) {
    out[m[1]] = [...m[2].matchAll(/'([a-z_]+)'/g)].map((x) => x[1])
  }
  return out
})()

/** The api's own flattening — `${parent}_${sub}` with an underscore, plus every bare parent. */
const backendValues = Object.entries(backendTree)
  .flatMap(([parent, subs]) => [parent, ...subs.map((s) => `${parent}_${s}`)])

describe('parse sanity — the api tree was really found', () => {
  test('eight parents, exactly one of them carrying children', () => {
    expect(Object.keys(backendTree).length).toBe(8)
    const withChildren = Object.entries(backendTree).filter(([, subs]) => subs.length > 0)
    expect(withChildren.map(([p]) => p)).toEqual(['applications'])
    expect(withChildren[0][1].length).toBe(8)
  })

  test('VALID_COMPONENTS is still DERIVED from the tree, not a second list', () => {
    // If it stops deriving, this whole comparison is against the wrong thing.
    expect(serviceSrc).toMatch(/^VALID_COMPONENTS = flatten_component_tree\(REQUEST_COMPONENT_TREE\)$/m)
  })
})

describe('REQUEST_COMPONENT_TREE vs models.REQUEST_COMPONENT_TREE', () => {
  test('the same parents, in the same order — the select\'s option order', () => {
    expect(REQUEST_COMPONENT_PARENTS).toEqual(Object.keys(backendTree))
  })

  test('the same children under each parent, in the same order', () => {
    for (const parent of REQUEST_COMPONENT_PARENTS) {
      expect([...(REQUEST_COMPONENT_TREE[parent] || [])]).toEqual(backendTree[parent])
    }
  })

  test('the flattened value set matches, both directions', () => {
    expect([...REQUEST_COMPONENT_VALUES].sort()).toEqual([...backendValues].sort())
  })

  test('no value the picker offers would be silently blanked by _clean_choice', () => {
    // The direction that matters most: `_clean_choice` clamps an unknown value to '' with no
    // error, so a picker offering one loses the scoping and nobody is told.
    expect(REQUEST_COMPONENT_VALUES.filter((v) => !backendValues.includes(v))).toEqual([])
    expect(serviceSrc).toMatch(/return v if v in valid else ''/)
  })

  test('a sub-component VALUE joins with an UNDERSCORE — a dot breaks the i18n lookup', () => {
    const subs = requestSubComponents('applications')
    expect(subs.length).toBe(backendTree.applications.length)
    expect(subs.every((v) => v.startsWith('applications_'))).toBe(true)
    expect(subs.some((v) => v.includes('.'))).toBe(false)
    // …and the label key is the nested path, which is why the value may not carry its own dot.
    expect(componentLabelKey(subs[0])).toBe(`admin.requests.component.${subs[0]}`)
  })

  test('a parent with no children offers none — Students and Course Data are absent by design', () => {
    for (const [parent, subs] of Object.entries(backendTree)) {
      if (subs.length === 0) expect(requestSubComponents(parent)).toEqual([])
    }
    expect(REQUEST_COMPONENT_PARENTS).not.toContain('students')
    expect(REQUEST_COMPONENT_PARENTS).not.toContain('course_data')
    expect(Object.keys(backendTree)).not.toContain('students')
  })
})
