"""The normaliser (design 4.1): an engine's answer as a canonical record, BEFORE the scrubber sees it.

  * keys sorted (json.dumps sort_keys at write); code lists sorted where order means nothing, the
    verdict's four facts in their fixed order;
  * a code that is registered leaves as written; any other text becomes `text_hash` (`h:<12 hex>`), so
    nothing reaches the scrubber as raw text (the scrubber would hash it too, but counts it as a finding);
  * an amount becomes a 2-decimal string, and only under a key in `scrub.AMOUNT_KEYS`; an int only under
    `scrub.INT_KEYS`; any other number is hashed like text;
  * a date becomes `YYYY-MM` under a month key, else a hash; `params` are always one hash (they can hold
    names);
  * a dict key that is not a code is folded into `other_keys` as `[hash(key), value]` pairs.
"""
import datetime
import json
import re
from decimal import Decimal

from . import scrub

MONTH_KEYS = frozenset({'month', 'months', 'paid_months', 'start_month', 'end_month'})
_AMOUNT_TEXT = re.compile(r'^-?\d{1,8}\.\d{2}$')   # the scrubber's amount shape


def code(value):
    """A registered code as written, '' / None as None, anything else hashed."""
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return value
    return value if scrub.is_code(value) else scrub.text_hash(value)


def codes(items):
    """Sorted, de-duplicated codes; an item may be a dict with `code` (a verdict item)."""
    out = {code(i.get('code') if isinstance(i, dict) else i) for i in (items or ())}
    return sorted((c for c in out if c is not None), key=str)


def amt(value):
    return None if value is None else scrub.amount(value)


def params_hash(items):
    """One hash of every item's params, in item order (never the params themselves)."""
    blob = [i.get('params') for i in (items or ()) if isinstance(i, dict)]
    return scrub.text_hash(json.dumps(blob, sort_keys=True, default=str))


def fact(f):
    """One verdict fact: present, status, sorted unresolved and evidence codes, and a hash of the params."""
    return {'fact': code(f.get('fact')), 'status': code(f.get('status')),
            'unresolved': codes(f.get('unresolved')), 'evidence': codes(f.get('evidence')),
            'params': params_hash(list(f.get('unresolved') or ()) + list(f.get('evidence') or ()))}


def canon(value, key=None):
    """Any engine answer (a result dict, a list, a leaf) as a canonical, pre-scrubbed value."""
    if isinstance(value, dict):
        out, other = {}, []
        for k in sorted(value, key=str):
            if isinstance(k, str) and scrub.is_code(k):
                out[k] = canon(value[k], k)
            else:
                other.append([scrub.text_hash(k), canon(value[k])])
        if other:
            out['other_keys'] = other
        return out
    if isinstance(value, (list, tuple)):
        return [canon(v, key) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((canon(v, key) for v in value), key=str)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if key in scrub.INT_KEYS and abs(value) < scrub.MAX_INT else scrub.text_hash(value)
    if isinstance(value, (float, Decimal)):
        return amt(value) if key in scrub.AMOUNT_KEYS else scrub.text_hash(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime('%Y-%m') if key in MONTH_KEYS else scrub.text_hash(value.isoformat())
    if isinstance(value, str):
        if key in scrub.AMOUNT_KEYS and _AMOUNT_TEXT.match(value):
            return value
        return code(value)
    return scrub.text_hash(repr(type(value).__name__))
