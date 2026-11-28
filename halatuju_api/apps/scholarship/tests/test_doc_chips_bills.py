"""Chip Sprint 2 (owner 2026-11-28): the water and electricity bills on the one chip standard.

Officer and student both see Type, Name, Address, Date, then the amount as a plain value. Reasonable
and Outstanding are no longer chips. Every amber / red STUDENT bill chip says what the student does.
All values here are invented.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.scholarship import doc_chips as O, doc_chips_student as S
from apps.scholarship.eval import chip_dry_run
from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
from apps.scholarship.tests.factories import create_document, make_application

HOLDER = 'SAMPLE HOLDER'


def bill(doc_type='water_bill', auth=None, **check):
    c = {'name': HOLDER, 'name_note': '', 'address': 'SAMPLE ADDRESS 1', 'address_status': 'found',
         'current_status': 'current', 'monthly_bill': '', 'unpaid_balance': ''}
    c.update(check)
    doc = {'id': 1, 'doc_type': doc_type, 'utility_check': c}
    if auth:
        doc['authenticity'] = {'status': auth, 'reason': '', 'doc_seen': ''}
    return doc


def states(chips):
    return {c['key']: c['state'] for c in chips}


class OfficerBillChipTests(SimpleTestCase):
    def test_the_order_is_type_name_address_date_then_the_amount(self):
        chips = O.chips_for(bill(auth='suspect', monthly_bill='84.20'))
        self.assertEqual([c['key'] for c in chips], ['type', 'name', 'address', 'date', 'amount'])
        self.assertEqual(chips[-1], {'key': 'amount', 'status': 'unknown', 'state': 'grey',
                                     'student_action': 'none', 'reason': 'read', 'kind': 'plain',
                                     'value': '84.20'})

    def test_every_address_word(self):
        for word, want in (('found', 'green'), ('mismatch', 'red'), ('unconfirmed', 'amber'),
                           ('unreadable', 'amber'), ('not_found', 'amber'), ('', 'grey'), (None, 'grey')):
            with self.subTest(word=word):
                self.assertEqual(states(O.chips_for(bill(address_status=word)))['address'], want)

    def test_every_date_word_and_unknown_is_amber(self):
        for word, want in (('current', 'green'), ('ageing', 'amber'), ('stale', 'red'),
                           ('unknown', 'amber'), ('', 'amber'), (None, 'amber'), (['x'], 'amber')):
            with self.subTest(word=word):
                chip = [c for c in O.chips_for(bill(current_status=word)) if c['key'] == 'date'][0]
                self.assertEqual(chip['state'], want)
                if want == 'amber' and word != 'ageing':
                    self.assertEqual(chip['reason'], 'unknown')

    def test_the_name_cases(self):
        self.assertEqual(states(O.chips_for(bill()))['name'], 'green')
        self.assertEqual(states(O.chips_for(bill(name='')))['name'], 'grey')
        self.assertEqual(states(O.chips_for(bill(name=None)))['name'], 'grey')
        self.assertEqual(states(O.chips_for(bill(name_note='unrelated')))['name'], 'red')
        # 'unrelated' wins even if the engine also served a name
        self.assertEqual(states(O.chips_for(bill(name='', name_note='unrelated')))['name'], 'red')

    def test_known_gap_name_is_green_with_nothing_to_compare(self):
        """PINNED EDGE, see docs/document-chip-standard.md "Known gaps" (Name with no reference name).
        The engine serves name_note '' both when the holder matches the family AND when there was no
        reference name to compare (a student profile with no name). The chip cannot tell them apart,
        so it shows green. A later fix that tells them apart should make this test fail on purpose."""
        nothing_to_compare = bill(name=HOLDER, name_note='')
        self.assertEqual(states(O.chips_for(nothing_to_compare))['name'], 'green')

    def test_a_wrong_type_caps_name_address_and_date_red_and_drops_the_amount(self):
        chips = O.chips_for(bill(auth='not_water_bill', monthly_bill='84.20'))
        self.assertEqual([(c['key'], c['state'], c['reason']) for c in chips],
                         [('type', 'red', 'not_water_bill'), ('name', 'red', 'not_water_bill'),
                          ('address', 'red', 'not_water_bill'), ('date', 'red', 'not_water_bill')])
        self.assertEqual(O.pill_for(chips), 'problem')

    def test_reasonable_and_outstanding_are_no_longer_chips(self):
        keys = {c['key'] for c in O.chips_for(bill(reasonable_status='high', outstanding_status='arrears'))}
        self.assertFalse(keys & {'reasonable', 'outstanding', 'current', 'ageing', 'stale'})

    def test_the_amount_never_counts_in_the_pill(self):
        self.assertEqual(O.pill_for(O.chips_for(bill(monthly_bill='84.20'))), 'verified')

    def test_no_name_or_address_is_ever_a_chip_value(self):
        for chip in O.chips_for(bill(monthly_bill='84.20')) + S.chips_for(bill(monthly_bill='84.20')):
            self.assertNotIn(HOLDER, str(chip))
            self.assertNotIn('SAMPLE ADDRESS', str(chip))


class StudentBillChipTests(SimpleTestCase):
    def actions(self, doc):
        return {c['key']: (c['state'], c['student_action']) for c in S.chips_for(doc)}

    def test_the_student_sees_the_officer_colours(self):
        for doc in (bill(), bill(address_status='not_found'), bill(name_note='unrelated', current_status='stale'),
                    bill(auth='not_electricity_bill', doc_type='electricity_bill'), bill(auth='suspect')):
            with self.subTest(doc=doc['utility_check']):
                officer = {c['key']: c['state'] for c in O.chips_for(doc) if c['kind'] == 'fact'}
                student = {c['key']: c['state'] for c in S.chips_for(doc) if c['kind'] == 'fact'}
                self.assertEqual(student, officer)

    def test_the_action_table(self):
        self.assertEqual(self.actions(bill(name_note='unrelated'))['name'], ('red', 'fix_entry'))
        self.assertEqual(self.actions(bill(address_status='mismatch'))['address'], ('red', 'fix_entry'))
        for word in ('unconfirmed', 'unreadable', 'not_found'):
            self.assertEqual(self.actions(bill(address_status=word))['address'], ('amber', 'we_check'))
        self.assertEqual(self.actions(bill(current_status='stale'))['date'], ('red', 'add_doc'))
        self.assertEqual(self.actions(bill(current_status='ageing'))['date'], ('amber', 'add_doc'))
        self.assertEqual(self.actions(bill(current_status='unknown'))['date'], ('amber', 'reupload'))
        self.assertEqual(self.actions(bill(auth='suspect'))['type'], ('amber', 'reupload'))
        capped = self.actions(bill(auth='not_water_bill'))
        self.assertEqual(set(capped.values()), {('red', 'reupload')})

    def test_every_amber_or_red_chip_asks_and_every_other_chip_does_not(self):
        docs = [bill(address_status=a, current_status=d, name_note=n, auth=g, monthly_bill='30.00')
                for a in ('found', 'mismatch', 'unconfirmed', 'not_found', '')
                for d in ('current', 'ageing', 'stale', 'unknown')
                for n in ('', 'unrelated')
                for g in (None, 'suspect', 'not_water_bill', 'final_owed')]
        for doc in docs:
            for chip in S.chips_for(doc):
                with self.subTest(doc=doc['utility_check'], key=chip['key']):
                    if chip['state'] in ('amber', 'red'):
                        self.assertNotEqual(chip['student_action'], 'none')
                    else:
                        self.assertEqual(chip['student_action'], 'none')
                    self.assertIn(chip['student_action'], O.STUDENT_ACTIONS)

    def test_labels_are_the_field_names(self):
        labels = [c['label'] for c in S.chips_for(bill(auth='suspect', monthly_bill='30.00'))]
        self.assertEqual(labels, ['scholarship.docs.utilityCheck.type', 'scholarship.docs.utilityCheck.name',
                                  'scholarship.docs.utilityCheck.address', 'scholarship.docs.utilityCheck.date',
                                  'scholarship.docs.incomeProofCheck.fromDoc'])

    def test_the_type_chip_replaces_the_genuineness_note_but_a_bill_with_no_check_keeps_it(self):
        self.assertNotIn('note', {c['kind'] for c in S.chips_for(bill(auth='suspect'))})
        no_check = {'id': 1, 'doc_type': 'water_bill', 'utility_check': None,
                    'authenticity': {'status': 'suspect', 'reason': '', 'doc_seen': ''}}
        self.assertEqual([c['kind'] for c in S.chips_for(no_check)], ['note'])


def _sprint1_officer(payload):
    """The officer bill chips BEFORE Sprint 2 (address, current, reasonable), frozen for the dry run."""
    if payload.get('doc_type') not in ('water_bill', 'electricity_bill'):
        return O.chips_for(payload)
    c = payload.get('utility_check') or {}
    addr = O.STATES[O._address_status(c.get('address_status'))]
    cur = {'current': 'green', 'ageing': 'amber', 'stale': 'red'}.get(c.get('current_status'), 'grey')
    rsn = {'reasonable': 'green', 'high': 'amber'}.get(c.get('reasonable_status'), 'grey')
    return [{'key': 'address', 'state': addr, 'kind': 'fact'}, {'key': 'current', 'state': cur, 'kind': 'fact'},
            {'key': 'reasonable', 'state': rsn, 'kind': 'fact'}]


class BillDryRunTests(TestCase):
    def test_no_band_changes_and_the_bill_chips_that_change_are_counted(self):
        app = make_application()
        create_document(app, 'water_bill', storage_path='s')
        served = {'name': HOLDER, 'name_note': '', 'address': 'SAMPLE ADDRESS 1', 'address_status': 'found',
                  'current_status': 'current', 'monthly_bill': '84.20', 'unpaid_balance': '',
                  'reasonable_status': 'reasonable', 'outstanding_status': '', 'bill_month': '',
                  'reasonable_detail': ''}
        with mock.patch.object(ApplicantDocumentSerializer, 'get_utility_check', lambda self, obj: served):
            result = chip_dry_run.run_dry(old=_sprint1_officer, allow_sqlite=True)
        self.assertTrue(result['bands_identical'])
        row = result['per_type']['water_bill']
        # old address/current/reasonable vs new name/address/date/amount, key by key: all 4 positions move
        self.assertEqual(row['state_changed'], 4)
        self.assertEqual(row['pill_changed'], 0)                     # verified both before and after
        self.assertEqual(row['problem_pills'], 0)
