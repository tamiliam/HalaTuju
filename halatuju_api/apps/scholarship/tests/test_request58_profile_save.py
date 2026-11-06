"""Request #58 (2026-11-06): My Profile's Save, both steps, for people who do not review cases.

The page saves in two steps: `admin/me/` (name, job title, About, mentoring area), then
`admin/reviewer-profile/` (qualifications, languages, address and, for a reviewer, the pause). The
second step used to carry `paused` for everybody, and the server refuses `paused` from anyone without
`review` (`not_reviewable`) and refuses the WHOLE step — so a mentor's qualifications, languages and
address never saved. The page now sends `paused` only for someone who reviews cases; the server's
permission rule is unchanged and pinned here. Synthetic data only.
"""
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import ReviewerProfile
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org
from apps.scholarship.tests.test_mentoring import make_mentor

ME = '/api/v1/admin/me/'
PROFILE = '/api/v1/admin/reviewer-profile/'
STAFF = '/api/v1/admin/mentors/staff/'

# Step 2 exactly as the page now sends it for someone who does not review: no `paused`, no phone.
STEP_TWO = {
    'highest_qualification': 'Degree', 'university': 'Universiti Contoh', 'graduation_year': 2012,
    'field_of_study': 'Engineering', 'english_fluency': 'fluent', 'bm_fluency': 'fluent',
    'tamil_fluency': 'conversational', 'street_address': '1 Jalan Contoh', 'postcode': '50000',
    'city': 'Kuala Lumpur', 'state': 'W.P. Kuala Lumpur',
}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheFullSave(TestCase):
    def setUp(self):
        self.org = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org)

    def _save_both_steps(self, login):
        client = authed_client(login)
        r = client.patch(ME, {'name': 'Test Person', 'job_title': 'Volunteer'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        r = client.patch(PROFILE, STEP_TWO, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        prof = ReviewerProfile.objects.get(partner_admin=login)
        for k, v in STEP_TWO.items():
            self.assertEqual(getattr(prof, k), v, k)
        login.refresh_from_db()
        self.assertEqual(login.name, 'Test Person')
        self.assertIsNone(login.paused_at)
        return client

    def test_a_mentor_account_saves_both_steps(self):
        mentor = PartnerAdmin.objects.get(mentor=make_mentor(self.org, name='Mentor Contoh'))
        client = self._save_both_steps(mentor)
        # The permission rule stands: a mentor may still never pause, and nothing is written.
        r = client.patch(PROFILE, {'city': 'Ipoh', 'paused': True}, format='json')
        self.assertEqual((r.status_code, r.json().get('code')), (400, 'not_reviewable'))
        mentor.refresh_from_db()
        self.assertIsNone(mentor.paused_at)
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=mentor).city, 'Kuala Lumpur')

    def test_a_staff_member_who_mentors_but_does_not_review_saves_both_steps(self):
        officer = make_admin('admin', owning_org=self.org)
        self.assertFalse(officer.has_perm('review'))
        r = authed_client(self.lead).post(STAFF, {'admin_id': officer.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        client = self._save_both_steps(officer)
        r = client.patch(PROFILE, {'paused': False}, format='json')
        self.assertEqual(r.json().get('code'), 'not_reviewable')

    def test_a_reviewer_still_pauses_and_saves_in_the_same_step(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        client = authed_client(reviewer)
        r = client.patch(PROFILE, {**STEP_TWO, 'paused': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['paused'])
        self.assertIsNotNone(PartnerAdmin.objects.get(pk=reviewer.pk).paused_at)
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=reviewer).city, 'Kuala Lumpur')
        r = client.patch(PROFILE, {'paused': False}, format='json')
        self.assertFalse(r.json()['paused'])
