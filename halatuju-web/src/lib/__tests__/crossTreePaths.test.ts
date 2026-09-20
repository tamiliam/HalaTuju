/**
 * THE ALARM ON THE SIDE THAT DOES THE MOVING — the other direction (TD-276, code health H16).
 *
 * `test_web_guards_read_live_paths.py` puts the api's gate in front of every web guard that reads
 * `halatuju_api/**`. This is its mirror: six api tests read `halatuju-web/**` by path — the
 * message catalogue, `officerCockpit.ts`, `subjects.ts`, `sponsorComms.ts`, `globals.css` — and a
 * WEB-only sprint runs `npm run gates` and `next build`, never `pytest`, so it can break one of
 * them and see nothing. That is H13's failure with the trees swapped, and it has exactly the same
 * cost: a drift guard that dies at import protects nothing while every gate the sprint ran is
 * green.
 *
 * Move a web file an api guard reads and this goes RED in the same sprint that moved it, naming
 * the api test that will die. It is a directory listing against a list of strings — no Python, no
 * Django, no api install.
 *
 * It answers the vanishing-FILE question the same way: `GUARD_FILES` names every api test that
 * reads the web tree, so one deleted or renamed fails here rather than simply ceasing to exist.
 */
import * as fs from 'fs'
import * as path from 'path'

import { REPO_ROOT, floorCount, walkFloor } from '@/test/sourceGuard'

const API_ROOT = path.join(REPO_ROOT, 'halatuju_api')
const WEB_ROOT = path.join(REPO_ROOT, 'halatuju-web')

/** A web path as an api test writes it: `'halatuju-web' / 'src' / 'lib' / 'subjects.ts'`. */
const WEB_JOIN = /'halatuju-web'((?:\s*\/\s*'[^']+')+)/g

/**
 * ⚠ A MANIFEST, AND IT MAY ONLY GROW. Every api test that reads the web tree by path. One
 * deleted or renamed fails the vanishing-file test below — the only thing in either tree that
 * notices a guard LEAVING the run, as opposed to a guard going quiet.
 */
const GUARD_FILES = [
  'apps/courses/tests/test_contrast.py',
  'apps/scholarship/tests/test_closed_case_writes.py',
  'apps/scholarship/tests/test_requirements.py',
  'apps/scholarship/tests/test_sponsor_comms.py',
  'apps/scholarship/tests/test_subject_drift.py',
  'apps/scholarship/tests/test_verdict_item_i18n.py',
  // Not a test — the shared reader the api's own source guards go through. If it moves, every
  // floor in the api suite dies at collection at once.
  'apps/scholarship/tests/source_walk.py',
]

/** `*.py` under `halatuju_api/apps` on 2026-09-20: 623. A MINIMUM, rounded well down. */
const API_SOURCE_FLOOR = 550

/** Api TEST files on 2026-09-20: 298. A MINIMUM — a new api test must leave this green. */
const API_TEST_FLOOR = 260

/** Distinct web paths the api tree named on 2026-09-20: 6. A minimum. */
const WEB_REFERENCE_FLOOR = 5

const apiTestFiles = (): string[] => walkFloor(
  path.join(API_ROOT, 'apps'), API_SOURCE_FLOOR,
  'six of these read the web tree by path, and a web-only sprint runs no api gate at all',
  { exts: ['.py'], skip: ['migrations'] },
).filter((f) => path.basename(f).startsWith('test_') || path.basename(f) === 'source_walk.py')

function webReferences(): Array<[string, string]> {
  const out: Array<[string, string]> = []
  for (const file of apiTestFiles()) {
    const rel = path.relative(API_ROOT, file).split(path.sep).join('/')
    const src = fs.readFileSync(file, 'utf8')
    for (const m of src.matchAll(WEB_JOIN)) {
      const parts = [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1])
      out.push([rel, parts.join('/')])
    }
  }
  return out
}

describe('the api suite still points at real web files', () => {
  test('every web path an api guard names is really there', () => {
    // ⚠ THE POINT OF THE WHOLE FILE. Break this by moving a web file, and the fix is to follow
    // the code in the API guard that names it — never to delete the reference.
    const broken = [...new Set(webReferences()
      .filter(([, web]) => !fs.existsSync(path.join(WEB_ROOT, ...web.split('/'))))
      .map(([api, web]) => `${api}  ->  halatuju-web/${web}`))].sort()
    // Named on the left so the failure prints the list rather than "expected [] to equal [...]".
    expect({ apiGuardsReadingAWebPathThatIsGone: broken })
      .toEqual({ apiGuardsReadingAWebPathThatIsGone: [] })
  })

  test('the scan actually found the references (the floor)', () => {
    // If the api tree moved or the path style changed, this scan would find zero references,
    // every one of them would trivially exist, and the test above would pass for ever.
    const refs = webReferences()
    floorCount([...new Set(refs.map(([, web]) => web))], WEB_REFERENCE_FLOOR,
      'distinct web paths named by api tests',
      'each is a path from the web tree into the api suite that no web gate walks')
    expect(refs.map(([, web]) => web)).toContain('src/messages/en.json')
  })

  test('no named api guard has vanished from the run', () => {
    // A whole test FILE leaving is invisible to every other check: a file count is a number
    // nobody reads, and a guard that is gone asserts nothing by definition.
    const gone = GUARD_FILES.filter((g) => !fs.existsSync(path.join(API_ROOT, ...g.split('/'))))
    expect(gone).toEqual([])
  })

  test('the api suite has not quietly shrunk', () => {
    // The coarse half, for a guard file nobody thought to name.
    expect(apiTestFiles().length).toBeGreaterThanOrEqual(API_TEST_FLOOR)
  })
})
