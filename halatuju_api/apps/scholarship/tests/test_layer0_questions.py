"""Layer 0 Sprint 4 — the catalogue governs the QUESTIONS (2026-08-24).

`application_completeness` now asks `requirements.resolve(app, 'question')` which story/funding/
address parts may gate, the way Sprint 3a moved the document gates. These tests pin the seam's
consumers, not the seam (that is `test_requirements.py`'s job):

- PRODUCTION'S SHAPE first: a programme beside an EMPTY catalogue must still gate everything —
  the 3a near-miss (an empty answer opening every gate, invisible to a suite whose fixtures all
  take the fallback branch) is exactly one wrong branch away here too.
- Switching a question off un-gates ONLY that question. Every "it moved" assertion is paired
  with "its neighbour did not" — two things off and everything silently off look identical to a
  test that only checks the two.
- The CORE floor: `consent` and `family_roster` gate whatever an organisation writes.
"""
from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship.models import (
    ApplicationItem, FundingNeed, Programme, ProgrammeApplicationItem,
    ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.services import application_completeness


class _QuestionCaseMixin:
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='q-org', name='Q Org')
        cls.programme = Programme.objects.create(
            organisation=cls.org, code='q-programme', name_en='Q Programme')
        cls.cohort = ScholarshipCohort.objects.create(
            code='q-c', name='Q', year=2026, programme=cls.programme)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='q-user', nric='080404-14-8888')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted')

    def _seed(self):
        from django.core.management import call_command
        call_command('seed_application_catalogue', verbosity=0)

    def _set(self, code, state):
        item = ApplicationItem.objects.get(kind='question', code=code)
        ProgrammeApplicationItem.objects.update_or_create(
            programme=self.programme, item=item, defaults={'state': state})

    def _fill_story(self, **overrides):
        """Fill the four story fields (any of them overridable to '')."""
        values = dict(aspirations='Be an engineer', plans='Study hard',
                      daily_life='School then chores', fears='Fees')
        values.update(overrides)
        for f, v in values.items():
            setattr(self.app, f, v)
        self.app.save()


class TestQuestionGates(_QuestionCaseMixin, TestCase):

    # ── Production's shape: nothing configured must mean "gate as today" ──────

    def test_an_empty_question_catalogue_beside_a_programme_still_gates_everything(self):
        # PRODUCTION'S SHAPE for an organisation onboarded before anyone seeds. An empty
        # resolved set here would flip details/funding/address to vacuously done and let a
        # student with a blank story submit — the exact 3a failure, one kind over.
        self.assertEqual(ApplicationItem.objects.filter(kind='question').count(), 0)
        c = application_completeness(self.app)
        self.assertFalse(c['details_done'])
        self.assertFalse(c['funding_done'])
        self.assertFalse(c['address_done'])

    def test_the_seeded_defaults_reproduce_todays_gates(self):
        # Seeding must change NOTHING: the defaults are today's literals by construction.
        self._seed()
        c = application_completeness(self.app)
        self.assertFalse(c['details_done'])
        self.assertFalse(c['funding_done'])
        self.assertFalse(c['address_done'])
        # …and filling the parts completes them, exactly as before.
        self._fill_story()
        FundingNeed.objects.create(application=self.app, categories=['books'],
                                   programme_months=12)
        self.profile.address, self.profile.postal_code, self.profile.city = (
            'No. 3, Jalan Q', '62100', 'Putrajaya')
        self.profile.save()
        self.app.refresh_from_db()
        c = application_completeness(self.app)
        self.assertTrue(c['details_done'])
        self.assertTrue(c['funding_done'])
        self.assertTrue(c['address_done'])

    # ── Switching off un-gates that question and ONLY that question ───────────

    def test_two_story_questions_off_ungate_them_but_not_their_neighbours(self):
        self._seed()
        self._set('aspirations', 'off')
        self._set('fears', 'off')
        # The two off questions blank → no longer block…
        self._fill_story(aspirations='', fears='')
        self.assertTrue(application_completeness(self.app)['details_done'])
        # …but a still-on neighbour blank must still block, or "two off" is
        # indistinguishable from "everything off".
        self._fill_story(aspirations='', fears='', plans='')
        self.assertFalse(application_completeness(self.app)['details_done'])

    def test_funding_off_makes_the_funding_part_vacuous(self):
        self._seed()
        self._set('funding', 'off')
        self.assertFalse(hasattr(self.app, 'funding_need'))
        self.assertTrue(application_completeness(self.app)['funding_done'])

    def test_address_off_makes_the_address_part_vacuous(self):
        self._seed()
        self._set('address', 'off')
        self.assertEqual((self.profile.address or '').strip(), '')
        self.assertTrue(application_completeness(self.app)['address_done'])

    def test_an_optional_question_accepts_but_never_gates(self):
        self._seed()
        self._set('daily_life', 'optional')
        self._fill_story(daily_life='')
        self.assertTrue(application_completeness(self.app)['details_done'])

    # ── The core floor ────────────────────────────────────────────────────────

    def test_core_questions_gate_even_with_an_explicit_off_row(self):
        # `consent` and `family_roster` are the owner's policy floor. A row written by a
        # migration or bulk edit passes through no UI guard, so the floor must hold here.
        self._seed()
        self._set('consent', 'off')
        self._set('family_roster', 'off')
        c = application_completeness(self.app)
        self.assertFalse(c['consent_done'])   # no consent on file → still gates
        self.assertFalse(c['family_done'])    # empty roster → still gates
