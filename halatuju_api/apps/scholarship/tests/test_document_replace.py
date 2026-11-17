"""H6: a document slot takes four student uploads (the first, then three replaces) until a person asks again.

A slot is (type + household member + request code). Every upload the door accepts is counted in
`document_slot_replaces` and the count survives Remove; the 5th upload is refused 409
`replace_limit_reached` whatever the copy's read said and whether or not the slot was emptied. Only an ask a
PERSON raised (an officer's request, a reviewer's "Ask again") after the slot's last upload lets ONE more in.
A request code must be an officer's document request on the case. The documents lock is checked first.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship.models import ApplicantDocument, DocumentSlotReplaces, ResolutionItem
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student,
)

DOCS = '/api/v1/scholarship/documents/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, CHECK2_STUDENT_QUERIES_ENABLED=True)
@patch('apps.scholarship.storage.delete_own_doc_objects', return_value=None)
@patch('apps.scholarship.upload_read.needs_read', return_value=True)    # recorded queued: no paid read
@patch('apps.scholarship.storage.object_exists', return_value=True)
class TestDocumentReplace(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='rp', name='Replace', year=2026)

    def _case(self, stage='interviewing', **kw):
        student = make_student()
        app = make_application(stage, cohort=self.cohort, student=student, **kw)
        return app, authed_client(student.supabase_user_id)

    def _post(self, client, app, doc_type='ic', replace=True, member='', code=''):
        body = {'doc_type': doc_type, 'storage_path': _key(app, doc_type, 'x'),
                'original_filename': 'a.pdf', 'size': 1000, 'household_member': member, 'request_code': code}
        if replace:
            body['replace'] = True
        return client.post(DOCS, body, format='json')

    def _slip(self, client, app, member='father', code=''):
        return self._post(client, app, 'salary_slip', member=member, code=code)

    def _first(self, app, doc_type='ic', member=''):
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, household_member=member, storage_path='first')

    def _live(self, app, doc_type=None):
        qs = ApplicantDocument.objects.filter(application=app, superseded_at__isnull=True)
        return qs.get(doc_type=doc_type) if doc_type else qs.get()

    def _promote_newest(self, app):
        """Stand-in for the read's promote (the reviewer's probe technique): the newest upload goes live."""
        from apps.scholarship import slot_writes
        doc = ApplicantDocument.objects.filter(application=app).order_by('-id').first()
        stale = list(ApplicantDocument.objects.filter(
            application=app, doc_type=doc.doc_type, household_member=doc.household_member,
            request_code=doc.request_code, superseded_at__isnull=True).exclude(pk=doc.pk).values_list('id', flat=True))
        self.assertTrue(slot_writes.promote_into_slot(app, doc, stale))
        return doc

    def _remove_live(self, client, app, doc_type='salary_slip'):
        return client.delete(f'{DOCS}{self._live(app, doc_type).id}/')

    def _listed(self, client, doc_type='salary_slip'):
        return [(d['replace_count'], d['replaces_left'], d['replace_limit'])
                for d in client.get(DOCS).json()['documents'] if d['doc_type'] == doc_type]

    def _counter(self, app, doc_type='salary_slip', member='father'):
        return DocumentSlotReplaces.objects.get(application=app, doc_type=doc_type, household_member=member)

    # ── the cap ───────────────────────────────────────────────────────────────────────────────────
    def test_three_replaces_work_and_the_fourth_is_refused(self, *_):
        app, client = self._case()
        self._first(app)
        for _n in range(3):
            self.assertEqual(self._post(client, app).status_code, 201)
        resp = self._post(client, app)
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertEqual((body['code'], body['limit']), ('replace_limit_reached', 3))
        self.assertTrue(body['message'])
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 4)   # nothing recorded

    def test_the_count_is_per_document(self, *_):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        self._first(app, 'salary_slip', 'mother')
        for _n in range(3):
            self.assertEqual(self._slip(client, app).status_code, 201)
        self.assertEqual(self._slip(client, app).status_code, 409)
        self.assertEqual(self._slip(client, app, 'mother').status_code, 201)

    def test_the_flag_changes_nothing_a_plain_upload_counts_and_is_capped(self, *_):
        app, client = self._case()
        self._first(app)
        for _n in range(3):
            self.assertEqual(self._post(client, app, replace=False).status_code, 201)
        resp = self._post(client, app, replace=False)
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'replace_limit_reached'))

    def test_a_returned_or_problem_copy_still_counts(self, *_):
        # every accepted upload is a paid read, so a copy the read turned down buys no extra upload
        app, client = self._case()
        self._first(app)
        for _n in range(3):
            self.assertEqual(self._post(client, app).status_code, 201)
        for fix in ({'verification_status': 'rejected'},
                    {'vision_fields': {'student_verdict': 'wrong_doc'}},
                    {'vision_fields': {'authenticity': {'status': 'not_ic'}}},
                    {'vision_fields': {'authenticity': {'status': 'suspect'}}}):
            ApplicantDocument.objects.filter(application=app).update(**fix)
            self.assertEqual(self._post(client, app).status_code, 409, fix)

    def test_a_first_upload_is_free_and_the_list_serves_the_servers_numbers(self, *_):
        app, client = self._case()
        self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        self.assertEqual(self._listed(client, 'bank_statement'), [(0, 3, 3)])
        self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        self.assertEqual(self._listed(client, 'bank_statement'), [(1, 2, 3)])
        self.assertEqual(self._counter(app, 'bank_statement', '').uploads, 2)

    def test_a_replaced_copy_stays_superseded(self, *_):
        app, client = self._case()
        old = self._first(app, 'bank_statement')
        self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        old.refresh_from_db()
        live = self._live(app)
        self.assertEqual(old.superseded_by_id, live.id)

    def test_a_slot_with_no_counter_yet_counts_its_stored_copies(self, *_):
        # older uploads (before the counter): four stored copies are a full slot, and the row is seeded
        app, client = self._case()
        live = self._first(app, 'bank_statement')
        for _n in range(3):
            ApplicantDocument.objects.create(application=app, doc_type='bank_statement', storage_path='old',
                                             superseded_at=live.uploaded_at, superseded_by=live)
        self.assertEqual(self._listed(client, 'bank_statement'), [(3, 0, 3)])
        self.assertEqual(self._post(client, app, 'bank_statement').status_code, 409)
        self.assertEqual(self._remove_live(client, app, 'bank_statement').status_code, 200)
        self.assertEqual(self._counter(app, 'bank_statement', '').uploads, 4)        # seeded before the delete
        self.assertEqual(self._post(client, app, 'bank_statement').status_code, 409)

    def test_locked_refuses_a_replace(self, *_):
        app, client = self._case('awaiting_qc', outcome='recommend')
        self._first(app)
        resp = self._post(client, app)
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'documents_locked'))

    def test_locked_but_exempt_type_is_still_capped(self, *_):
        app, client = self._case('awarded')
        self._first(app, 'bank_statement')
        for _n in range(3):
            self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        self.assertEqual(self._post(client, app, 'bank_statement').json()['code'], 'replace_limit_reached')

    # ── the reviewer's probes A to E (round 2) ────────────────────────────────────────────────────
    def test_A_upload_and_remove_loop_stops_at_the_fourth_re_upload(self, *_):
        app, client = self._case()
        codes = []
        for _n in range(8):
            r = self._slip(client, app)
            codes.append(r.status_code)
            if r.status_code != 201:
                break
            self._promote_newest(app)
            self.assertEqual(self._remove_live(client, app).status_code, 200)
        self.assertEqual(codes, [201, 201, 201, 201, 409])   # the first upload, three re-uploads, then shut
        self.assertEqual(self._counter(app).uploads, 4)

    def test_B_a_slot_at_two_replaces_removed_and_refilled_stops_at_the_cap(self, *_):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        for _n in range(2):
            self.assertEqual(self._slip(client, app).status_code, 201)
            self._promote_newest(app)
        self.assertEqual(self._listed(client), [(2, 1, 3)])
        codes = []
        for _n in range(6):
            self.assertEqual(self._remove_live(client, app).status_code, 200)
            r = self._slip(client, app)
            codes.append(r.status_code)
            if r.status_code != 201:
                break
            self._promote_newest(app)
        self.assertEqual(codes, [201, 409])

    def test_C_after_remove_with_one_left_the_refill_is_the_last(self, *_):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        for _n in range(2):
            self._slip(client, app)
            self._promote_newest(app)
        self._remove_live(client, app)
        self.assertEqual(self._slip(client, app).status_code, 201)   # refill: the 3rd replace
        self._promote_newest(app)
        self.assertEqual(self._listed(client), [(3, 0, 3)])
        self.assertEqual(self._slip(client, app).status_code, 409)
        self._remove_live(client, app)
        self.assertEqual(self._slip(client, app).status_code, 409)

    def test_D_a_crafted_request_code_is_refused(self, *_):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        for _n in range(3):
            self._slip(client, app)
        self.assertEqual(self._slip(client, app).status_code, 409)
        for i in range(4):
            resp = self._slip(client, app, code=f'zz{i}')
            self.assertEqual((resp.status_code, resp.json()['code']), (400, 'bad_request_code'))
        # an officer's request is its own slot, for its own type and member only
        ResolutionItem.objects.create(application=app, code='officer_1', doc_type='salary_slip', kind='doc',
                                      source='officer', status='open', params={'household_member': 'father'})
        self.assertEqual(self._slip(client, app, 'mother', code='officer_1').status_code, 400)
        self.assertEqual(self._post(client, app, 'epf', member='father', code='officer_1').status_code, 400)
        self.assertEqual(self._slip(client, app, code='officer_1').status_code, 201)
        # a system ticket's code is no request code either
        ResolutionItem.objects.create(application=app, code='ic_missing', doc_type='ic', kind='doc',
                                      source='system', status='open')
        self.assertEqual(self._post(client, app, 'ic', code='ic_missing').status_code, 400)
        self.assertEqual(ApplicantDocument.objects.filter(application=app).exclude(request_code='').count(), 1)

    def test_D_a_resolved_officer_request_code_stays_one_capped_slot(self, *_):
        # the Done card's Replace sends the resolved request's code: accepted, and capped like any slot
        app, client = self._case()
        ResolutionItem.objects.create(application=app, code='officer_2', doc_type='bank_statement', kind='doc',
                                      source='officer', status='resolved')
        codes = [self._post(client, app, 'bank_statement', code='officer_2').status_code for _n in range(5)]
        self.assertEqual(codes, [201, 201, 201, 201, 409])

    def test_E_the_str_sweep_counts_the_legacy_blank_slot(self, *_):
        app, client = self._case()
        app.income_route = 'str'
        app.income_earner = 'father'
        app.profile_completed_at = None
        app.save()
        DocumentSlotReplaces.objects.create(application=app, doc_type='salary_slip', household_member='', uploads=4)
        r = self._slip(client, app, member='')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'replace_limit_reached'))
        # two legacy blank uploads and two tagged ones are four in the swept slot too
        app2, client2 = self._case()
        app2.income_route, app2.income_earner, app2.profile_completed_at = 'str', 'father', None
        app2.save()
        DocumentSlotReplaces.objects.create(application=app2, doc_type='salary_slip', household_member='', uploads=2)
        self.assertEqual(self._slip(client2, app2, member='').status_code, 201)
        self.assertEqual(self._slip(client2, app2, member='').status_code, 201)
        self.assertEqual(self._counter(app2).uploads, 2)
        self.assertEqual(self._slip(client2, app2, member='').status_code, 409)

    # ── the one exemption: an ask a person raised after the last upload ───────────────────────────
    def _full_slip_slot(self, client, app):
        self._first(app, 'salary_slip', 'father')
        for _n in range(3):
            self.assertEqual(self._slip(client, app).status_code, 201)
        self.assertEqual(self._slip(client, app).status_code, 409)

    def _ask(self, app, code, doc_type='salary_slip', source='system', status='open', **kw):
        return ResolutionItem.objects.create(application=app, code=code, doc_type=doc_type, kind='doc',
                                             source=source, status=status, **kw)

    def test_an_officer_ask_after_the_last_upload_lets_exactly_one_more_in(self, *_):
        app, client = self._case()
        self._full_slip_slot(client, app)
        self._ask(app, 'officer_7', source='officer')
        self.assertEqual(self._listed(client), [(3, 1, 3)])
        self.assertEqual(self._slip(client, app).status_code, 201)
        self.assertEqual(self._slip(client, app).status_code, 409)                # the ask is answered
        self._ask(app, 'officer_8', source='officer')                            # a second ask: one more
        self.assertEqual(self._slip(client, app).status_code, 201)
        self.assertEqual(self._slip(client, app).status_code, 409)

    def test_an_officer_ask_raised_before_the_uploads_grants_nothing(self, *_):
        app, client = self._case()
        self._ask(app, 'officer_7', source='officer')
        self._full_slip_slot(client, app)

    def test_an_officer_ask_lets_a_removed_full_slot_be_filled_once(self, *_):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        for _n in range(3):
            self._slip(client, app)
            self._promote_newest(app)
        self._remove_live(client, app)
        self.assertEqual(self._slip(client, app).status_code, 409)
        self._ask(app, 'officer_7', source='officer')
        self.assertEqual(self._slip(client, app).status_code, 201)
        self._promote_newest(app)
        self._remove_live(client, app)
        self.assertEqual(self._slip(client, app).status_code, 409)

    def test_a_reviewers_ask_again_lets_exactly_one_more_in(self, *_):
        app, client = self._case()
        item = self._ask(app, 'officer_3', source='officer', status='resolved', resolved_by='student',
                         params={'household_member': 'father'})       # raised before the uploads: spent
        self._full_slip_slot(client, app)
        reviewer = make_admin('super', super_admin=True)
        resp = authed_client(reviewer).post(f'/api/v1/admin/scholarship/resolution-items/{item.id}/reopen/',
                                            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')
        self.assertIn('asked_again_at', item.params)
        self.assertEqual(self._slip(client, app).status_code, 201)
        self.assertEqual(self._slip(client, app).status_code, 409)

    def test_a_remove_reopened_or_auto_ticket_grants_nothing(self, *_):
        # the `<type>_missing` ticket Remove re-opens, a system ticket and a Check 2 query are raised by code
        app, client = self._case()
        self._first(app, 'offer_letter')
        for _n in range(3):
            self._post(client, app, 'offer_letter')
            self._promote_newest(app)
        self._remove_live(client, app, 'offer_letter')
        self._ask(app, 'offer_letter_missing', 'offer_letter')        # as after_document_deleted re-opens it
        self._ask(app, 'offer_no_identity', 'offer_letter')
        self._ask(app, 'income_doc_stale', 'offer_letter', source='check2')
        self.assertEqual(self._post(client, app, 'offer_letter').status_code, 409)
        # an "Ask again" stamped BEFORE the last upload is spent
        app2, client2 = self._case()
        self._first(app2, 'salary_slip', 'father')
        from django.utils import timezone
        old = self._ask(app2, 'income_doc_stale', source='check2',
                        params={'asked_again_at': timezone.now().isoformat()})
        for _n in range(3):
            self._slip(client2, app2)
        self.assertTrue(old.params['asked_again_at'])
        self.assertEqual(self._slip(client2, app2).status_code, 409)

    def test_an_ask_for_another_member_or_type_grants_nothing(self, *_):
        app, client = self._case()
        self._full_slip_slot(client, app)
        self._ask(app, 'officer_7', source='officer', params={'household_member': 'mother'})
        self._ask(app, 'officer_8', 'epf', source='officer')
        self.assertEqual(self._slip(client, app).status_code, 409)
        self._ask(app, 'officer_9', source='officer', params={'household_member': 'father'})
        self.assertEqual(self._slip(client, app).status_code, 201)

    def test_an_ask_the_student_cannot_see_grants_nothing(self, *_):
        app, client = self._case()
        self._full_slip_slot(client, app)
        self._ask(app, 'income_doc_stale', source='check2',
                  params={'asked_again_at': '2999-01-01T00:00:00+00:00'})
        with override_settings(CHECK2_STUDENT_QUERIES_ENABLED=False):     # check2 asks are hidden
            self.assertEqual(self._slip(client, app).status_code, 409)

    def test_the_serializer_shares_the_auth_lists(self, *_):
        from apps.scholarship.document_replace import AUTH_TYPES, AUTH_WRONG_TYPE_ONLY
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        app, _c = self._case()
        for dt in AUTH_TYPES:
            d = ApplicantDocument.objects.create(application=app, doc_type=dt, storage_path='s', household_member=dt,
                                                 vision_fields={'authenticity': {'status': 'suspect'}})
            shown = ApplicantDocumentSerializer(d).data['authenticity'] is not None
            self.assertEqual(shown, dt not in AUTH_WRONG_TYPE_ONLY, dt)
