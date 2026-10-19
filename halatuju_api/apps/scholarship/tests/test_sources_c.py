"""Sources and referral partners, Sprint C (2026-10-19) — each APPLICATION keeps its own answer.

Owner's rulings (2026-10-09, accepted for Sprint C):
1. partner emails and Sources counts count the answer given ON THAT APPLICATION, not the
   student's latest answer;
2. the witness comes from the source only, never from the referral partner;
3. only a super records a witness (until sources have logins) — `test_bursary_agreement.py`;
4. a `?ref=` link never pre-fills the bursary form's "Who referred you?";
5. CUMIG (source) and CUMIG (referral partner) contact details stay separate (Sprint B).

Plus TD-381 part 4 (source names every list role can read, fenced) and TD-386 (a), (b).
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.db import connection
from django.test import TestCase, override_settings

from apps.courses.models import PartnerOrganisation
from apps.scholarship import partner_comms
from apps.scholarship.bursary import _resolve_witness_org
from apps.scholarship.models import ProgrammeReferralSource, ScholarshipApplication
from apps.scholarship.services import apply_gate
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_shortlistable_student, make_source, make_student,
)
from apps.scholarship.views_admin import _source_application_counts

FILL = import_module('apps.scholarship.migrations.0174_application_source')
APPLY = '/api/v1/scholarship/applications/'
NAMES = '/api/v1/admin/scholarship/source-names/'
GATE = '/api/v1/scholarship/apply-gate/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _TwoOrganisations(TestCase):
    """A runs an open gift offering SMC and CUMIG (CUMIG is also the platform referral partner);
    B is a second tenant with its OWN `smc` and an open gift of its own."""

    @classmethod
    def setUpTestData(cls):
        cls.a = make_org('sc-a')
        cls.b = make_org('sc-b')
        cls.gift_a = make_programme(organisation=cls.a, code='sc-gift-a', is_active=True)
        cls.gift_b = make_programme(organisation=cls.b, code='sc-gift-b', is_active=True)
        cls.round_a = make_cohort(programme=cls.gift_a, code='sc-a-2026', is_open=True,
                                  is_active=True)
        cls.round_b = make_cohort(programme=cls.gift_b, code='sc-b-2026', is_open=True,
                                  is_active=True)
        cls.cumig = PartnerOrganisation.objects.create(code='cumig', name='CUMIG',
                                                       is_referral_partner=True,
                                                       contact_email='rp@cumig.test')
        cls.cumig_source = make_source(cls.a, 'cumig', pk=cls.cumig.pk,
                                       contact_email='src@cumig.test')
        cls.smc_a = make_source(cls.a, 'smc', name='SMC A', contact_email='a@smc.test')
        cls.smc_b = make_source(cls.b, 'smc', name='SMC B', contact_email='b@smc.test')
        cls.pptm = make_source(cls.a, 'pptm', name='PPTM')
        for source in (cls.cumig_source, cls.smc_a, cls.pptm):
            ProgrammeReferralSource.objects.create(programme=cls.gift_a, source=source)
        ProgrammeReferralSource.objects.create(programme=cls.gift_b, source=cls.smc_b)

    def _apply(self, student, code, gift='sc-gift-a'):
        return authed_client(student).post(APPLY, {
            'household_income': 2500, 'receives_str': True, 'consent_to_contact': True,
            'programme_code': gift, 'referral_source': code,
        }, format='json')


class TestTheSubmitKeepsTheAnswerOnTheApplication(_TwoOrganisations):
    def test_a_source_a_fixed_choice_and_blank(self):
        for code, source in (('smc', self.smc_a), ('cumig', self.cumig_source),
                             ('other', None), ('halatuju', None), ('', None)):
            with self.subTest(code=code):
                student = make_shortlistable_student()
                self.assertEqual(self._apply(student, code).status_code, 201)
                app = ScholarshipApplication.objects.get(profile=student)
                self.assertEqual((app.referral_code, app.source_id),
                                 (code, getattr(source, 'pk', None)))
                # The column and the frozen snapshot say the same thing.
                self.assertEqual(app.intake_snapshot['profile']['referral_source'], code)

    def test_the_source_is_the_applications_own_organisations(self):
        """TD-386 (a): B's `smc` answered on B's gift is B's source — never A's, though A has one
        with the same code, and whatever her profile said before."""
        student = make_shortlistable_student(source=self.smc_a, referral_source='smc')
        self.assertEqual(self._apply(student, 'smc', gift='sc-gift-b').status_code, 201)
        app = ScholarshipApplication.objects.get(profile=student)
        self.assertEqual((app.owning_organisation_id, app.source_id), (self.b.pk, self.smc_b.pk))


class TestALaterAnswerNeverMovesAnEarlierApplication(_TwoOrganisations):
    """Owner's ruling 1: the counts and emails count the answer given ON THAT APPLICATION."""

    def setUp(self):
        old_round = make_cohort(programme=self.gift_a, code='sc-a-2025', is_open=False)
        self.student = make_shortlistable_student(referral_source='smc')
        self.first = make_application('expired', cohort=old_round, student=self.student)
        self.assertEqual(self.first.source_id, self.smc_a.pk)
        self.assertEqual(self._apply(self.student, 'pptm').status_code, 201)
        self.second = ScholarshipApplication.objects.exclude(pk=self.first.pk).get(
            profile=self.student)

    def test_each_application_keeps_its_own_source(self):
        self.first.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.student.referral_source, 'pptm')          # her LATEST answer
        self.assertEqual((self.first.referral_code, self.first.source_id), ('smc', self.smc_a.pk))
        self.assertEqual((self.second.referral_code, self.second.source_id),
                         ('pptm', self.pptm.pk))

    def test_counts_and_partner_emails_follow_each_application(self):
        counts = _source_application_counts()
        self.assertEqual((counts.get(self.smc_a.pk, 0), counts.get(self.pptm.pk, 0)), (1, 1))
        self.assertEqual(list(partner_comms.partner_applications(self.smc_a)), [self.first])
        self.assertEqual(list(partner_comms.partner_applications(self.pptm)), [self.second])
        # One predicate: the screen's count IS the email's set, for every source.
        for source in (self.smc_a, self.smc_b, self.pptm, self.cumig_source):
            self.assertEqual(counts.get(source.pk, 0),
                             partner_comms.partner_applications(source).count(), source.code)

    def test_the_applications_filter_reads_the_application(self):
        oa = make_admin('org_admin', owning_org=self.a)
        rows = authed_client(oa).get('/api/v1/admin/scholarship/applications/?source=smc').json()
        self.assertEqual([r['id'] for r in rows['applications']], [self.first.pk])
        self.assertEqual(rows['applications'][0]['referral_source'], 'smc')


class TestTheWitnessIsTheApplicationsSource(_TwoOrganisations):
    def test_a_referral_partner_alone_is_no_witness_and_is_never_emailed(self):
        """Owner's ruling 2 / TD-386 (b): a `?ref=cumig` student who named no source has no
        witness organisation — CUMIG's referral-partner row is never paired with its source."""
        student = make_student(referred_by_org=self.cumig, referral_source='other')
        app = make_application('awarded', cohort=self.round_a, student=student)
        self.assertIsNone(app.source_id)
        self.assertIsNone(_resolve_witness_org(app))

    def test_the_profiles_later_source_is_not_the_witness(self):
        """TD-386 (a): she applied to A naming SMC A, then her profile's source moved (another
        organisation's form). A's witness is still A's SMC."""
        student = make_student(referral_source='smc')
        app = make_application('awarded', cohort=self.round_a, student=student)
        student.source = self.smc_b
        student.save(update_fields=['source'])
        app.refresh_from_db()
        self.assertEqual(_resolve_witness_org(app), self.smc_a)

    def test_the_cockpit_serves_the_source_under_both_keys(self):
        app = make_application('profile_complete', cohort=self.round_a,
                               student=make_student(referral_source='smc',
                                                    referred_by_org=self.cumig))
        body = authed_client(make_admin('super', super_admin=True)).get(
            f'/api/v1/admin/scholarship/applications/{app.pk}/').json()
        want = {'id': self.smc_a.pk, 'code': 'smc', 'name': 'SMC A'}
        self.assertEqual((body['source'], body['referred_by_org'], body['referral_source']),
                         (want, want, 'smc'))


class TestSourceNames(_TwoOrganisations):
    """TD-381 part 4: the Applications filter's names, for EVERY list role, fenced."""

    def _names(self, admin, org=None):
        return authed_client(admin).get(NAMES, {'org': org} if org else None)

    def test_every_list_role_gets_its_own_organisations_names_only(self):
        for role in ('org_admin', 'admin', 'reviewer', 'qc'):
            with self.subTest(role=role):
                resp = self._names(make_admin(role, owning_org=self.a))
                self.assertEqual(resp.status_code, 200, resp.content)
                self.assertEqual(resp.json(), {'sources': [
                    {'code': 'cumig', 'name': 'CUMIG'}, {'code': 'pptm', 'name': 'PPTM'},
                    {'code': 'smc', 'name': 'SMC A'}]})

    def test_a_switched_off_source_is_still_named(self):
        """Old applicants stay filterable after a source is switched off."""
        self.pptm.is_active = False
        self.pptm.save(update_fields=['is_active'])
        codes = [s['code'] for s in self._names(make_admin('qc', owning_org=self.a)).json()['sources']]
        self.assertIn('pptm', codes)

    def test_roles_without_the_list_are_refused(self):
        for role in ('finance', 'partner'):
            with self.subTest(role=role):
                self.assertEqual(self._names(make_admin(role, owning_org=self.a)).status_code, 403)

    def test_a_super_is_global_and_narrows_by_org(self):
        sup = make_admin('super', super_admin=True)
        names = {(s['code'], s['name']) for s in self._names(sup).json()['sources']}
        self.assertTrue({('smc', 'SMC A'), ('smc', 'SMC B')} <= names)
        self.assertEqual(self._names(sup, 'sc-b').json(),
                         {'sources': [{'code': 'smc', 'name': 'SMC B'}]})
        self.assertEqual(self._names(sup, 'nope').status_code, 404)

    def test_an_organisation_less_caller_gets_none(self):
        self.assertEqual(self._names(make_admin('reviewer')).json(), {'sources': []})

    def test_names_only_never_a_contact(self):
        body = self._names(make_admin('reviewer', owning_org=self.a)).content.decode()
        for planted in ('a@smc.test', 'src@cumig.test'):
            self.assertIn(planted, {self.smc_a.contact_email, self.cumig_source.contact_email})
            self.assertNotIn(planted, body)


class TestTheApplyFormPrefill(_TwoOrganisations):
    """Owner's ruling 4: a `?ref=` code never pre-fills "Who referred you?"; only her own earlier
    answer to the SAME organisation does."""

    def _gate(self, student, code):
        return authed_client(student).get(f'{GATE}?programme={code}').json()

    def test_a_ref_code_on_the_profile_never_prefills(self):
        student = make_student(referral_source='cumig', referred_by_org=self.cumig)
        self.assertEqual(self._gate(student, 'sc-gift-a')['referral'], '')

    def test_her_earlier_answer_to_this_organisation_prefills(self):
        student = make_student(referral_source='other')        # the chip moved on since
        old = make_cohort(programme=self.gift_a, code='sc-a-old', is_open=False)
        make_application('expired', cohort=old, student=student, referral_code='smc')
        self.assertEqual(self._gate(student, 'sc-gift-a')['referral'], 'smc')

    def test_an_answer_to_another_organisation_never_prefills(self):
        student = make_student()
        old = make_cohort(programme=self.gift_b, code='sc-b-old', is_open=False)
        make_application('expired', cohort=old, student=student, referral_code='smc')
        self.assertEqual(self._gate(student, 'sc-gift-a')['referral'], '')
        self.assertEqual(self._gate(student, 'sc-gift-b')['referral'], 'smc')

    def test_several_open_rounds_and_no_profile_answer_blank(self):
        self.assertEqual(apply_gate.earlier_referral(None, 'sc-gift-a'), '')
        student = make_student()
        make_application('expired', cohort=make_cohort(programme=self.gift_a, is_open=False),
                         student=student, referral_code='smc')
        self.assertEqual(apply_gate.earlier_referral(student, ''), '')    # A and B both open


class TestTheBackfill(TestCase):
    """scholarship 0174's data step: the snapshot's answer, resolved inside the application's
    OWN organisation — the same rule as the submit (`gift_sources.submitted_source`)."""

    def test_every_shape(self):
        a, b = make_org('bf-a'), make_org('bf-b')
        smc_a = make_source(a, 'smc')
        make_source(b, 'only-b')
        round_a = make_cohort(programme=make_programme(organisation=a))
        cases = (({'profile': {'referral_source': 'smc'}}, 'smc', smc_a.pk),
                 ({'profile': {'referral_source': 'other'}}, 'other', None),
                 ({'profile': {'referral_source': 'only-b'}}, 'only-b', None),   # B's, not A's
                 ({'profile': {'referral_source': None}}, '', None),
                 ({'profile': 'odd'}, '', None),
                 ({}, '', None))
        apps = [make_application(cohort=round_a, student=make_student(), intake_snapshot=snap)
                for snap, _, _ in cases]
        ScholarshipApplication.objects.update(referral_code='stale', source=None)
        for _ in range(2):                                   # idempotent
            FILL.fill_from_snapshot(live_apps, connection.schema_editor())
        for app, (_, code, source_id) in zip(apps, cases):
            app.refresh_from_db()
            self.assertEqual((app.referral_code, app.source_id), (code, source_id))

    def test_the_old_image_can_still_insert(self):
        """Between the hand-applied migration and the deploy, the serving image inserts
        applications without naming `referral_code`: the database default answers for it."""
        round_ = make_cohort()
        fields = [f for f in ScholarshipApplication._meta.concrete_fields
                  if f.name not in ('id', 'referral_code', 'source')]
        probe = ScholarshipApplication(cohort=round_, profile=make_student())
        values = [f.get_db_prep_save(f.pre_save(probe, add=True), connection) for f in fields]
        cols = ', '.join(connection.ops.quote_name(f.column) for f in fields)
        marks = ', '.join(['%s'] * len(fields))
        with connection.cursor() as cur:
            cur.execute(f'INSERT INTO scholarship_applications ({cols}) VALUES ({marks})', values)
        row = ScholarshipApplication.objects.get(cohort=round_)
        self.assertEqual((row.referral_code, row.source_id), ('', None))
