"""H7: "I don't have this" on an OPTIONAL Check 2 document ask (`apps/scholarship/optional_asks.py`).

An optional ask takes a reason (+ note) and closes; a required ask refuses it; "Other" needs a note;
Check 2 never re-asks a declined item, however often it re-runs; the reviewer's payload carries the
reason; a declined ask no longer exempts H6's replace cap. Synthetic data only.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import optional_asks
from apps.scholarship.check2_queries import DOC_SPECS, sync_check2_queries
from apps.scholarship.document_replace import ASKED_AGAIN_AT, human_asks
from apps.scholarship.models import ResolutionItem
from apps.scholarship.serializers import ResolutionItemSerializer

from .factories import TEST_JWT_SECRET, authed_client, make_application, make_student


def _item(app, code, **kw):
    spec = DOC_SPECS[code]
    params = {'household_member': spec['member']} if spec.get('member') else {}
    return ResolutionItem.objects.create(
        application=app, source='check2', code=code, fact=spec.get('fact', 'income'), kind='doc',
        doc_type=spec['doc_type'], params=params, **kw)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestDeclineOptionalAsk(TestCase):
    def setUp(self):
        student = make_student()
        self.app = make_application('profile_complete', student=student)
        self.client = authed_client(student.supabase_user_id)

    def _post(self, item, **body):
        return self.client.post(f'/api/v1/scholarship/resolution-items/{item.id}/resolve/', body, format='json')

    def test_the_marker_is_exactly_the_four_optional_asks(self):
        marked = {c for c, s in DOC_SPECS.items() if s.get('optional')}
        self.assertEqual(marked, {
            'father_epf_missing', 'mother_epf_missing', 'guardian_epf_missing', 'brother_epf_missing',
            'sister_epf_missing', 'water_bill_recheck', 'electricity_bill_recheck', 'school_leaving_cert_missing'})
        for code in marked:
            self.assertIn(DOC_SPECS[code]['doc_type'], optional_asks.REASONS)

    def test_every_list_ends_with_other(self):
        for doc_type, reasons in optional_asks.REASONS.items():
            self.assertEqual(list(reasons)[-1], 'other', doc_type)

    def test_an_optional_item_accepts_a_reason_and_closes(self):
        item = _item(self.app, 'electricity_bill_recheck')
        resp = self._post(item, reason='landlord_pays')
        self.assertEqual(resp.status_code, 200, resp.content)
        item.refresh_from_db()
        self.assertEqual((item.status, item.resolved_by), ('resolved', 'student'))
        self.assertEqual(item.params['declined_reason'], 'landlord_pays')
        self.assertEqual(item.resolution_text, '')    # never quoted into an AI prompt as a typed answer

    def test_each_documents_own_list_is_what_it_accepts(self):
        item = _item(self.app, 'water_bill_recheck')
        self.assertEqual(self._post(item, reason='no_supply').status_code, 400)       # an electricity reason
        self.assertEqual(self._post(item, reason='no_water_bill').status_code, 200)
        epf = _item(self.app, 'father_epf_missing')
        self.assertEqual(self._post(epf, reason='abroad').status_code, 200)
        cert = _item(self.app, 'school_leaving_cert_missing')
        self.assertEqual(self._post(cert, reason='cannot_reach_school').status_code, 200)

    def test_an_unknown_reason_is_refused_and_the_item_stays_open(self):
        item = _item(self.app, 'water_bill_recheck')
        resp = self._post(item, reason='because')
        self.assertEqual((resp.status_code, resp.json()['error']), (400, 'invalid_reason'))
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')

    def test_other_needs_a_note(self):
        item = _item(self.app, 'school_leaving_cert_missing')
        for body in ({'reason': 'other'}, {'reason': 'other', 'note': '   '}):
            resp = self._post(item, **body)
            self.assertEqual((resp.status_code, resp.json()['error']), (400, 'note_required'))
        self.assertEqual(self._post(item, reason='other', note='The school closed down.').status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.params['declined_note'], 'The school closed down.')

    def test_a_required_doc_item_still_refuses_a_reason(self):
        item = _item(self.app, 'father_income_proof_missing')
        resp = self._post(item, reason='other', note='no payslip')
        self.assertEqual((resp.status_code, resp.json()['error']), (400, 'reason_not_allowed'))
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')
        self.assertEqual(self._post(item, text='I have none').status_code, 400)       # and text, as before

    def test_a_deprecated_either_or_bill_ask_is_not_optional(self):
        item = _item(self.app, 'utility_bill_missing')
        self.assertEqual(self._post(item, reason='lost_bill').json()['error'], 'reason_not_allowed')

    def test_the_served_item_lists_its_reasons_only_when_optional(self):
        opt = _item(self.app, 'mother_epf_missing')
        req = _item(self.app, 'mother_income_proof_missing')
        self.assertEqual(ResolutionItemSerializer(opt).data['decline_reasons'],
                         ['no_epf_job', 'abroad', 'cannot_get_now', 'not_with_us', 'other'])
        self.assertEqual(ResolutionItemSerializer(req).data['decline_reasons'], [])

    def test_someone_elses_item_is_not_found(self):
        other = make_application('profile_complete', student=make_student())
        item = _item(other, 'water_bill_recheck')
        self.assertEqual(self._post(item, reason='lost_bill').status_code, 404)

    def test_the_reviewer_payload_carries_the_reason_and_the_note(self):
        item = _item(self.app, 'electricity_bill_recheck')
        self._post(item, reason='other', note='We rent a room.')
        item.refresh_from_db()
        data = ResolutionItemSerializer(item).data
        self.assertEqual((data['status'], data['params']['declined_reason'], data['params']['declined_note']),
                         ('resolved', 'other', 'We rent a room.'))
        # the cockpit's queue is open items plus those the student answered: a declined ask is in it
        from django.db.models import Q
        queue = self.app.resolution_items.filter(Q(status='open') | Q(status='resolved', resolved_by='student'))
        self.assertIn(item.id, [i.id for i in queue])

    def test_a_declined_ask_no_longer_exempts_the_replace_cap(self):
        # a Check 2 ask grants an extra upload only once a reviewer has asked again (a person's ask)
        item = _item(self.app, 'electricity_bill_recheck')
        item.params = {**item.params, ASKED_AGAIN_AT: '2026-11-17T01:00:00+00:00'}
        item.save(update_fields=['params'])
        with override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True):
            self.assertEqual([t for t, _m, _at in human_asks(self.app)], ['electricity_bill'])
            self._post(item, reason='lost_bill')
            self.assertEqual(human_asks(self.app), [])


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestCheck2NeverReasksADeclinedItem(TestCase):
    def setUp(self):
        self.app = make_application('profile_complete', student=make_student())

    def _rerun(self, wanted, times=3):
        with patch('apps.scholarship.check2_queries._gap_sets', return_value=(set(), set(wanted))), \
             patch('apps.scholarship.check2_queries.higher_owed.may_raise', return_value=True):
            for _ in range(times):
                sync_check2_queries(self.app)

    def test_a_declined_item_stays_closed_through_every_rerun(self):
        item = _item(self.app, 'water_bill_recheck')
        optional_asks.decline(item, 'lost_bill')
        self._rerun({'water_bill_recheck'})
        item.refresh_from_db()
        self.assertEqual((item.status, item.params['declined_reason']), ('resolved', 'lost_bill'))
        self.assertEqual(ResolutionItem.objects.filter(application=self.app, code='water_bill_recheck').count(), 1)

    def test_an_answered_by_upload_item_still_reopens_when_its_gap_refires(self):
        item = _item(self.app, 'water_bill_recheck', status='resolved', resolved_by='student')
        self._rerun({'water_bill_recheck'}, times=1)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')        # V2 (#4) unchanged: only a decline is final

    def test_a_second_decline_overwrites_the_first(self):
        item = _item(self.app, 'electricity_bill_recheck')
        optional_asks.decline(item, 'lost_bill')
        self.assertTrue(optional_asks.is_declined(item))
        self.assertIsNone(optional_asks.decline(item, 'other', 'new words'))     # a re-decline overwrites
        item.refresh_from_db()
        self.assertEqual((item.params['declined_reason'], item.params['declined_note']), ('other', 'new words'))
        self.assertEqual(optional_asks.decline(item, 'lost_bill'), None)
        item.refresh_from_db()
        self.assertNotIn('declined_note', item.params)     # the old note does not linger
