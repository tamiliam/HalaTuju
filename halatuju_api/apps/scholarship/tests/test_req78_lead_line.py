"""Request #78, Part D: each tile leads with the item that decides its band.

The owner's rule (after the 17 Nov Academic fix and #804): the tile's top line is the item that sets
the band. On the STR route the earner-IC and relationship items are appended to `review` BEFORE the
STR's own item, so when the STR alone puts income at Unsure (`str_unsure` / `str_mismatch` in
`_place_income_verdict`) the tile used to lead with the relationship line. The case-177 shape: the STR
uploaded is next year's application status (`str_not_current`, status `future`) and the relationship is
also in question. The STR line now leads; the server orders the items, so every reader agrees.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import income_engine, verdict_income_str
from apps.scholarship.tests.package_patch import patch_engine


def _str_check(status='current', name='match', nric='match'):
    return {'current_status': status, 'name_status': name, 'nric_status': nric}


def _income(str_check, *, rel='mismatch', earner='mother'):
    """The STR route's income fact, with only the reads stubbed: the earner's IC reads, the
    relationship step returns `rel` (appending its real item), and the STR reads as `str_check`."""
    def relationship(application, earner, student_name, name, deferred, present, evidence, gap, review,
                     ic_nric=''):
        if rel == 'mismatch':
            review.append(verdict_income_str._item('birth_cert_mismatch'))
        return rel
    with mock.patch.object(verdict_income_str, '_earner_ic', return_value=('A NAME', False, '')), \
            mock.patch.object(verdict_income_str, '_earner_relationship', side_effect=relationship), \
            patch_engine(income_engine, 'student_str_check', return_value=str_check), \
            mock.patch.object(verdict_income_str._ve, '_stronger_income_fact',
                              side_effect=lambda current, *a, **k: current):
        return verdict_income_str.str_route_income_fact(
            SimpleNamespace(), earner, SimpleNamespace(doc_type='str'), 'A STUDENT', set(), [], None)


def _codes(fact):
    return [i['code'] for i in fact['unresolved']]


class TestTheStrItemLeadsWhenItSetsTheBand(SimpleTestCase):

    def test_case_177_shape_next_years_str_leads_the_relationship_line(self):
        fact = _income(_str_check('future'))
        self.assertEqual(fact['status'], 'recommend')
        self.assertEqual(_codes(fact), ['str_not_current', 'birth_cert_mismatch'])
        self.assertEqual(fact['unresolved'][0]['params'], {'status': 'future'})

    def test_every_unsure_str_state_leads(self):
        for status in ('stale', 'future', 'unreadable'):
            with self.subTest(status=status):
                self.assertEqual(_codes(_income(_str_check(status))), ['str_not_current', 'birth_cert_mismatch'])

    def test_an_str_in_someone_elses_name_leads(self):
        fact = _income(_str_check(name='mismatch'))
        self.assertEqual(fact['status'], 'recommend')
        self.assertEqual(_codes(fact), ['str_recipient_mismatch', 'birth_cert_mismatch'])

    def test_an_unknown_str_read_leads_with_its_own_item(self):
        """'unknown' (not read yet) bands Unsure too; its item is the unverified-STR line."""
        fact = _income(_str_check('unknown', name='', nric=''))
        self.assertEqual(_codes(fact), ['str_present_unverified', 'birth_cert_mismatch'])

    def test_a_blue_review_keeps_its_order(self):
        """A current STR with the relationship open is a BLUE review that no single item sets: the order
        is untouched (the relationship line still leads, as before)."""
        fact = _income(_str_check('unconfirmed'))
        self.assertEqual(fact['status'], 'review')
        self.assertEqual(_codes(fact), ['birth_cert_mismatch', 'str_not_current'])

    def test_no_relationship_item_nothing_to_move(self):
        fact = _income(_str_check('future'), rel='match')
        self.assertEqual(_codes(fact), ['str_not_current'])
