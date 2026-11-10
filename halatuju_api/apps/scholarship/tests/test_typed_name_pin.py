"""Pins the two live "typed name equals actual name" checks (audit RD-09, A3.11).

The audit counted three copies. There are two implementations: `letters.names_match` (letter
confirm) and `payments._name_matches` (payment-run and wallet-credit sign-off; `sign_admin_credit`
and `payments_chain.sign` both call it). They are NOT identical - the letter check collapses runs of
whitespace, the payment check only strips the ends - so they were left unmerged. This table pins
each one's answer for every pair so a future merge has to be a decision, not an accident.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship import letters, payments

#: (typed, actual, letters.names_match, payments._name_matches)
PAIRS = [
    ('Siti Nur binti Ahmad', 'Siti Nur binti Ahmad', True, True),
    ('siti nur binti ahmad', 'Siti Nur Binti Ahmad', True, True),
    ('  Siti Nur binti Ahmad  ', 'Siti Nur binti Ahmad', True, True),
    ('Siti Nur binti Ahmad', 'Siti Nur bt Ahmad', False, False),
    ('Siti Nur', 'Siti Nur binti Ahmad', False, False),
    ('Ahmad bin Ali', 'Ali bin Ahmad', False, False),
    ('Muthu A/L Raman', 'Muthu a/l Raman', True, True),
    ('Muthu A/L Raman', 'Muthu A/P Raman', False, False),
    ('Muthu A/L Raman', 'Muthu AL Raman', False, False),
    ('Priya a/p Kumar.', 'Priya a/p Kumar', False, False),
    ('Tan  Wei   Ming', 'Tan Wei Ming', True, False),     # internal runs of spaces: the two differ
    ('Tan Wei Ming', 'Tan  Wei Ming', True, False),       # internal runs of spaces: the two differ
    ('Tan\tWei Ming', 'Tan Wei Ming', True, False),       # a tab inside: the two differ
    ('TAN WEI MING', 'tan wei ming', True, True),
    ('Lim Mei-Ling', 'Lim Mei Ling', False, False),
    ('\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb0\u0bbe\u0bae\u0ba9\u0bcd',
     '\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb0\u0bbe\u0bae\u0ba9\u0bcd', True, True),
    ('\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1  \u0bb0\u0bbe\u0bae\u0ba9\u0bcd',
     '\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb0\u0bbe\u0bae\u0ba9\u0bcd', True, False),
    ('\u9648\u5927\u6587', '\u9648\u5927\u6587', True, True),
    ('\u9648 \u5927\u6587', '\u9648\u5927\u6587', False, False),
    ('Stra\u00dfe', 'STRASSE', True, True),                 # casefold folds sharp s in both
    ('', 'Siti', False, False),
    ('Siti', '', False, False),
    ('', '', False, False),
    ('   ', '   ', False, False),
    (None, 'Siti', False, False),
    ('Siti', None, False, False),
    (None, None, False, False),
]


class TypedNamePin(SimpleTestCase):
    def test_letters_names_match(self):
        for typed, actual, want, _ in PAIRS:
            with self.subTest(typed=typed, actual=actual):
                self.assertIs(letters.names_match(typed, actual), want)

    def test_payments_name_matches(self):
        for typed, actual, _, want in PAIRS:
            with self.subTest(typed=typed, actual=actual):
                self.assertIs(payments._name_matches(SimpleNamespace(name=actual), typed), want)
