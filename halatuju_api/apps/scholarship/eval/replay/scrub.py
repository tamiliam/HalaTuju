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
  * an int below 10**8 ONLY under a key in `INT_KEYS` (the counts, totals and case keys the harness
    emits); any other int is DROPPED. An 8-digit landline (41234567) or an IC split into parts
    ([990101, 14, 5678]) is below the cap, so the cap alone never made an int safe;
  * a Decimal / float below 10**8, written as a 2-decimal amount, and an amount string `-?\\d{1,8}.\\d\\d`,
    ONLY under a key in `AMOUNT_KEYS` (R2: anywhere else a float or Decimal is DROPPED and an amount-shaped
    string is hashed, so a figure that is not an amount cannot leave as one);
  * a COURSE CODE (a catalogue id, design 3.2) ONLY under a key in `COURSE_KEYS`, and only when it has two
    letters or more and is not one letter and 7-9 digits (`_course_code`). Course codes are NOT registered
    codes: `UP6500001` has the passport shape the registry refuses, so they pass by key, never by registry;
  * a string that is: a known code; a hash `h:<8-16 hex>` or `!h:<12 hex>`; a month `YYYY-MM`; and, ONLY under `old_commit` / `new_commit` in the top-level `start` event the
    parent emits, a commit hash (7-40 hex with at least one letter a-f AND one digit: a lower-cased
    passport has that shape too, so it is honoured nowhere else).

The registry is FROZEN once `engine_map` is imported (it imports the adapters, which register first);
a later `register_codes` raises. A code is checked with its separators (`_ . : / -`) removed, and is
refused when what is left holds a run of six or more digits (an IC, a phone, a long number, `d010203`)
or one or two letters and 7-9 digits (a passport), even before the freeze. Each child refuses to start
without the parent's salt (`use_salt`).
"""
import hashlib
import hmac
import math
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
#: 7-40 hex with at least one letter a-f and one digit (so neither an all-digit IC nor a word).
_COMMIT = re.compile(r'^(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}$')
#: Keys under which a commit-hash-shaped string may leave as written: ONLY in the top-level `start` event.
_COMMIT_KEYS = frozenset({'old_commit', 'new_commit'})
#: The only keys under which an int leaves as written (directly or inside a list): the case counts, the
#: per-engine totals, a side's exit code / record / drop counts, and a case `key` (an id). R2 adds its own
#: count, amount and index keys HERE, by review; nothing registers them at run time.
INT_KEYS = frozenset({
    'key', 'exit', 'records', 'dropped', 'failed_modules',
    'applications', 'documents_live', 'payable', 'profiles_spm', 'profiles_stpm', 'sponsors',
    'same', 'differs', 'could_not_run', 'noise',
    # R2 (reviewed here, never at run time): ids in a record, and the comparer's own counts
    'doc', 'template_id', 'expected', 'unexplained',
})
#: The only keys under which a Decimal / float or an amount-shaped string leaves as an amount (R2, 5a).
AMOUNT_KEYS = frozenset({
    'amount', 'amount_due', 'stored_award', 'monthly_amount', 'remaining', 'paid_to_date', 'balance', 'available_total',
    'monthly', 'total', 'merit',
})
#: The only keys under which a course code leaves as written (R2, 5b): the course adapters' eligible sets,
#: built ONLY from the catalogue's own ids (never from a student's data).
COURSE_KEYS = frozenset({'eligible_courses'})
#: Two letters or more; letters, digits and hyphens, at most 24; never one letter and 7-9 digits (a passport).
_COURSE = re.compile(r'^(?=(?:[^A-Za-z]*[A-Za-z]){2})[A-Za-z0-9][A-Za-z0-9-]{1,23}$')
_ONE_LETTER_PASSPORT = re.compile(r'^[A-Za-z]\d{7,9}$')
#: What `register_codes` accepts: one token, no spaces, at most 64 characters...
_CODE_SHAPE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_:./-]{0,63}$')
#: ...and, once its separators are removed (`_SEPARATORS`), none of these anywhere in it: a run of six or
#: more digits (an IC however split, a phone, a long number, `d010203`), or one or two letters and 7-9
#: digits (a passport, `AB1234567`).
_SEPARATORS = re.compile(r'[_.:/\- ]')
_PERSONAL_SHAPES = re.compile(r'\d{6,}|[A-Za-z]{1,2}\d{7,9}')
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
#: `frozen`: set by `freeze_registry` (engine_map, at import). `salt`: the run's HMAC key.
_STATE = {'salt': None, 'errors': frozenset(), 'frozen': False}
SALT_MIN_LEN = 32


class RegistryFrozen(RuntimeError):
    """`register_codes` was called after the registry was frozen."""


class SaltMissing(RuntimeError):
    """A child was started without the parent's scrub salt."""


def register_codes(codes):
    """Add ``codes`` (an R2 adapter's statuses, field names, engine names) to the registry, at the
    adapter module's import. Each must be a single token (`_CODE_SHAPE`) with no IC, phone, passport or
    long-number shape in it; anything else raises ValueError, so free text cannot be registered. After
    `freeze_registry` every call raises RegistryFrozen."""
    if _STATE['frozen']:
        raise RegistryFrozen('replay: the code registry is frozen')
    codes = list(codes)
    bad = [c for c in codes if not isinstance(c, str) or not _CODE_SHAPE.match(c)
           or _PERSONAL_SHAPES.search(_SEPARATORS.sub('', c))]
    if bad:
        raise ValueError(f'replay: {len(bad)} value(s) are not codes')
    _REGISTERED.update(codes)


def freeze_registry():
    """No more codes: called once `engine_map` (and with it every adapter) has been imported."""
    _STATE['frozen'] = True


def is_code(s):
    return isinstance(s, str) and (s in R1_CODES or s in _REGISTERED)


def _salt():
    if _STATE['salt'] is None:                          # the parent before `new_salt`; never a child
        _STATE['salt'] = secrets.token_hex(16)
    return _STATE['salt'].encode('ascii')


def new_salt():
    """A fresh run salt (the parent's): used here and returned for the children's environment."""
    _STATE['salt'] = secrets.token_hex(16)
    return _STATE['salt']


def use_salt(env):
    """A child's salt: the parent's, from ``env``. SaltMissing (the child refuses to start) when it is
    absent or short, so a child can never hash with a salt of its own making."""
    given = env.get(SALT_ENV, '')
    if not isinstance(given, str) or len(given) < SALT_MIN_LEN:
        raise SaltMissing(f'replay: {SALT_ENV} is not set')
    _STATE['salt'] = given


def _keyed(s):
    return hmac.new(_salt(), s.encode('utf-8'), hashlib.sha256).hexdigest()[:12]


def text_hash(value):
    """A short hash for free text (the normaliser's tool; R2), keyed with the run's salt, so it is stable
    within one run and cannot be reversed by hashing guesses. Upper-cased and trimmed first."""
    return 'h:' + _keyed(str(value if value is not None else '').strip().upper())


def amount(value):
    """A 2-decimal amount string, or DROPPED when it is not a finite number or not below MAX_INT (the
    same cap as a text amount: a full IC or mobile number held as a Decimal is longer)."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return DROPPED
    if not d.is_finite() or abs(d) >= MAX_INT:
        return DROPPED
    q = d.quantize(Decimal('0.01'))
    return DROPPED if abs(q) >= MAX_INT else str(q)


def _passes_as_written(s):
    return bool(is_code(s) or _HASH.match(s) or _SCRUB_HASH.match(s) or _MONTH.match(s) or s == DROPPED)


def _course_code(s):
    return bool(_COURSE.match(s)) and not _ONE_LETTER_PASSPORT.match(s)


def _leaf(value, key):
    """``key``: the dict key the value sits under (a list passes its key to its items), or None."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if key in INT_KEYS and abs(value) < MAX_INT else DROPPED
    if isinstance(value, (float, Decimal)):
        if key not in AMOUNT_KEYS or (isinstance(value, float) and not math.isfinite(value)):
            return DROPPED
        return amount(value)
    if isinstance(value, str):
        if _passes_as_written(value):
            return value
        if key in AMOUNT_KEYS and _AMOUNT.match(value):
            return value
        if key in COURSE_KEYS and _course_code(value):
            return value
        return SCRUB_HASH_PREFIX + _keyed(value)
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
    return _scrub(value, top=True, key=None)


def _scrub(value, *, top, key):
    """``top``: ``value`` is the whole line (only there may a `start` event carry its commit hashes).
    ``key``: the key ``value`` sits under (INT_KEYS, AMOUNT_KEYS and COURSE_KEYS read it; a list under
    one passes it to its items)."""
    if isinstance(value, dict):
        error_shaped = 'error' in value and set(value) <= _ERROR_RECORD_KEYS
        start_event = top and value.get('event') == 'start'
        out = {}
        for k, v in value.items():
            if k == 'error' and error_shaped and _is_error_name(v):
                out[k] = v
            elif k == '!dropped_keys' and type(v) is int and 0 <= v < MAX_INT:   # an already-scrubbed record
                out[k] = out.get(k, 0) + v
            elif start_event and k in _COMMIT_KEYS and isinstance(v, str) and _COMMIT.match(v):
                out[k] = v
            elif is_code(k):
                out[k] = _scrub(v, top=False, key=k)
            else:
                out.setdefault('!dropped_keys', 0)
                out['!dropped_keys'] += 1
        if '!dropped_keys' in out:
            out['!dropped_keys'] = min(out['!dropped_keys'], MAX_INT - 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_scrub(v, top=False, key=key) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_scrub(v, top=False, key=key) for v in value), key=repr)
    return _leaf(value, key)


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
