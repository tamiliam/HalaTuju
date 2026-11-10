"""Staff nudges Phase A (2026-11-08) — the ONE profile-completion rule, served on `admin/me/`.

`apps/scholarship/profile_completion.py`. Decisions 1-3 of `docs/plans/2026-11-08-staff-nudges.md`:
per-role items (equal weight), done/total/percent, the banner's "important missing" list, and never a
super.
"""
from django.test import TestCase, override_settings

from apps.scholarship import profile_completion
from apps.scholarship.models import Mentor, StaffProfile
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org

ME = '/api/v1/admin/me/'
BASE = ['photo', 'name', 'job_title', 'about', 'phone']
STUDENTS = BASE + ['qualifications', 'language', 'address']
FULL_CARD = {'photo_path': 'staff-photos/1/a.webp', 'job_title': 'Officer', 'about': 'Hello', 'phone': '123456789'}
FULL_REVIEWER = {'highest_qualification': 'Degree', 'university': 'UM', 'graduation_year': 2010,
                 'field_of_study': 'Law', 'english_fluency': 'fluent', 'street_address': '1 Jalan',
                 'postcode': '50000', 'city': 'KL', 'state': 'Selangor'}


def _keys(admin):
    return [i['key'] for i in profile_completion.completion(admin, None)['items']]


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestItemSets(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_staff_without_review_get_the_five_everyone_items(self):
        for role in ('org_admin', 'admin', 'finance', 'qc', 'partner', 'source_partner'):
            with self.subTest(role=role):
                self.assertEqual(_keys(make_admin(role, owning_org=self.org)), BASE)

    def test_a_review_holder_also_gets_qualifications_language_and_address(self):
        self.assertEqual(_keys(make_admin('reviewer', owning_org=self.org)), STUDENTS)
        # The PERMISSION, not the role: an admin given `review` too; an org admin who reviews too.
        self.assertEqual(_keys(make_admin('admin', owning_org=self.org, permissions=['review'])), STUDENTS)
        self.assertEqual(_keys(make_admin('org_admin', owning_org=self.org, permissions=['review'])), STUDENTS)

    def test_a_mentor_login_gets_the_student_items_and_the_mentoring_area(self):
        self.assertEqual(_keys(make_admin('mentor', owning_org=self.org)), STUDENTS + ['mentoring_area'])

    def test_a_staff_member_who_mentors_now_does_too_and_stops_when_they_stop(self):
        mentor = Mentor.objects.create(organisation=self.org)
        qc = make_admin('qc', owning_org=self.org, mentor=mentor)
        self.assertEqual(_keys(qc), STUDENTS + ['mentoring_area'])
        from django.utils import timezone
        Mentor.objects.filter(pk=mentor.pk).update(deactivated_at=timezone.now())
        qc.refresh_from_db()
        self.assertEqual(_keys(qc), BASE)

    def test_a_super_is_never_asked(self):
        self.assertIsNone(profile_completion.completion(make_admin('super', super_admin=True), None))
        self.assertIsNone(profile_completion.completion(None, None))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestScoring(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_nothing_filled_but_the_name(self):
        c = profile_completion.completion(make_admin('admin', owning_org=self.org), None)
        self.assertEqual((c['done'], c['total'], c['percent']), (1, 5, 20))
        self.assertEqual(c['important_missing'], ['photo', 'phone'])

    def test_three_of_five_is_sixty_and_percent_rounds_down(self):
        admin = make_admin('admin', owning_org=self.org)
        p = StaffProfile.objects.create(partner_admin=admin, job_title='Officer', phone='123')
        c = profile_completion.completion(admin, p)
        self.assertEqual((c['done'], c['total'], c['percent']), (3, 5, 60))
        self.assertEqual(c['important_missing'], ['photo'])
        reviewer = make_admin('reviewer', owning_org=self.org)
        p = StaffProfile.objects.create(partner_admin=reviewer, **FULL_CARD)   # 5 of 8 = 62.5
        self.assertEqual(profile_completion.completion(reviewer, p)['percent'], 62)

    def test_blank_text_does_not_count(self):
        admin = make_admin('admin', owning_org=self.org)
        p = StaffProfile.objects.create(partner_admin=admin, job_title='   ', about='\n', phone=' ')
        self.assertEqual(profile_completion.completion(admin, p)['done'], 1)

    def test_everything_filled_is_one_hundred(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        p = StaffProfile.objects.create(partner_admin=reviewer, **FULL_CARD, **FULL_REVIEWER)
        c = profile_completion.completion(reviewer, p)
        self.assertEqual((c['done'], c['total'], c['percent'], c['important_missing']), (8, 8, 100, []))
        self.assertTrue(all(i['done'] for i in c['items']))

    def test_qualifications_are_one_item_needing_all_four_parts(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        p = StaffProfile.objects.create(partner_admin=reviewer, **{**FULL_REVIEWER, 'graduation_year': None})
        done = {i['key']: i['done'] for i in profile_completion.completion(reviewer, p)['items']}
        self.assertFalse(done['qualifications'])
        self.assertTrue(done['language'] and done['address'])

    def test_language_needs_en_bm_or_ta_at_conversational_and_the_fourth_never_counts(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        p = StaffProfile.objects.create(partner_admin=reviewer, other_language='Mandarin',
                                        other_language_fluency='fluent', tamil_fluency='')
        done = {i['key']: i['done'] for i in profile_completion.completion(reviewer, p)['items']}
        self.assertFalse(done['language'])
        p.bm_fluency = 'conversational'
        done = {i['key']: i['done'] for i in profile_completion.completion(reviewer, p)['items']}
        self.assertTrue(done['language'])

    def test_address_needs_all_four_parts_and_is_never_important(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        p = StaffProfile.objects.create(partner_admin=reviewer, **{**FULL_CARD, **FULL_REVIEWER, 'city': ''})
        c = profile_completion.completion(reviewer, p)
        self.assertFalse({i['key']: i['done'] for i in c['items']}['address'])
        self.assertEqual(c['important_missing'], [])

    def test_a_mentor_without_an_area_has_it_in_the_important_list(self):
        mentor = make_admin('mentor', owning_org=self.org)
        c = profile_completion.completion(mentor, None, '')
        self.assertEqual(c['important_missing'], ['photo', 'phone', 'mentoring_area'])
        c = profile_completion.completion(mentor, None, 'Engineering')
        self.assertEqual(c['important_missing'], ['photo', 'phone'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestServedOnAdminMe(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_get_serves_it(self):
        admin = make_admin('admin', owning_org=self.org)
        StaffProfile.objects.create(partner_admin=admin, job_title='Officer', phone='123')
        c = authed_client(admin).get(ME).json()['completion']
        self.assertEqual((c['done'], c['total'], c['percent'], c['important_missing']), (3, 5, 60, ['photo']))
        self.assertEqual([i['key'] for i in c['items']], BASE)

    def test_a_super_is_served_none(self):
        self.assertIsNone(authed_client(make_admin('super', super_admin=True)).get(ME).json()['completion'])

    def test_patch_answers_the_new_completion(self):
        admin = make_admin('finance', owning_org=self.org)
        c = authed_client(admin).patch(ME, {'phone': '123456789', 'about': 'Hi'},
                                       content_type='application/json').json()['completion']
        self.assertEqual((c['done'], c['important_missing']), (3, ['photo']))

    def test_a_mentor_reads_its_area_in_the_completion(self):
        mentor = make_admin('mentor', owning_org=self.org)
        Mentor.objects.filter(pk=mentor.mentor_id).update(area='Engineering')
        c = authed_client(mentor).get(ME).json()['completion']
        self.assertTrue({i['key']: i['done'] for i in c['items']}['mentoring_area'])

    def test_a_source_user_is_served_it(self):
        c = authed_client(make_admin('source_partner', owning_org=self.org)).get(ME).json()['completion']
        self.assertEqual([i['key'] for i in c['items']], BASE)

    def test_the_photo_delete_answers_the_completion(self):
        admin = make_admin('admin', owning_org=self.org)
        r = authed_client(admin).delete(ME + 'photo/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['completion']['important_missing'], ['photo', 'phone'])
