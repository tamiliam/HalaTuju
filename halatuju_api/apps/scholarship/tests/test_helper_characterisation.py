"""Characterisation of the helper families code health H7 unifies — TODAY'S behaviour, pinned.

⚠ THIS FILE DESCRIBES, IT DOES NOT PRESCRIBE. Every row below was READ OFF the untouched tree
before a single line of H7's refactor was written, and every row is what the function does today,
warts included. A row that looks wrong is not a bug in the table — it is the finding. The ones
that surprised the author carry an `H7-FINDING` comment and are reported to the owner rather than
fixed, because these are money paths and a fix to money code is the owner's call, not a
refactor's side-effect.

**The contract of this file: after H7, it passes UNCHANGED.** Not "passes after an expected value
was adjusted" — unchanged. That is the whole proof that the unification moved no behaviour. The
one concession is `_fn` below: H7 RENAMES several of these helpers (that is the point — four
`_norm`s were four different contracts wearing one name), so the table reaches its subject through
a list of names rather than one. The names may move. **The expected values may not.**

**TD-261, 2026-09-19 — the one sanctioned exception, and how it was taken.** The owner ordered the
five findings and the three surprises fixed. A fix is made HERE FIRST, by editing the pinned row
to the value the fixed code must produce and watching it go red against the unfixed tree; the
edited row IS the review, and every one of them carries a `TD-261` comment saying what it used to
be and why it moved. Nothing else in the table was touched. Any future change to these helpers
answers to the table the same way: edit the row, in the open, or do not change the behaviour.

Nothing here touches the database: every subject is a pure function, and the two that are not
(the Gemini seams) are exercised against a fake client.
"""
import unittest
from decimal import Decimal, InvalidOperation
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.scholarship import (academic_engine, apply_copy_draft, bc_parse, contracts, doc_parse,
                              funding_estimate, invoice_parsers, invoicing, offer_parse, payments,
                              sponsor_comms, sponsor_terms, sponsorship, vircle_airtable)
from apps.scholarship.genuineness import (electricity_doc, results_doc, salary_doc,
                                          school_leaving_doc, water_doc)
from apps.scholarship.management.commands import award_students_batch, import_vircle_csv
from apps.scholarship.management.commands import send_award_offer_emails, send_sign_invitation_emails
from apps.scholarship.management.commands import send_vircle_install_emails


def _fn(module, *names):
    """The subject, by whichever of `names` the module currently carries.

    An import-path alias, and the ONLY thing in this file H7 is allowed to move. The first name is
    the one H7 leaves behind; the rest are what the function was called before. If none is present
    the test fails loudly rather than silently characterising nothing.
    """
    for name in names:
        found = getattr(module, name, None)
        if found is not None:
            return found
    raise AssertionError(
        f'{module.__name__} defines none of {names!r} — a characterised helper has been renamed '
        f'without adding its new name to the alias list. The table must keep running.')


class Raises:
    """An expected refusal: the exception type, and the `code` / message text that the caller
    downstream actually reads. A wrong code is a behaviour change even when the type matches."""

    def __init__(self, exc, *, code=None, message=None):
        self.exc, self.code, self.message = exc, code, message

    def __repr__(self):
        return f'Raises({self.exc.__name__}, code={self.code!r}, message={self.message!r})'


class _Table(SimpleTestCase):
    """Runs one (input → exact output-or-refusal) table against one function."""

    def check(self, fn, table):
        for value, expected in table:
            with self.subTest(fn=getattr(fn, '__name__', fn), value=repr(value)):
                if isinstance(expected, Raises):
                    with self.assertRaises(expected.exc) as caught:
                        fn(value)
                    if expected.code is not None:
                        self.assertEqual(getattr(caught.exception, 'code', None), expected.code)
                    if expected.message is not None:
                        self.assertEqual(str(caught.exception), expected.message)
                else:
                    self.assertEqual(fn(value), expected)
                    self.assertIs(type(fn(value)), type(expected))


# ── Money, job 1 of 3: EXTRACT a figure from OCR text ────────────────────────────────────────
# `doc_parse._money` shares ONLY the name with the other seven. It reads a utility bill's OCR
# text and hands back a display string; it parses nothing and refuses nothing. H7 renames it
# `_first_rm_figure`.

class TestFirstRmFigure(_Table):

    def test_the_table(self):
        self.check(_fn(doc_parse, '_first_rm_figure', '_money'), [
            (None, ''),
            ('', ''),
            ('   ', ''),
            ('0', 'RM0'),
            ('0.00', 'RM0.00'),
            ('1234', 'RM1234'),
            # TD-261 defect 2, FIXED 2026-09-19: a figure with ONE decimal place used to lose its
            # decimals entirely ('1234.5' → 'RM1234') because the pattern admitted exactly two or
            # none. It now admits one OR two, and reports what the document says rather than
            # normalising — this helper extracts, it does not format.
            ('1234.5', 'RM1234.5'),
            ('1234.56', 'RM1234.56'),
            ('1234.567', 'RM1234.56'),
            ('12.345678', 'RM12.34'),
            ('1,234.56', 'RM1234.56'),
            ('$1,234.56', 'RM1234.56'),
            ('RM1,234.56', 'RM1234.56'),
            (' 12.34 ', 'RM12.34'),
            # TD-261 defect 1, FIXED 2026-09-19: the minus sign used to be DROPPED, so a credit
            # line on a bill ('-5.00') read back as a charge of RM5.00. The sign is now kept, and
            # it is kept AFTER the 'RM' — the shape both consumers of the stored string already
            # read correctly (`income_engine._arrears_amount` matches `-\s*\d`, which '-RM40.00'
            # would NOT satisfy; the web's `officerCockpit._arrearsAmount` reads either). Only the
            # LEADING minus is supported: no fixture, corpus or test in this repo shows a
            # Malaysian utility bill printing a credit as '40.00-', '40.00 CR' or '(40.00)'.
            ('-5.00', 'RM-5.00'),
            ('-0.01', 'RM-0.01'),
            ('Caj Semasa (RM) 88.20', 'RM88.20'),
            # Pinned surprise: the comma-strip runs AFTER the match, so a non-thousands comma
            # run is swallowed whole rather than rejected.
            ('1,2,3', 'RM123'),
            ('1e3', 'RM1'),
            ('abc', ''),
            ('NaN', ''),
            ('Infinity', ''),
            ('99999999999999999999.99', 'RM99999999999999999999.99'),
            # An Arabic-Indic digit IS `\d`; a superscript is not. This asymmetry is the same one
            # that decides `_digits` below.
            ('٣', 'RM٣'),
            ('³', ''),
            (12, Raises(TypeError)),
            (12.5, Raises(TypeError)),
            (Decimal('12.50'), Raises(TypeError)),
            (True, Raises(TypeError)),
            # ...but a FALSY non-string short-circuits on `v or ''` and never reaches the regex,
            # so `0` reads as "no figure" while `'0'` reads as RM0.
            (0, ''),
            (Decimal('0'), ''),
        ])


# ── Money, job 2 of 3: PARSE to a Decimal ────────────────────────────────────────────────────
# Four callers, four contracts. The differences that matter: what a blank means, whether zero and
# negatives are legal, whether the figure is quantised or merely checked, which characters are
# stripped first, and the exact refusal each one raises.

class TestParseInvoiceParsers(_Table):
    """`invoice_parsers`: a vendor invoice PDF. Strips `,` and `$`; accepts anything else a
    `Decimal` accepts, including negatives and unlimited decimal places. Since TD-261 a comma
    must be a THOUSANDS separator (`1,234.56`) and a non-finite figure is refused."""

    def test_the_table(self):
        bad = lambda v: Raises(invoice_parsers.InvoiceParseError,  # noqa: E731
                               message=f'Not a money figure: {v!r}')
        self.check(_fn(invoice_parsers, '_invoice_amount', '_money'), [
            (None, bad(None)),
            ('', bad('')),
            ('   ', bad('   ')),
            ('0', Decimal('0')),
            ('0.00', Decimal('0.00')),
            (0, Decimal('0')),
            ('1234', Decimal('1234')),
            ('1234.5', Decimal('1234.5')),
            ('1234.56', Decimal('1234.56')),
            ('1234.567', Decimal('1234.567')),
            ('12.345678', Decimal('12.345678')),
            ('1,234.56', Decimal('1234.56')),
            ('$1,234.56', Decimal('1234.56')),
            ('RM1,234.56', bad('RM1,234.56')),
            ('-5.00', Decimal('-5.00')),
            ('-0.01', Decimal('-0.01')),
            (' 12.34 ', Decimal('12.34')),
            (12, Decimal('12')),
            (12.5, Decimal('12.5')),
            (Decimal('12.50'), Decimal('12.50')),
            (Decimal('12.345'), Decimal('12.345')),
            (Decimal('0'), Decimal('0')),
            ('1e3', Decimal('1E+3')),
            ('abc', bad('abc')),
            # TD-261 oddity (a), FIXED 2026-09-19: comma-stripping used to be unconditional, so
            # '1,2,3' was read as 123. A comma must now group thousands properly or the figure is
            # refused. No real fixture in `test_invoice_parsers.py` carries a comma at all (every
            # printed figure on the eight invoices is under 1,000), so nothing real changes.
            ('1,2,3', bad('1,2,3')),
            ('99999999999999999999.99', Decimal('99999999999999999999.99')),
            ('٣', Decimal('3')),
            ('³', bad('³')),
            (True, bad(True)),
        ])

    def test_the_two_decimal_specials_are_refused(self):
        """⚠ TD-261 defects 3/4, FIXED 2026-09-19 at the one home. `Decimal('NaN')` and
        `Decimal('Infinity')` PARSE, and used to pass straight through here — an invoice line that
        cannot reconcile to a printed total. `money.parse_money` now refuses a non-finite figure
        as a syntax error inside its guard, so this caller answers with its own refusal like any
        other unreadable figure. Pinned separately from the table because `Decimal('NaN')` is not
        equal to itself."""
        parse = _fn(invoice_parsers, '_invoice_amount', '_money')
        for value in ('NaN', 'Infinity', '-Infinity', 'sNaN'):
            with self.subTest(value=value):
                with self.assertRaises(invoice_parsers.InvoiceParseError) as caught:
                    parse(value)
                self.assertEqual(str(caught.exception), f'Not a money figure: {value!r}')


class TestParseInvoicing(_Table):
    """`invoicing`: an amount an admin types into the receipt box. Must be above zero and carry
    at most two decimal places; no comma or symbol tolerance at all. TWO distinct messages, both
    under the code `bad_amount` — one for "that is not a number", one for "that number is not
    allowed" — and the view shows the message, so they are pinned separately."""

    SYNTAX_MSG = 'Enter the amount received, like 1552.50.'
    RANGE_MSG = 'Enter an amount above zero with at most two decimals.'

    def test_the_table(self):
        syntax = Raises(invoicing.InvoicingError, code='bad_amount', message=self.SYNTAX_MSG)
        out_of_range = Raises(invoicing.InvoicingError, code='bad_amount',
                              message=self.RANGE_MSG)
        self.check(_fn(invoicing, '_receipt_amount', '_money'), [
            (None, syntax),
            ('', syntax),
            ('   ', syntax),
            ('0', out_of_range),
            ('0.00', out_of_range),
            (0, out_of_range),
            (Decimal('0'), out_of_range),
            ('1234', Decimal('1234')),
            ('1234.5', Decimal('1234.5')),
            ('1234.56', Decimal('1234.56')),
            ('1234.567', out_of_range),
            ('12.345678', out_of_range),
            (Decimal('12.345'), out_of_range),
            ('1,234.56', syntax),
            ('$1,234.56', syntax),
            ('RM1,234.56', syntax),
            ('-5.00', out_of_range),
            ('-0.01', out_of_range),
            (' 12.34 ', Decimal('12.34')),
            (12, Decimal('12')),
            (12.5, Decimal('12.5')),
            (Decimal('12.50'), Decimal('12.50')),
            ('1e3', Decimal('1E+3')),
            ('abc', syntax),
            ('1,2,3', syntax),
            ('99999999999999999999.99', Decimal('99999999999999999999.99')),
            # TD-261 defect 3: 'NaN' used to read as out-of-range (a NaN is not equal to its own
            # quantise, so the places check tripped on it). It is now refused for what it is —
            # not a number — which is also the sentence the person in front of the receipt box
            # needs.
            ('NaN', syntax),
            ('٣', Decimal('3')),
            ('³', syntax),
            (True, syntax),
        ])

    def test_a_non_finite_figure_is_a_bad_amount_not_a_crash(self):
        """⚠ TD-261 defect 3, FIXED 2026-09-19. `Decimal('Infinity')` PARSES, so the guarded
        try/except used to be already behind us when `amount.quantize(CENTS)` raised
        `InvalidOperation` on it — and `record_receipt`, reached from an admin request body,
        therefore returned a 500 where every other bad input returns a 400 carrying `bad_amount`.
        `money.parse_money` now refuses a non-finite figure inside the guard. The endpoint proof
        is `test_invoicing.TestReceiptEndpointRefusals`."""
        amount = _fn(invoicing, '_receipt_amount', '_money')
        for value in ('Infinity', '-Infinity', 'NaN', 'sNaN'):
            with self.subTest(value=value):
                with self.assertRaises(invoicing.InvoicingError) as caught:
                    amount(value)
                self.assertEqual(caught.exception.code, 'bad_amount')
                self.assertEqual(str(caught.exception), self.SYNTAX_MSG)


class TestParsePayments(_Table):
    """`payments`: an amount on a payment-run line. Zero is legal — an RM0 credit line is a real
    thing — and negatives are not. Since TD-261 a third decimal place is REFUSED rather than
    rounded (the only path that reaches this is an officer typing into the run-item box; the one
    figure the product computes, `default_amount`, quantises at its own site and never comes
    through here); the 2dp quantise that remains only normalises the REPRESENTATION of a figure
    that already passed that check, so 'RM12' is stored as 12.00."""

    def test_the_table(self):
        bad = Raises(payments.PaymentsError, code='bad_amount', message='bad_amount')
        self.check(_fn(payments, '_payment_amount', '_money'), [
            (None, bad),
            ('', bad),
            ('   ', bad),
            ('0', Decimal('0.00')),
            ('0.00', Decimal('0.00')),
            (0, Decimal('0.00')),
            (Decimal('0'), Decimal('0.00')),
            ('1234', Decimal('1234.00')),
            ('1234.5', Decimal('1234.50')),
            ('1234.56', Decimal('1234.56')),
            # TD-261 oddity (b), FIXED 2026-09-19: a third decimal place used to be silently
            # ROUNDED (banker's rounding, the default decimal context) on money going OUT to a
            # student's wallet. It is refused now, as `invoicing` always refused the same input.
            ('1234.567', bad),
            ('12.345678', bad),
            (Decimal('12.345'), bad),
            ('1,234.56', bad),
            ('$1,234.56', bad),
            ('RM1,234.56', bad),
            ('-5.00', bad),
            ('-0.01', bad),
            (' 12.34 ', Decimal('12.34')),
            (12, Decimal('12.00')),
            (12.5, Decimal('12.50')),
            (Decimal('12.50'), Decimal('12.50')),
            ('1e3', Decimal('1000.00')),
            ('abc', bad),
            ('1,2,3', bad),
            ('99999999999999999999.99', Decimal('99999999999999999999.99')),
            ('Infinity', bad),
            ('٣', Decimal('3.00')),
            ('³', bad),
            (True, bad),
        ])

    def test_a_non_finite_figure_is_a_bad_amount_not_a_crash(self):
        """⚠ TD-261 defect 4, FIXED 2026-09-19 — the twin of defect 3, in the other direction.
        `Decimal('NaN')` quantises to NaN without raising, so the try/except was behind us when
        the `amount < 0` range check compared against a NaN and raised `InvalidOperation`.
        `payments.set_item` (the entry the debt entry calls `set_run_item`) is reached from an
        admin request body. The endpoint proof is
        `test_payment_endpoints.TestRunItemAmountRefusals`."""
        amount = _fn(payments, '_payment_amount', '_money')
        for value in ('NaN', 'sNaN', 'Infinity', '-Infinity'):
            with self.subTest(value=value):
                with self.assertRaises(payments.PaymentsError) as caught:
                    amount(value)
                self.assertEqual(caught.exception.code, 'bad_amount')


class TestParseVircleImport(_Table):
    """`import_vircle_csv`: a Monthly column out of the owner's CSV. The only one of the four for
    which a BLANK is a legal value — it means zero, not "unreadable". Since TD-261 a NEGATIVE
    monthly amount is refused by name and row (a bursary paid to a student is money out; a
    negative one describes nothing the column can mean), and so is a non-finite figure."""

    def test_the_table(self):
        bad = lambda v: Raises(import_vircle_csv.CommandError,  # noqa: E731
                               message=f'Unrecognised Monthly amount: {v!r}')
        self.check(_fn(import_vircle_csv, '_monthly_amount', '_money'), [
            (None, Decimal('0.00')),
            ('', Decimal('0.00')),
            ('   ', Decimal('0.00')),
            ('0', Decimal('0.00')),
            ('0.00', Decimal('0.00')),
            (0, Decimal('0.00')),
            (Decimal('0'), Decimal('0.00')),
            ('1234', Decimal('1234.00')),
            ('1234.5', Decimal('1234.50')),
            ('1234.56', Decimal('1234.56')),
            ('1234.567', Decimal('1234.57')),
            ('12.345678', Decimal('12.35')),
            (Decimal('12.345'), Decimal('12.34')),
            ('1,234.56', bad('1,234.56')),
            ('$1,234.56', bad('$1,234.56')),
            ('RM1,234.56', bad('RM1,234.56')),
            # TD-261 oddity (c), FIXED 2026-09-19: a NEGATIVE monthly amount used to be accepted
            # without comment.
            ('-5.00', bad('-5.00')),
            ('-0.01', bad('-0.01')),
            (' 12.34 ', Decimal('12.34')),
            (12, Decimal('12.00')),
            (12.5, Decimal('12.50')),
            (Decimal('12.50'), Decimal('12.50')),
            ('1e3', Decimal('1000.00')),
            ('abc', bad('abc')),
            ('1,2,3', bad('1,2,3')),
            ('99999999999999999999.99', Decimal('99999999999999999999.99')),
            ('Infinity', bad('Infinity')),
            ('٣', Decimal('3.00')),
            ('³', bad('³')),
            (True, bad(True)),
        ])

    def test_a_non_finite_figure_is_refused_by_name(self):
        """TD-261: 'NaN' used to be ACCEPTED and returned as a NaN, and nothing downstream
        range-checked it — a row that would have summed every batch total to NaN. Pinned here
        rather than in the table because NaN is not equal to itself."""
        amount = _fn(import_vircle_csv, '_monthly_amount', '_money')
        for value in ('NaN', 'sNaN', 'Infinity', '-Infinity'):
            with self.subTest(value=value):
                with self.assertRaises(import_vircle_csv.CommandError) as caught:
                    amount(value)
                self.assertEqual(str(caught.exception),
                                 f'Unrecognised Monthly amount: {value!r}')


# ── Money, job 3 of 3: FORMAT for display ────────────────────────────────────────────────────
# Three callers, three answers for an absent figure: '0.00', '' and None. That disagreement is
# the whole reason the name had to stop being shared.

class TestFormatSponsorship(_Table):
    """`sponsorship`: the sponsor-card payload. Every falsy value renders '0.00'; a value that is
    not already a `Decimal` is NOT coerced, so a string or a float raises `AttributeError`. No
    caller passes one — these are `DecimalField` reads and `Sum()` aggregates."""

    def test_the_table(self):
        no_quantize = Raises(AttributeError)
        self.check(_fn(sponsorship, '_amount_str', '_money'), [
            (None, '0.00'),
            ('', '0.00'),
            (0, '0.00'),
            (Decimal('0'), '0.00'),
            (Decimal('12.50'), '12.50'),
            (Decimal('20000'), '20000.00'),
            (Decimal('12.345'), '12.34'),
            (Decimal('-5.00'), '-5.00'),
            (Decimal('99999999999999999999.99'), '99999999999999999999.99'),
            ('   ', no_quantize),
            ('0', no_quantize),
            ('1234.56', no_quantize),
            (12, no_quantize),
            (12.5, no_quantize),
            (True, no_quantize),
        ])


class TestFormatSponsorComms(_Table):
    """`sponsor_comms`: the same figure inside a sponsor's email. Its docstring says it matches
    `sponsorship`'s — and for a real figure it does. For an ABSENT one it does not: this renders
    '', that renders '0.00'. Both are deliberate (an email omits what it has no figure for); the
    docstring is what is inaccurate."""

    def test_the_table(self):
        unparseable = Raises(InvalidOperation)
        self.check(_fn(sponsor_comms, '_amount_str', '_money'), [
            (None, ''),
            ('', ''),
            (0, '0.00'),
            (Decimal('0'), '0.00'),
            ('0', '0.00'),
            ('0.00', '0.00'),
            ('1234', '1234.00'),
            ('1234.5', '1234.50'),
            ('1234.56', '1234.56'),
            ('1234.567', '1234.57'),
            ('12.345678', '12.35'),
            (Decimal('12.345'), '12.34'),
            (Decimal('12.50'), '12.50'),
            ('-5.00', '-5.00'),
            ('-0.01', '-0.01'),
            (' 12.34 ', '12.34'),
            (12, '12.00'),
            (12.5, '12.50'),
            ('1e3', '1000.00'),
            ('99999999999999999999.99', '99999999999999999999.99'),
            ('NaN', 'NaN'),
            ('٣', '3.00'),
            ('   ', unparseable),
            ('1,234.56', unparseable),
            ('$1,234.56', unparseable),
            ('RM1,234.56', unparseable),
            ('abc', unparseable),
            ('1,2,3', unparseable),
            ('Infinity', unparseable),
            ('³', unparseable),
            (True, unparseable),
        ])


class TestFormatPlatformCosts(_Table):
    """The eighth `_money`, nested inside `AdminPlatformCostsView.get`. (The H7 survey placed it
    in `_invoice_payload`; the code says otherwise — it stringifies the platform-cost ledger and
    the per-tenant charge lines.) It quantises NOTHING: it exists only to stop DRF rendering a
    bare `Decimal` inside a nested dict as a float, so `str()` is the whole rule, and `None` must
    survive as `None` because the screen distinguishes "no figure" from "zero"."""

    @staticmethod
    def _subject():
        """Read the nested function out of its enclosing view. It has no module-level name, so
        `_fn` cannot reach it; after H7 it delegates to the shared formatter and this still
        exercises the real thing the payload is built with."""
        from apps.scholarship import views_admin
        view = views_admin.AdminPlatformCostsView()
        for const in view.get.__code__.co_consts:
            if getattr(const, 'co_name', '') in ('_money', '_str_or_none'):
                import types
                return types.FunctionType(const, vars(views_admin))
        raise AssertionError('the platform-cost payload no longer defines its money formatter')

    def test_the_invoice_payload_formatter_is_the_same_rule(self):
        """⚠ THE NINTH `_money`, which the H7 survey did not have. `views_admin` also carries a
        module-level `_invoice_money`, written four days after the nested one and byte-identical
        to it (`None if v is None else str(v)` against `str(v) if v is not None else None`). It
        escaped the `duplicated_names` ledger only because the name differs. Both now call the
        shared formatter with the same parameters; this proves they agree on every row of the
        table below, which is what makes "the same rule" a fact rather than a claim."""
        from apps.scholarship import views_admin
        nested = self._subject()
        for value, _expected in self._TABLE:
            with self.subTest(value=repr(value)):
                self.assertEqual(views_admin._invoice_money(value), nested(value))

    def test_the_table(self):
        self.check(self._subject(), self._TABLE)

    _TABLE = [
            (None, None),
            ('', ''),
            ('   ', '   '),
            ('0', '0'),
            ('0.00', '0.00'),
            (0, '0'),
            (Decimal('0'), '0'),
            (Decimal('12.50'), '12.50'),
            (Decimal('12.345'), '12.345'),
            (Decimal('20000'), '20000'),
            ('1234.567', '1234.567'),
            ('1,234.56', '1,234.56'),
            ('-5.00', '-5.00'),
            (12, '12'),
            (12.5, '12.5'),
            ('abc', 'abc'),
            ('NaN', 'NaN'),
            (True, 'True'),
    ]


# ── `_norm` ×4: four contracts, one name ─────────────────────────────────────────────────────
# These are NOT merged by H7 and must never be: they disagree on case, on digits and on accents,
# and each is the input to a name- or marker-matching decision. They are renamed to say so.

_NORM_INPUTS = [None, '', '  ', 'Abc', 'ABC def', 'a-b_c', 'Ahmad bin Ali', 'Café',
                'ÀÉÎÕÜ', 'ABC123', '123', 'a  b', ' x ',
                'MÜLLER', 'Nurul A/P Samy', "O'Brien", 'ஆதி', '٣']


def _norm_table(outputs):
    return list(zip(_NORM_INPUTS, outputs))


class TestNormAcademicEngine(_Table):
    """Lower-case, every run of non-alphanumerics to one space. Digits SURVIVE; accented letters
    are DROPPED (they are not in `[a-z0-9]`), so 'Café' matches 'Caf'."""

    def test_the_table(self):
        self.check(_fn(academic_engine, '_norm_lower_alnum', '_norm'), _norm_table([
            '', '', '', 'abc', 'abc def', 'a b c', 'ahmad bin ali', 'caf',
            '', 'abc123', '123', 'a b', 'x',
            'm ller', 'nurul a p samy', 'o brien', '', '',
        ]))


class TestNormBcParse(_Table):
    """Upper-case, LETTERS ONLY — every digit and separator deleted outright, not spaced. This is
    the one that would silently change a birth-certificate row match if it were merged with any
    of the others: 'ABC123' and 'ABC' are the same string to it."""

    def test_the_table(self):
        self.check(_fn(bc_parse, '_norm_letters_upper', '_norm'), _norm_table([
            '', '', '', 'ABC', 'ABCDEF', 'ABC', 'AHMADBINALI', 'CAF',
            '', 'ABC', '', 'AB', 'X',
            'MLLER', 'NURULAPSAMY', 'OBRIEN', '', '',
        ]))


class TestNormFundingEstimate(_Table):
    """Strip and lower-case, and nothing else. Punctuation, accents and non-Latin scripts all
    survive intact — it compares course-name substrings, not names."""

    def test_the_table(self):
        self.check(_fn(funding_estimate, '_norm_strip_lower', '_norm'), _norm_table([
            '', '', '', 'abc', 'abc def', 'a-b_c', 'ahmad bin ali', 'café',
            'àéîõü', 'abc123', '123', 'a  b', 'x',
            'müller', 'nurul a/p samy', "o'brien", 'ஆதி', '٣',
        ]))


class TestNormResultsDoc(_Table):
    """Accent-FOLD (NFKD, combining marks dropped), upper-case, non-alphanumerics to one space.
    The only one of the four that folds rather than deletes: 'Café' → 'CAFE', not 'CAF'. Every
    genuineness marker probe in the package is matched through it."""

    def test_the_table(self):
        self.check(_fn(results_doc, '_norm_fold_upper_alnum', '_norm'), _norm_table([
            '', '', '', 'ABC', 'ABC DEF', 'A B C', 'AHMAD BIN ALI', 'CAFE',
            'AEIOU', 'ABC123', '123', 'A B', 'X',
            'MULLER', 'NURUL A P SAMY', 'O BRIEN', '', '',
        ]))

    def test_the_four_disagree_on_the_same_string(self):
        """The single row that makes merging them indefensible. One string, four answers."""
        self.assertEqual(
            [_fn(academic_engine, '_norm_lower_alnum', '_norm')('Café 2'),
             _fn(bc_parse, '_norm_letters_upper', '_norm')('Café 2'),
             _fn(funding_estimate, '_norm_strip_lower', '_norm')('Café 2'),
             _fn(results_doc, '_norm_fold_upper_alnum', '_norm')('Café 2')],
            ['caf 2', 'CAF', 'café 2', 'CAFE 2'])


# ── `_digits` ×3 ─────────────────────────────────────────────────────────────────────────────

_DIGIT_INPUTS = [None, '', '  ', 'abc', '123', 'a1b2c3', '012345', '080805-08-1489',
                 'RM1,234.56', 0, False]
_DIGIT_COMMON = ['', '', '', '', '123', '123', '012345', '080805081489', '123456', '', '']


class TestDigitsOfferParse(_Table):
    """`offer_parse`: fed arbitrary OCR text from an offer letter, on the way to an NRIC. Uses
    `re.sub(r'\\D', ...)`, so it keeps exactly the Unicode DECIMAL digits and nothing else."""

    def test_the_shared_table(self):
        self.check(_fn(offer_parse, '_decimal_digits', '_digits'),
                   list(zip(_DIGIT_INPUTS, _DIGIT_COMMON)))

    def test_where_it_differs_from_the_other_two(self):
        """The two differences H7 had to decide about, pinned as they are today.

        ONE: a non-string raises. TWO: `\\D` and `str.isdigit()` do not agree on characters that
        are digit-LIKE without being decimal digits. A superscript is a digit to `str.isdigit()`
        and not to `\\d`; an Arabic-Indic digit is both. The second difference is why this one is
        NOT merged with the other two: its input is raw OCR text, and an identity number is the
        wrong place to keep a character that only looks like a digit."""
        digits = _fn(offer_parse, '_decimal_digits', '_digits')
        self.assertEqual(digits('٣'), '٣')       # Arabic-Indic 3 — a decimal digit
        self.assertEqual(digits('³'), '')             # superscript 3 — NOT a decimal digit
        for value in (12, 12.5, Decimal('12'), True, ['1', '2']):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypeError):
                    digits(value)


class TestDigitsVircleAirtable(_Table):
    """`vircle_airtable`: an NRIC or wallet id out of a record. `str()`-coerces first (the
    defensive one) and filters on `str.isdigit()`."""

    def test_the_shared_table(self):
        self.check(_fn(vircle_airtable, 'digits_only', '_digits'),
                   list(zip(_DIGIT_INPUTS, _DIGIT_COMMON)))

    def test_where_it_differs_from_offer_parse(self):
        digits = _fn(vircle_airtable, 'digits_only', '_digits')
        self.assertEqual(digits('٣'), '٣')
        self.assertEqual(digits('³'), '³')       # kept here, dropped by offer_parse
        self.assertEqual([digits(12), digits(12.5), digits(Decimal('12')), digits(True)],
                         ['12', '125', '12', ''])


class TestDigitsVircleImport(_Table):
    """`import_vircle_csv`: the same filter as `vircle_airtable`, which is why H7 merged the two.

    ⚠ ONE DELIBERATE WIDENING, and the only behaviour this sprint changed anywhere. Before H7 this
    copy lacked the `str()` coercion, so a non-string input raised `TypeError`. Its three call
    sites pass a CSV cell (`str` or `None`) and a profile NRIC (`str`), so no caller could reach
    that branch — and the surviving copy is the tolerant one on purpose, because this runs inside
    a whole-file import where a crash costs the whole file's progress. That one assertion was
    therefore dropped from this table when the merge was made; every OTHER row is untouched, and
    the Unicode rows below are the ones that decided WHICH copy survived."""

    def test_the_shared_table(self):
        self.check(_fn(import_vircle_csv, 'digits_only', '_digits'),
                   list(zip(_DIGIT_INPUTS, _DIGIT_COMMON)))

    def test_where_it_differs_from_the_other_two(self):
        digits = _fn(import_vircle_csv, 'digits_only', '_digits')
        self.assertEqual(digits('٣'), '٣')
        self.assertEqual(digits('³'), '³')


# ── `_ids` ×4: byte-identical in four management commands ────────────────────────────────────

_IDS_TABLE = [
    (None, []), ('', []), (' ', []), ('1,2,3', [1, 2, 3]), ('1, 2, 3', [1, 2, 3]),
    ('a,2', [2]), ('0,1', [0, 1]), ('1;2', []), (' 7 ', [7]), ('1,,2', [1, 2]),
    ('03', [3]), (12, [12]),
    # Pinned surprise: a MINUS sign is not a digit, so '-1' is silently dropped rather than
    # read as -1 or refused. Every one of the four behaves this way.
    ('-1,2', [2]),
]


class TestIdsInEveryCommand(_Table):

    def test_all_four_commands_agree_exactly(self):
        for module in (award_students_batch, send_award_offer_emails,
                       send_sign_invitation_emails, send_vircle_install_emails):
            with self.subTest(module=module.__name__):
                self.check(_fn(module, 'id_list', '_ids'), _IDS_TABLE)


# ── The genuineness marker helpers ───────────────────────────────────────────────────────────

class TestAnyTokenInEveryDocModule(_Table):
    """`_any` is byte-identical in all four doc modules and reads the SAME normaliser out of
    `results_doc` — a true duplicate with no contract to preserve but its own."""

    def test_all_four_agree_exactly(self):
        text = results_doc._norm('Tenaga Nasional  Café No. Akaun') \
            if hasattr(results_doc, '_norm') else \
            results_doc._norm_fold_upper_alnum('Tenaga Nasional  Café No. Akaun')
        for module in (electricity_doc, salary_doc, school_leaving_doc, water_doc):
            with self.subTest(module=module.__name__):
                any_token = _fn(module, '_any_token', '_any')
                self.assertIs(any_token(['TENAGA NASIONAL'], text), True)
                self.assertIs(any_token(['CAFE'], text), True)       # folded, so it matches
                self.assertIs(any_token(['CAFÉ'], text), True)  # …and so does the accented probe
                self.assertIs(any_token(['SYABAS'], text), False)
                self.assertIs(any_token([], text), False)
                self.assertIs(any_token(['NO AKAUN', 'SYABAS'], text), True)


class TestScoreMarkersAreThreeDifferentContracts(SimpleTestCase):
    """Three functions, one name, three different dictionaries. Nothing is shared but the name,
    so H7 gives each the name of the document it scores (following `salary_doc.score_family`,
    which already had one)."""

    def test_electricity(self):
        score = _fn(electricity_doc, 'score_electricity_markers', 'score_markers')
        self.assertEqual(
            score('TNB No. Akaun Caj Semasa Tarikh Bil Tarif Kegunaan kWj'),
            {'issuer': 'tnb', 'labels': 5, 'electricity': True, 'water': False, 'mykad': False})
        self.assertEqual(
            score(''),
            {'issuer': '', 'labels': 0, 'electricity': False, 'water': False, 'mykad': False})

    def test_water(self):
        score = _fn(water_doc, 'score_water_markers', 'score_markers')
        self.assertEqual(
            score('AIR SELANGOR No. Akaun Tunggakan Tarif Jumlah Perlu Dibayar meter padu'),
            # `water` is False here and that is correct: 'AIR SELANGOR' is an OPERATOR marker,
            # not one of the water TERMS, and the two tallies are deliberately separate.
            {'operator': 'air_selangor', 'labels': 4, 'water': False, 'm3': True,
             'electricity': False, 'mykad': False})

    def test_school_leaving(self):
        score = _fn(school_leaving_doc, 'score_school_leaving_markers', 'score_markers')
        out = score('SIJIL BERHENTI SEKOLAH MENENGAH KEBANGSAAN Nama Penuh Tarikh Lahir')
        self.assertEqual(sorted(out), ['label_names', 'labels', 'leaver', 'mykad', 'school',
                                       'title'])
        self.assertIs(out['title'], True)
        self.assertIs(out['school'], True)
        self.assertIs(out['mykad'], False)

    def test_the_three_return_different_key_sets(self):
        keys = [
            sorted(_fn(electricity_doc, 'score_electricity_markers', 'score_markers')('x')),
            sorted(_fn(water_doc, 'score_water_markers', 'score_markers')('x')),
            sorted(_fn(school_leaving_doc, 'score_school_leaving_markers', 'score_markers')('x')),
        ]
        self.assertEqual(len(set(map(tuple, keys))), 3,
                         'three contracts wearing one name — if they ever agree, revisit H7')


# ── `_gemini_generate` ×3 ────────────────────────────────────────────────────────────────────

class _Response:
    text = 'the model said this'
    usage_metadata = None


class _Models:
    def __init__(self, sink):
        self._sink = sink

    def generate_content(self, model, contents):
        self._sink['model'] = model
        self._sink['contents'] = contents
        return _Response()


class _Client:
    def __init__(self, sink):
        self.models = _Models(sink)


class TestGeminiSeams(SimpleTestCase):
    """Three copies of one skeleton: key check → import → single call → meter → `.text`. What is
    NOT shared is the refusal each one raises, and `contracts`' optional `images`. H7 keeps all
    three names (every test in the suite patches them by name) and every refusal exactly."""

    SEAMS = (
        (apply_copy_draft, apply_copy_draft.DraftError, 'ai_unconfigured', 'ai_unavailable'),
        (sponsor_terms, sponsor_terms.SponsorTermsError, 'quiz_ai_unconfigured',
         'quiz_ai_unavailable'),
        (contracts, contracts.ContractsError, 'quiz_ai_unconfigured', 'quiz_ai_unavailable'),
    )

    @override_settings(GEMINI_API_KEY='')
    def test_no_key_raises_each_modules_own_error_with_its_own_code(self):
        for module, exc, unconfigured, _unavailable in self.SEAMS:
            with self.subTest(module=module.__name__):
                with self.assertRaises(exc) as caught:
                    module._gemini_generate('a prompt', 'gemini-2.5-flash')
                self.assertEqual(caught.exception.code, unconfigured)

    @override_settings(GEMINI_API_KEY='k')
    def test_a_text_only_call_sends_the_bare_prompt_and_meters_it(self):
        from apps.scholarship import usage
        for module, _exc, _u, _a in self.SEAMS:
            with self.subTest(module=module.__name__):
                sink = {}
                with patch('google.genai.Client', return_value=_Client(sink)), \
                        patch.object(usage, 'record_usage') as meter:
                    out = module._gemini_generate('just text', 'gemini-2.5-pro')
                self.assertEqual(out, 'the model said this')
                self.assertEqual(sink['contents'], 'just text',
                                 'a text-only call must not become a parts list')
                self.assertEqual(sink['model'], 'gemini-2.5-pro')
                self.assertEqual(meter.call_count, 1)
                self.assertEqual(meter.call_args.args, (usage.GEMINI,))
                self.assertEqual(meter.call_args.kwargs['model'], 'gemini-2.5-pro')

    @override_settings(GEMINI_API_KEY='k')
    def test_only_contracts_takes_images_and_puts_them_before_the_prompt(self):
        from apps.scholarship import usage
        sink = {}
        with patch('google.genai.Client', return_value=_Client(sink)), \
                patch.object(usage, 'record_usage'):
            contracts._gemini_generate('the instructions', 'gemini-2.5-pro',
                                       images=[(b'\x89PNG', 'image/png')])
        self.assertEqual(len(sink['contents']), 2)
        self.assertEqual(sink['contents'][-1], 'the instructions',
                         'the prompt follows the evidence — vision._call_gemini_json order')
        for module, _exc, _u, _a in self.SEAMS[:2]:
            with self.subTest(module=module.__name__):
                with self.assertRaises(TypeError):
                    module._gemini_generate('p', 'm', images=[(b'x', 'image/png')])


# ── The one asymmetry H7 reported and TD-261 closed ──────────────────────────────────────────

class _Template:
    def __init__(self, subject, body):
        self.subject, self.body = subject, body


class TestStructuralTokenLeak(SimpleTestCase):
    """⚠ H7-FINDING 5, FIXED by TD-261 on 2026-09-19. `partner_comms.render` gives every
    structural token its kind DECLARES an empty `('', '')` block, so a caller that omits one
    cannot leave a literal `{token}` in an inbox. `sponsor_comms.render` had no such line; it
    has the same three now.

    The two halves the finding established are both kept: the render layer no longer leaks, and
    no production path ever omitted the block in the first place."""

    def test_the_sponsor_renderer_renders_a_missing_block_as_nothing(self):
        template = _Template('Your students', 'Hello {sponsor_name}\n\n{student_cards}\n\nBye')
        _subject, text, html = sponsor_comms.render(
            'new_students', template, {'sponsor_name': 'Ravi'})
        self.assertNotIn('{student_cards}', text)
        self.assertNotIn('{student_cards}', html)
        # …and the rest of the letter is untouched. The empty block still occupies its slot in
        # the text join (hence the wider gap) and contributes nothing to the html — byte for
        # byte what `partner_comms.render` has always produced for an omitted block, which is
        # the point: the two families now answer the same way.
        self.assertEqual(text, 'Hello Ravi\n\n\n\nBye')
        self.assertEqual(html, '<p style="margin:0 0 14px;">Hello Ravi</p>'
                               '<p style="margin:0 0 14px;">Bye</p>')

    def test_the_sponsor_renderer_does_not_leak_it_into_the_subject_line_either(self):
        template = _Template('{student_cards} for you', 'Hello {sponsor_name}')
        subject, _text, _html = sponsor_comms.render(
            'new_students', template, {'sponsor_name': 'Ravi'})
        self.assertNotIn('{student_cards}', subject)
        self.assertEqual(subject, ' for you')

    def test_a_declared_and_supplied_block_still_renders_exactly_as_before(self):
        """The other half of the defaulting: filling the gap must not touch the filled case. The
        card builder is stubbed because it reads an organisation's card cap and the tax-name map;
        what is under test here is where the block LANDS, not what a card looks like."""
        template = _Template('{student_cards} for you',
                             'Hello {sponsor_name}\n\n{student_cards}\n\nBye')
        with patch.object(sponsor_comms, 'student_cards_blocks',
                          return_value=('<p>CARDS</p>', 'CARDS')) as build:
            subject, text, html = sponsor_comms.render(
                'new_students', template, {'sponsor_name': 'Ravi', 'cards': [{'ref': 'A1'}]})
        self.assertEqual(build.call_count, 1)
        self.assertEqual(subject, 'CARDS for you')
        self.assertEqual(text, 'Hello Ravi\n\nCARDS\n\nBye')
        self.assertIn('<p>CARDS</p>', html)

    def test_the_partner_renderer_does_not(self):
        """The same shape on the other family: the declared token renders as nothing at all."""
        from apps.scholarship import partner_comms
        kind = next(k for k, tokens in partner_comms.PLACEHOLDERS.items()
                    if any(t in partner_comms.STRUCTURAL_TOKENS for t in tokens))
        token = next(t for t in partner_comms.PLACEHOLDERS[kind]
                     if t in partner_comms.STRUCTURAL_TOKENS)
        template = _Template('A subject', 'Hello\n\n{%s}\n\nBye' % token)
        _subject, text, html = partner_comms.render(kind, template, {})
        self.assertNotIn('{%s}' % token, text)
        self.assertNotIn('{%s}' % token, html)

    def test_no_production_path_ever_omitted_the_block_in_the_first_place(self):
        """Why H7-FINDING 5 was a latent gap and not an incident, kept as the record — and kept
        as a live guard, because the defaulting above is the second line of defence, not the
        first. `{student_cards}` is allowed in exactly two kinds; both are sent only by
        `sponsor_notify.send_student_alert`, which returns before rendering when it has no cards
        and always puts them in the context when it has. The save-time allowlist keeps the token
        out of every other kind's template."""
        from apps.scholarship import sponsor_notify
        allowed = {kind for kind, tokens in sponsor_comms.PLACEHOLDERS.items()
                   if 'student_cards' in tokens}
        self.assertEqual(allowed, {'new_students', 'weekly_digest'})
        for kind in sponsor_comms.KINDS:
            if kind not in allowed:
                with self.subTest(kind=kind):
                    self.assertEqual(
                        sponsor_comms.unknown_placeholders(kind, '', '{student_cards}'),
                        ('student_cards',),
                        'a template of this kind cannot be saved carrying the token')
        with patch.object(sponsor_notify, '_safe') as delivered:
            self.assertIs(sponsor_notify.send_student_alert(object(), []), False)
        self.assertFalse(delivered.called, 'no cards → no send, so no render')


if __name__ == '__main__':          # pragma: no cover - parity with the other test modules
    unittest.main()
