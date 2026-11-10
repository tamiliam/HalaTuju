"""A1.11a — the staff footprint reads the QC separation guard's own evidence (TD-484) and every
recorded-email stamp a staff member leaves (TD-443).

Why it matters: a person with no footprint may be DELETED, and the delete SET_NULLs their
`AssignmentEvent`s and CASCADEs their `StaffActivity` rows — the very rows `qc_separation.refusal`
reads. Deleted and re-invited under the same email, they came back as a stranger to the guard.
"""
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_activity, staff_footprint
from apps.scholarship.models import AssignmentEvent, ScholarshipApplication, StaffActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org)

REQ = 'apps.courses.views_admin.http_requests'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestGuardEvidenceKeepsThePerson(TestCase):
    """TD-484: assign, reassign, delete, re-invite, QC -> 403."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.cohort = make_cohort(owning_organisation=cls.org)

    def _delete(self, target):
        with patch(f'{REQ}.get'), patch(f'{REQ}.delete'):
            return authed_client(self.org_admin).delete(f'/api/v1/admin/admins/{target.pk}/')

    def _qc(self, who, app):
        return authed_client(who).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
            {'decision': 'accept'}, format='json')

    def test_a_past_assignment_refuses_the_delete_and_the_guard_still_holds(self):
        once = make_admin('admin', owning_org=self.org)
        now = make_admin('reviewer', owning_org=self.org)
        app = make_application('awaiting_qc', outcome='recommend', reviewer=now, cohort=self.cohort)
        # Assigned to `once`, then reassigned away: no current assignment names them.
        AssignmentEvent.objects.create(application=app, from_admin=None, to_admin=once)
        AssignmentEvent.objects.create(application=app, from_admin=once, to_admin=now)
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            verdict_decided_by='', verified_by='')
        r = self._delete(once)
        self.assertEqual((r.status_code, r.json().get('code')), (409, 'has_work'), r.content[:300])
        self.assertEqual(r.json()['work']['cases_held_before'], 2)
        # They stay the same row, so "re-invited" they still carry the history: QC is refused.
        PartnerAdmin.objects.filter(pk=once.pk).update(permissions=['review', 'see_all', 'qc'])
        r = self._qc(PartnerAdmin.objects.get(pk=once.pk), app)
        self.assertEqual((r.status_code, r.json().get('code')), (403, 'self_assigned_qc_forbidden'))

    def test_a_review_verb_activity_row_refuses_the_delete(self):
        drafter = make_admin('admin', owning_org=self.org)
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort)
        staff_activity.record(drafter, staff_activity.INTERVIEW_DRAFTED, app)
        r = self._delete(drafter)
        self.assertEqual((r.status_code, r.json().get('code')), (409, 'has_work'), r.content[:300])
        self.assertEqual(r.json()['work']['review_actions'], 1)

    def test_a_non_review_activity_row_is_not_review_work(self):
        clerk = make_admin('admin', owning_org=self.org)
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort)
        row = staff_activity.record(clerk, staff_activity.QUERY_RAISED, app)
        self.assertIsNotNone(row)   # the row IS written; it is simply not review work
        self.assertTrue(StaffActivity.objects.filter(actor=clerk, verb='query_raised').exists())
        self.assertNotIn('review_actions', staff_footprint.footprint(clerk))


class TestEveryEmailStamp(TestCase):
    """TD-443: the recorded-email stamps beyond payments and verdicts."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.person = make_admin('admin', owning_org=cls.org, email='Stamp.Person@example.org')

    def test_every_listed_stamp_is_a_real_field(self):
        for key, label, model_name, fields in (staff_footprint.EMAIL_STAMPS
                                               + staff_footprint.CORE_EMAIL_STAMPS):
            model = apps.get_model(label, model_name)
            for field in fields:
                with self.subTest(key=key, field=field):
                    model._meta.get_field(field)

    def test_the_keys_are_unique_and_do_not_shadow_the_older_ones(self):
        keys = [k for k, *_ in staff_footprint.EMAIL_STAMPS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertFalse(set(keys) & {'payment_runs_made', 'applications_decided',
                                      'benefactors_vetted', 'cases_held_before', 'review_actions'})

    def test_nothing_recorded_is_no_footprint(self):
        self.assertEqual(staff_footprint.footprint(self.person), {})

    def test_a_reassignment_they_made_is_work(self):
        app = make_application('shortlisted')
        AssignmentEvent.objects.create(application=app, to_admin=None,
                                       by_email='stamp.person@example.org')
        self.assertEqual(staff_footprint.footprint(self.person), {'assignments_made': 1})

    def test_a_case_they_closed_or_recommended_is_work_matched_without_case(self):
        a = make_application('shortlisted')
        b = make_application('shortlisted')
        ScholarshipApplication.objects.filter(pk=a.pk).update(closed_by='STAMP.PERSON@example.org')
        ScholarshipApplication.objects.filter(pk=b.pk).update(recommended_by='stamp.person@example.org')
        work = staff_footprint.footprint(self.person)
        self.assertEqual((work.get('cases_closed'), work.get('cases_recommended')), (1, 1))

    def test_a_reopen_they_made_is_work(self):
        from apps.scholarship.models import DecisionReopen
        app = make_application('shortlisted')
        DecisionReopen.objects.create(application=app, reopened_by='stamp.person@example.org',
                                      reason='x')
        self.assertEqual(staff_footprint.footprint(self.person).get('decisions_reopened'), 1)

    def test_a_row_with_the_address_in_two_stamps_counts_once(self):
        from apps.scholarship.models import ResolutionItem
        app = make_application('shortlisted')
        ResolutionItem.objects.create(application=app, code='x', prompt='x',
                                      created_by='stamp.person@example.org',
                                      resolved_by='stamp.person@example.org')
        self.assertEqual(staff_footprint.footprint(self.person).get('resolution_items'), 1)

    def test_the_whole_footprint_costs_one_query(self):
        # Sprint T2: the stamps AND the foreign-key traces are one query for one person ...
        with self.assertNumQueries(1):
            staff_footprint.footprint(self.person)

    def test_many_people_cost_one_query(self):
        # ... and for a whole table (the Admins and Mentors lists read every row's at once).
        others = [make_admin('reviewer', owning_org=self.org) for _ in range(3)]
        with self.assertNumQueries(1):
            work = staff_footprint.footprints([self.person, *others])
        self.assertEqual(work, {p.pk: {} for p in [self.person, *others]})
