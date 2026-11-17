"""H6: a student may replace a sent / done document up to three times, counted in the database.

A document is its slot (type + household member + request code). Only an upload sent with `replace`
is counted; the 4th is refused 409 `replace_limit_reached`. The documents lock is checked first, and
the exempt types stay replaceable after it. A replaced copy stays superseded (version history).
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

DOCS = '/api/v1/scholarship/documents/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, CHECK2_STUDENT_QUERIES_ENABLED=True)
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

    def _post(self, client, app, doc_type='ic', replace=True, member=''):
        body = {'doc_type': doc_type, 'storage_path': _key(app, doc_type, 'x'),
                'original_filename': 'a.pdf', 'size': 1000, 'household_member': member}
        if replace:
            body['replace'] = True
        return client.post(DOCS, body, format='json')

    def _first(self, app, doc_type='ic', member=''):
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, household_member=member, storage_path='first')

    def test_three_replaces_work_and_the_fourth_is_refused(self, _o, _n):
        app, client = self._case()
        self._first(app)
        for n in (1, 2, 3):
            resp = self._post(client, app)
            self.assertEqual(resp.status_code, 201, resp.content)
            self.assertEqual(ApplicantDocument.objects.filter(application=app).order_by('-id').first().replace_count, n)
        resp = self._post(client, app)
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertEqual(body['code'], 'replace_limit_reached')
        self.assertTrue(body['message'])
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 4)   # nothing recorded

    def test_the_count_is_per_document(self, _o, _n):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        self._first(app, 'salary_slip', 'mother')
        for _ in range(3):
            self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 409)
        self.assertEqual(self._post(client, app, 'salary_slip', member='mother').status_code, 201)

    def test_the_flag_changes_nothing_a_plain_upload_counts_and_is_capped(self, _o, _n):
        app, client = self._case()
        self._first(app)
        for _ in range(3):
            self.assertEqual(self._post(client, app, replace=False).status_code, 201)
        resp = self._post(client, app, replace=False)
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'replace_limit_reached'))
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 4)   # nothing stored

    def _live(self, app):
        return ApplicantDocument.objects.get(application=app, superseded_at__isnull=True)

    def _newest(self, app):   # an upload is recorded staged until its read promotes it, so the live copy stays put
        return ApplicantDocument.objects.filter(application=app).order_by('-id').first()

    def test_a_returned_or_problem_live_copy_is_retried_without_counting(self, _o, _n):
        app, client = self._case()
        self._first(app)
        for _ in range(3):
            self.assertEqual(self._post(client, app).status_code, 201)
        for fix in ({'verification_status': 'rejected'},
                    {'vision_fields': {'student_verdict': 'wrong_doc'}},
                    {'vision_fields': {'authenticity': {'status': 'not_ic'}}}):
            ApplicantDocument.objects.filter(pk=self._live(app).pk).update(**fix)
            self.assertEqual(self._post(client, app, replace=False).status_code, 201)
            self.assertEqual(self._newest(app).replace_count, 3)        # carried, not counted
        ApplicantDocument.objects.filter(pk=self._live(app).pk).update(
            verification_status='pending', vision_fields={})
        resp = self._post(client, app)                                   # a clean copy now: counted, capped
        self.assertEqual(resp.status_code, 409)

    def test_a_live_copy_still_being_read_counts(self, _o, _n):
        app, client = self._case()
        self._first(app)
        ApplicantDocument.objects.filter(pk=self._live(app).pk).update(read_state='pending')
        self.assertEqual(self._post(client, app).status_code, 201)
        self.assertEqual(self._post(client, app, replace=False).status_code, 201)
        self.assertEqual(self._newest(app).replace_count, 2)

    def test_a_replace_the_reader_turns_down_still_shows_in_the_page_count(self, _o, _n):
        app, client = self._case()
        self._first(app, 'bank_statement')
        for _ in range(3):
            self._post(client, app, 'bank_statement')
        # the reader turned the newest copy down: the older live copy keeps the slot with a lower count
        live = self._live(app)
        ApplicantDocument.objects.create(application=app, doc_type='bank_statement', storage_path='x',
                                         replace_count=3, superseded_at=live.uploaded_at)
        ApplicantDocument.objects.filter(pk=live.pk).update(replace_count=0)
        docs = client.get(DOCS).json()['documents']
        self.assertEqual([d['replace_count'] for d in docs], [3])

    def test_a_first_upload_is_not_a_replace(self, _o, _n):
        app, client = self._case()
        self.assertEqual(self._post(client, app).status_code, 201)
        self.assertEqual(ApplicantDocument.objects.get(application=app).replace_count, 0)

    def test_list_serves_the_count_and_the_limit(self, _o, _n):
        app, client = self._case()
        self._first(app, 'bank_statement')
        self._post(client, app, 'bank_statement')
        docs = client.get(DOCS).json()['documents']
        self.assertEqual([(d['replace_count'], d['replace_limit']) for d in docs], [(1, 3)])

    def test_a_replaced_copy_stays_superseded(self, _o, _n):
        app, client = self._case()
        old = self._first(app, 'bank_statement')
        self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        old.refresh_from_db()
        self.assertIsNotNone(old.superseded_at)
        live = ApplicantDocument.objects.get(application=app, superseded_at__isnull=True)
        self.assertEqual((old.superseded_by_id, live.replace_count), (live.id, 1))

    def test_locked_refuses_a_replace(self, _o, _n):
        app, client = self._case('awaiting_qc', outcome='recommend')
        self._first(app)
        resp = self._post(client, app)
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'documents_locked'))

    def test_locked_but_exempt_type_can_still_be_replaced(self, _o, _n):
        app, client = self._case('awarded')
        self._first(app, 'bank_statement')
        for _ in range(3):
            self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        resp = self._post(client, app, 'bank_statement')
        self.assertEqual(resp.json()['code'], 'replace_limit_reached')

    # ---- round 2: the cap never blocks a fix the case is asking for ----
    def _ask(self, app, code, doc_type, status='open', source='system', **kw):
        from apps.scholarship.models import ResolutionItem
        return ResolutionItem.objects.create(application=app, code=code, doc_type=doc_type, kind='doc',
                                             source=source, status=status, **kw)

    def _three_then(self, client, app, doc_type='str'):
        for _ in range(3):
            self.assertEqual(self._post(client, app, doc_type).status_code, 201)

    def _ok_copy(self, app, doc_type):
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, storage_path='first',
            vision_fields={'student_verdict': 'ok', 'authenticity': {'status': 'genuine'}})

    def test_open_str_not_current_ticket_exempts_a_copy_that_read_fine(self, _o, _n):
        app, client = self._case()
        self._ok_copy(app, 'str')
        self._three_then(client, app)
        ApplicantDocument.objects.filter(pk=self._live(app).pk).update(
            vision_fields={'student_verdict': 'ok', 'authenticity': {'status': 'genuine'}})
        ticket = self._ask(app, 'str_not_current', 'str')
        for _ in range(2):                                   # 4th and 5th: allowed, not counted
            self.assertEqual(self._post(client, app, 'str').status_code, 201)
            self.assertEqual(self._newest(app).replace_count, 3)
            ApplicantDocument.objects.filter(pk=self._live(app).pk).update(
                vision_fields={'student_verdict': 'ok', 'authenticity': {'status': 'genuine'}})
        ticket.status = 'resolved'
        ticket.save()                                        # ticket closed: counted again
        self.assertEqual(self._post(client, app, 'str').status_code, 409)

    def test_open_offer_no_identity_ticket_likewise(self, _o, _n):
        app, client = self._case()
        self._ok_copy(app, 'offer_letter')
        self._three_then(client, app, 'offer_letter')
        self.assertEqual(self._post(client, app, 'offer_letter').status_code, 409)
        ticket = self._ask(app, 'offer_no_identity', 'offer_letter')
        self.assertEqual(self._post(client, app, 'offer_letter').status_code, 201)
        self.assertEqual(self._newest(app).replace_count, 3)
        ticket.status = 'resolved'
        ticket.save()
        ApplicantDocument.objects.filter(pk=self._live(app).pk).update(vision_fields={})
        self.assertEqual(self._post(client, app, 'offer_letter').status_code, 409)

    def test_an_open_ticket_for_another_type_exempts_nothing(self, _o, _n):
        app, client = self._case()
        self._first(app)
        self._three_then(client, app, 'ic')
        self._ask(app, 'str_not_current', 'str')
        self.assertEqual(self._post(client, app, 'ic').status_code, 409)

    def test_suspect_is_exempt_where_the_student_is_shown_it_and_counted_where_hidden(self, _o, _n):
        suspect = {'authenticity': {'status': 'suspect'}}
        app, client = self._case()
        self._first(app, 'ic')
        self._three_then(client, app, 'ic')
        ApplicantDocument.objects.filter(pk=self._live(app).pk).update(vision_fields=suspect)
        self.assertEqual(self._post(client, app, 'ic').status_code, 201)        # shown: a fix, not counted
        self.assertEqual(self._newest(app).replace_count, 3)
        app2, client2 = self._case()
        self._first(app2, 'salary_slip', 'father')
        for _ in range(3):
            self.assertEqual(self._post(client2, app2, 'salary_slip', member='father').status_code, 201)
        ApplicantDocument.objects.filter(pk=self._live(app2).pk).update(vision_fields=suspect)
        self.assertEqual(self._post(client2, app2, 'salary_slip', member='father').status_code, 409)  # hidden: counted

    def test_the_serializer_and_the_exemption_share_one_suspect_list(self, _o, _n):
        from apps.scholarship.document_replace import AUTH_TYPES, SUSPECT_SHOWN_TYPES
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        app, _c = self._case()
        for dt in AUTH_TYPES:
            d = ApplicantDocument.objects.create(application=app, doc_type=dt, storage_path='s', household_member=dt,
                                                 vision_fields={'authenticity': {'status': 'suspect'}})
            shown = ApplicantDocumentSerializer(d).data['authenticity'] is not None
            self.assertEqual(shown, dt in SUSPECT_SHOWN_TYPES, dt)

    def test_the_newest_live_copy_is_the_one_read(self, _o, _n):
        # an STR sweep can hold two live copies (the member's and a legacy untagged one): read the newest
        app, client = self._case()
        old = self._first(app, 'str', '')
        ApplicantDocument.objects.filter(pk=old.pk).update(verification_status='rejected')
        new = self._first(app, 'str', 'father')
        ApplicantDocument.objects.filter(pk=new.pk).update(replace_count=3)
        resp = self._post(client, app, 'str', member='father')
        self.assertEqual((resp.status_code, resp.json().get('code')), (409, 'replace_limit_reached'))

    # ---- round 3: any ask the student can see exempts, whatever its source ----
    def _slip_at_cap(self, app, client, member='father'):
        self._first(app, 'salary_slip', member)
        for _ in range(3):
            self.assertEqual(self._post(client, app, 'salary_slip', member=member).status_code, 201)
        ApplicantDocument.objects.filter(pk=self._live(app).pk).update(
            vision_fields={'student_verdict': 'ok', 'authenticity': {'status': 'genuine'}})

    def test_a_check2_income_doc_stale_ask_exempts_a_slip_that_read_fine(self, _o, _n):
        app, client = self._case()
        self._slip_at_cap(app, client)
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 409)
        ask = self._ask(app, 'income_doc_stale', 'salary_slip', source='check2')
        for _ in range(2):                                   # 4th and 5th: allowed, not counted
            self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)
            self.assertEqual(self._newest(app).replace_count, 3)
            ApplicantDocument.objects.filter(pk=self._live(app).pk).update(
                vision_fields={'student_verdict': 'ok', 'authenticity': {'status': 'genuine'}})
        ask.status = 'resolved'
        ask.save()                                           # closed: counted again
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 409)

    def test_a_check2_ask_for_the_father_does_not_exempt_the_mothers_slot(self, _o, _n):
        app, client = self._case()
        self._slip_at_cap(app, client, 'mother')
        self._ask(app, 'father_income_proof_missing', 'salary_slip', source='check2',
                  params={'household_member': 'father'})
        self.assertEqual(self._post(client, app, 'salary_slip', member='mother').status_code, 409)
        self._ask(app, 'mother_income_proof_missing', 'salary_slip', source='check2',
                  params={'household_member': 'mother'})
        self.assertEqual(self._post(client, app, 'salary_slip', member='mother').status_code, 201)

    def test_an_officer_ask_exempts(self, _o, _n):
        app, client = self._case()
        self._slip_at_cap(app, client)
        self._ask(app, 'officer_doc', 'salary_slip', source='officer')
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)

    def test_an_ask_the_student_cannot_see_exempts_nothing(self, _o, _n):
        app, client = self._case()
        self._slip_at_cap(app, client)
        with override_settings(CHECK2_STUDENT_QUERIES_ENABLED=False):     # check2 asks are hidden
            self._ask(app, 'income_doc_stale', 'salary_slip', source='check2')
            self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 409)
        # a system ticket outside STUDENT_DOC_REQUEST_CODES (a name-mismatch judgement) is hidden too
        app2, client2 = self._case()
        self._slip_at_cap(app2, client2)
        self._ask(app2, 'results_slip_name_mismatch', 'salary_slip')
        self.assertEqual(self._post(client2, app2, 'salary_slip', member='father').status_code, 409)

    # ── Remove must not reset the cap (review round: a hard-delete took the count with it) ──────────
    def _remove_live(self, client, app, doc_type='salary_slip'):
        live = ApplicantDocument.objects.get(application=app, doc_type=doc_type, superseded_at__isnull=True)
        with patch('apps.scholarship.storage.delete_own_doc_objects', return_value=None):
            return client.delete(f'{DOCS}{live.id}/')

    def test_remove_does_not_reset_the_cap(self, _o, _n):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        for _ in range(3):
            self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 409)
        self.assertEqual(self._remove_live(client, app).status_code, 200)
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 0)
        resp = self._post(client, app, 'salary_slip', member='father')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()['code'], 'replace_limit_reached')
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 0)   # nothing recorded
        # another member's slot is its own
        self.assertEqual(self._post(client, app, 'salary_slip', member='mother').status_code, 201)

    def test_remove_with_replaces_left_keeps_the_count_and_the_first_upload_is_no_replace(self, _o, _n):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        for _ in range(2):
            self._post(client, app, 'salary_slip', member='father')
        self._remove_live(client, app)
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)
        live = ApplicantDocument.objects.filter(application=app, doc_type='salary_slip').order_by('-id').first()
        self.assertEqual(live.replace_count, 2)               # carried, not incremented: filling an empty slot

    def test_a_never_used_slot_removed_then_filled_is_free(self, _o, _n):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        self._remove_live(client, app)
        for _ in range(1):
            self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)
        live = ApplicantDocument.objects.filter(application=app, doc_type='salary_slip').order_by('-id').first()
        self.assertEqual(live.replace_count, 0)

    def test_an_open_ask_still_lets_a_removed_full_slot_be_filled(self, _o, _n):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        for _ in range(3):
            self._post(client, app, 'salary_slip', member='father')
        self._remove_live(client, app)
        self._ask(app, 'officer_doc', 'salary_slip', source='officer')
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)
