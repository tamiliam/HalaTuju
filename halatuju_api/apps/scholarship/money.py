"""Money: one place that reads a figure, one place that writes one.

**Why this module exists.** Before code health H7 the name `_money` was defined in seven modules
of this app plus once more inside a view, and no two of them did the same thing. They did three
different JOBS — pull a figure out of OCR text, parse a figure to a `Decimal`, print a figure for
a screen — and within each job they disagreed about what a blank means, whether zero is legal,
whether a third decimal place is rounded or refused, and which exception carries the refusal. A
money-format fix made in one copy was not made in the other six.

**What this module is NOT.** It is not a policy. Every disagreement listed above was a deliberate
decision by the surface that made it, and H7 changed none of them:

  * an RM0 line on a payment run is legal, and a receipt for RM0 is not;
  * a blank Monthly cell in the Vircle CSV means zero, and a blank receipt box means "unreadable";
  * an absent balance on a sponsor card prints `0.00`, in a sponsor's email prints nothing, and on
    the platform-cost screen prints `null`, because there "we have no figure" and "the figure is
    zero" are different facts and the screen shows them differently.

So the parameters below are not options to pick from taste. Each one exists because one real
caller needs it and another real caller needs its opposite, and the characterisation table in
`tests/test_helper_characterisation.py` pins every one of those answers exactly as it was before
this module existed.

**Refusals.** `parse_money` raises `MoneyError` and nothing else, carrying a `reason` — `'syntax'`
(that is not a number) or `'range'` (that is a number this caller does not accept). Each caller
translates it into its own exception with its own code in two or three lines, because those codes
are read by a view, a command and a browser, and a shared module has no business knowing them.

⚠ **The two escapes are closed (TD-261, owner's order, 2026-09-19).** `Decimal('Infinity')` and
`Decimal('NaN')` parse successfully, and the quantise or the range comparison that followed then
raised `InvalidOperation` from OUTSIDE the guard — reaching the caller raw, as a 500 rather than a
400. That was H7-FINDING 3/4. A non-finite figure is now refused as a `'syntax'` `MoneyError`
before anything else looks at it, so all four callers answer with their own refusal and their own
code. It is the honest reason as well as the safe one: `Infinity` is not an amount of money.
"""
from decimal import Decimal, InvalidOperation

#: Two decimal places — ringgit and sen. The rounding is the decimal module's default
#: (ROUND_HALF_EVEN); `payments` and the Vircle import have always rounded that way.
CENTS = Decimal('0.01')

#: What counts as "no figure" for `format_money`, in the three shapes the three callers need.
BLANK_NONE = 'none'              # only `None` — an empty string is a value and prints as one
BLANK_NONE_OR_EMPTY = 'empty'    # `None` or `''`
BLANK_FALSY = 'falsy'            # anything falsy, including `0` and `Decimal('0')`


class MoneyError(ValueError):
    """A figure that could not be read. `reason` is `'syntax'` (not a number) or `'range'` (a
    number this caller refuses: zero, negative, or more decimal places than it allows).

    The distinction is not academic: `invoicing` shows the person a different sentence for each,
    and the sentence is the only part of a 400 they read.
    """

    def __init__(self, reason, value):
        super().__init__(reason)
        self.reason = reason
        self.value = value


def parse_money(value, *, strip_chars='', strip_whitespace=True, blank_as=None,
                quantize=False, places_exact=False, allow_zero=True, allow_negative=True):
    """Read `value` as a `Decimal`, or raise `MoneyError`.

    * `strip_chars` — characters deleted before parsing, e.g. `',$'` for a vendor invoice whose
      printed total carries thousands separators. Deleted, not tolerated: `'1,2,3'` becomes 123.
    * `strip_whitespace` — surrounding whitespace removed. Off for `payments`, which has never
      done it (`Decimal` tolerates its own leading and trailing spaces, so the two agree for
      every input a caller can pass; the parameter keeps that provable rather than assumed).
    * `blank_as` — the string to read INSTEAD when the value is empty. Only the Vircle CSV import
      sets it (`'0'`): a blank Monthly cell means nothing was paid. Everywhere else a blank is an
      unreadable figure and must refuse.
    * `quantize` — round to two places. `places_exact` — refuse anything that is not already
      exactly two places. ORDER MATTERS AND IS FIXED HERE: `places_exact` is answered against the
      figure AS READ, before any rounding, so a caller may ask for both. `payments` does since
      TD-261 — it refuses a third decimal place (nothing it accepts may be silently rounded) and
      still quantises, which then only normalises the REPRESENTATION of a figure that has already
      passed the check (`'12'` → `12.00`). Asking for `quantize` alone keeps the old rounding.
    * `allow_zero` / `allow_negative` — the range rule, answered after the parse.
    """
    text = value
    if blank_as is not None and not text:
        text = blank_as
    text = str(text)
    for char in strip_chars:
        text = text.replace(char, '')
    if strip_whitespace:
        text = text.strip()
        if blank_as is not None and not text:
            text = blank_as

    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError, TypeError, AttributeError) as exc:
        raise MoneyError('syntax', value) from exc

    # ⚠ FIRST, AND BEFORE ANYTHING TOUCHES IT (TD-261). `Decimal('Infinity')`, `'-Infinity'`,
    # `'NaN'` and `'sNaN'` all PARSE. Every operation below them — quantising, comparing to zero —
    # then raises `InvalidOperation` from outside any guard, which is how an admin request body
    # used to produce a 500 instead of a 400. A non-finite figure is not a figure: it is a syntax
    # refusal, and it is one here rather than four times over in the callers.
    if not amount.is_finite():
        raise MoneyError('syntax', value)

    # Answered against the figure as READ, before `quantize` rounds anything — see the docstring.
    if places_exact and amount != amount.quantize(CENTS):
        raise MoneyError('range', value)
    if quantize:
        try:
            amount = amount.quantize(CENTS)
        except InvalidOperation as exc:
            # A figure with more digits than the decimal context can hold at two places. It has
            # always been a `'syntax'` refusal (the quantise used to sit inside the guard above)
            # and it stays one.
            raise MoneyError('syntax', value) from exc

    if not allow_zero and amount == 0:
        raise MoneyError('range', value)
    if not allow_negative and amount < 0:
        raise MoneyError('range', value)
    return amount


def format_money(value, *, blank, blank_when=BLANK_NONE_OR_EMPTY, quantize=True, coerce=True):
    """`value` → the string this surface prints for it.

    * `blank` — what an absent figure prints as, and `blank_when` says which values are absent.
      The three real answers are `'0.00'` on a falsy value (the sponsor card), `''` on `None` or
      `''` (a sponsor's email), and `None` on `None` alone (the platform-cost payload).
    * `quantize` — print two decimal places ALWAYS. A `DecimalField` read gives `'3000.00'` but a
      `Sum()` over the same column gives `'20000'`, so a payload mixing the two renders
      "RM 20000" beside "RM 3,000.00" on one card unless this is on.
    * `coerce` — accept anything `Decimal(str(...))` accepts. Off for the sponsor card, whose
      figures are always `Decimal` or absent and which has always raised `AttributeError` on
      anything else; leaving it off keeps that true rather than widening a money surface as a
      side-effect of sharing code.
    """
    if blank_when == BLANK_FALSY:
        if not value:
            return blank
    elif blank_when == BLANK_NONE_OR_EMPTY:
        if value is None or value == '':
            return blank
    elif value is None:
        return blank

    amount = Decimal(str(value)) if coerce else value
    return str(amount.quantize(CENTS) if quantize else amount)
