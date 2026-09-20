"""EVERY GUARD THAT READS THE TREE MUST HAVE A FLOOR (TD-276, code health H16, 2026-09-20).

**The shape this file exists to kill.** A guard walks the tree, finds N things, asserts something
about each one. Then the code moves — a module becomes a package, a folder is renamed, a glob
stops matching — and the walk finds ZERO things. Every assertion is now vacuous and the guard goes
on passing. Nothing goes red, nothing appears in a failure list, and the rule the guard was
written to hold is simply gone.

This arc has met that failure four times and every time it was SILENT:

1. `officerGateDrift.test.ts` read `views_admin.py` by path; H11 made it a package and the whole
   suite died at import — thirteen tests gone, unnoticed for two sprints.
2. `test_verdict_item_i18n.py` used `glob` where a package needed `rglob`; it would have stopped
   scanning inside `models/` and `services/` and stayed green.
3. `AuditLoggerNameTest` was hard-coded to one package, so a moved module could take a new logger
   name with nothing going red. That bite came back SILENT at H15.
4. `test_wallet_credit.py` allowlisted by bare filename, so the exemption widened as the tree grew.

**A guard that can pass while seeing nothing is not a guard.**

So: read a path through `read_source`, and walk a tree through `walk_sources`. Both fail LOUDLY —
naming the path, the number they expected and the reason it was written — instead of quietly
handing back nothing.

⚠ A FLOOR IS A MINIMUM, NOT AN EQUALITY. It is the count the walk found on the day it was written,
usually rounded down a little. Adding a legitimate new file must leave the guard GREEN, or the
next engineer learns to edit the number without reading it, and a floor nobody believes is worse
than none. A guard that genuinely needs a CLOSED set — one extra file is itself the defect —
asserts that equality itself, beside the reason it is closed; it does not get a flag here, because
a flag would let the choice be made without writing the reason down.

**Raising, not asserting.** These raise `AssertionError` at the point of the read, so a guard that
collects its corpus at module scope fails during collection with a message a human can act on,
rather than an `ENOENT`/`FileNotFoundError` traceback into a stdlib frame. Never convert one of
these into a `skipTest`: a skipped drift test is how the 64-subject drift shipped
(`test_subject_drift.py`).
"""
import pathlib

#: `halatuju_api/` — three levels up from `apps/scholarship/tests/`.
API_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: The repository root, the parent of both `halatuju_api/` and `halatuju-web/`.
REPO_ROOT = API_ROOT.parent

#: Directories no source guard ever wants to read. Kept here so one walk cannot quietly
#: disagree with another about what counts as source.
SKIP_PARTS = ('__pycache__', 'node_modules', '.next', '.git', 'migrations')


def _relative(path):
    """`path` as a repo-relative POSIX string, so a message reads the same on every platform."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:                       # pragma: no cover — a path outside the repo
        return str(path)


def read_source(path, why):
    """The text at `path`, or a loud AssertionError naming the path and why it is read.

    `why` is a sentence for the engineer who breaks this: what the guard is holding and where to
    look for the code that moved. "The rule it guards has MOVED — follow it, never delete the
    assertion" is the tone; a bare `FileNotFoundError` is what this replaces.
    """
    path = pathlib.Path(path)
    if not path.is_file():
        raise AssertionError(
            f'SOURCE GUARD: {_relative(path)} is not there.\n'
            f'  This guard reads it because: {why}\n'
            '  The code it watches has MOVED or been renamed. Follow it and re-point this path - '
            'never delete the assertion, and never convert this into a skip.')
    return path.read_text(encoding='utf-8')


def walk_sources(root, pattern, floor, why, skip_parts=SKIP_PARTS):
    """Every file under `root` matching `pattern`, sorted — with a FLOOR under the count.

    Recursive by `rglob`, because a directory becomes a package the day someone splits a long
    module, and a top-level `glob` would then read the package's `__init__.py` and nothing else
    (bite 2 above).

    `floor` is the number the walk found when the floor was written. Fewer than that and this
    raises, naming the shortfall, the root and `why` — so a walk that has silently narrowed says
    what moved rather than asserting nothing. More than that is fine and deliberately so: a floor
    is a minimum, so adding a file the walk legitimately finds leaves the guard green. A guard
    that needs a CLOSED set asserts that equality itself, beside the reason it is closed.
    """
    root = pathlib.Path(root)
    if not root.is_dir():
        raise AssertionError(
            f'SOURCE GUARD: {_relative(root)} is not a directory.\n'
            f'  This guard walks it because: {why}\n'
            '  The tree it watches has MOVED or been renamed. Follow it and re-point this walk - '
            'never delete the assertion, and never convert this into a skip.')
    found = sorted(
        p for p in root.rglob(pattern)
        if p.is_file() and not any(part in skip_parts for part in p.parts))
    if len(found) < floor:
        raise AssertionError(
            f'THE FLOOR: walking {_relative(root)} for {pattern!r} found only {len(found)} '
            f'file(s); this guard expects at least {floor}.\n'
            f'  It walks that tree because: {why}\n'
            '  Either the tree MOVED (follow it and re-point this walk) or the pattern stopped '
            'matching. Check before lowering the floor - a walk that finds nothing asserts '
            'nothing and passes for ever, which is the whole reason this number is here.')
    return found


def floor_count(found, floor, what, why):
    """The same floor, for a corpus a guard assembled itself (a scan's results, a parse's output).

    `walk_sources` floors the FILES; this floors the THINGS, which is the other half of the shape:
    a walk can still read every file and find none of what it came for, because the marker it
    greps was renamed.
    """
    if len(found) < floor:
        raise AssertionError(
            f'THE FLOOR: the scan found only {len(found)} {what}; this guard expects at least '
            f'{floor}.\n'
            f'  It scans for them because: {why}\n'
            '  Either the marker it greps was RENAMED or the corpus narrowed. Check before '
            'lowering the floor - a scan that finds nothing asserts nothing.')
    return found
