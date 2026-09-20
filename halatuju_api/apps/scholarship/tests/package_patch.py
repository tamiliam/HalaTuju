"""PATCHING A NAME THAT LIVES IN A PACKAGE (code health H16, 2026-09-20).

**The shape this file exists to kill.** A test writes
``mock.patch('apps.scholarship.income_engine.member_cluster_complete', ...)``. That worked for
years, because `income_engine` was one module and every caller looked the name up in that one
namespace. Then the module became a package: the function now lives in `income_engine.evidence`,
its callers inside the package hold their own reference to it, and the patch rebinds an attribute
of a re-export shell that nothing calls. **The real function still runs.** Sometimes that is a
loud failure; sometimes the test simply stops testing what it says it tests.

There are three ways a name in a package gets looked up, and a patch has to cover all three:

  1. through the package  — ``income_engine.member_cluster_complete(...)``, as `resolution.py`
     and `services/blockers.py` do. Patching the shell is enough for these.
  2. from a sibling       — ``from .evidence import member_cluster_complete`` at the top of
     another module. That module's own global is what its functions read.
  3. in its own home      — the module that defines it, where its neighbours read it directly.

`patch_engine` patches ONE shared mock into all three, so a single ``with`` restores exactly the
semantics the old one-module patch had: *this name, wherever it is looked up*.

⚠ It asserts it patched at least one scope. A name nobody holds any more is a MOVE nobody
followed, and this says so rather than handing back a context manager that does nothing.
"""
import contextlib
import types
from unittest import mock


def _scopes(package):
    """The package itself, plus every submodule of it that is already imported."""
    prefix = package.__name__ + '.'
    out = [package]
    for value in vars(package).values():
        if (isinstance(value, types.ModuleType)
                and getattr(value, '__name__', '').startswith(prefix)
                and value not in out):
            out.append(value)
    return out


@contextlib.contextmanager
def patch_engine(package, name, **kwargs):
    """Patch `name` with one shared mock in every scope of `package` that holds it.

    `kwargs` are `MagicMock`'s — `return_value=`, `side_effect=` — so a call site reads the same
    as the `mock.patch` it replaces. Yields the shared mock, so `assert_called_once()` still means
    *called once in total*, whichever scope did the calling.
    """
    shared = mock.MagicMock(**kwargs)
    holders = [s for s in _scopes(package) if name in vars(s)]
    assert holders, (
        f'nothing in `{package.__name__}` holds {name!r} any more.\n'
        '  The name MOVED, or was renamed, or the module that reads it is not imported yet.\n'
        '  Follow it and re-point this patch — never delete it. An income-engine name that is '
        'not patched means the REAL rule ran and this test asserted nothing about the case it '
        'was written for.')
    with contextlib.ExitStack() as stack:
        for scope in holders:
            stack.enter_context(mock.patch.object(scope, name, shared))
        yield shared
