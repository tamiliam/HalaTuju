"""Code health H4 — THE STANDARDS, AS TESTS. The api half.

**Why this file exists.** The owner's ruling, 2026-09-18: *"once this is built, future builds
would ensure the standards are maintained to prevent bugs or inefficiencies creeping in."* Since
H2 the whole pytest suite runs inside the Cloud Build deploy gate, so **a standard written as a
test cannot be broken by a change that deploys.** A standard written in a document can, and this
project's own record says documents are what rot. So every standard below is an assertion.

`Settings/_tools/code_health.py` MEASURES and reports a trend; this file REFUSES. One tells you
where you are, the other stops you going backwards. The definitions here are deliberately taken
from that tool — what counts as source versus test, which directories are skipped, how a long
function or a duplicated name or a suppression or a skipped test is detected — so the readings in
`docs/code-health.md` and the limits enforced here can never describe two different codebases.
Where a number differs it is because a THRESHOLD differs and that is stated at the constant.

**THE RATCHET, AND WHY IT HAS NO GIT.** The Cloud Build checkout is `depth-1`: there is no parent
commit to compare against, so "is this worse than before?" cannot be answered by reading history.
It is answered by a committed file instead — `halatuju_api/code-standards.json`, which sits INSIDE
the api folder so it is inside the path filter of the trigger that runs these tests. That file
holds two blocks:

  * `baseline` — FROZEN. Every number and every ledger as H4 found them on 2026-09-19.
  * `budget`   — the CURRENT limits. Starts identical to `baseline`, and only ever gets tighter.

Four rules hold it shut, and all four are asserted below:

  1. `actual <= budget`            — the code may not get worse.
  2. `budget <= baseline`          — a limit may never be raised above where H4 found it, and a
                                     ledger may never gain a member it did not have then.
  3. `budget <= actual + slack`    — TIGHTNESS. A limit may not sit loose above reality. When the
                                     code improves, this FAILS until the budget is lowered. The
                                     manners are `NOT_YET_SCANNED`'s: "lower me", "remove me".
  4. the `baseline` block is PINNED by a SHA-256 held in this file, so rewriting history needs a
     second, deliberate edit in a second file that a reviewer cannot miss.
  5. a DECLARED MOVE may RELABEL a frozen entry onto the path the code went to, and may do
     nothing else. See below.

**RULE 5 — A LEDGER KEY FOLLOWS ITS CODE (TD-272, 2026-09-20).** Every ledger here is keyed on a
FILE PATH. When a file MOVES — which is what this roadmap's whole Phase 4 asks for — its key stops
naming a real file: the entry is orphaned, the same debt at the new path is UNLISTED (which fails),
and it cannot be added because a ledger may only shrink. H11 hit it on `views_admin.py` and paid
for it by editing the frozen baseline and re-pinning `BASELINE_SHA256` by hand; H14 hit it again
on `IncomeWizard` and simply did not do the move. A ratchet that refuses the improvement it exists
to encourage gets switched off.

So a move is now DECLARED, in a `_moved` array in `code-standards.json`, and the tests read the
`baseline` THROUGH it: `effective_baseline()` returns the frozen record with each declared move's
key relabelled, and every rule above then runs against that, unchanged. What makes this safe is
that a relabel is the ONLY thing it can do — a move names one key that is in the frozen ledger and
one that is not, so the ledger's length and its total are arithmetically identical either side, and
`budget <= baseline` then holds the new key to exactly the room the old one had. A move that would
buy anything — a bigger number, an extra member, a key the ledger already has, a file that is not
in the tree — is refused and named.

⚠ `_moved` sits OUTSIDE the `baseline` block, so **`BASELINE_SHA256` does NOT move for an honest
move.** That is the point: H11's hand re-pin was the loophole, not the fix. The frozen record stays
byte-for-byte what H4 measured; `_moved` is the (auditable, reviewable) lens through which it is
read. Rewriting `baseline` itself still fails rule 4, exactly as before.

**⚠ THE LOOPHOLE THAT REMAINS, STATED, because a guard whose limits are unwritten gets trusted
for things it never claimed.** Without git this file cannot see the PREVIOUS commit, only the
frozen baseline. So a number that has been ratcheted down to 70 can be raised back to 80 in the
same commit that makes the code worse, as long as 80 is still at or below the 2026-09-19 baseline
— and rules 1–3 will all pass. What it CANNOT do is exceed the baseline, add a ledger member, or
leave a budget loose. The remaining window is caught by the lead's sprint-close tool, which does
have git: `code_health.py` compares this run's readings with the last recorded row and FAILs on a
regression. Two guards, two mechanisms, one direction.

**ADDED IN H5** (2026-09-19): `hand_built_application_fixtures` — "a new test file may not
hand-build a `ScholarshipApplication`", now that `apps/scholarship/tests/factories.py` exists.
It is the only standard here that reads the TEST tree for something other than a skip, and it is
the one that answers BrightPath #24: a hand-built fixture described a state the product cannot
produce, so a test could never reach the branch it named. Adding it put a new key in the frozen
`baseline` block, so `BASELINE_SHA256` below was deliberately re-pinned in the same commit — see
the `_history` note in the JSON.

**NOT IN H4/H5, on purpose** (later sprints add them, each with its own test here or in the web
half):
  * database-query and first-load-JS budgets — H18.
Style and formatting are deliberately out of scope for ever: a formatter pass rewrites every file
and proves nothing about bugs.
"""
import ast
import hashlib
import io
import json
import os
import re

from django.test import SimpleTestCase

# ── Where things are ────────────────────────────────────────────────────────────────────────
#: `…/halatuju_api`. Four levels up from `apps/scholarship/tests/this_file.py`. Derived, never
#: hard-coded, so a move fails loudly at the floor test rather than silently scanning nothing.
API_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
BUDGET_PATH = os.path.join(API_ROOT, 'code-standards.json')

# ── The definitions, taken from Settings/_tools/code_health.py ──────────────────────────────
#: Verbatim from `code_health.EXCLUDE_DIRS`. A directory the reading skips must be a directory
#: the standard skips, or the two would describe different codebases.
EXCLUDE_DIRS = {
    'migrations', 'node_modules', '.next', '__pycache__', 'archive', '.worktrees', '.git',
    'venv', '.venv', 'staticfiles', 'coverage', 'out', 'build', 'dist',
}
TEST_DIRS = {'tests', '__tests__'}

#: Verbatim from `code_health.SUPPRESS_PY` and `code_health.SKIP_PY`.
NOQA = re.compile(r'#\s*noqa\b')
TYPE_IGNORE = re.compile(r'#\s*type:\s*ignore')
#: ⚠ The `@` is split from the word that follows it, and the prose below never spells the
#: decorators out with a real dot. Not fussiness: `code_health.py` scans this very file with this
#: very pattern and does NOT excuse it, so writing the pattern out contiguously made the tool
#: report three skipped tests that do not exist (seen 2026-09-19). The regex is unchanged —
#: adjacent string literals are one literal — but the file no longer matches itself.
SKIP_PY = re.compile(
    r'pytest\.mark\.(skip|skipif|xfail)\b|pytest\.skip\(|unittest\.skip'
    r'|@' r'skip(If|Unless)?\b')
#: NOT part of `code_health.SKIP_PY` — checked and confirmed: `self.skipTest(...)` is a RUNTIME
#: skip and the tool does not count it, which is why `skip` reads 0 while eight of these exist.
#: The tool's treatment is followed (they are not "skipped tests"), but they are a way a test can
#: decline to fail, so they are LEDGERED instead of ignored: the known ones are written down and
#: the list may only shrink. A new one fails.
RUNTIME_SKIP = re.compile(r'\.skipTest\(')

#: Verbatim from `code_health.DUP_IGNORE` and `code_health.DUP_FILES`.
DUP_IGNORE = {'main'}
DUP_FILES = 3
#: Verbatim from `code_health.LONG_FUNC_LINES`.
LONG_FUNC_LINES = 150

# ── The thresholds this file OWNS (they are stricter than the tool's on purpose) ─────────────
#: ⚠ The tool reports files over 1,000 lines (`code_health.BIG_FILE_LINES`); the STANDARD is 600.
#: They are different jobs. 1,000 is "this is one of the worst files in the project" — a triage
#: list a person reads. 600 is "no human or agent should have to hold this in one head to change
#: it safely" — a line a NEW file may not cross. Because the standard is stricter, this file's
#: ledger is longer than the tool's list, and that is expected: 36 here, 25 (both services) there.
MAX_FILE_LINES = 600

#: ONE fixed allowance, stated once, for every file already in the ledger. A hotfix that adds four
#: lines to an 8,500-line file must not be blocked by a guard whose real target is the NEXT giant
#: file. Because the recorded number can never rise (rule 2), total creep is capped at 20 lines
#: for ever, for each file, no matter how many hotfixes there are.
FILE_GROWTH_ALLOWANCE = 20
#: Tightness for the same ledger. A file that has shrunk by more than this is no longer described
#: by its entry, so the entry must be lowered. Generous enough that ordinary deletions do not nag.
FILE_SHRINK_SLACK = 50
#: The same pair for functions, scaled to a function rather than a file.
FUNC_GROWTH_ALLOWANCE = 10
FUNC_SHRINK_SLACK = 25

#: Tightness slack per counted number. Two matches `code_health.TOL_COUNT`, the tolerance the
#: trend tool already uses for a count — so ordinary churn does not nag on the big suppression
#: counts. ZERO where the number is already small enough that every unit matters: a count of 1
#: with a slack of 2 would let the budget sit at 1 while the real answer is 0, which is exactly
#: the looseness rule 3 exists to stop.
COUNT_SLACK = {
    'noqa': 2,
    'type_ignore': 2,
    'skip_sites': 0,
    'courses_to_scholarship_imports': 2,
    'courses_to_scholarship_module_level_imports': 0,
}

#: The SHA-256 of the canonical JSON of the `baseline` block (sorted keys, no whitespace, UTF-8).
#: ⚠ If you are here because this failed: the baseline is the frozen record of what H4 found. It
#: is not a number to keep current. Lower a limit in `budget`, never in `baseline`.
#: ⚠ RE-PINNED 2026-09-20 (code health H11), the second deliberate re-pin after H5's. Nothing was
#: raised and no ledger gained a member: `apps/scholarship/views_admin.py` became the package
#: `apps/scholarship/views_admin/`, so its `oversize_files` KEY was renamed to
#: `apps/scholarship/views_admin/__init__.py` in both blocks — same file, new path, baseline number
#: untouched at 8547. A path rename is the one case where the frozen record must follow: a key
#: naming a file that no longer exists describes nothing, and the two tests above would then
#: demand the line be removed AND refuse the package root with no line left to lower. See the
#: `_history` note in the JSON and `docs/retrospective-2026-09-20-code-health-h11.md`.
BASELINE_SHA256 = '20c521daa4565d11842f95fdac43f2874f00ca67836c6c38150851ff2c3919f2'

LEDGERS = ('oversize_files', 'long_functions', 'duplicated_names', 'runtime_skips',
           'hand_built_application_fixtures')

#: Which of those are keyed on a REPO PATH — the whole key for three of them, the part before the
#: `::` for `long_functions`. `duplicated_names` is keyed `app::name` and names no file at all, so
#: it is the one ledger whose move cannot be checked against the tree; everything else about a move
#: is checked for it like any other.
PATH_KEYED_LEDGERS = frozenset({'oversize_files', 'long_functions', 'runtime_skips',
                                'hand_built_application_fixtures'})

#: Every field a `_moved` record must carry, all non-empty strings. `why` is not decoration: a
#: relabel of the frozen record is the one edit that survives a reviewer's glance, so it has to say
#: what moved and what for. `MIN_MOVE_WORDS` is the same "three words of prose is not a sentence"
#: reasoning the web half applies to an eslint-disable reason, one notch stricter.
MOVE_FIELDS = ('on', 'why', 'ledger', 'from', 'to')
MIN_MOVE_WORDS = 5

#: H5. The model whose hand-built fixtures are ledgered, and the call that builds one. Counted
#: from the AST — never from a string match — because a guard that fires on the words in a
#: comment or a docstring is a guard somebody deletes within a month (H4's own `SELF` note makes
#: the same point). `objects.filter(...).update(...)`, which is how a test legitimately pokes one
#: column without re-running `save()`, is deliberately NOT a match.
FIXTURE_MODEL = 'ScholarshipApplication'
FIXTURE_CALL = 'create'

#: The two files that MAY hand-build one, because they are the factory and its drift test.
#: ⚠ EXACTLY TWO, and `test_the_fixture_exclusion_is_exactly_the_factory_and_its_test` keeps it
#: that way: an exclusion list that can grow is how a standard becomes a formality.
FACTORY_FILES = (
    'apps/scholarship/tests/factories.py',
    'apps/scholarship/tests/test_factories.py',
)

#: ⚠ THIS FILE EXCLUDES ITSELF FROM THE TEST-FILE SCAN, and only from that scan. It has to: the
#: patterns above are written out in full here, so the skip decorators and the runtime skip call
#: appear as source text on the lines that DEFINE them. Without this the guard would fire on its own
#: documentation, and a guard that does that gets deleted within a month (`test_org_fence` makes
#: the same point about its own `SPONSOR_WATCHED` tokens). The cost is a hole exactly one file
#: wide — a skip hidden in THIS file would not be seen — which `test_the_self_exclusion_is_one
#: _file_wide` keeps honest by proving nothing else is excused.
SELF = os.path.relpath(os.path.abspath(__file__), API_ROOT).replace(os.sep, '/')


# ── Reading the tree, once ──────────────────────────────────────────────────────────────────
def _read(path):
    """`newline=None` so a CRLF file counts the same lines as a LF one — the gate runs on Linux
    and the authoring machine is Windows. Same call `code_health._read` makes."""
    with io.open(path, 'r', encoding='utf-8', errors='replace', newline=None) as fh:
        return fh.read()


def _rel(path):
    """Relative to the api root, forward slashes ALWAYS, so a ledger key written on Windows is
    the same string the Linux gate computes."""
    return os.path.relpath(path, API_ROOT).replace(os.sep, '/')


def _is_test_path(relpath):
    """`code_health.is_test_path`, less the JS half (there are no .ts files here)."""
    parts = relpath.split('/')
    base = parts[-1]
    if any(p in TEST_DIRS for p in parts[:-1]):
        return True
    return base.startswith('test_') or base == 'conftest.py'


def _walk():
    """Every `.py` under the api root, EXCLUDE_DIRS skipped. `code_health.walk`'s behaviour."""
    for dirpath, dirnames, filenames in os.walk(API_ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for name in sorted(filenames):
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


def _qualnames(tree):
    """(dotted name, line count) for every function, nested ones included.

    ⚠ The key is the NAME, never the line number — `code_health` prints `path:1008 post`, which
    moves the moment anything above it changes. A ledger keyed on that would need rewriting after
    every edit, and a ledger that is rewritten constantly is a ledger nobody reads."""
    rows = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                rows.append((name, (child.end_lineno or child.lineno) - child.lineno + 1))
                visit(child, name + '.')
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + '.')
            else:
                visit(child, prefix)

    visit(tree, '')
    return rows


def _imports(tree):
    """(module, is_module_level, line) for every import. Module level means NOT inside a function
    — so it runs at import time, which is what makes a cross-app edge an import cycle risk. The
    deliberate fix for such an edge is to move the import inside the function that needs it."""
    out = []

    def visit(node, in_func):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ImportFrom) and child.module and child.level == 0:
                out.append((child.module, not in_func, child.lineno))
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    out.append((alias.name, not in_func, child.lineno))
            visit(child, in_func or isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)))

    visit(tree, False)
    return out


def _hand_built_applications(tree):
    """How many times this module calls ``ScholarshipApplication.objects.create(...)``.

    Matched on the AST shape ``<Name|Attribute>.objects.create(...)`` whose model name is
    ``FIXTURE_MODEL``, so `models.ScholarshipApplication.objects.create(...)` counts and the
    same words inside a comment, a docstring or a message string do not."""
    found = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = node.func
        if not (isinstance(call, ast.Attribute) and call.attr == FIXTURE_CALL):
            continue
        manager = call.value
        if not (isinstance(manager, ast.Attribute) and manager.attr == 'objects'):
            continue
        model = manager.value
        name = (model.id if isinstance(model, ast.Name)
                else model.attr if isinstance(model, ast.Attribute) else None)
        if name == FIXTURE_MODEL:
            found += 1
    return found


def _app_of(relpath):
    """`apps/scholarship/views.py` -> `scholarship`. `code_health._app_of`'s rule."""
    parts = relpath.split('/')
    if 'apps' in parts[:-1]:
        i = parts.index('apps')
        if i + 1 < len(parts) - 1:
            return parts[i + 1]
    return None


def scan():
    """Walk the api tree ONCE and return every reading this file asserts on.

    Cached in `_SCAN` by the tests below, so the whole standard costs one pass over 550-odd
    files (about half a second) however many assertions read it."""
    sources, tests = [], []
    for path in _walk():
        (tests if _is_test_path(_rel(path)) else sources).append(path)

    oversize, long_functions, homes = {}, {}, {}
    noqa = type_ignore = 0
    xapp, xapp_module_level = [], []
    for path in sources:
        rel, text = _rel(path), _read(path)
        lines = len(text.splitlines())
        if lines > MAX_FILE_LINES:
            oversize[rel] = lines
        noqa += len(NOQA.findall(text))
        type_ignore += len(TYPE_IGNORE.findall(text))
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        for name, count in _qualnames(tree):
            if count >= LONG_FUNC_LINES:
                long_functions[f'{rel}::{name}'] = count
        app = _app_of(rel)
        if not app:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name not in DUP_IGNORE:
                homes.setdefault(f'{app}::{node.name}', set()).add(rel)
        for module, module_level, line in _imports(tree):
            bits = module.split('.')
            if len(bits) >= 2 and bits[0] == 'apps' and bits[1] != app:
                if app == 'courses' and bits[1] == 'scholarship':
                    xapp.append(f'{rel}:{line} {module}')
                    if module_level:
                        xapp_module_level.append(f'{rel}:{line} {module}')

    skip_sites, runtime_skips, excused = [], {}, []
    hand_built, fixture_excused = {}, []
    for path in tests:
        rel, text = _rel(path), _read(path)
        # H5, and NOT under the `SELF` excuse below: this file is excused from the SKIP scan
        # only, and it hand-builds nothing, so it is counted here like any other test file.
        if rel in FACTORY_FILES:
            fixture_excused.append(rel)
        else:
            try:
                found = _hand_built_applications(ast.parse(text))
            except (SyntaxError, ValueError):
                found = 0
            if found:
                hand_built[rel] = found
        if rel == SELF:
            excused.append(rel)       # see the note at SELF — this file spells the patterns out
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if SKIP_PY.search(line):
                skip_sites.append(f'{rel}:{i}  {line.strip()[:110]}')
        found = len(RUNTIME_SKIP.findall(text))
        if found:
            runtime_skips[rel] = found

    return {
        'source_files': len(sources),
        'test_files': len(tests),
        'excused_from_the_skip_scan': sorted(excused),
        'excused_from_the_fixture_ledger': sorted(fixture_excused),
        'hand_built_application_fixtures': dict(sorted(hand_built.items())),
        'oversize_files': dict(sorted(oversize.items())),
        'long_functions': dict(sorted(long_functions.items())),
        'duplicated_names': {k: len(v) for k, v in sorted(homes.items()) if len(v) >= DUP_FILES},
        'duplicated_homes': {k: sorted(v) for k, v in sorted(homes.items()) if len(v) >= DUP_FILES},
        'runtime_skips': dict(sorted(runtime_skips.items())),
        'skip_sites': skip_sites,
        'counts': {
            'noqa': noqa,
            'type_ignore': type_ignore,
            'skip_sites': len(skip_sites),
            'courses_to_scholarship_imports': len(xapp),
            'courses_to_scholarship_module_level_imports': len(xapp_module_level),
        },
        'courses_to_scholarship': sorted(xapp),
        'courses_to_scholarship_module_level': sorted(xapp_module_level),
    }


_SCAN = None
_BUDGET_FILE = None


def _scan():
    global _SCAN
    if _SCAN is None:
        _SCAN = scan()
    return _SCAN


def _budget_file():
    global _BUDGET_FILE
    if _BUDGET_FILE is None:
        _BUDGET_FILE = json.loads(_read(BUDGET_PATH))
    return _BUDGET_FILE


def canonical(block):
    """The exact bytes the pin is taken over. Sorted keys, no whitespace, UTF-8."""
    return json.dumps(block, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


# ── Rule 5: a declared move, and every way it can fail to be one ────────────────────────────
def _in_api_tree(relpath):
    """Is this a real file under the api root? Injected as `exists` so the arithmetic tests below
    can prove the rule without needing files on disk."""
    return os.path.isfile(os.path.join(API_ROOT, relpath))


def effective_baseline(baseline, moves, exists=_in_api_tree):
    """The frozen `baseline` ledgers, with every DECLARED move RELABELLED onto its new key.

    See RULE 5 at the top of this file. Returns `(effective, problems)`:

      * `effective` — `{ledger name: {key: number}}`, the frozen ledgers with the relabels applied.
        The `baseline` block itself is never touched, so `BASELINE_SHA256` never moves.
      * `problems`  — one sentence per move that is NOT an honest relabel, written at the engineer
        who has to fix it. A refused move relabels nothing, so the old key stays and the ordinary
        "unlisted" / "gained a member" failures fire too; this list is what says WHY.

    A move is honest when all of these hold, and together they make it impossible for debt to grow
    through one:

      * the record is complete — `on`, `why`, `ledger`, `from`, `to`, and a `why` that is a
        sentence rather than a shrug;
      * `from` IS in that ledger (there is a real recorded debt to relabel), and
      * `to` is NOT (a move is a relabel, never a merge — two entries landing on one key would
        give the survivor the room of both), and
      * `to` names a file that is actually in the tree.

    Because a relabel pops one key and inserts one key, the ledger's LENGTH and its TOTAL are
    arithmetically unchanged — `test_a_move_changes_no_ledger_s_length_or_total` asserts exactly
    that, so a future edit here cannot quietly make a move generous. And since the new key inherits
    the old key's frozen number, `test_no_budget_number_is_above_the_baseline` then holds the moved
    entry to precisely the room the entry it replaced had, and no more.
    """
    effective = {ledger: dict(baseline.get(ledger, {})) for ledger in LEDGERS}
    problems = []
    for i, move in enumerate(moves):
        at = f'_moved[{i}]'
        if not isinstance(move, dict):
            problems.append(f'{at}: every entry in "_moved" must be an object carrying '
                            f'{", ".join(MOVE_FIELDS)}.')
            continue
        blank = [f for f in MOVE_FIELDS
                 if not isinstance(move.get(f), str) or not move[f].strip()]
        if blank:
            problems.append(
                f'{at}: missing or empty {", ".join(blank)}. A move record carries '
                f'{", ".join(MOVE_FIELDS)}, all non-empty strings.')
            continue
        ledger, old, new = move['ledger'], move['from'], move['to']
        if ledger not in LEDGERS:
            problems.append(f'{at}: "ledger" is "{ledger}", which is not one of '
                            f'{", ".join(LEDGERS)}.')
            continue
        if len(re.findall(r'[A-Za-z]{2,}', move['why'])) < MIN_MOVE_WORDS:
            problems.append(
                f'{at}: "why" needs at least {MIN_MOVE_WORDS} words saying what moved and what '
                f'for. Relabelling the frozen record is the one edit a reviewer will not question '
                f'on sight, so it has to explain itself.')
            continue
        entries = effective[ledger]
        if old not in entries:
            problems.append(
                f'{at}: "from" names "{old}", which the frozen {ledger} ledger does not hold. A '
                f'move may only RELABEL a debt that is already recorded — if it is not recorded, '
                f'moving the code does not make room for it. Fix the code instead, or correct the '
                f'"from" key to the one the baseline actually has.')
            continue
        if new in entries:
            problems.append(
                f'{at}: "to" names "{new}", which the {ledger} ledger ALREADY holds. A move is a '
                f'relabel, never a merge: two entries landing on one key would give the survivor '
                f'the room of both. Land the moved code on a path of its own.')
            continue
        if ledger in PATH_KEYED_LEDGERS and not exists(new.split('::')[0]):
            problems.append(
                f'{at}: "to" names the file "{new.split("::")[0]}", which is not in the tree. A '
                f'move must land on a file that EXISTS, or the ledger goes back to describing '
                f'nothing — which is the whole defect this mechanism ends (TD-272).')
            continue
        entries[new] = entries.pop(old)
    return effective, problems


class _Standard(SimpleTestCase):
    """Shared plumbing. Nothing asserts here; the standards are the subclasses."""
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scan = _scan()
        cls.file = _budget_file()
        cls.budget = cls.file['budget']
        cls.baseline = cls.file['baseline']
        #: RULE 5. The frozen ledgers as the DECLARED moves leave them — what every ledger rule
        #: below is measured against. `cls.baseline` stays the untouched, pinned block.
        cls.moves = cls.file.get('_moved', [])
        cls.effective, cls.move_problems = effective_baseline(
            cls.baseline, cls.moves if isinstance(cls.moves, list) else [])


class TestTheScanActuallyFoundTheCode(_Standard):
    """THE FLOOR, and the only reason anything below means anything.

    A scan that walked no files reports no violations and passes for ever while watching nothing —
    the exact failure mode `test_org_fence` and `test_endpoint_exercise` each guard against with a
    floor of their own. These are the numbers seen on 2026-09-19, less a wide margin for churn."""

    def test_the_tree_is_where_this_file_thinks_it_is(self):
        self.assertTrue(os.path.isdir(os.path.join(API_ROOT, 'apps')),
                        f'API_ROOT resolved to {API_ROOT}, which has no apps/ — this file moved '
                        f'and the path derivation at the top must move with it.')
        self.assertGreater(self.scan['source_files'], 200,
                           'fewer than 200 source files found — the walk is not seeing the tree, '
                           'so every standard below is vacuous.')
        self.assertGreater(self.scan['test_files'], 200,
                           'fewer than 200 test files found — the skip standard is vacuous.')

    def test_the_readings_are_not_all_empty(self):
        self.assertGreater(len(self.scan['oversize_files']), 10,
                           'no large files found at all — the line counter is broken.')
        self.assertGreater(len(self.scan['long_functions']), 5,
                           'no long functions found at all — the AST walk is broken.')

    def test_the_self_exclusion_is_one_file_wide(self):
        """The hole at `SELF` is acceptable only while it stays exactly one file wide. If a second
        name ever appears here, the skip standard has been quietly switched off for something."""
        self.assertEqual(
            self.scan['excused_from_the_skip_scan'], [SELF],
            'The skip scan is excusing a file other than this one. Only this file may be excused, '
            'and only because it spells the skip patterns out as source text. Remove the other '
            'excuse and make that file pass the standard.')

    def test_the_budget_file_is_the_shape_this_file_expects(self):
        for block in ('baseline', 'budget'):
            self.assertIn(block, self.file,
                          f'{BUDGET_PATH} has no "{block}" block — restore it from git; it is '
                          f'what every standard in this file is measured against.')
        for ledger in LEDGERS:
            for block in ('baseline', 'budget'):
                self.assertIn(ledger, self.file[block],
                              f'{BUDGET_PATH}: "{block}" is missing the "{ledger}" ledger.')
        self.assertIn('_how_this_works', self.file,
                      f'{BUDGET_PATH} has lost its "_how_this_works" note — it is what lets '
                      f'someone opening the file cold understand what they may change.')
        self.assertIsInstance(
            self.file.get('_moved', []), list,
            f'{BUDGET_PATH}: "_moved" must be an ARRAY of move records (it may be empty). It is '
            f'the declared list of ledger keys that followed their code to a new path — RULE 5 at '
            f'the top of this file.')


class TestNoNewGiantFile(_Standard):
    """A file too big to hold in one head is where the fixes land: `views_admin.py` was fixed 34
    times in 90 days and is 8,547 lines. The standard is not "make them small" — that is Phase 4's
    job — it is "no NEW one, and the known ones may not grow"."""

    def test_no_unlisted_source_file_passes_the_line_limit(self):
        new = sorted(f'{n} lines  {f}' for f, n in self.scan['oversize_files'].items()
                     if f not in self.budget['oversize_files'])
        self.assertEqual(
            new, [],
            f'Source file(s) over {MAX_FILE_LINES} lines that are not in the oversize_files '
            f'ledger. A file this size is where bugs land: it cannot be held in one head, and '
            f'nobody reviews it properly. SPLIT IT into modules under {MAX_FILE_LINES} lines, in '
            f'its own commit with no behaviour change. Do NOT add it to the ledger — the ledger '
            f'is frozen at what H4 found and may only shrink.\n' + '\n'.join(new))

    def test_a_listed_file_has_not_grown_past_its_allowance(self):
        grown = []
        for path, limit in sorted(self.budget['oversize_files'].items()):
            now = self.scan['oversize_files'].get(path)
            if now is not None and now > limit + FILE_GROWTH_ALLOWANCE:
                grown.append(f'{path}: {now} lines, recorded at {limit}, '
                             f'allowance {limit + FILE_GROWTH_ALLOWANCE}')
        self.assertEqual(
            grown, [],
            f'File(s) in the oversize_files ledger have grown more than {FILE_GROWTH_ALLOWANCE} '
            f'lines past their recorded size. That allowance exists for a hotfix, not for new '
            f'work. SPLIT THE FILE FIRST, in its own commit, then add your change to the smaller '
            f'module. Never raise the recorded number — it may only go down.\n' + '\n'.join(grown))

    def test_a_listed_file_that_shrank_has_its_entry_lowered(self):
        """Tightness. A budget that sits loose above reality re-permits the growth the split just
        removed, so the entry must follow the file down. The manners are `NOT_YET_SCANNED`'s."""
        stale = []
        for path, limit in sorted(self.budget['oversize_files'].items()):
            now = self.scan['oversize_files'].get(path)
            if now is None:
                stale.append(f'{path}: now {MAX_FILE_LINES} lines or fewer (or gone) — '
                             f'REMOVE this line from "oversize_files" in budget')
            elif limit > now + FILE_SHRINK_SLACK:
                stale.append(f'{path}: now {now} lines but recorded at {limit} — '
                             f'LOWER this line to {now}')
        self.assertEqual(
            stale, [],
            f'The oversize_files budget is looser than the code. Edit "budget" in '
            f'{os.path.basename(BUDGET_PATH)} exactly as each line says. This is the ratchet '
            f'catching up with your improvement, not a complaint about it.\n' + '\n'.join(stale))


class TestNoNewGiantFunction(_Standard):
    """Same reasoning, one level down. A 300-line function has no seams to test against, so the
    only way to exercise a branch in the middle of it is to run the whole thing."""

    def test_no_unlisted_function_reaches_the_line_limit(self):
        new = sorted(f'{n} lines  {k}' for k, n in self.scan['long_functions'].items()
                     if k not in self.budget['long_functions'])
        self.assertEqual(
            new, [],
            f'Function(s) of {LONG_FUNC_LINES}+ lines that are not in the long_functions ledger. '
            f'Extract the steps into named helpers each of which can be tested on its own. Do NOT '
            f'add the function to the ledger — it is frozen at what H4 found and may only '
            f'shrink.\n' + '\n'.join(new))

    def test_a_listed_function_has_not_grown_past_its_allowance(self):
        grown = []
        for key, limit in sorted(self.budget['long_functions'].items()):
            now = self.scan['long_functions'].get(key)
            if now is not None and now > limit + FUNC_GROWTH_ALLOWANCE:
                grown.append(f'{key}: {now} lines, recorded at {limit}, '
                             f'allowance {limit + FUNC_GROWTH_ALLOWANCE}')
        self.assertEqual(
            grown, [],
            f'Function(s) in the long_functions ledger have grown more than '
            f'{FUNC_GROWTH_ALLOWANCE} lines past their recorded size. Extract a helper for the '
            f'part you are adding rather than lengthening the body. Never raise the recorded '
            f'number.\n' + '\n'.join(grown))

    def test_a_listed_function_that_shrank_has_its_entry_lowered(self):
        stale = []
        for key, limit in sorted(self.budget['long_functions'].items()):
            now = self.scan['long_functions'].get(key)
            if now is None:
                stale.append(f'{key}: now under {LONG_FUNC_LINES} lines, renamed or gone — '
                             f'REMOVE this line from "long_functions" in budget')
            elif limit > now + FUNC_SHRINK_SLACK:
                stale.append(f'{key}: now {now} lines but recorded at {limit} — '
                             f'LOWER this line to {now}')
        self.assertEqual(
            stale, [],
            f'The long_functions budget is looser than the code. Edit "budget" in '
            f'{os.path.basename(BUDGET_PATH)} exactly as each line says.\n' + '\n'.join(stale))


class TestOneRuleOneHome(_Standard):
    """`_money` is seven functions with one name in one app. A money-format fix made in one copy is
    not made in the other six — and that is not hypothetical, it is why H7 exists. The standard:
    a module-level function name may not appear in three or more files of one Django app."""

    def test_no_unlisted_name_has_three_or_more_homes(self):
        new = []
        for key, count in sorted(self.scan['duplicated_names'].items()):
            if key not in self.budget['duplicated_names']:
                homes = ', '.join(self.scan['duplicated_homes'][key])
                new.append(f'{key} in {count} files: {homes}')
        self.assertEqual(
            new, [],
            f'Function name(s) defined at module level in {DUP_FILES}+ files of ONE app. That is '
            f'one rule with several homes, and a fix to one copy leaves the others wrong. GIVE '
            f'THE RULE ONE HOME: put it in a shared module and import it. If the two are genuinely '
            f'unrelated, rename one so the name stops claiming they are the same thing. Do NOT add '
            f'it to the ledger.\n' + '\n'.join(new))

    def test_a_listed_name_has_not_gained_a_home(self):
        grown = [f'{k}: now in {self.scan["duplicated_names"].get(k, 0)} files, recorded at {v}'
                 for k, v in sorted(self.budget['duplicated_names'].items())
                 if self.scan['duplicated_names'].get(k, 0) > v]
        self.assertEqual(
            grown, [],
            'Name(s) in the duplicated_names ledger have gained another home. The ledger records '
            'a rule that is ALREADY copied too many times; copying it once more is the thing it '
            'exists to stop. Import the existing one instead.\n' + '\n'.join(grown))

    def test_a_listed_name_that_lost_a_home_has_its_entry_lowered(self):
        stale = []
        for key, limit in sorted(self.budget['duplicated_names'].items()):
            now = self.scan['duplicated_names'].get(key)
            if now is None:
                stale.append(f'{key}: now in fewer than {DUP_FILES} files — '
                             f'REMOVE this line from "duplicated_names" in budget')
            elif limit > now:
                stale.append(f'{key}: now in {now} files but recorded at {limit} — '
                             f'LOWER this line to {now}')
        self.assertEqual(
            stale, [],
            f'The duplicated_names budget is looser than the code. Edit "budget" in '
            f'{os.path.basename(BUDGET_PATH)} exactly as each line says — otherwise the entry '
            f'quietly re-permits the copy H7 just removed.\n' + '\n'.join(stale))


class TestTestsCanFail(_Standard):
    """A skipped test is a test that cannot fail, sitting in a suite people read as green. Both
    golden masters used to skip themselves on the run straight after a regenerate — the least
    supervised moment in the whole process passed green. H1 removed them; this keeps them gone."""

    def test_there_are_no_skip_markers_in_the_test_suite(self):
        self.assertLessEqual(
            self.scan['counts']['skip_sites'], self.budget['counts']['skip_sites'],
            f'A `skip` / `skipif` / `xfail` marker, or a unittest skip decorator, found in the '
            f'test suite. A test that '
            f'cannot fail is not a test. DELETE it, or FIX what it was waiting for, or make it '
            f'assert the thing it is avoiding. Never raise this budget.\n'
            + '\n'.join(self.scan['skip_sites']))

    def test_no_new_file_declines_to_run_at_runtime(self):
        """`self.skipTest(...)` is NOT counted by `code_health.SKIP_PY`, and that treatment is
        followed here rather than contradicted. But it is still a test deciding not to run, so the
        eight that exist are written down and the list may only shrink. Each is honest — "the real
        corpus is not on this machine", "the web tree is not in an api-only checkout" — and each
        would hide a real failure if its condition ever became permanent."""
        new = sorted(f'{f} ({n} site(s))' for f, n in self.scan['runtime_skips'].items()
                     if f not in self.budget['runtime_skips'])
        self.assertEqual(
            new, [],
            'Test file(s) call `self.skipTest(...)` and are not in the runtime_skips ledger. A '
            'runtime skip passes green on a machine where the condition holds, which is how a '
            'drift ships. Make the test run everywhere — build the fixture it needs, or assert '
            'the absent case explicitly. Do NOT add the file to the ledger.\n' + '\n'.join(new))

    def test_a_listed_file_has_not_gained_a_runtime_skip(self):
        grown = [f'{k}: now {self.scan["runtime_skips"].get(k, 0)} site(s), recorded at {v}'
                 for k, v in sorted(self.budget['runtime_skips'].items())
                 if self.scan['runtime_skips'].get(k, 0) > v]
        self.assertEqual(
            grown, [],
            'File(s) in the runtime_skips ledger have gained another runtime skip. Write the test '
            'so it runs everywhere instead.\n' + '\n'.join(grown))

    def test_a_listed_file_that_lost_a_runtime_skip_has_its_entry_lowered(self):
        stale = []
        for key, limit in sorted(self.budget['runtime_skips'].items()):
            now = self.scan['runtime_skips'].get(key)
            if now is None:
                stale.append(f'{key}: no runtime skips left — '
                             f'REMOVE this line from "runtime_skips" in budget')
            elif limit > now:
                stale.append(f'{key}: now {now} site(s) but recorded at {limit} — '
                             f'LOWER this line to {now}')
        self.assertEqual(
            stale, [],
            f'The runtime_skips budget is looser than the code. Edit "budget" in '
            f'{os.path.basename(BUDGET_PATH)} exactly as each line says.\n' + '\n'.join(stale))


class TestNewTestsUseTheFactory(_Standard):
    """H5. A hand-built fixture can describe a state the product cannot produce.

    That is not a theory: on 2026-09-18 BrightPath request #24 came out of one. A fixture fed
    `status='rejected'` to a check whose live states never include it, so the test could never
    reach the branch it named and a real bug sat behind a green test. There are TWO roads to QC
    and they leave DIFFERENT marks — Recommend stamps `verified_at`, Decline stamps nothing —
    and a hand-built row gets that wrong silently.

    `apps/scholarship/tests/factories.py` knows the difference, and `test_factories.py` walks
    every stage through the real services and endpoints so the factory itself cannot drift. So
    the standard is: a test file NOT already in the ledger may not hand-build an application.
    The 134 files that do are written down and may only ever shrink — the other ~200 convert
    when they are next touched (`small-change-lane.md`), not in a big-bang rewrite."""

    def test_the_fixture_exclusion_is_exactly_the_factory_and_its_test(self):
        """The hole is two files wide and must stay two files wide. A third name here would be
        a file quietly permitted to build unreachable states again."""
        self.assertEqual(
            self.scan['excused_from_the_fixture_ledger'], sorted(FACTORY_FILES),
            'The hand-built-fixture scan is excusing a file other than the factory and its '
            'drift test. Only those two may build a ScholarshipApplication by hand — the '
            'factory because it IS the builder, its test because it proves the builder matches '
            'the product. Remove the other excuse and use `make_application` in that file.')

    def test_no_unlisted_test_file_hand_builds_an_application(self):
        new = sorted(f'{n} call(s)  {f}'
                     for f, n in self.scan['hand_built_application_fixtures'].items()
                     if f not in self.budget['hand_built_application_fixtures'])
        self.assertEqual(
            new, [],
            'Test file(s) call `ScholarshipApplication.objects.create(` and are not in the '
            'hand_built_application_fixtures ledger. A hand-built fixture can describe a state '
            'the product cannot reach, and then the test passes for ever while testing nothing '
            '(BrightPath #24). Use `make_application` from '
            '`apps/scholarship/tests/factories.py`; if the state truly cannot be expressed, '
            'extend the factory — and add the stage to `test_factories.py` so it is walked '
            'through the real code. Do NOT add the file to the ledger.\n' + '\n'.join(new))

    def test_a_listed_file_has_not_gained_a_hand_built_fixture(self):
        grown = [
            f'{k}: now {self.scan["hand_built_application_fixtures"].get(k, 0)} call(s), '
            f'recorded at {v}'
            for k, v in sorted(self.budget['hand_built_application_fixtures'].items())
            if self.scan['hand_built_application_fixtures'].get(k, 0) > v]
        self.assertEqual(
            grown, [],
            'File(s) in the hand_built_application_fixtures ledger have gained another '
            'hand-built application. The ledger records fixtures that are ALREADY waiting to '
            'be converted; adding one more is the thing it exists to stop. Use '
            '`make_application` from `apps/scholarship/tests/factories.py` for the new '
            'fixture.\n' + '\n'.join(grown))

    def test_a_listed_file_that_converted_has_its_entry_lowered(self):
        """Tightness. A count left sitting above reality re-permits the fixtures the conversion
        just removed, so the entry must follow the file down."""
        stale = []
        for path, limit in sorted(self.budget['hand_built_application_fixtures'].items()):
            now = self.scan['hand_built_application_fixtures'].get(path, 0)
            if now == 0:
                stale.append(f'{path}: no hand-built applications left — REMOVE this line '
                             f'from "hand_built_application_fixtures" in budget')
            elif limit > now:
                stale.append(f'{path}: now {now} call(s) but recorded at {limit} — '
                             f'LOWER this line to {now}')
        self.assertEqual(
            stale, [],
            f'The hand_built_application_fixtures budget is looser than the code. Edit "budget" '
            f'in {os.path.basename(BUDGET_PATH)} exactly as each line says. This is the ratchet '
            f'catching up with your conversion, not a complaint about it.\n' + '\n'.join(stale))


class TestNoNewBlindSpots(_Standard):
    """Every `# noqa` and every `# type: ignore` is a place a gate was told to look away. Most of
    the 80 here are deliberate — the broad `except` that stops a mirror ever breaking a write — and
    H4 does not relitigate them. It stops the count rising, so the next one is a decision somebody
    makes on purpose rather than a habit."""

    def test_the_noqa_count_has_not_risen(self):
        self._count('noqa', '`# noqa`',
                    'Fix what the linter is objecting to, or narrow the exception it hides.')

    def test_the_type_ignore_count_has_not_risen(self):
        self._count('type_ignore', '`# type: ignore`',
                    'Type the value properly, or narrow the ignore to the one line that needs it.')

    def _count(self, key, label, advice):
        now, limit = self.scan['counts'][key], self.budget['counts'][key]
        self.assertLessEqual(
            now, limit,
            f'{label} count is {now}; the budget is {limit}. A suppression is a gate told to look '
            f'away, and the count may not rise. {advice} Never raise this budget.')


class TestTheAppBoundary(_Standard):
    """`scholarship -> courses` is 104 imports and `courses -> scholarship` is 25: the back-edge.
    Two apps that import each other are one app with a line drawn through it, and the import-time
    half of that edge is what turns into a circular-import failure at start-up. Neither number may
    rise; the module-level one is the one that matters."""

    def test_the_back_edge_has_not_grown(self):
        now = self.scan['counts']['courses_to_scholarship_imports']
        limit = self.budget['counts']['courses_to_scholarship_imports']
        self.assertLessEqual(
            now, limit,
            f'`apps/courses` now imports `apps.scholarship` {now} times; the budget is {limit}. '
            f'The back-edge may not grow. Move the shared thing into a module both apps may '
            f'import, or have scholarship CALL courses rather than courses reach into '
            f'scholarship. Never raise this budget.\n'
            + '\n'.join(self.scan['courses_to_scholarship']))

    def test_the_module_level_back_edge_has_not_grown(self):
        now = self.scan['counts']['courses_to_scholarship_module_level_imports']
        limit = self.budget['counts']['courses_to_scholarship_module_level_imports']
        self.assertLessEqual(
            now, limit,
            f'`apps/courses` now imports `apps.scholarship` at MODULE level {now} times; the '
            f'budget is {limit}. A module-level back-edge runs at import time and is how a '
            f'circular import takes the whole service down at start-up. Move the import INSIDE '
            f'the function that needs it. Never raise this budget.\n'
            + '\n'.join(self.scan['courses_to_scholarship_module_level']))


class TestTheRatchetItself(_Standard):
    """The budget file may only ever get tighter, and the baseline may not be rewritten quietly.

    Without these four tests the standards above are decorative: anything they refuse could be
    permitted by editing one number in a JSON file, in the same commit, with nobody the wiser."""

    def test_no_budget_number_is_above_the_baseline(self):
        raised = [f'counts.{k}: budget {v}, baseline {self.baseline["counts"][k]}'
                  for k, v in sorted(self.budget['counts'].items())
                  if v > self.baseline['counts'].get(k, v)]
        for ledger in LEDGERS:
            base = self.effective[ledger]
            raised += [f'{ledger}["{k}"]: budget {v}, baseline {base[k]}'
                       for k, v in sorted(self.budget[ledger].items())
                       if k in base and v > base[k]]
        self.assertEqual(
            raised, [],
            'A limit in "budget" has been raised above the frozen "baseline". A budget may only '
            'go DOWN. If the code genuinely needs more room, it needs a smaller change instead — '
            'split the file, extract the function, give the rule one home. ⚠ A key that arrived '
            'through a declared move inherits the room of the entry it replaced and not a line '
            'more — a move may not buy anything.\n' + '\n'.join(raised))

    def test_no_ledger_has_gained_a_member(self):
        """⚠ Measured against the EFFECTIVE baseline — the frozen record read through `_moved`
        (RULE 5). A key that a declared move relabelled is not a gain; a key that no move accounts
        for still is, and still fails here."""
        added = []
        for ledger in LEDGERS:
            base = self.effective[ledger]
            added += [f'{ledger}: "{k}" is in budget but not in baseline'
                      for k in sorted(self.budget[ledger]) if k not in base]
        self.assertEqual(
            added, [],
            'An exemption list has gained a member. A ledger records what H4 found on 2026-09-19 '
            'and can only ever shrink — adding to it is how a list of known debts turns into a '
            'list of permissions. Fix the code instead: split the file, extract the function, '
            'give the rule one home, delete the skip. ⚠ If the code MOVED and this is the same '
            'debt at a new path, do not add the key: DECLARE THE MOVE in the "_moved" array of '
            'code-standards.json ({"on", "why", "ledger", "from", "to"}), which relabels the '
            'frozen entry and grants exactly the room it already had. See RULE 5 at the top of '
            'this file.\n' + '\n'.join(added))

    def test_no_budget_counter_sits_loose_above_the_code(self):
        """Tightness for the plain numbers. When a count improves, its budget must follow, or the
        headroom quietly re-permits the thing that was just removed."""
        loose = []
        for key, limit in sorted(self.budget['counts'].items()):
            now = self.scan['counts'][key]
            if limit > now + COUNT_SLACK[key]:
                loose.append(f'counts.{key}: budget {limit}, code {now} — LOWER it to {now}')
        self.assertEqual(
            loose, [],
            f'A budget number sits loose above the code. Edit "budget" in '
            f'{os.path.basename(BUDGET_PATH)} exactly as each line says. This is the ratchet '
            f'catching up with your improvement.\n' + '\n'.join(loose))

    def test_the_baseline_block_has_not_been_rewritten(self):
        """⚠ RULE 5 DOES NOT TOUCH THIS. `_moved` is a sibling of `baseline`, not a part of it, so
        an honest move leaves this hash exactly where it is. If this is failing, someone edited
        the frozen record itself — which is still the thing rule 4 refuses."""
        now = hashlib.sha256(canonical(self.baseline)).hexdigest()
        self.assertEqual(
            now, BASELINE_SHA256,
            f'The frozen "baseline" block in {os.path.basename(BUDGET_PATH)} has changed. The '
            f'baseline is the record of what H4 found on 2026-09-19 and is not maintained — the '
            f'thing you lower is "budget". If this change really is intended (a whole file was '
            f'deleted, say), say so in the sprint retro and set BASELINE_SHA256 in this test file '
            f'to {now} in the SAME commit, so a reviewer sees both halves.')


class TestADeclaredMoveBuysNothing(_Standard):
    """RULE 5, asserted against the real file. TD-272.

    A ledger key may follow its code to a new path, and that is ALL it may do. These three tests
    are what make the relabel safe enough to allow at all: the first refuses a move that is not an
    honest relabel, the second proves the relabelling itself cannot enlarge a ledger however the
    code above is later edited, and the third stops `_moved` turning into a junk drawer of records
    that describe nothing."""

    def test_every_declared_move_is_an_honest_relabel(self):
        self.assertEqual(
            self.move_problems, [],
            f'A record in the "_moved" array of {os.path.basename(BUDGET_PATH)} is not an honest '
            f'relabel. A move declares that ONE key already in the frozen ledger is now spelt as '
            f'ONE key the ledger does not have — nothing else. It may not raise a number, add a '
            f'member, merge two entries, or name a file that is not in the tree. Each line below '
            f'says which record and what to do.\n' + '\n'.join(self.move_problems))

    def test_a_move_changes_no_ledger_s_length_or_total(self):
        """THE INVARIANT THE WHOLE MECHANISM RESTS ON, asserted rather than argued. A relabel pops
        one key and inserts one, so both numbers must be identical either side. If a future edit
        to `effective_baseline` ever made a move generous, this is what catches it — long before
        anyone notices the budget quietly had more room than the frozen record gave it."""
        grew = []
        for ledger in LEDGERS:
            frozen, now = self.baseline[ledger], self.effective[ledger]
            if len(now) != len(frozen):
                grew.append(f'{ledger}: {len(frozen)} entries frozen, {len(now)} after the '
                            f'declared moves — a move may only RELABEL')
            if sum(now.values()) != sum(frozen.values()):
                grew.append(f'{ledger}: total {sum(frozen.values())} frozen, '
                            f'{sum(now.values())} after the declared moves')
        self.assertEqual(
            grew, [],
            'Applying the declared moves changed the SIZE of a frozen ledger. It must not: a move '
            'relabels one entry onto one new key, so the count and the total are the same numbers '
            'either side. Something in `effective_baseline` is doing more than relabelling.\n'
            + '\n'.join(grew))

    def test_every_declared_move_is_still_doing_a_job(self):
        """A move record exists to let a key sit in `budget`. When that key leaves `budget` — the
        debt was fixed, or the file fell under the limit and the tightness test removed the line —
        the record describes nothing, and a list of records describing nothing is the rot this
        whole file exists against. Prune it; the history lives in `_history` and the CHANGELOG."""
        stale = []
        for i, move in enumerate(self.moves):
            if not (isinstance(move, dict) and move.get('ledger') in LEDGERS
                    and isinstance(move.get('to'), str)):
                continue                       # already named by the honest-relabel test above
            if move['to'] not in self.effective[move['ledger']]:
                continue                       # the move was refused, so it relabelled nothing
            if move['to'] not in self.budget[move['ledger']]:
                stale.append(f'_moved[{i}]: "{move["to"]}" is no longer in '
                             f'budget.{move["ledger"]} — REMOVE this move record')
        self.assertEqual(
            stale, [],
            f'A record in "_moved" points at a budget line that is gone. The debt it followed has '
            f'been paid, so the relabel has nothing left to do. Delete the record from '
            f'{os.path.basename(BUDGET_PATH)}; the story of the move belongs in "_history" and '
            f'the CHANGELOG, not in a live lens over the frozen record.\n' + '\n'.join(stale))


# ── The ratchet's own arithmetic, proven on a throwaway budget ──────────────────────────────
#
# The tests above can only exercise the ratchet against the REAL tree, where every rule happens
# to pass. These prove the comparisons themselves fire, without needing anyone to break the repo.

class TestTheRatchetArithmetic(SimpleTestCase):
    """`_Standard` reads the live scan; this one feeds the same comparisons made-up numbers."""

    def test_a_raised_number_is_detected(self):
        self.assertTrue(81 > 80, 'a budget above its baseline must compare as raised')
        self.assertFalse(79 > 80)

    def test_a_gained_ledger_member_is_detected(self):
        baseline = {'a.py': 700}
        budget = {'a.py': 700, 'b.py': 900}
        self.assertEqual([k for k in budget if k not in baseline], ['b.py'])

    def test_the_growth_allowance_is_a_ceiling_not_a_licence(self):
        """A file recorded at 700 may reach 720 and no further, whatever the history."""
        self.assertFalse(720 > 700 + FILE_GROWTH_ALLOWANCE)
        self.assertTrue(721 > 700 + FILE_GROWTH_ALLOWANCE)

    def test_tightness_fires_only_past_the_slack(self):
        self.assertFalse(700 > 660 + FILE_SHRINK_SLACK, 'a 40-line shrink must not nag')
        self.assertTrue(700 > 640 + FILE_SHRINK_SLACK, 'a 60-line shrink must demand a lower entry')

    def test_the_canonical_form_ignores_key_order_and_whitespace(self):
        a = canonical({'b': 1, 'a': {'d': 2, 'c': 3}})
        b = canonical(json.loads('{ "a" : { "c" : 3 , "d" : 2 } , "b" : 1 }'))
        self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())
        self.assertNotEqual(hashlib.sha256(a).hexdigest(),
                            hashlib.sha256(canonical({'b': 2, 'a': {'d': 2, 'c': 3}})).hexdigest())


class TestTheMoveArithmetic(SimpleTestCase):
    """RULE 5's own rules, proven on a throwaway ledger — both directions, each named.

    `TestADeclaredMoveBuysNothing` can only exercise the real file, where every move happens to be
    honest. These feed `effective_baseline` the dishonest shapes and prove each one is refused,
    without anyone having to break the repo. The tree check is injected, so nothing here touches
    the disk."""
    maxDiff = None

    #: Two files and one long function. `exists` below says yes to exactly these three names.
    REAL = {'a.py', 'a/__init__.py', 'b.py', 'c.py'}

    def base(self):
        return {'oversize_files': {'a.py': 900, 'b.py': 700},
                'long_functions': {'a.py::big': 200},
                'duplicated_names': {'scholarship::_money': 7},
                'runtime_skips': {}, 'hand_built_application_fixtures': {}}

    def move(self, **kw):
        row = {'on': '2026-09-20', 'ledger': 'oversize_files',
               'why': 'the body moved to its own module beside it',
               'from': 'a.py', 'to': 'a/__init__.py'}
        row.update(kw)
        return row

    def apply(self, *moves):
        return effective_baseline(self.base(), list(moves), exists=lambda p: p in self.REAL)

    # ── the one shape that passes ────────────────────────────────────────────────────────────
    def test_a_move_relabels_the_entry_and_nothing_else(self):
        effective, problems = self.apply(self.move())
        self.assertEqual(problems, [])
        self.assertEqual(effective['oversize_files'], {'a/__init__.py': 900, 'b.py': 700},
                         'the moved entry keeps its frozen number at the new key')
        self.assertEqual(effective['long_functions'], {'a.py::big': 200},
                         'a move in one ledger leaves every other ledger alone')

    def test_a_relabel_holds_the_length_and_the_total(self):
        effective, _ = self.apply(self.move())
        before, after = self.base()['oversize_files'], effective['oversize_files']
        self.assertEqual(len(after), len(before))
        self.assertEqual(sum(after.values()), sum(before.values()))

    def test_two_moves_may_chain_through_the_same_key(self):
        """A file moved twice (H11's package, then H12's emptying) is two records, not a rewrite."""
        effective, problems = self.apply(
            self.move(), self.move(**{'from': 'a/__init__.py', 'to': 'c.py'}))
        self.assertEqual(problems, [])
        self.assertEqual(effective['oversize_files'], {'c.py': 900, 'b.py': 700})

    def test_a_long_function_key_is_moved_on_its_path_half(self):
        effective, problems = self.apply(
            self.move(ledger='long_functions', **{'from': 'a.py::big', 'to': 'c.py::big'}))
        self.assertEqual(problems, [])
        self.assertEqual(effective['long_functions'], {'c.py::big': 200})

    def test_a_name_ledger_needs_no_file_because_its_key_is_not_a_path(self):
        effective, problems = self.apply(self.move(
            ledger='duplicated_names',
            **{'from': 'scholarship::_money', 'to': 'scholarship::format_ringgit'}))
        self.assertEqual(problems, [])
        self.assertEqual(effective['duplicated_names'], {'scholarship::format_ringgit': 7})

    # ── and the shapes that must not ─────────────────────────────────────────────────────────
    def test_a_move_onto_a_key_the_ledger_already_holds_is_refused(self):
        """The merge. Two entries on one key would give the survivor the room of both."""
        effective, problems = self.apply(self.move(**{'to': 'b.py'}))
        self.assertTrue(problems and 'ALREADY holds' in problems[0], problems)
        self.assertEqual(effective['oversize_files'], self.base()['oversize_files'],
                         'a refused move must relabel nothing at all')

    def test_a_move_from_a_key_the_ledger_does_not_hold_is_refused(self):
        """The invention. Nothing left, so nothing was renamed — debt cannot arrive this way."""
        effective, problems = self.apply(self.move(**{'from': 'c.py'}))
        self.assertTrue(problems and 'does not hold' in problems[0], problems)
        self.assertEqual(effective['oversize_files'], self.base()['oversize_files'])

    def test_a_move_onto_a_file_that_is_not_in_the_tree_is_refused(self):
        effective, problems = self.apply(self.move(**{'to': 'nowhere/at/all.py'}))
        self.assertTrue(problems and 'not in the tree' in problems[0], problems)
        self.assertEqual(effective['oversize_files'], self.base()['oversize_files'])

    def test_a_move_with_a_shrug_for_a_reason_is_refused(self):
        _, problems = self.apply(self.move(why='moved'))
        self.assertTrue(problems and 'at least' in problems[0], problems)

    def test_a_move_naming_a_ledger_that_does_not_exist_is_refused(self):
        _, problems = self.apply(self.move(ledger='oversize_filez'))
        self.assertTrue(problems and 'not one of' in problems[0], problems)

    def test_a_move_missing_a_field_is_refused(self):
        row = self.move()
        del row['on']
        _, problems = self.apply(row)
        self.assertTrue(problems and 'missing or empty' in problems[0], problems)

    def test_a_move_that_is_not_an_object_is_refused(self):
        _, problems = self.apply('a.py -> a/__init__.py')
        self.assertTrue(problems and 'must be an object' in problems[0], problems)

    def test_no_declared_moves_leaves_the_frozen_record_exactly_as_it_is(self):
        effective, problems = self.apply()
        self.assertEqual(problems, [])
        self.assertEqual(effective, self.base())
