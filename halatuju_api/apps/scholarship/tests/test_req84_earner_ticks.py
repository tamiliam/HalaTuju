"""Request #84 (2026-11-25): a "working" tick on the income step that the family details disagree with.

The fault: the student ticked father, mother, guardian, brother and sister as working, while the
family details say the mother is unemployed and list no guardian or siblings; the case page showed
"Earns" for each. ONE rule (``family.earner_tick_conflicts``) says, per member, what a tick would
disagree with; the student's income step asks before saving such a tick, and the officer's card
warns. A WARNING only: what is owed (the blockers) does not read it.
"""
from types import SimpleNamespace

from django.test import TestCase, override_settings

from apps.scholarship.family import earner_tick_conflicts, earner_tick_warnings
from apps.scholarship.serializers.application_read import ApplicationReadSerializer
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application,
)


def _roster(**kw):
    base = dict(father_name='', father_occupation='', mother_name='', mother_occupation='',
                other_family_members=[], income_route='salary', income_working_members=[])
    base.update(kw)
    return SimpleNamespace(**base)


#: The #84 shape: father works, mother unemployed, nobody else listed, every member ticked.
CASE_84 = dict(father_name='A', father_occupation='factory', mother_name='B',
               mother_occupation='unemployed',
               income_working_members=['father', 'mother', 'guardian', 'brother', 'sister'])


class TestTheOneRule(TestCase):
    def test_the_84_shape(self):
        self.assertEqual(earner_tick_conflicts(_roster(**CASE_84)), {
            'mother': {'kind': 'not_working', 'occupation': 'unemployed'},
            'guardian': {'kind': 'not_listed'},
            'brother': {'kind': 'not_listed'},
            'sister': {'kind': 'not_listed'},
        })

    def test_every_non_earning_code_disagrees(self):
        for code in ('homemaker', 'retired', 'unemployed', 'unable', 'deceased', 'no_contact'):
            with self.subTest(code=code):
                got = earner_tick_conflicts(_roster(father_name='A', father_occupation=code))
                self.assertEqual(got['father'], {'kind': 'not_working', 'occupation': code})

    def test_earning_other_and_blank_occupations_agree(self):
        for code in ('factory', 'hawker', 'other', ''):
            with self.subTest(code=code):
                got = earner_tick_conflicts(_roster(father_name='A', father_occupation=code))
                self.assertNotIn('father', got)

    def test_a_parent_with_no_name_and_no_occupation_is_not_listed(self):
        got = earner_tick_conflicts(_roster(father_name='A', father_occupation='factory'))
        self.assertEqual(got['mother'], {'kind': 'not_listed'})

    def test_pool_members_any_earning_entry_agrees(self):
        pool = [{'role': 'brother', 'occupation': 'unemployed'},
                {'role': 'brother', 'occupation': 'driver'},
                {'role': 'sister', 'occupation': 'homemaker'},
                {'role': 'guardian', 'occupation': ''}]
        got = earner_tick_conflicts(_roster(father_name='A', other_family_members=pool))
        self.assertNotIn('brother', got)
        self.assertNotIn('guardian', got)   # listed, occupation blank: the details say nothing
        self.assertEqual(got['sister'], {'kind': 'not_working', 'occupation': 'homemaker'})

    def test_no_roster_at_all_compares_nothing(self):
        self.assertEqual(earner_tick_conflicts(_roster(income_working_members=['father'])), {})


class TestTheSavedTicks(TestCase):
    def test_only_ticked_members_in_tick_order(self):
        app = _roster(**dict(CASE_84, income_working_members=['sister', 'father', 'mother']))
        self.assertEqual(earner_tick_warnings(app), [
            {'member': 'sister', 'kind': 'not_listed'},
            {'member': 'mother', 'kind': 'not_working', 'occupation': 'unemployed'},
        ])

    def test_off_the_salary_route_no_warning(self):
        for route in ('str', ''):
            with self.subTest(route=route):
                self.assertEqual(earner_tick_warnings(_roster(**dict(CASE_84, income_route=route))), [])

    def test_junk_ticks_are_tolerated(self):
        self.assertEqual(earner_tick_warnings(_roster(**dict(CASE_84, income_working_members=None))), [])
        app = _roster(**dict(CASE_84, income_working_members=['mother', 'mother', 'cousin']))
        self.assertEqual([w['member'] for w in earner_tick_warnings(app)], ['mother'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestItIsServed(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app = make_application('interviewing', income_route='salary', **CASE_84)
        cls.admin = make_admin('org_admin', owning_org=cls.app.owning_organisation)

    def test_the_officer_payload_carries_the_warnings(self):
        r = authed_client(self.admin).get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertEqual([w['member'] for w in r.json()['earner_tick_warnings']],
                         ['mother', 'guardian', 'brother', 'sister'])

    def test_the_student_payload_carries_the_per_member_answer(self):
        served = ApplicationReadSerializer(self.app).data['earner_tick_conflicts']
        self.assertEqual(set(served), {'mother', 'guardian', 'brother', 'sister'})
        self.assertEqual(served['mother'], {'kind': 'not_working', 'occupation': 'unemployed'})


class TestWhatIsOwedDoesNotMove(TestCase):
    """Step 5 of the brief: the promise is a check and a warning, not a change to what is owed.
    The blockers for a disagreeing tick are the blockers for the same tick with no disagreement."""

    def test_blockers_ignore_the_disagreement(self):
        from apps.scholarship.income_engine import income_requirements
        disagreeing = make_application('submitted', income_route='salary', **CASE_84)
        agreeing = make_application('submitted', income_route='salary', **dict(
            CASE_84, mother_occupation='factory',
            other_family_members=[{'role': r, 'occupation': 'factory'}
                                  for r in ('guardian', 'brother', 'sister')]))
        self.assertTrue(earner_tick_warnings(disagreeing))
        self.assertEqual(earner_tick_warnings(agreeing), [])
        owed = income_requirements(disagreeing)
        self.assertEqual(owed, income_requirements(agreeing))
        # …and every ticked member, the disagreeing ones included, still owes their own proof.
        self.assertEqual({b['member'] for b in owed['members']},
                         {'father', 'mother', 'guardian', 'brother', 'sister'})
