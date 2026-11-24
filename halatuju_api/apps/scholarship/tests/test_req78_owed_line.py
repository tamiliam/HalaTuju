"""Request #78, Part C: the owed line for a red parent IC names the check that failed.

A parent IC's check carries three person keys (`doc_red_keys.PERSON_RED_KEYS['parent_ic']`):
`name_status` is the LINK to the student (the birth certificate, the guardianship letter, or the
father's name in the student's own name); `proof_name_status` / `proof_nric_status` compare the card
with the income proof. Before this sprint every one of them owed the same line, "it doesn't match
their income documents", which blamed the card for a broken link (the case-177 shape).

Pinned here, through the real gate (`document_red_blockers`) with only its reads stubbed:
  * link alone, mother / guardian       -> `parent_link_mismatch`
  * link alone, father / brother / sister -> `parent_name_link_mismatch`
  * a proof key (alone)                 -> `parent_ic_person_mismatch`, as before
  * link AND a proof key                -> `parent_ic_person_mismatch` only (the card first)
The Action Centre still reads every one of these as red (the drift test's agreement holds), and a link
code opens the birth certificate and guardianship letter slots as well as the card's.
"""
import contextlib
import importlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import income_engine, resolution
from apps.scholarship.services import blockers
from apps.scholarship.tests.package_patch import patch_engine

cb = importlib.import_module('apps.scholarship.services.consent_blockers')   # the module, not the re-export
KEYS = ('name_status', 'proof_name_status', 'proof_nric_status')


def _doc(member, doc_type='parent_ic', doc_id=1):
    return SimpleNamespace(
        id=doc_id, doc_type=doc_type, household_member=member, request_code='', vision_run_at='2026-11-23',
        vision_error='', vision_fields={'student_verdict': 'ok'}, vision_nric='', vision_name='',
        application=SimpleNamespace(profile=None))


def _check(member, *red):
    return {**{k: 'match' for k in KEYS}, **{k: 'mismatch' for k in red}, 'member': member, 'readable': True}


def _read(member, *red):
    """(gate codes, Action Centre verdict) for one parent IC of `member` red on the keys `red`."""
    doc = _doc(member)
    app = SimpleNamespace(income_route='salary', income_earner=member)
    with patch_engine(income_engine, 'student_income_ic_check', return_value=_check(member, *red)), \
            patch_engine(income_engine, 'income_established', return_value=False), \
            patch_engine(income_engine, 'working_members', return_value=[member]), \
            mock.patch.object(blockers, 'live_docs', return_value=[doc]):
        return sorted(blockers.document_red_blockers(app)), resolution.doc_match_verdict(doc)


class TestTheOwedLineNamesTheCheck(SimpleTestCase):

    def test_a_link_red_alone_on_a_mother_or_guardian_names_the_certificate_or_letter(self):
        for member in ('mother', 'guardian'):
            with self.subTest(member=member):
                self.assertEqual(_read(member, 'name_status'), (['parent_link_mismatch'], 'mismatch'))

    def test_a_link_red_alone_on_a_father_or_sibling_names_the_fathers_name(self):
        for member in ('father', 'brother', 'sister'):
            with self.subTest(member=member):
                self.assertEqual(_read(member, 'name_status'), (['parent_name_link_mismatch'], 'mismatch'))

    def test_a_proof_red_keeps_the_income_documents_line(self):
        for member in ('mother', 'father', 'guardian'):
            for key in ('proof_name_status', 'proof_nric_status'):
                with self.subTest(member=member, key=key):
                    self.assertEqual(_read(member, key), (['parent_ic_person_mismatch'], 'mismatch'))

    def test_link_and_proof_both_red_owe_the_card_line_only(self):
        """Chosen behaviour: a card that matches neither its link nor its proof is most likely the wrong
        person's card, so one line asks for the card; the link line follows if it is still broken."""
        for member in ('mother', 'father', 'guardian'):
            for key in ('proof_name_status', 'proof_nric_status'):
                with self.subTest(member=member, key=key):
                    self.assertEqual(_read(member, 'name_status', key),
                                     (['parent_ic_person_mismatch'], 'mismatch'))

    def test_a_clean_card_owes_nothing(self):
        self.assertEqual(_read('mother'), ([], 'ok'))


class TestTheLinkLineOpensTheLinkDocuments(SimpleTestCase):

    def _slots(self, code):
        card, bc, letter = _doc('mother'), _doc('', 'birth_certificate', 2), _doc('', 'guardianship_letter', 3)

        def live(_app, doc_type=None, doc_types=None, members=None):
            wanted = doc_types or ((doc_type,) if doc_type else None)
            return [d for d in (card, bc, letter) if wanted is None or d.doc_type in wanted]
        with mock.patch.object(cb, 'consent_blockers', return_value=[code]), \
                mock.patch.object(cb, 'document_red_blockers', return_value=[(card, code)]), \
                mock.patch.object(cb, 'document_unreadable_blockers', return_value=[]), \
                mock.patch('apps.scholarship.document_snapshot.live_docs', side_effect=live), \
                mock.patch('apps.scholarship.document_snapshot.snapshot_unless_open',
                           return_value=contextlib.nullcontext()), \
                mock.patch('apps.scholarship.document_replace.slot_members', return_value=[]):
            return cb.consent_blocking_slots(SimpleNamespace())

    def test_a_link_code_opens_the_card_and_both_link_documents(self):
        for code in ('parent_link_mismatch', 'parent_name_link_mismatch'):
            with self.subTest(code=code):
                slots, missing = self._slots(code)
                self.assertEqual(slots, {('parent_ic', 'mother', ''), ('birth_certificate', '', ''),
                                         ('guardianship_letter', '', '')})
                self.assertEqual(missing, set())

    def test_the_card_line_opens_the_card_alone(self):
        slots, _missing = self._slots('parent_ic_person_mismatch')
        self.assertEqual(slots, {('parent_ic', 'mother', '')})
