"""Where a student was BORN, read from the MyKad number — request #31 (BrightPath, 2026-10-08).

A Malaysian NRIC is YYMMDD-PB-###G. PB, digits 7-8, is the JPN place-of-birth code: a state or
federal territory, a country, or "unknown". This module reads it, and nothing else does.

⚠⚠ THE TEST IS "BORN IN", AND ONLY THAT (owner + BrightPath). Not "Sabahan": family roots and where
the student lives now do not count. The IC's place-of-birth code is the source; a birth certificate
is a MANUAL follow-up a reviewer can already ask for from the cockpit, never an input here.

⚠ FAIL CLOSED. A student born outside Malaysia (60-99 except 82), with "state unknown" (82), or
with an IC we cannot read (fewer or more than 12 digits, 00, 17-20) does NOT pass a state rule.
Nothing here guesses.

Pure, no DB, no Django imports — `shortlisting.evaluate` reads it at submit and on every rescore,
the admin serializer reads it for the cockpit line, and the intake-year endpoints validate against
`STATE_KEYS`.

drift-test: halatuju-web/src/lib/__tests__/birthStatesDrift.test.ts — the web's tick boxes must
offer exactly these keys, with these names, in this order.
"""
from typing import NamedTuple

#: The 13 states and 3 federal territories as (stable key, display name). The NAMES are the
#: platform's own spelling — the web's `MALAYSIAN_STATES` (`lib/scholarship.ts`), the list the
#: profile and apply forms store — and the ORDER is that list's order. The KEYS are what an intake
#: year stores in `allowed_birth_states`; they never change once stored, so a renamed display name
#: must not touch them.
STATE_CHOICES = (
    ('johor', 'Johor'),
    ('kedah', 'Kedah'),
    ('kelantan', 'Kelantan'),
    ('melaka', 'Melaka'),
    ('negeri_sembilan', 'Negeri Sembilan'),
    ('pahang', 'Pahang'),
    ('perak', 'Perak'),
    ('perlis', 'Perlis'),
    ('pulau_pinang', 'Pulau Pinang'),
    ('sabah', 'Sabah'),
    ('sarawak', 'Sarawak'),
    ('selangor', 'Selangor'),
    ('terengganu', 'Terengganu'),
    ('wp_kuala_lumpur', 'W.P. Kuala Lumpur'),
    ('wp_putrajaya', 'W.P. Putrajaya'),
    ('wp_labuan', 'W.P. Labuan'),
)
STATE_KEYS = tuple(k for k, _ in STATE_CHOICES)
STATE_NAMES = dict(STATE_CHOICES)

#: The JPN place-of-birth codes for each state (owner's list, 2026-10-08). 01-16 are the original
#: codes; 21-59 were issued later for the same states. Every code from 21 to 59 is assigned.
_CODES = {
    'johor': ('01', '21', '22', '23', '24'),
    'kedah': ('02', '25', '26', '27'),
    'kelantan': ('03', '28', '29'),
    'melaka': ('04', '30'),
    'negeri_sembilan': ('05', '31', '59'),
    'pahang': ('06', '32', '33'),
    'pulau_pinang': ('07', '34', '35'),
    'perak': ('08', '36', '37', '38', '39'),
    'perlis': ('09', '40'),
    'selangor': ('10', '41', '42', '43', '44'),
    'terengganu': ('11', '45', '46'),
    'sabah': ('12', '47', '48', '49'),
    'sarawak': ('13', '50', '51', '52', '53'),
    'wp_kuala_lumpur': ('14', '54', '55', '56', '57'),
    'wp_labuan': ('15', '58'),
    'wp_putrajaya': ('16',),
}
CODE_TO_STATE = {code: state for state, codes in _CODES.items() for code in codes}

#: "State unknown" — a real JPN code, and NOT a pass.
UNKNOWN_CODE = '82'

#: The code the QC accept floor (`views_admin/verdict.py`) adds to its red facts when the
#: CURRENT IC fails the intake's rule. The cockpit labels it with the served `warning`.
FLOOR_FACT = 'birth_state'

# What kind of answer the IC gave.
STATE, ABROAD, UNKNOWN, UNREADABLE = 'state', 'abroad', 'unknown', 'unreadable'


class BirthState(NamedTuple):
    kind: str    # STATE | ABROAD | UNKNOWN | UNREADABLE
    state: str   # a STATE_KEYS key when kind == STATE, else ''
    code: str    # the two-digit PB code; '' when the IC is unreadable


_UNREADABLE = BirthState(UNREADABLE, '', '')


def birth_state_from_nric(nric):
    """The place of birth an NRIC states. Digits-only, like `consent.gender_from_nric`, so
    `120304-12-1234`, `120304121234` and `120304 12 1234` read the same.

    ⚠ EXACTLY 12 DIGITS OR UNREADABLE. Fewer is a half-typed number; more is not a MyKad number
    (a passport or a typo), and reading digits 7-8 of either would be a guess.

    ⚠ ASCII DIGITS ONLY, not `str.isdigit()`: '²' is a digit to Python and `int('²1')` raises, so
    a pasted superscript would have crashed the gate instead of reading as unreadable."""
    digits = ''.join(c for c in str(nric or '') if c in '0123456789')
    if len(digits) != 12:
        return _UNREADABLE
    code = digits[6:8]
    state = CODE_TO_STATE.get(code)
    if state:
        return BirthState(STATE, state, code)
    if code == UNKNOWN_CODE:
        return BirthState(UNKNOWN, '', code)
    if 60 <= int(code) <= 99:
        return BirthState(ABROAD, '', code)
    return _UNREADABLE       # 00 and 17-20: no place of birth is issued under them


def normalise_states(value):
    """An `allowed_birth_states` value from an admin request → ``(stored_list, ok)``.

    ⚠ IT REFUSES, IT NEVER DROPS. A list holding one unknown key must not save as the list without
    it — request #30's lesson: a bad value must never quietly become a different rule while the
    screen says Saved. ``None`` clears the rule (the value IS the switch, and null is how every
    other requirement is unticked); anything that is not a list of known keys is refused whole.
    Duplicates collapse, and the result is in `STATE_KEYS` order so the same choice is always
    stored the same way."""
    if value is None:
        return [], True
    if not isinstance(value, list):
        return None, False
    if any(not isinstance(v, str) or v not in STATE_NAMES for v in value):
        return None, False
    return [k for k in STATE_KEYS if k in value], True


def readable_list(keys):
    """`['sabah']` → 'Sabah'; two → 'Sabah and Sarawak'; more → 'A, B and C'. A key this module
    does not know is printed as itself rather than dropped (it can only come from a hand edit)."""
    names = [STATE_NAMES.get(k, str(k)) for k in keys]
    if len(names) <= 1:
        return ''.join(names)
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def describe(b):
    """The staff-facing words for one reading — the cockpit line and the decline reason share it."""
    if b.kind == STATE:
        return f'born in {STATE_NAMES[b.state]} (IC code {b.code})'
    if b.kind == ABROAD:
        return f'born outside Malaysia (IC code {b.code})'
    if b.kind == UNKNOWN:
        return f'place of birth unknown (IC code {b.code})'
    return 'IC number not readable'


def stored_keys(value):
    """A STORED `allowed_birth_states` → the list of keys it holds, as strings (TD-373).

    ⚠ THE ONE READER OF THE STORED VALUE. The gate (`check`), the QC floor and the cockpit
    (`meets_rule`), the IC-lock and reopen-cancel refusals, and the intake-year row the Rules tab
    loads (`views_admin/gifts._cohort_row`) all read it through here, so what the server enforces
    and what the screen shows cannot disagree. Before TD-373 the row served a bare string as
    itself, the screen read a non-list as "nothing ticked", and the next Save cleared a rule the
    server was still enforcing.

    Only a database edit can store anything but a list of known keys (`normalise_states` refuses
    the rest on the way in). A list → its items as strings; a bare string → that one entry; empty
    or None → ``[]`` (the rule off). Anything else is read as ONE entry, so it fails closed rather
    than matching a substring. A wrong-case key ('Sabah') is KEPT as typed: it matches no IC, and
    the Rules tab shows it as an extra ticked box so the admin can see it and untick it."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _accepted(allowed):
    """The rule's keys in the platform order (a hand-stored unknown key last)."""
    keys = stored_keys(allowed)
    return [k for k in STATE_KEYS if k in keys] + [k for k in keys if k not in STATE_NAMES]


def meets_rule(nric, allowed):
    """``None`` when the intake has no rule (an EMPTY list — the IC is not read); otherwise
    whether this IC names a state in it. The ONE answer the gate, the cockpit and the QC floor
    share."""
    if not stored_keys(allowed):
        return None
    b = birth_state_from_nric(nric)
    return b.kind == STATE and b.state in _accepted(allowed)


def check(nric, allowed):
    """``(ok, reason)`` for the intake's birth-state rule. An EMPTY list is the rule switched off
    and passes without reading the IC at all; otherwise only a STATE reading inside the list
    passes."""
    if meets_rule(nric, allowed) is not False:
        return True, ''
    b = birth_state_from_nric(nric)
    return False, f'{describe(b)}; this intake accepts {readable_list(_accepted(allowed))}'


def for_cockpit(nric, allowed=None):
    """The served cockpit value: ``{kind, state, code, label, meets_rule, warning}``. ADMIN
    SERIALIZER ONLY — a place of birth is identity data; it never reaches a student or sponsor.

    ⚠ `meets_rule` IS RE-READ ON EVERY LOAD, against the CURRENT IC and the intake's CURRENT list
    (request #31 review). The gate runs at submit; an unverified NRIC can be changed afterwards
    (`profile/claim-nric/`), and a MyKad that then matches the NEW number locks it. False here is
    what the reviewer sees, and the QC accept floor reads the same answer (`views_admin/verdict.py`).

    ⚠ `label` AND `warning` ARE SERVED IN ENGLISH, like the decline reason the engine stores, and
    that is a choice made for weight: every string in `en.json` rides on almost every student
    route (TD-360), and the budgeted lines had under 0.25 kB of room. The browser prints them and
    never re-reads the IC.
    """
    b = birth_state_from_nric(nric)
    if b.kind == STATE:
        label = f'Born in: {STATE_NAMES[b.state]} (IC code {b.code})'
    else:
        label = describe(b)
        label = label[0].upper() + label[1:]
    meets = meets_rule(nric, allowed)
    warning = (f"{label} — does not meet this intake's rule ({readable_list(_accepted(allowed))})"
               if meets is False else '')
    return {'kind': b.kind, 'state': b.state or None, 'code': b.code, 'label': label,
            'meets_rule': meets, 'warning': warning}
