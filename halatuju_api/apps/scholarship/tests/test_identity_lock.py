"""The IC lock rule — genuine card + exact number + same person (2026-07-29).

The owner's rule, and the three ways it is easy to get wrong. Written against
``apps.scholarship.identity``, which is the ONE home for the question so the padlock, the
student's flag and the lock itself cannot drift apart.

Two of these tests exist because of specific near-misses in this codebase's history:

* ``test_a_card_that_was_never_scored_does_not_lock`` — every other consumer of genuineness
  fails OPEN on an absent verdict (``income_engine`` treats '' as passing). That is right for a
  soft signal and wrong for a one-way lock, and the wrong version would have passed a suite
  where no fixture scores a card.
* ``test_a_misspelling_never_locks`` — there is a tolerant matcher next door built for income
  documents. Using it here is the natural reading of "minor differences are not a blocker" and
  is exactly what must not happen.
"""
from django.test import TestCase

from apps.scholarship import identity


class _Doc:
    """The two OCR columns and the stored genuineness verdict — all the rule reads."""
    def __init__(self, name='', nric='', status='genuine'):
        self.vision_name = name
        self.vision_nric = nric
        self.vision_fields = {'authenticity': {'status': status}} if status is not None else {}


class _Profile:
    def __init__(self, name='', nric=''):
        self.name = name
        self.nric = nric


# Production's shape, taken from application #106 after its correction: a genuine card whose
# name and number both agree with what the student typed. Deliberately a REAL row rather than a
# tidy invention — the Layer 0 lesson is that a suite full of convenient fixtures proves nothing
# about the branch production actually takes.
CARD = 'THARANI A/P A.UDAYA KUMAR'
NRIC = '080722-14-1140'


def _lock(doc, profile):
    return identity.locks_now(identity.compare(doc, profile))


class TestTheLockRule(TestCase):
    def test_genuine_card_exact_number_same_name_locks(self):
        self.assertTrue(_lock(_Doc(CARD, NRIC), _Profile(CARD, NRIC)))

    def test_a_card_that_was_never_scored_does_not_lock(self):
        """An absent verdict means NOT CONFIRMED — never 'confirmed'."""
        never_scored = _Doc(CARD, NRIC, status=None)
        self.assertFalse(_lock(never_scored, _Profile(CARD, NRIC)))
        # …and the ONLY thing standing between it and a lock is the missing verdict.
        self.assertTrue(_lock(_Doc(CARD, NRIC, 'genuine'), _Profile(CARD, NRIC)))

    def test_a_suspect_or_wrong_type_card_does_not_lock(self):
        for status in ('suspect', 'not_ic', 'wrong_type', 'low_confidence'):
            with self.subTest(status=status):
                self.assertFalse(_lock(_Doc(CARD, NRIC, status), _Profile(CARD, NRIC)))

    def test_likely_genuine_counts_as_genuine(self):
        """32 of production's live cards carry this legacy word; `== 'genuine'` would drop them."""
        self.assertTrue(_lock(_Doc(CARD, NRIC, 'likely_genuine'), _Profile(CARD, NRIC)))

    def test_a_wrong_digit_does_not_lock(self):
        """#106's actual defect: the state code typed 11 against a card reading 14."""
        self.assertFalse(_lock(_Doc(CARD, NRIC), _Profile(CARD, '080722-11-1140')))

    def test_a_shorter_name_still_locks(self):
        """A missing middle name is the same person — the owner's 'mild mismatch' case."""
        self.assertTrue(_lock(_Doc(CARD, NRIC), _Profile('THARANI KUMAR', NRIC)))

    def test_a_misspelling_never_locks(self):
        """One letter out might be a different person. The tolerant income-document matcher
        would fold this; identity must not."""
        self.assertFalse(_lock(_Doc('KRISHNAN THACAYAHNI', NRIC),
                               _Profile('KRISHNAN THACHAYAHNI', NRIC)))

    def test_a_different_person_does_not_lock(self):
        self.assertFalse(_lock(_Doc('SITI NURHALIZA BINTI TARUDIN', NRIC),
                               _Profile(CARD, NRIC)))

    def test_no_card_at_all_does_not_lock(self):
        self.assertFalse(_lock(None, _Profile(CARD, NRIC)))
        self.assertFalse(_lock(_Doc('', ''), _Profile(CARD, NRIC)))


class TestWhatTheStudentIsTold(TestCase):
    def test_a_single_digit_slip_is_named_as_one(self):
        """#106 again: the nudge should say 'one digit', not something vague."""
        c = identity.compare(_Doc(CARD, NRIC), _Profile(CARD, '080722-11-1140'))
        self.assertEqual(c['nric'], 'near')
        self.assertIn('nric_one_digit', identity.flags(c))

    def test_a_wholly_different_number_is_flagged_too(self):
        c = identity.compare(_Doc(CARD, NRIC), _Profile(CARD, '990101-05-1234'))
        self.assertEqual(c['nric'], 'mismatch')
        self.assertIn('nric_differs', identity.flags(c))

    def test_a_locked_record_can_still_carry_a_name_flag(self):
        """A shorter name locks AND is flagged — nothing else will ever ask them to align it."""
        c = identity.compare(_Doc(CARD, NRIC), _Profile('THARANI KUMAR', NRIC))
        self.assertTrue(identity.locks_now(c))
        self.assertIn('name_incomplete', identity.flags(c))

    def test_agreement_says_nothing(self):
        self.assertEqual(identity.flags(identity.compare(_Doc(CARD, NRIC), _Profile(CARD, NRIC))), [])

    def test_nothing_to_compare_is_not_a_disagreement(self):
        """No card, or an unread one, must not accuse the student of anything."""
        self.assertEqual(identity.flags(identity.compare(None, _Profile(CARD, NRIC))), [])
        self.assertEqual(identity.flags(identity.compare(_Doc('', ''), _Profile(CARD, NRIC))), [])

    def test_the_card_values_are_reported_for_the_screen(self):
        """The student must be able to SEE what the card says — that is what makes it fixable."""
        c = identity.compare(_Doc(CARD, NRIC), _Profile(CARD, '080722-11-1140'))
        self.assertEqual((c['card_name'], c['card_nric']), (CARD, NRIC))
