"""The pinned clock (design 3.6): old and new both run at ONE instant, the snapshot time.

`pinned_clock(instant)` patches, for the length of the block:
  * `django.utils.timezone.now` (so `timezone.now()`, `localdate()` and `localtime()` all read it);
  * in every LOADED module under ``prefixes``: a module-level `now` bound from django, a `date` /
    `datetime` class imported from `datetime`, and a module-level `datetime` MODULE (for
    `datetime.date.today()`), each swapped for a pinned twin.
Engines import lazily inside functions, so `preload` imports every module under the packages FIRST.
The pinned classes still answer `isinstance` for real dates (`_PinnedMeta`), so no engine branch moves.
Not pinned: the database's own `now()` (each transaction's start) and `time.time()`. A leak shows up as
noise (N) in the new-against-new-again control, which is what that control is for.
"""
import contextlib
import datetime as _dt
import importlib
import pkgutil
import sys
import types
from unittest import mock

_REAL_DATE, _REAL_DATETIME = _dt.date, _dt.datetime
_STATE = {'instant': None}
SKIP_PARTS = ('tests', 'migrations', 'eval', 'management', 'admin')


def _instant():
    v = _STATE['instant']
    if v is None:
        raise RuntimeError('replay: the clock is not pinned')
    return v


class _PinnedMeta(type):
    def __instancecheck__(cls, obj):
        return isinstance(obj, cls._real)

    def __subclasscheck__(cls, sub):
        return issubclass(sub, cls._real)


class PinnedDate(_REAL_DATE, metaclass=_PinnedMeta):
    _real = _REAL_DATE

    @classmethod
    def today(cls):
        return _instant().astimezone().date()


class PinnedDateTime(_REAL_DATETIME, metaclass=_PinnedMeta):
    _real = _REAL_DATETIME

    @classmethod
    def now(cls, tz=None):
        return _instant().astimezone(tz) if tz else _instant().astimezone().replace(tzinfo=None)

    @classmethod
    def today(cls):
        return cls.now()

    @classmethod
    def utcnow(cls):
        return _instant().astimezone(_dt.timezone.utc).replace(tzinfo=None)


def _datetime_module_twin():
    twin = types.ModuleType('datetime')
    twin.__dict__.update({k: v for k, v in vars(_dt).items() if not k.startswith('__')})
    twin.date, twin.datetime = PinnedDate, PinnedDateTime
    return twin


def pinned_now():
    return _instant()


def preload(packages=('apps',)):
    """Import every module under ``packages`` (tests, migrations, eval, management and admin skipped).
    Returns the names that failed to import (old tree gaps), by name only."""
    failed = []
    for pkg_name in packages:
        pkg = importlib.import_module(pkg_name)
        for info in pkgutil.walk_packages(pkg.__path__, pkg_name + '.'):
            if any(part in SKIP_PARTS for part in info.name.split('.')):
                continue
            try:
                importlib.import_module(info.name)
            except Exception:
                failed.append(info.name)
    return failed


@contextlib.contextmanager
def pinned_clock(instant, prefixes=('apps.',)):
    """Every clock the engines read answers ``instant`` (an aware datetime) inside the block."""
    if instant is None or instant.tzinfo is None:
        raise ValueError('replay: the pinned instant must be timezone-aware')
    from django.utils import timezone as dj_tz
    # Swaps are decided against LOCAL references, and the harness's own package is never patched (it
    # would otherwise rebind this module's `_REAL_*` names halfway through the loop).
    swaps = {id(dj_tz.now): pinned_now, id(_REAL_DATE): PinnedDate, id(_REAL_DATETIME): PinnedDateTime,
             id(_dt): _datetime_module_twin()}
    originals = (dj_tz.now, _REAL_DATE, _REAL_DATETIME, _dt)        # keep the ids alive and unique
    own = __package__ or __name__.rpartition('.')[0]
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(dj_tz, 'now', pinned_now))
        for name, mod in list(sys.modules.items()):
            if mod is None or not name.startswith(tuple(prefixes)) or name.startswith(own):
                continue
            for attr, value in list(vars(mod).items()):
                if any(value is o for o in originals):
                    stack.enter_context(mock.patch.object(mod, attr, swaps[id(value)]))
        _STATE['instant'] = instant
        try:
            yield instant
        finally:
            _STATE['instant'] = None
