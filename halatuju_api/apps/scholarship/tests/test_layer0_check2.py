"""Layer 0 — the Check-2 pass (2026-08-30): an automatic ask is governed by the catalogue item
it chases.

Sprint 3a deferred this file because it is income-driven but ALSO carries academic and family
follow-ups — gating it wholesale on the income switch would have silenced the wrong asks. The
grain is per code (`GOVERNED_BY`). These tests pin: the defaults change nothing; a switched-off
item silences exactly its asks and no neighbour's; an open ask whose item is off auto-resolves;
and every code is classified, so a new ask cannot slip in unclassified.
"""
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import check2_queries as c2
from apps.scholarship.models import (
    ApplicantDocument, ApplicationItem, Programme, ProgrammeApplicationItem, ResolutionItem,
    ScholarshipApplication, ScholarshipCohort,
)


class _Check2Case(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='c2-org', name='C2 Org')
        cls.programme = Programme.objects.create(
            organisation=cls.org, code='c2-programme', name_en='C2 Programme')
        cls.cohort = ScholarshipCohort.objects.create(
            code='c2-c', name='C2', year=2026, programme=cls.programme)
        call_command('seed_application_catalogue', verbosity=0)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'c2-{self.id()}', name='Priya Devi', nric='030101-14-1234',
            household_income=1200, household_size=3)
        # Submitted, NO snapshot (so the live catalogue governs — the shape of a row backfilled
        # before an override, or a test that wants to move the configuration under it).
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            profile_completed_at=timezone.now(),
            aspirations='I want to teach.', field_of_study='Education',
            siblings_in_tertiary=0, siblings_in_school=0,
            chosen_pathway='stpm', pathway_certainty='sure',
            # Father earns formally with NO payslip → a father_income_proof_missing doc request;
            # mother's slot blank → a mother_status_unknown clarify. Two asks, two governors.
            father_occupation='gov', mother_occupation='')

    def _set(self, code, state, kind='document'):
        item = ApplicationItem.objects.get(kind=kind, code=code)
        ProgrammeApplicationItem.objects.update_or_create(
            programme=self.programme, item=item, defaults={'state': state})


class TestGovernedAsks(_Check2Case):

    def test_the_defaults_change_nothing(self):
        # Same asks with the seeded catalogue as the old literals produced: both fire.
        gaps, proof = c2._gap_sets(self.app)
        self.assertIn('mother_status_unknown', gaps)
        self.assertIn('father_income_proof_missing', proof)

    def test_income_off_silences_the_income_asks_but_not_the_family_ones(self):
        self._set('income_proof', 'off')      # a core item — the floor keeps it required…
        gaps, proof = c2._gap_sets(self.app)
        self.assertIn('father_income_proof_missing', proof)   # …so nothing changes. The floor holds.
        # A programme that genuinely runs no means test is expressed by DEACTIVATING the aggregate
        # platform-side (it is core, so an organisation cannot switch it off) — model that.
        ApplicationItem.objects.filter(kind='document', code='income_proof').update(is_active=False)
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        gaps, proof = c2._gap_sets(fresh)
        self.assertNotIn('father_income_proof_missing', proof)
        self.assertIn('mother_status_unknown', gaps)          # the neighbour still asks

    def test_both_bills_off_silences_the_utility_asks(self):
        self._set('water_bill', 'off')
        self._set('electricity_bill', 'off')
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertFalse(c2._asked(fresh, 'utility_holder_unknown'))
        self.assertFalse(c2._asked(fresh, 'water_bill_recheck'))
        # One bill back on → the shared utility clarifies are asked again (either bill governs).
        self._set('electricity_bill', 'optional')
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertTrue(c2._asked(fresh, 'utility_holder_unknown'))
        self.assertFalse(c2._asked(fresh, 'water_bill_recheck'))   # its own bill is still off

    def test_an_open_ask_whose_item_is_off_auto_resolves(self):
        self._set('school_leaving_cert', 'off')
        ResolutionItem.objects.create(
            application=self.app, source='check2', code='school_leaving_cert_missing',
            fact='academic', kind='doc', doc_type='school_leaving_cert')
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        c2.sync_check2_queries(fresh)
        item = ResolutionItem.objects.get(application=fresh, code='school_leaving_cert_missing')
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')

    def test_a_frozen_application_ignores_a_later_switch(self):
        # Submitted with the defaults frozen; the bills are switched off afterwards → still asked.
        from apps.scholarship import requirements
        requirements.freeze(self.app)
        self._set('water_bill', 'off')
        self._set('electricity_bill', 'off')
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertTrue(c2._asked(fresh, 'utility_holder_unknown'))

    def test_every_check2_code_is_classified(self):
        # The FENCED_OR_EXEMPT shape: an ask added without a governor (or an explicit None) fails
        # here, so it cannot silently fire on a programme that never asked for its evidence.
        codes = set(c2.CLARIFY_SPECS) | set(c2.DOC_SPECS)
        self.assertEqual(codes, set(c2.GOVERNED_BY),
                         'A Check-2 code is missing from GOVERNED_BY (or GOVERNED_BY names a '
                         'code that no longer exists). Classify it: a governing catalogue item, '
                         'or None with the reason it follows a per-student rule.')
        # Every governor names a real seeded catalogue item.
        seeded = {(i.kind, i.code) for i in ApplicationItem.objects.all()}
        for code, governors in c2GOVERNED_ITEMS():
            for g in governors:
                self.assertIn(g, seeded, f'{code} is governed by an unseeded item {g}')


def c2GOVERNED_ITEMS():
    return [(code, governors) for code, governors in c2.GOVERNED_BY.items() if governors]
