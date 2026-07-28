"""PF-2 — module flags vs what an organisation actually does.

The flags drifted from production for one reason: **nothing connected them to reality.** They
are written once at onboarding and read by no gate, so `module_payout` sat at False through
15 payment runs, 19 disbursements and 46 Vircle wallets without anything noticing.

These tests pin the check that makes the later enforcement sprint safe to switch on. They also
encode the one asymmetry that matters: only "flag OFF while the evidence exists" is drift.
"""
from decimal import Decimal

from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import module_flags
from apps.scholarship.models import (
    PaymentRun, ScholarshipApplication, ScholarshipCohort, Sponsor, Sponsorship,
    WhatsAppMessage,
)


class TestModuleFlagDrift(TestCase):
    @classmethod
    def setUpTestData(cls):
        # module_scholarship=True on purpose: this org is given an application below, and an
        # org with applications whose scholarship flag is False is ITSELF drift. A fixture that
        # is internally inconsistent makes every drift assertion below ambiguous — the first
        # draft of this file had exactly that bug, and the detector caught it.
        cls.org = PartnerOrganisation.objects.create(
            code='bp', name='BrightPath', module_scholarship=True)
        cls.cohort = ScholarshipCohort.objects.create(
            code='c1', name='c1', year=2026, owning_organisation=cls.org)
        prof = StudentProfile.objects.create(
            supabase_user_id='s1', nric='010101-14-0001', name='Stud')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=prof, status='submitted')

    def test_an_org_with_no_activity_has_no_drift(self):
        """A brand-new tenant must be quiet. If this reported drift, whoever runs the check
        would learn to ignore it, and the check would be worthless on the day it matters."""
        empty = PartnerOrganisation.objects.create(code='new', name='New Tenant')
        self.assertEqual(module_flags.drift(empty), {})

    def test_the_EXACT_brightpath_situation_is_detected(self):
        """The case this whole sprint came from: payment runs exist, module_payout is False.
        Written as the real scenario, so if the detector is ever weakened this fails with a
        recognisable name rather than an abstract one."""
        PaymentRun.objects.create(organisation=self.org, reference='PR-2026-08-01',
                                  payment_date='2026-08-01', period_month='2026-08-01')
        self.org.module_payout = False
        self.org.save(update_fields=['module_payout'])

        d = module_flags.drift(self.org)
        self.assertIn('module_payout', d)
        flag_value, evidence = d['module_payout']
        self.assertFalse(flag_value)
        self.assertEqual(evidence, 1)

    def test_reconciling_the_flag_clears_the_drift(self):
        """What migration courses/0067 does, asserted end to end."""
        PaymentRun.objects.create(organisation=self.org, reference='PR-2026-08-01',
                                  payment_date='2026-08-01', period_month='2026-08-01')
        self.org.module_payout = True
        self.org.save(update_fields=['module_payout'])
        self.assertNotIn('module_payout', module_flags.drift(self.org))

    def test_a_flag_ON_with_no_evidence_yet_is_NOT_drift(self):
        """A module is routinely switched on before its first row exists. Reporting that as an
        error is how a useful check becomes noise that people mute."""
        self.org.module_payout = True
        self.org.save(update_fields=['module_payout'])
        self.assertEqual(module_flags.drift(self.org), {})

    def test_every_module_flag_is_covered_by_evidence(self):
        """Completeness: a fifth flag added to the model without a matching evidence rule would
        be invisible to this check, which is exactly how the first drift went unnoticed."""
        model_flags = {f.name for f in PartnerOrganisation._meta.get_fields()
                       if f.name.startswith('module_')}
        self.assertEqual(
            model_flags, set(module_flags.MODULE_EVIDENCE),
            'A module_* flag exists with no evidence rule (or vice versa). Add it to '
            'MODULE_EVIDENCE, or this flag can drift from production unnoticed.')

    def test_evidence_is_scoped_to_the_organisation(self):
        """Another tenant's activity must never justify this tenant's flag."""
        other = PartnerOrganisation.objects.create(code='in', name='Inspire')
        PaymentRun.objects.create(organisation=other, reference='PR-X',
                                  payment_date='2026-08-01', period_month='2026-08-01')
        self.assertEqual(module_flags.evidence_counts(self.org)['payment_runs'], 0)
        self.assertEqual(module_flags.evidence_counts(other)['payment_runs'], 1)

    def test_all_four_evidence_paths_actually_resolve(self):
        """Each count traverses a different relationship; a renamed FK would silently return 0
        and read as 'no evidence', which is the failure mode that looks like success."""
        sponsor = Sponsor.objects.create(supabase_user_id='sp1', name='S', email='s@x.com')
        Sponsorship.objects.create(sponsor=sponsor, application=self.app,
                                   amount=Decimal('1000'), status='offered')
        WhatsAppMessage.objects.create(application=self.app, kind='interview_reminder_1day')
        PaymentRun.objects.create(organisation=self.org, reference='PR-1',
                                  payment_date='2026-08-01', period_month='2026-08-01')

        counts = module_flags.evidence_counts(self.org)
        self.assertEqual(counts['applications'], 1)
        self.assertEqual(counts['sponsorships'], 1)
        self.assertEqual(counts['whatsapp_messages'], 1)
        self.assertEqual(counts['payment_runs'], 1)
