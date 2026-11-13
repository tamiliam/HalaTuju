"""The output scrubber: the LAST layer before anything is printed (design 3.2, 4.1).

Only these leave the job as written: KNOWN CODES, amounts, hashes, ids (and yes / no / nothing). A code
is known only when it is in the registry: `R1_CODES` (what the harness itself emits) plus what the R2
adapters add with `register_codes` when their module is imported (engine_map imports them, so the parent
and every child share one registry). Shape alone never makes a code: `siti`, `ahmad.bin.ali` and
`A12345678` all look like codes.

Any other string leaves as a KEYED hash `!h:<12 hex>` (HMAC with the run's secret salt, never printed),
so old and new can still be compared without the text; any other value leaves as `DROPPED`. Both are
counted by `count_dropped` (any one is a finding: the R2 normaliser must hash free text with `text_hash`
BEFORE it gets here). A dict key that is not a known code is dropped with its value.

An error leaves as an exception CLASS NAME only (`error_record`), never its message or traceback: the
`error` key is honoured only in an error record (keys within `error`, `event`, `side`, `engine`) and only
for the name of a loaded exception class; anywhere else its value is hashed like any other text.

What leaves as written:
  * None, True, False;
  * an int below 10**8 (an id or a count; an IC or a phone number held as a number is longer);
  * a Decimal / float, written as a 2-decimal amount;
  * a string that is: a known code; a hash `h:<8-16 hex>` or `!h:<12 hex>`; an amount `-?\\d+.\\d\\d`;
    a month `YYYY-MM`; a commit hash (7-40 hex with at least one letter AND one digit).
"""
import hashlib
import hmac
import math
import os
import re
import secrets
from decimal import Decimal, InvalidOperation

DROPPED = '!dropped'
MAX_INT = 10 ** 8
SCRUB_HASH_PREFIX = '!h:'
#: The parent sets this in each child's environment so all three sides hash alike. Never printed.
SALT_ENV = 'REPLAY_SCRUB_SALT'

_HASH = re.compile(r'^h:[0-9a-f]{8,16}$')
_SCRUB_HASH = re.compile(r'^!h:[0-9a-f]{12}$')
_AMOUNT = re.compile(r'^-?\d{1,8}\.\d{2}$')
_MONTH = re.compile(r'^20\d{2}-(0[1-9]|1[0-2])$')
_COMMIT = re.compile(r'^(?=[0-9]*[a-f])(?=[a-f]*[0-9])[0-9a-f]{7,40}$')
#: What `register_codes` accepts: one token, no spaces, at most 64 characters.
_CODE_SHAPE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_:./-]{0,63}$')
#: Keys an error record (or a fatal event) may carry beside `error`.
_ERROR_RECORD_KEYS = frozenset({'error', 'event', 'side', 'engine'})

#: Every code the R1 harness itself emits: event names, sides, outcomes, join states and keys.
R1_CODES = frozenset({
    # keys
    'event', 'side', 'engine', 'key', 'record', 'outcome', 'fields', 'old', 'new', 'new_again', 'error',
    'records', 'exit', 'dropped', 'fatal', 'cases', 'months', 'snapshot_joined', 'old_commit', 'new_commit',
    'failed_modules', 'applications', 'documents_live', 'payable', 'profiles_spm', 'profiles_stpm',
    'sponsors', 'value', 'could_not_run', 'same', 'differs', 'noise',
    # values: events, outcomes, join states
    'start', 'counts', 'joins', 'joined', 'exited', 'timed_out', 'done', 'preload', 'totals', 'no_output',
    'unknown', 'Missing',
})
_REGISTERED = set()


def register_codes(codes):
    """Add ``codes`` (an R2 adapter's statuses, field names, engine names) to the registry. Each must be
    a single token (`_CODE_SHAPE`); anything else raises ValueError, so free text cannot be registered."""
    codes = list(codes)
    bad = [c for c in codes if not isinstance(c, str) or not _CODE_SHAPE.match(c)]
    if bad:
        raise ValueError(f'replay: {len(bad)} value(s) are not codes')
    _REGISTERED.update(codes)


def is_code(s):
    return isinstance(s, str) and (s in R1_CODES or s in _REGISTERED)


_STATE = {'salt': None, 'errors': frozenset()}


def _salt():
    if _STATE['salt'] is None:
        given = os.environ.get(SALT_ENV, '')
        _STATE['salt'] = given if len(given) >= 32 else secrets.token_hex(16)
    return _STATE['salt'].encode('ascii')


def new_salt():
    """A fresh run salt (the parent's): used here and returned for the children's environment."""
    _STATE['salt'] = secrets.token_hex(16)
    return _STATE['salt']


def _keyed(s):
    return hmac.new(_salt(), s.encode('utf-8'), hashlib.sha256).hexdigest()[:12]


def text_hash(value):
    """A short hash for free text (the normaliser's tool; R2), keyed with the run's salt, so it is stable
    within one run and cannot be reversed by hashing guesses. Upper-cased and trimmed first."""
    return 'h:' + _keyed(str(value if value is not None else '').strip().upper())


def amount(value):
    """A 2-decimal amount string, or DROPPED when it is not a finite number."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return DROPPED
    if not d.is_finite():
        return DROPPED
    return str(d.quantize(Decimal('0.01')))


def _passes_as_written(s):
    return bool(is_code(s) or _HASH.match(s) or _SCRUB_HASH.match(s) or _AMOUNT.match(s) or _MONTH.match(s)
                or _COMMIT.match(s) or s == DROPPED)


def _leaf(value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if abs(value) < MAX_INT else DROPPED
    if isinstance(value, float):
        return amount(value) if math.isfinite(value) else DROPPED
    if isinstance(value, Decimal):
        return amount(value)
    if isinstance(value, str):
        return value if _passes_as_written(value) else SCRUB_HASH_PREFIX + _keyed(value)
    return DROPPED


def _exception_names():
    seen, stack = set(), [BaseException]
    while stack:
        for sub in type.__subclasses__(stack.pop()):
            if sub not in seen:
                seen.add(sub)
                stack.append(sub)
    return {c.__name__ for c in seen} | {'BaseException', 'Missing'}


def _is_error_name(value):
    """True for the name of a loaded exception class (re-walked on a miss: classes load lazily)."""
    if not isinstance(value, str):
        return False
    if value not in _STATE['errors']:
        _STATE['errors'] = frozenset(_exception_names())
    return value in _STATE['errors']


def scrub(value):
    """A copy of ``value`` with every non-conforming leaf hashed or dropped and every dict key that is not
    a known code dropped. Lists and tuples become lists; sets become sorted lists."""
    if isinstance(value, dict):
        error_shaped = 'error' in value and set(value) <= _ERROR_RECORD_KEYS
        out = {}
        for k, v in value.items():
            if k == 'error' and error_shaped and _is_error_name(v):
                out[k] = v
            elif k == '!dropped_keys' and type(v) is int:        # an already-scrubbed record
                out[k] = out.get(k, 0) + v
            elif is_code(k):
                out[k] = scrub(v)
            else:
                out.setdefault('!dropped_keys', 0)
                out['!dropped_keys'] += 1
        return out
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((scrub(v) for v in value), key=repr)
    return _leaf(value)


def count_dropped(value):
    """How many leaves and keys `scrub` dropped or hashed in ``value`` (a scrubbed value)."""
    if isinstance(value, dict):
        return value.get('!dropped_keys', 0) + sum(count_dropped(v) for k, v in value.items()
                                                    if k != '!dropped_keys')
    if isinstance(value, list):
        return sum(count_dropped(v) for v in value)
    return 1 if value == DROPPED or (isinstance(value, str) and _SCRUB_HASH.match(value)) else 0


def error_record(exc):
    """An error as its class name only. Never ``str(exc)``: a message can quote a field."""
    return {'error': type(exc).__name__}
