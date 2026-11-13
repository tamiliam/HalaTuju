"""The output scrubber: the LAST layer before anything is printed (design 3.2, 4.1).

Only these leave the job: codes, amounts, hashes, ids (and yes / no / nothing). Every other value is
replaced by `DROPPED`, and `count_dropped` lets the run report how many (any drop is a finding: the R2
normaliser must hash free text BEFORE it gets here). A dict key that is not a code is dropped with its
value. An error leaves as its class name only (`error_record`), never its message or traceback.

What counts:
  * None, True, False;
  * an int below 10**8 (an id or a count; an IC or a phone number held as a number is longer);
  * a Decimal / float, written as a 2-decimal amount;
  * a string that is: a hash `h:<8-16 hex>`; an amount `-?\\d+.\\d\\d`; a month `YYYY-MM`; a commit hash
    (7-40 hex with at least one letter); a lowercase code (`higher_results_not_declared`, `tick:name`);
    or an upper-case course / subject code with at least one letter AND one digit and no run of 10+ digits.
A capitalised word (`Probable`, a name) is NOT a code: the normaliser lower-cases statuses first.
"""
import hashlib
import math
import re
from decimal import Decimal, InvalidOperation

DROPPED = '!dropped'
MAX_INT = 10 ** 8

_HASH = re.compile(r'^h:[0-9a-f]{8,16}$')
_AMOUNT = re.compile(r'^-?\d{1,8}\.\d{2}$')
_MONTH = re.compile(r'^20\d{2}-(0[1-9]|1[0-2])$')
_COMMIT = re.compile(r'^(?=[0-9]*[a-f])[0-9a-f]{7,40}$')
_LOWER_CODE = re.compile(r'^[a-z][a-z0-9_]{0,47}(?:[:./-][a-z0-9_]{1,47}){0,4}$')
_UPPER_CODE = re.compile(r'^(?=[A-Z0-9_-]*[A-Z])(?=[A-Z0-9_-]*[0-9])[A-Z0-9][A-Z0-9_-]{2,23}$')
_LONG_DIGITS = re.compile(r'\d{10,}')
_CLASS_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')


def text_hash(value):
    """A short, stable hash for free text (the normaliser's tool; R2). Upper-cased and trimmed first."""
    s = str(value if value is not None else '').strip().upper()
    return 'h:' + hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]


def amount(value):
    """A 2-decimal amount string, or DROPPED when it is not a finite number."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return DROPPED
    if not d.is_finite():
        return DROPPED
    return str(d.quantize(Decimal('0.01')))


def is_code(s):
    if not isinstance(s, str):
        return False
    if _LOWER_CODE.match(s):
        return True
    return bool(_UPPER_CODE.match(s)) and not _LONG_DIGITS.search(s)


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
        if (_HASH.match(value) or _AMOUNT.match(value) or _MONTH.match(value) or _COMMIT.match(value)
                or is_code(value)):
            return value
        return DROPPED
    return DROPPED


def scrub(value):
    """A copy of ``value`` with every non-conforming leaf replaced by DROPPED and every dict key that is
    not a code dropped. Lists and tuples become lists; sets become sorted lists."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == 'error':
                out[k] = v if isinstance(v, str) and _CLASS_NAME.match(v) else DROPPED
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
    """How many leaves and keys `scrub` dropped in ``value`` (a scrubbed value)."""
    if isinstance(value, dict):
        return value.get('!dropped_keys', 0) + sum(count_dropped(v) for k, v in value.items()
                                                    if k != '!dropped_keys')
    if isinstance(value, list):
        return sum(count_dropped(v) for v in value)
    return 1 if value == DROPPED else 0


def error_record(exc):
    """An error as its class name only. Never ``str(exc)``: a message can quote a field."""
    return {'error': type(exc).__name__}
