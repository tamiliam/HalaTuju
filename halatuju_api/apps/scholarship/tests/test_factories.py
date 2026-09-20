"""Code health H5 — THE FACTORY MAY NOT DRIFT FROM THE PRODUCT.

`factories.make_application` builds each stage by SETTING FIELDS, because the suite is 6,760
tests and walking the whole funnel for every fixture would make all of them slower. The price
of that shortcut is exactly the failure H5 exists to stop: a fixture that describes a state the
product cannot produce, asserted against by a test that can therefore never reach the branch it
names (BrightPath request #24, 2026-09-18).

This file is the price being paid. For every stage in `factories.STAGES` it walks a FRESH
application to that stage **through the real services and the real HTTP endpoints**, and asserts
the factory-built application at the same stage carries the same values for a declared set of
stage-defining fields (`factories.STAGE_FIELDS` + the derived facts in `_snapshot`). When the
product changes, this goes red and the factory is corrected — which is the whole difference
between a factory and the stale fixture it replaces.

⚠ BOTH ROADS TO QC ARE WALKED AND COMPARED SEPARATELY, and
`test_the_decline_road_leaves_no_verify_stamps` is the one that would have caught #24: the
decline road must leave `verified_at` NULL, because `submit-decline` never writes it.

WHAT IS MOCKED: `views_admin.verdict.build_verdict` (the verdict engine's read of the applicant's
documents) — the same seam `test_qc_gate.py` already patches, and for the same reason: these
fixtures carry stub documents, so the real verdict would be all-gaps and the QC gap floor would
refuse every accept. Emails go to Django's locmem backend as everywhere else. Nothing else is
mocked: every status change below is made by the product.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import closure, disbursement, pool, services, sponsorship
from apps.scholarship.models import (
    ApplicantDocument, Consent, Donation, FundingNeed, InterviewSession,
    ScholarshipApplication, Sponsor, SponsorProfile,
)
from apps.scholarship.tests import factories
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
    make_shortlistable_student as make_student,
)

#: The anonymous profile the reviewer's finalise prepares. Published by QC-Accept, never before.
ANON_MARKDOWN = 'A determined SPM leaver hoping to read engineering.'

#: Actor columns hold an email address, which legitimately differs between a walked application
#: (a real admin row) and a factory-built one. What is stage-defining is whether the product
#: wrote an actor there AT ALL — the same rule as the timestamps.
BLANKNESS_ONLY = frozenset({
    'verdict_decided_by', 'verified_by', 'recommended_by', 'rejected_by',
    'pending_decline_by', 'closed_by',
})


def _snapshot(application):
    """The stage-defining facts, reduced so two applications built minutes apart compare.

    Timestamps → NULL vs NOT NULL. Actor emails → blank vs written. Everything else by value,
    plus four derived facts no single column carries."""
    application.refresh_from_db()
    out = {}
    for field in factories.STAGE_FIELDS:
        value = getattr(application, field)
        if field in factories.NULLNESS_ONLY:
            out[field] = value is not None
        elif field in BLANKNESS_ONLY:
            out[field] = bool(value)
        else:
            out[field] = value
    profile = application.profile
    out['profile.nric_verified'] = bool(profile and profile.nric_verified)
    out['verify_checklist_written'] = bool(application.verify_checklist)
    out['officer_verdict.overall'] = (application.officer_verdict or {}).get('overall', '')
    out['requirements_frozen'] = bool(application.requirements_snapshot)
    out['in_the_fundable_pool'] = application.id in set(
        pool.eligible_pool_queryset(ScholarshipApplication).values_list('id', flat=True))
    return out


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    AWARD_COOLOFF_DAYS=0, DECLINE_QC_COOLOFF_HOURS=24,
    BURSARY_AGREEMENT_ENABLED=False, CHECK2_AUTO_GENERATE=False,
    PROFILE_COMPLETE_EMAIL_ENABLED=False, STUDENT_ASSIGNMENT_EMAIL_ENABLED=False,
)
class TestTheFactoryMatchesTheProduct(TestCase):
    """One walk per road, done once for the whole class; one assertion method per stage."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        # The B40 fence compares the admin's `owning_organisation` with the application's, so
        # a non-super acting on these cases must sit inside the cohort's organisation.
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.superadmin = make_admin('super', super_admin=True)
        # ONE patch around both walks: the verdict engine's document read. See the module
        # docstring — the same seam test_qc_gate.py patches, for the same reason.
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        try:
            cls.walked = {}
            cls.walked.update(cls._walk('recommend'))
            cls.walked.update(cls._walk('decline'))
            cls.walked.update(cls._walk_to_expired())
        finally:
            patcher.stop()
        cls.built = {stage: _snapshot(cls._build(stage)) for stage in cls._stage_keys()}

    # ── building the same stage with the factory ────────────────────────────────────────────
    @classmethod
    def _stage_keys(cls):
        """Every stage, with the QC roads spelled out — the keys `walked` and `built` share."""
        keys = []
        for stage in factories.STAGES:
            if stage in factories.OUTCOME_STAGES:
                keys += [f'{stage}:{outcome}' for outcome in factories.OUTCOMES]
            else:
                keys.append(stage)
        return keys

    @classmethod
    def _build(cls, key):
        stage, _, outcome = key.partition(':')
        # `reviewer` is passed only from the stage a reviewer is actually attached, because
        # naming one earlier tells the factory to attach it early — a legitimate override, but
        # not what the product does, and the comparison must be against the product.
        attached = factories.stage_reaches(stage, 'assigned')
        return make_application(
            stage, outcome=outcome or None, cohort=cls.cohort, student=make_student(),
            reviewer=cls.reviewer if attached else None)

    # ── walking the same stage through the product ──────────────────────────────────────────
    @classmethod
    def _complete_the_profile(cls, application):
        """Everything `services.application_completeness` asks for — the STR route with a
        father earner, the compulsory documents and a structured family roster. Copied in
        substance from `test_phase_c.PhaseCBase._complete`, which is how the suite has built a
        completable application since Phase C."""
        FundingNeed.objects.create(
            application=application, categories=['living'], programme_months=36)
        for doc_type in ('ic', 'results_slip', 'offer_letter', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(
                application=application, doc_type=doc_type, storage_path=f'test/{doc_type}')
        Consent.objects.create(application=application, version='t', is_active=True)
        ScholarshipApplication.objects.filter(pk=application.pk).update(
            income_route='str', income_earner='father',
            father_name='AROON', father_occupation='driver',
            mother_name='KOMATHI', mother_occupation='homemaker',
            siblings_in_school=1, siblings_in_tertiary=0,
            # The four "your story" answers — the narrative half of the completeness gate.
            aspirations='Be an auditor', plans='Study hard',
            daily_life='Help at home each evening', fears='Worried about fees')
        application.refresh_from_db()

    @classmethod
    def _walk_to_expired(cls):
        """The OTHER branch: a shortlisted student who never completes. The daily sweep sends
        R1–R4 and then, five days after the final one, auto-closes the case. Walked with a
        moving ``now`` because that is the only input the sweep takes."""
        student = make_student()
        application = services.create_application(
            profile=student, cohort=cls.cohort,
            validated_data={'consent_to_contact': True, 'intends_tertiary_2026': True},
            to_email=student.contact_email, lang='en')
        services.score_application(application)
        application.refresh_from_db()
        services.release_decision(application)
        application.refresh_from_db()
        anchor = application.reminder_anchor_at
        for days in services.REMINDER_THRESHOLDS_DAYS:
            services.send_application_reminders(
                now=anchor + datetime.timedelta(days=days))
        services.send_application_reminders(
            now=anchor + datetime.timedelta(
                days=services.REMINDER_THRESHOLDS_DAYS[-1]
                + services.FINAL_REMINDER_GRACE_DAYS))
        return {'expired': _snapshot(application)}

    @classmethod
    def _walk(cls, road):
        """Walk one fresh application down ``road``, snapshotting at each stage it passes.

        Only the stages this road actually produces are returned, so the two walks compose into
        one table without either overwriting the other's branch."""
        recommend = road == 'recommend'
        student = make_student()
        seen = {}

        # submitted — the row is created by the apply submit, nothing else has run.
        application = services.create_application(
            profile=student, cohort=cls.cohort,
            validated_data={'consent_to_contact': True, 'intends_tertiary_2026': True,
                            'declaration_name': student.name},
            to_email=student.contact_email, lang='en')
        seen['submitted'] = _snapshot(application)

        # scored — the engine runs SILENTLY; the status does not move (S8 delayed reveal).
        services.score_application(application)
        seen['scored'] = _snapshot(application)

        # shortlisted — the scheduler releases the verdict.
        application.refresh_from_db()
        services.release_decision(application)
        seen['shortlisted'] = _snapshot(application)

        # profile_complete — the student confirms a complete Step-4 profile.
        application.refresh_from_db()
        cls._complete_the_profile(application)
        services.confirm_profile(application)
        seen['profile_complete'] = _snapshot(application)

        # assigned — a super hands the case to a reviewer. `now` is pushed past the Check-2
        # query SLA so the case is ready-for-assignment the way a real one becomes ready when
        # the window lapses (`services.is_ready_for_assignment`, proceed-as-is).
        application.refresh_from_db()
        services.assign_reviewer(
            application, reviewer=cls.reviewer, by_admin=cls.superadmin,
            now=timezone.now() + datetime.timedelta(days=30))
        seen['assigned'] = _snapshot(application)

        # interviewing — the reviewer submits the interview findings and settles the reporting
        # date (QC refuses a case without one — it sizes the bursary).
        application.refresh_from_db()
        services.submit_interview(InterviewSession.objects.create(
            application=application, interviewer=cls.reviewer, status='draft'))
        application.refresh_from_db()
        services.set_reporting_date_by_officer(
            application, cls.reviewer, factories.REPORTING_DATE)
        # The reviewer's finalise PREPARES the anonymous profile; it does not publish it.
        SponsorProfile.objects.create(
            application=application, anon_markdown=ANON_MARKDOWN,
            anon_blurb='A determined SPM leaver.')
        seen['interviewing'] = _snapshot(application)

        # awaiting_qc — the reviewer records the verdict, then takes ONE of the two roads.
        reviewer_client = authed_client(cls.reviewer)
        url = f'/api/v1/admin/scholarship/applications/{application.pk}/'
        verdict = factories.RECOMMEND_VERDICT if recommend else factories.DECLINE_VERDICT
        response = reviewer_client.post(
            url + 'record-verdict/', {'officer_verdict': verdict}, format='json')
        assert response.status_code == 200, response.content
        # ⚠ The status has NOT moved: recording a verdict is its own state.
        seen[f'verdict_recorded:{road}'] = _snapshot(application)
        if recommend:
            response = reviewer_client.post(
                url + 'verify-accept/', {'checklist': factories.VERIFY_CHECKLIST},
                format='json')
        else:
            response = reviewer_client.post(url + 'submit-decline/', {}, format='json')
        assert response.status_code == 200, response.content
        seen[f'awaiting_qc:{road}'] = _snapshot(application)

        qc_client = authed_client(cls.qc)
        if not recommend:
            # The QC upholds the decline: rejected, with the student email embargoed for 24h.
            response = qc_client.post(url + 'qc-decision/', {'decision': 'accept'},
                                      format='json')
            assert response.status_code == 200, response.content
            seen['rejected'] = _snapshot(application)
            return seen

        # recommended — the QC accepts, which is the SINGLE point the student becomes
        # sponsor-visible (`pool.publish_profile_to_pool`).
        response = qc_client.post(url + 'qc-decision/', {'decision': 'accept'}, format='json')
        assert response.status_code == 200, response.content
        seen['recommended'] = _snapshot(application)

        # awarded — a sponsor with a confirmed donation IN THIS PROGRAMME funds the student.
        application.refresh_from_db()
        sponsor = Sponsor.objects.create(
            supabase_user_id=factories.unique_suffix('sponsor-uid-'),
            name='Test Sponsor', email='sponsor@example.test', status='approved')
        Donation.objects.create(
            sponsor=sponsor, programme=application.programme, amount=Decimal('5000'),
            status=Donation.STATUS_CONFIRMED)
        sponsorship.fund_student(sponsor, application)
        seen['awarded'] = _snapshot(application)

        # active — the student accepts the offer (award cool-off disabled for this class).
        application.refresh_from_db()
        sponsorship.respond_to_award(application, action='accept')
        seen['active'] = _snapshot(application)

        # maintenance — the first tranche is released.
        application.refresh_from_db()
        disbursement.release_tranche(
            disbursement.schedule_tranche(application, amount=1000))
        seen['maintenance'] = _snapshot(application)

        # closed — an admin closes the file by hand, with a recorded reason.
        application.refresh_from_db()
        closure.close_application(
            application, closure_reason='graduated', by_email=cls.superadmin.email)
        seen['closed'] = _snapshot(application)
        return seen

    # ── the comparison ──────────────────────────────────────────────────────────────────────
    def assertStageMatches(self, key):
        walked, built = self.walked[key], self.built[key]
        differences = [
            f'  {name}: the product leaves {walked[name]!r}, the factory builds {built[name]!r}'
            for name in sorted(walked) if walked[name] != built[name]
        ]
        self.assertEqual(
            differences, [],
            f'`make_application(stage={key!r})` no longer describes what the product does at '
            f'that stage. A fixture that describes an unreachable state is how BrightPath #24 '
            f'shipped. FIX THE FACTORY in apps/scholarship/tests/factories.py to match the '
            f'product (timestamps are compared NULL vs NOT NULL, actors blank vs written, '
            f'everything else by value) — never loosen this comparison.\n'
            + '\n'.join(differences))

    def test_every_stage_in_the_table_is_walked(self):
        """THE FLOOR. A stage added to `factories.STAGES` with no walk here is a stage the
        factory can invent freely, which is the whole failure mode this file exists to stop."""
        missing = [k for k in self._stage_keys()
                   if k not in self.walked and k.split(':')[0] not in factories.UNVERIFIED_STAGES]
        self.assertEqual(
            missing, [],
            'Stage(s) in factories.STAGES that no test here walks through real product code. '
            'Add a walk in `_walk`, or — if the stage genuinely cannot be reached in a test — '
            'record it in `factories.UNVERIFIED_STAGES` with the reason, so the gap is visible '
            'rather than assumed.\n' + '\n'.join(missing))

    def test_the_unverified_list_is_empty_or_explained(self):
        """`UNVERIFIED_STAGES` maps a stage to WHY it cannot be walked. A bare name would be a
        silent exemption."""
        for stage, reason in factories.UNVERIFIED_STAGES.items():
            self.assertIn(stage, factories.STAGES,
                          f'UNVERIFIED_STAGES names {stage!r}, which is not a stage.')
            self.assertTrue(
                (reason or '').strip(),
                f'UNVERIFIED_STAGES[{stage!r}] has no reason written. A stage excused from the '
                f'drift check must say why in the same line that excuses it.')

    def test_submitted(self):
        self.assertStageMatches('submitted')

    def test_scored(self):
        self.assertStageMatches('scored')

    def test_shortlisted(self):
        self.assertStageMatches('shortlisted')

    def test_profile_complete(self):
        self.assertStageMatches('profile_complete')

    def test_assigned(self):
        self.assertStageMatches('assigned')

    def test_interviewing(self):
        self.assertStageMatches('interviewing')

    def test_verdict_recorded_on_the_recommend_road(self):
        self.assertStageMatches('verdict_recorded:recommend')

    def test_verdict_recorded_on_the_decline_road(self):
        """Recording a verdict moves NO status — the case is still 'interviewing'."""
        self.assertStageMatches('verdict_recorded:decline')
        self.assertEqual(self.walked['verdict_recorded:decline']['status'], 'interviewing')

    def test_awaiting_qc_on_the_recommend_road(self):
        self.assertStageMatches('awaiting_qc:recommend')

    def test_awaiting_qc_on_the_decline_road(self):
        self.assertStageMatches('awaiting_qc:decline')

    def test_recommended(self):
        self.assertStageMatches('recommended')

    def test_awarded(self):
        self.assertStageMatches('awarded')

    def test_active(self):
        self.assertStageMatches('active')

    def test_maintenance(self):
        self.assertStageMatches('maintenance')

    def test_closed(self):
        self.assertStageMatches('closed')

    def test_rejected(self):
        self.assertStageMatches('rejected')

    def test_expired(self):
        self.assertStageMatches('expired')

    # ── the two roads, stated as their own assertions ───────────────────────────────────────
    def test_the_decline_road_leaves_no_verify_stamps(self):
        """BrightPath #24, in one test. `submit-decline` moves the status and saves one field;
        it stamps no `verified_at`, no `verified_by`, no checklist, and locks no NRIC. A fixture
        that gives a declined case a `verified_at` describes a row production never writes."""
        for source in (self.walked['awaiting_qc:decline'], self.built['awaiting_qc:decline']):
            self.assertEqual(source['status'], 'interviewed')
            self.assertFalse(source['verified_at'], 'the decline road never stamps verified_at')
            self.assertFalse(source['verified_by'])
            self.assertFalse(source['verify_checklist_written'])
            self.assertFalse(source['profile.nric_verified'])
            self.assertEqual(source['officer_verdict.overall'], 'decline')
            self.assertIsNone(source['award_amount'],
                              'a decline verdict clears the award amount')

    def test_the_recommend_road_leaves_every_verify_stamp(self):
        for source in (self.walked['awaiting_qc:recommend'],
                       self.built['awaiting_qc:recommend']):
            self.assertEqual(source['status'], 'interviewed')
            self.assertTrue(source['verified_at'])
            self.assertTrue(source['verified_by'])
            self.assertTrue(source['verify_checklist_written'])
            self.assertTrue(source['profile.nric_verified'])
            self.assertEqual(source['officer_verdict.overall'], 'accept')

    def test_both_roads_reach_the_same_status_and_that_is_the_point(self):
        """The status alone cannot tell the two apart — which is exactly why a fixture keyed on
        status alone gets the rest wrong."""
        self.assertEqual(self.walked['awaiting_qc:recommend']['status'],
                         self.walked['awaiting_qc:decline']['status'])

    def test_only_a_recommended_case_is_in_the_fundable_pool(self):
        """Pool eligibility is three things at once (`pool.eligible_pool_queryset`): an
        anon-published sponsor profile, an active share consent, and status 'recommended'. The
        factory builds all three at `recommended` and the product agrees."""
        for source in (self.walked['recommended'], self.built['recommended']):
            self.assertTrue(source['in_the_fundable_pool'])
        for key in ('awaiting_qc:recommend', 'awarded', 'rejected'):
            self.assertFalse(self.walked[key]['in_the_fundable_pool'],
                             f'{key} must not be in the fundable pool')
            self.assertFalse(self.built[key]['in_the_fundable_pool'])

    def test_a_recommended_case_the_factory_built_can_actually_be_funded(self):
        """The end of the line for TD-258: a factory application must carry a programme, or
        `fund_student` refuses it ('programme_required') and every money test built on one
        would be testing the refusal instead of the money."""
        application = make_application('recommended', cohort=self.cohort)
        self.assertIsNotNone(application.programme_id)
        self.assertTrue(sponsorship.is_fundable(application))
        sponsor = Sponsor.objects.create(
            supabase_user_id=factories.unique_suffix('sponsor-uid-'),
            name='Test Sponsor', email='sponsor2@example.test', status='approved')
        Donation.objects.create(sponsor=sponsor, programme=application.programme,
                                amount=Decimal('5000'), status=Donation.STATUS_CONFIRMED)
        sponsorship.fund_student(sponsor, application)
        application.refresh_from_db()
        self.assertEqual(application.status, 'awarded')


class TestTheFactoryRefusesAnImpossibleRequest(TestCase):
    """A factory that quietly accepts nonsense is a fixture builder again."""

    def test_an_unknown_stage_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            make_application('accepted')
        self.assertIn('unknown stage', str(caught.exception))

    def test_an_outcome_at_a_stage_that_has_none_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            make_application('shortlisted', outcome='decline')
        self.assertIn('takes no outcome', str(caught.exception))

    def test_awaiting_qc_without_an_outcome_is_refused(self):
        """The two roads leave different marks, so 'awaiting QC' alone is not a state."""
        with self.assertRaises(ValueError) as caught:
            make_application('awaiting_qc')
        self.assertIn('needs an outcome', str(caught.exception))

    def test_an_unknown_outcome_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            make_application('awaiting_qc', outcome='hold')
        self.assertIn('unknown outcome', str(caught.exception))

    def test_an_unknown_admin_role_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            make_admin('auditor')
        self.assertIn('unknown admin role', str(caught.exception))


class TestTheSupportingRows(TestCase):
    """The small guarantees every converted test leans on."""

    def test_two_calls_never_collide(self):
        """Safe under `pytest -n auto`, and safe within one test: a fixed literal here would be
        a unique-constraint failure the day two fixtures met."""
        students = [make_student() for _ in range(3)]
        admins = [make_admin('reviewer') for _ in range(3)]
        cohorts = [make_cohort() for _ in range(3)]
        self.assertEqual(len({s.supabase_user_id for s in students}), 3)
        self.assertEqual(len({s.nric for s in students}), 3)
        self.assertEqual(len({a.supabase_user_id for a in admins}), 3)
        self.assertEqual(len({a.email for a in admins}), 3)
        self.assertEqual(len({c.code for c in cohorts}), 3)

    def test_the_fake_nric_is_valid_in_shape_and_belongs_to_an_adult(self):
        """Obviously fake, but the product parses it: `services.age_from_nric` reads the first
        six digits as a date, so a nonsense date would make every factory student ageless."""
        student = make_student()
        self.assertRegex(student.nric, r'^\d{6}-\d{2}-\d{4}$')
        self.assertGreaterEqual(services.age_from_nric(student.nric), 18)
        self.assertFalse(services.is_minor(student))

    def test_a_default_cohort_always_carries_a_programme(self):
        cohort = make_cohort()
        self.assertIsNotNone(cohort.programme_id)
        self.assertEqual(cohort.owning_organisation_id, cohort.programme.organisation_id)

    def test_the_application_programme_matches_its_cohort(self):
        cohort = make_cohort()
        application = make_application('submitted', cohort=cohort)
        self.assertEqual(application.programme_id, cohort.programme_id)
        self.assertEqual(application.owning_organisation_id, cohort.owning_organisation_id)

    def test_a_programme_less_cohort_is_still_possible_when_asked_for(self):
        """A tenancy test may need the degenerate NULL bucket; it just has to say so."""
        cohort = make_cohort(programme=None)
        self.assertIsNone(cohort.programme_id)
        self.assertIsNone(make_application('submitted', cohort=cohort).programme_id)

    def test_overrides_win_over_the_stage(self):
        application = make_application('interviewing', reporting_date=None, bucket='B')
        self.assertIsNone(application.reporting_date)
        self.assertEqual(application.bucket, 'B')
        self.assertEqual(application.status, 'interviewing')

    def test_make_admin_covers_every_role_plus_super(self):
        from apps.courses.models import PartnerAdmin
        for role, _label in PartnerAdmin.ROLE_CHOICES:
            admin = make_admin(role)
            self.assertEqual(admin.role, role)
            self.assertFalse(admin.is_super_admin)
        self.assertTrue(make_admin('super', super_admin=True).is_super_admin)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSharedToken(TestCase):
    """`auth_token` / `authed_client` replace the JWT helper 83 test files each defined."""

    def test_a_token_opens_an_admin_endpoint(self):
        admin = make_admin('admin', super_admin=True)
        response = authed_client(admin).get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(response.status_code, 200)

    def test_an_admin_object_and_its_uid_give_the_same_token(self):
        admin = make_admin('reviewer')
        self.assertEqual(factories.auth_token(admin),
                         factories.auth_token(admin.supabase_user_id))

    def test_no_credentials_is_refused(self):
        from rest_framework.test import APIClient
        self.assertEqual(
            APIClient().get('/api/v1/admin/scholarship/applications/').status_code, 401)
