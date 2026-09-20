"""THE ALARM ON THE SIDE THAT DOES THE MOVING (TD-269, closed by TD-276 at code health H16).

**What this is for.** Thirty-one web test files read source text, and two dozen of them read
`halatuju_api/**` by path — through `readApi('apps/scholarship/serializers.py')` and friends — to
check a front-end rule against the backend's own source. Every one of those is a path from the api
tree into the web suite **that no api gate walks**.

H13 measured what that costs. H11 turned `views_admin.py` into a package and H12 finished the job;
both were backend-only sprints, both ran `pytest`, `manage.py check` and `makemigrations --check`
all green, and neither ran `jest`, because neither touched a web file. `officerGateDrift.test.ts`
had been **dead at import** ever since — not failing an assertion, failing to LOAD — so the web
suite ran 2,900 tests / 158 suites while the record said 2,913 / 159, and thirteen tests covering
the irreversible org-admin reject gate enforced nothing for two sprints. The guard even printed
the right instruction — *"The rule it guards has MOVED"* — to nobody. **The break was structurally
invisible from the side that caused it.**

So this test is a directory listing against a list of strings, on the api side, inside the api's
own gate. It needs no jest, no node and no web install. Move an api file that a web guard reads
and `pytest` goes red in the same sprint that moved it, naming the web file that will die.

**It answers the other half too: a whole test FILE vanishing from the run.** A named manifest
(`GUARD_FILES`) plus a floor on the web suite's file count means a guard that is DELETED or
RENAMED fails here, which a count alone would not catch and which nothing else in either tree
notices. What it cannot see is a guard file that still exists and still runs but has been hollowed
out — that is what each guard's own floor is for (`source_walk.py`).
"""
import re

from django.test import SimpleTestCase

from apps.scholarship.tests.source_walk import (
    API_ROOT, REPO_ROOT, floor_count, walk_sources,
)

WEB_SRC = REPO_ROOT / 'halatuju-web' / 'src'

#: An api path as a web test writes it: a single-quoted `apps/…` literal, with or without `.py`.
#: This is the `readApi(MODELS)` form as well as the inline one, because the constant it is
#: assigned to is written the same way.
_API_LITERAL = re.compile(r"'(apps/[A-Za-z0-9_/]+(?:\.py)?)'")

#: The other form: `path.join(__dirname, '..', 'halatuju_api', 'apps', 'scholarship', 'x.py')`.
_API_JOIN = re.compile(r"'halatuju_api'((?:\s*,\s*'[^']+')+)")

#: ⚠ A MANIFEST, AND IT MAY ONLY GROW. Every web test file that reads the api tree by path. A
#: file deleted or renamed fails `test_no_named_web_guard_has_vanished` — which is the only thing
#: in either tree that notices a guard leaving the run, as opposed to a guard going quiet.
#: When you add a web guard that reads `halatuju_api/**`, add it here on the same day.
GUARD_FILES = (
    'src/lib/__tests__/adminRoleDrift.test.ts',
    'src/lib/__tests__/applicationStatusDrift.test.ts',
    'src/lib/__tests__/commsKindsDrift.test.ts',
    'src/lib/__tests__/contractTermsDrift.test.ts',
    'src/lib/__tests__/familyRosterDrift.test.ts',
    'src/lib/__tests__/financeAllowlistDrift.test.ts',
    'src/lib/__tests__/incomeEvidenceHomes.test.ts',
    'src/lib/__tests__/officerGateDrift.test.ts',
    'src/lib/__tests__/payoutAccountDrift.test.ts',
    'src/lib/__tests__/profileClaimCodes.test.ts',
    'src/lib/__tests__/requestComponentDrift.test.ts',
    'src/lib/__tests__/requestStatusDrift.test.ts',
    'src/lib/__tests__/soft-evidence-drift.test.ts',
    'src/lib/__tests__/staffDrift.test.ts',
    'src/lib/__tests__/strCoachDrift.test.ts',
    'src/lib/__tests__/studentScreenDrift.test.ts',
    'src/lib/__tests__/themeContrastDrift.test.ts',
    'src/lib/__tests__/webMirrorDrift.test.ts',
    'src/test/adminApplicationDetail.test.ts',
    #: Not a test — the shared reader every drift test above goes through. If it moves, all of
    #: them die at import at once, which is precisely the H13 failure at nineteen times the size.
    'src/test/apiSource.ts',
)

#: Web test files on 2026-09-20: 159 suites. A MINIMUM — a new web test must leave this green.
WEB_TEST_FLOOR = 150

#: Distinct api paths the web tree named on 2026-09-20: 24. A minimum.
API_REFERENCE_FLOOR = 20


def _web_test_files():
    """Every `*.test.ts(x)` under `halatuju-web/src`, plus the shared readers in `src/test/`."""
    files = walk_sources(
        WEB_SRC, '*.ts', WEB_TEST_FLOOR,
        'the web suite reads the api tree by path from ~20 of these files, and an api refactor '
        'can kill one of them with every api gate green')
    files += walk_sources(
        WEB_SRC, '*.tsx', 1,
        'some web drift guards are .tsx; the walk must see both extensions')
    return sorted(files)


def _api_references():
    """(web file, api path) for every reference from the web tree into `halatuju_api/`."""
    out = []
    for path in _web_test_files():
        rel = path.relative_to(WEB_SRC.parent).as_posix()
        src = path.read_text(encoding='utf-8')
        for m in _API_LITERAL.finditer(src):
            out.append((rel, m.group(1)))
        for m in _API_JOIN.finditer(src):
            parts = re.findall(r"'([^']+)'", m.group(1))
            out.append((rel, '/'.join(parts)))
    return out


class TestTheWebSuiteStillPointsAtRealApiFiles(SimpleTestCase):
    def test_every_api_path_a_web_guard_names_is_really_there(self):
        """⚠ THE POINT OF THE WHOLE FILE. Break this by moving an api file, and the fix is to
        follow the code in the WEB guard that names it — never to delete the reference, and never
        to delete the assertion it feeds."""
        broken = sorted({
            f'{web}  ->  {api}'
            for web, api in _api_references()
            if not (API_ROOT / api).exists()
        })
        self.assertEqual(broken, [], (
            'These web tests read an api path that is NO LONGER THERE. Each one will die at '
            'IMPORT the next time jest runs — the whole file, not one assertion — and the api '
            'gate that let it happen will stay green (that is H13, exactly). Re-point the path in '
            'the WEB file, in this sprint, beside the move that broke it:\n  '
            + '\n  '.join(broken)))

    def test_the_scan_actually_found_the_references(self):
        """THE FLOOR. If `readApi` were renamed, or the web tree moved, this scan would find zero
        paths, every one of them would trivially exist, and the test above would pass for ever
        while watching nothing — the shape TD-276 was raised to end."""
        refs = _api_references()
        floor_count(sorted({api for _web, api in refs}), API_REFERENCE_FLOOR,
                    'distinct api paths named by web tests',
                    'each is a path from the api tree into the web suite that no api gate walks')
        self.assertIn('apps/scholarship/serializers.py', {api for _web, api in refs},
                      'the serializers path is named by payoutAccountDrift — if it is missing, '
                      'the extraction stopped working, not the reference')

    def test_no_named_web_guard_has_vanished(self):
        """A whole test FILE leaving the run is invisible to every other check in either tree: a
        suite count is a number nobody reads, and a guard that is gone asserts nothing by
        definition. This names them. A file RENAMED belongs in the list under its new name in the
        same commit; a file deliberately DELETED belongs out of the list, deliberately."""
        web_root = REPO_ROOT / 'halatuju-web'
        gone = [g for g in GUARD_FILES if not (web_root / g).is_file()]
        self.assertEqual(gone, [], (
            'These web guard files are NOT THERE. Each read the api tree by path, so each was a '
            'rule this repository had decided to enforce. If one was renamed, rename it here too; '
            'if one was deliberately deleted, delete the entry deliberately — do not let a guard '
            'leave the run by accident:\n  ' + '\n  '.join(gone)))

    def test_the_web_suite_has_not_quietly_shrunk(self):
        """The coarse half of the same question, for a guard file nobody thought to name: the web
        suite had 159 test files on 2026-09-20 and must not fall below the floor."""
        tests = [p for p in _web_test_files() if p.name.endswith(('.test.ts', '.test.tsx'))]
        self.assertGreaterEqual(len(tests), WEB_TEST_FLOOR, (
            f'THE FLOOR: only {len(tests)} web test file(s) under {WEB_SRC}. The suite has shrunk '
            f'or the tree MOVED. Check before lowering this number.'))
