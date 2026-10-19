"""The student record's two INDEPENDENT referral columns — sources and referral partners, Sprint A.

Owner's model, 2026-10-09 (decisions.md, "The student record has two independent columns: source and
referral partner"): `StudentProfile.source` is what the student named on the bursary "Who referred
you?" form; `StudentProfile.referred_by_org` is the platform REFERRAL PARTNER whose `?ref=` link
brought them. Either may be empty, both may be filled, they may name the same organisation, and
NEITHER WRITER EVER TOUCHES THE OTHER. The `partner`-role logins see `referred_by_org` students only
(NRIC, phone, address, household income), so a bursary answer must never put a student there.

1. The bursary submit writes the SOURCE only (NULL for a fixed choice) and keeps its refusal.
2. A `?ref=` sign-in sync writes the REFERRAL PARTNER only — first touch, partner rows only — and
   no longer overwrites the bursary answer on the chip.
3. `PUT /profile/` can set neither.
4. The partner logins' list, on a production-shaped fixture, as the writers keep it.
5. The migration (courses 0078): the marker.
6. What the image already serving needs: payload keys, and an INSERT that does not name the column.

Sources-and-referrals Sprint B (2026-10-18) moved SOURCES into their own table, owned by the
organisation: this world now has CUMIG as a REFERRAL PARTNER row (`partner_organisations`, its
login, `referred_by_org`) AND a SOURCE twin (`referral_sources`, same id and code, owned by the
tenant), and SMC as a source only — production's shape after the Sprint B cutover. The three tests
of 0078's BACKFILL left with it: they ran that data step against the live models, and once the
source column names the new table a backfill writing `partner_organisations` ids cannot run. It ran
on production on 2026-10-18 with the counts in `docs/scholarship/two-columns-cutover-sql.md`; what
it protected — the partner list unchanged — is pinned here against the writers and in
`test_sources_b.py` against the Sprint B copy.
"""
from django.apps import apps as live_apps
from django.db import connection
from django.test import TestCase, override_settings

from importlib import import_module

from apps.courses import referral_links
from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship.models import ProgrammeReferralSource, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_shortlistable_student, make_source, make_student,
)

MIGRATION = import_module('apps.courses.migrations.0078_two_referral_columns')
APPLY = '/api/v1/scholarship/applications/'
SYNC = '/api/v1/profile/sync/'
PROFILE = '/api/v1/profile/'
PARTNER_LIST = '/api/v1/admin/students/'


def _org(code, *, partner=False, show=True, active=True):
    """A `partner_organisations` row — since Sprint B, a REFERRAL PARTNER (or a tenant), never a
    source."""
    return PartnerOrganisation.objects.create(
        code=code, name=code.upper(), show_in_apply=show, is_active=active,
        is_referral_partner=partner)


def _snapshot(code):
    return {'profile': {'referral_source': code}}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _World(TestCase):
    """One tenant running one gift that offers SMC and CUMIG; CUMIG is ALSO the referral partner,
    with a `partner`-role login, exactly as production is shaped after the Sprint B cutover."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = make_org('tc-tenant')
        make_admin('org_admin', owning_org=cls.tenant)
        cls.gift = make_programme(organisation=cls.tenant, code='tc-gift', is_active=True)
        cls.round = make_cohort(programme=cls.gift, code='tc-gift-2026', is_open=True,
                                is_active=True)
        cls.cumig = _org('cumig', partner=True)                           # the referral partner
        cls.cumig_source = make_source(cls.tenant, 'cumig', pk=cls.cumig.pk)   # its source twin
        cls.smc = make_source(cls.tenant, 'smc')
        for source in (cls.cumig_source, cls.smc):
            ProgrammeReferralSource.objects.create(programme=cls.gift, source=source)
        cls.partner_login = make_admin('partner', org=cls.cumig)

    def _apply(self, student, code):
        return authed_client(student).post(APPLY, {
            'household_income': 2500, 'receives_str': True, 'consent_to_contact': True,
            'programme_code': 'tc-gift', 'referral_source': code,
        }, format='json')

    def _sync(self, uid, code):
        return authed_client(uid).post(SYNC, {'referral_source': code}, format='json')

    def _columns(self, profile):
        profile.refresh_from_db()
        return profile.referral_source, profile.source_id, profile.referred_by_org_id


class TestTheBursarySubmitWritesTheSourceOnly(_World):
    def test_picking_a_source_fills_the_source_and_never_the_referral_partner(self):
        for code, org in (('smc', self.smc), ('cumig', self.cumig_source)):
            with self.subTest(code=code):
                student = make_shortlistable_student()
                self.assertEqual(self._apply(student, code).status_code, 201)
                # Picking CUMIG on the form no longer puts her on CUMIG's course-selector list.
                self.assertEqual(self._columns(student), (code, org.pk, None))

    def test_a_referral_partner_link_already_there_is_left_alone(self):
        student = make_shortlistable_student(referred_by_org=self.cumig, referral_source='cumig')
        self.assertEqual(self._apply(student, 'smc').status_code, 201)
        self.assertEqual(self._columns(student), ('smc', self.smc.pk, self.cumig.pk))

    def test_a_fixed_choice_or_blank_empties_the_source_and_leaves_the_partner(self):
        from apps.scholarship.services import sync_profile_fields
        for code in ('halatuju', 'social', 'other', ''):
            with self.subTest(code=code):
                student = make_student(source=self.smc, referred_by_org=self.cumig)
                sync_profile_fields(student, {'referral_source': code})
                self.assertEqual(self._columns(student), (code, None, self.cumig.pk))

    def test_a_write_that_does_not_carry_the_answer_leaves_the_source_alone(self):
        """The guardian-contact writers call the same sync with `guardians` only."""
        from apps.scholarship.services import sync_profile_fields
        student = make_student(source=self.smc, referral_source='smc')
        sync_profile_fields(student, {'guardians': [{'name': 'A Parent', 'phone': '0123456789'}]})
        self.assertEqual(self._columns(student), ('smc', self.smc.pk, None))

    def test_the_refusal_still_holds_and_writes_nothing(self):
        tara = make_source(self.tenant, 'tara', show_in_apply=False)   # switched off in Sources
        ProgrammeReferralSource.objects.create(programme=self.gift, source=tara)
        student = make_shortlistable_student()
        resp = self._apply(student, 'tara')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['code'], 'referral_source_not_offered')
        self.assertEqual(self._columns(student)[1:], (None, None))

    def test_a_source_that_is_not_active_or_is_a_tenant_never_fills_the_column(self):
        """The second line behind the view's refusal: the sync on its own."""
        from apps.scholarship.services import sync_profile_fields
        PartnerOrganisation.objects.filter(pk=self.tenant.pk).update(show_in_apply=True)
        for code in ('tc-tenant', 'nope'):
            with self.subTest(code=code):
                student = make_student()
                sync_profile_fields(student, {'referral_source': code}, programme=self.gift)
                self.assertEqual(self._columns(student)[1:], (None, None))


class TestTheRefLinkWritesTheReferralPartnerOnly(_World):
    def test_a_partner_code_links_a_new_student_and_fills_nothing_else(self):
        student = make_student()          # the NRIC gate lets only a claimed profile sync
        self.assertEqual(self._sync(student, 'cumig').status_code, 200)
        self.assertEqual(self._columns(student), ('cumig', None, self.cumig.pk))

    def test_first_touch_never_moves_an_existing_link(self):
        other_partner = _org('ptwo', partner=True)
        student = make_student(referred_by_org=other_partner)
        self._sync(student, 'cumig')
        self.assertEqual(self._columns(student)[2], other_partner.pk)

    def test_only_an_active_referral_partner_is_ever_linked(self):
        _org('sleepy', partner=True, active=False)
        for code in ('smc', 'tc-tenant', 'sleepy', 'nope'):     # a source, a tenant, off, unknown
            with self.subTest(code=code):
                student = make_student()
                self.assertEqual(self._sync(student, code).status_code, 200)
                self.assertEqual(self._columns(student)[1:], (None, None))

    def test_a_sign_in_sync_no_longer_overwrites_the_bursary_answer(self):
        """The live bug: every sign-in re-sent the browser's saved `?ref` and overwrote the chip,
        moving the student between partners' counts and emails."""
        student = make_shortlistable_student()
        self.assertEqual(self._apply(student, 'smc').status_code, 201)
        for _ in range(2):                                    # every sign-in resends it
            self.assertEqual(self._sync(student, 'cumig').status_code, 200)
        # The chip and the source keep the bursary answer; the ?ref fills only its own column.
        self.assertEqual(self._columns(student), ('smc', self.smc.pk, self.cumig.pk))

    def test_a_ref_never_writes_the_chip_of_a_student_who_has_applied(self):
        """Even a blank bursary answer: the chip is what the bursary counts and partner emails
        read, so a `?ref` after she has applied may not move her into a partner's figures."""
        student = make_student(referral_source='')
        make_application(cohort=self.round, student=student, intake_snapshot=_snapshot(''))
        self._sync(student, 'cumig')
        self.assertEqual(self._columns(student), ('', None, self.cumig.pk))

    def test_the_chip_is_first_touch_too(self):
        student = make_student(referral_source='social')
        self._sync(student, 'cumig')
        self.assertEqual(self._columns(student)[0], 'social')

    def test_a_badly_shaped_code_links_and_writes_nothing_and_never_raises(self):
        """Review fix: only `[a-z0-9_-]{1,50}` (ASCII, case-folded) is a code."""
        student = make_student()
        for code in (['cumig'], 42, None, 'x' * 51, '   ', 'cum\x00ig', 'cumig\x07', 'cu mig',
                     'cumig;drop', 'cümig', 'Kumig'):
            with self.subTest(code=repr(code)[:20]):
                self.assertEqual(referral_links.apply_ref_code(student, code), [])
        self.assertEqual(self._columns(student), (None, None, None))

    def test_a_code_in_capitals_or_with_spaces_round_it_is_the_same_code(self):
        student = make_student()
        self.assertEqual(referral_links.apply_ref_code(student, '  CUMIG '),
                         ['referred_by_org', 'referral_source'])
        self.assertEqual(self._columns(student), ('cumig', None, self.cumig.pk))

    def test_a_marked_tenant_fixed_or_house_row_is_never_a_referral_partner(self):
        """Review fix: even a row wrongly marked `is_referral_partner` never collects students when
        it is a tenant, carries a fixed form code, or is the house organisation."""
        PartnerOrganisation.objects.filter(pk=self.tenant.pk).update(is_referral_partner=True)
        _org('other', partner=True)
        # The house row is seeded by scholarship 0098; mark it, and take away anything that would
        # make it a tenant, so only the house-code exclusion can keep it out.
        house, _ = PartnerOrganisation.objects.update_or_create(
            code='brightpath', defaults={'name': 'House', 'is_active': True,
                                         'is_referral_partner': True})
        from apps.courses.models import PartnerAdmin
        from apps.scholarship.models import Programme
        Programme.objects.filter(organisation=house).update(is_active=False)
        PartnerAdmin.objects.filter(owning_organisation=house, role='org_admin').update(
            is_active=False)
        self.assertNotIn(house.pk, set(PartnerOrganisation.objects.tenants()
                                       .values_list('pk', flat=True)))
        self.assertEqual(set(referral_links.referral_partners().values_list('code', flat=True)),
                         {'cumig'})
        for code in ('tc-tenant', 'other', 'brightpath'):
            with self.subTest(code=code):
                student = make_student()
                self._sync(student, code)
                self.assertEqual(self._columns(student)[2], None)


class TestThePutCannotSetEither(_World):
    def test_a_client_supplied_code_is_ignored_by_put(self):
        student = make_student(referral_source='smc', source=self.smc)
        resp = authed_client(student).put(PROFILE, {'referral_source': 'cumig', 'school': 'SMK X'},
                                          format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._columns(student), ('smc', self.smc.pk, None))
        self.assertEqual(StudentProfile.objects.get(pk=student.pk).school, 'SMK X')   # the rest saved


class TestThePartnerListOnAProductionShapedFixture(_World):
    """241 course-selector-only students and the 13 applicants who picked CUMIG (owner: "Filled" —
    both columns CUMIG), plus the two shapes the Sprint A backfill left: an SMC picker with no
    partner, and a `?ref=cumig` student who picked SMC. Production after the Sprint A cutover."""

    def setUp(self):
        StudentProfile.objects.bulk_create([
            StudentProfile(supabase_user_id=f'tc-cs-{i}', referral_source='cumig',
                           referred_by_org=self.cumig) for i in range(241)])
        self.cumig_applicants = []
        for _ in range(13):
            s = make_student(referral_source='cumig', referred_by_org=self.cumig,
                             source=self.cumig_source)
            make_application(cohort=self.round, student=s, intake_snapshot=_snapshot('cumig'))
            self.cumig_applicants.append(s)
        self.smc_only = make_student(referral_source='smc', source=self.smc)
        make_application(cohort=self.round, student=self.smc_only, intake_snapshot=_snapshot('smc'))
        self.ref_then_smc = make_student(referral_source='smc', referred_by_org=self.cumig,
                                         source=self.smc)
        make_application(cohort=self.round, student=self.ref_then_smc,
                         intake_snapshot=_snapshot('smc'))

    def _visible(self):
        """What the partner login's own list endpoint counts, and the ids behind its scope."""
        resp = authed_client(self.partner_login).get(PARTNER_LIST)
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()['count'], set(StudentProfile.objects.filter(referred_by_org=self.cumig)
                                         .values_list('pk', flat=True))

    def test_exactly_the_cumig_students_are_visible(self):
        count, visible = self._visible()
        self.assertEqual(count, 241 + 13 + 1)
        self.assertIn(self.ref_then_smc.pk, visible)
        self.assertTrue({s.pk for s in self.cumig_applicants} <= visible)
        self.assertNotIn(self.smc_only.pk, visible)

    def test_the_new_writers_keep_the_list_exact(self):
        newcomer = make_shortlistable_student()
        self._sync(newcomer, 'cumig')                         # ?ref=cumig → visible
        self.assertEqual(self._apply(newcomer, 'smc').status_code, 201)
        picker = make_shortlistable_student()
        self.assertEqual(self._apply(picker, 'cumig').status_code, 201)   # form only → not visible
        count, visible = self._visible()
        self.assertEqual(count, 241 + 13 + 1 + 1)
        self.assertIn(newcomer.pk, visible)
        self.assertNotIn(picker.pk, visible)


class TestTheReferralPartnerMarker(TestCase):
    def test_a_row_with_a_partner_login_is_marked_and_nothing_else(self):
        partner = PartnerOrganisation.objects.create(code='mk-p', name='P')
        source = PartnerOrganisation.objects.create(code='mk-s', name='S')
        make_admin('partner', org=partner)
        make_admin('reviewer', org=source)          # a referring org on another role marks nothing
        MIGRATION.mark_referral_partners(live_apps, None)
        marked = set(PartnerOrganisation.objects.filter(is_referral_partner=True)
                     .values_list('code', flat=True))
        self.assertEqual(marked, {'mk-p'})
        MIGRATION.mark_referral_partners(live_apps, None)         # idempotent
        self.assertEqual(PartnerOrganisation.objects.filter(is_referral_partner=True).count(), 1)

    def test_a_tenant_carrying_a_partner_login_is_refused(self):
        tenant = make_org('mk-t')
        make_admin('org_admin', owning_org=tenant)
        make_admin('partner', org=tenant)
        with self.assertRaises(RuntimeError):
            MIGRATION.mark_referral_partners(live_apps, None)
        self.assertFalse(PartnerOrganisation.objects.filter(is_referral_partner=True).exists())

    def test_the_reserved_codes_copy_still_equals_its_originals(self):
        # courses keeps a COPY so the courses -> scholarship back-edge does not grow; this pins it.
        from apps.scholarship import gift_sources, partner_comms
        self.assertEqual(set(referral_links.RESERVED_CODES),
                         {*gift_sources.FIXED_CODES, partner_comms.HOUSE_ORG_CODE})


class TestTheWitnessIsTheApplicationsSourceOnly(_World):
    """Superseded "the witness reads the same organisation as before" (Sprint A: source, else the
    referral partner; Sprint B: the partner's source twin). Sources Sprint C, owner's ruling
    2026-10-09: the witness comes from the SOURCE the application named, never the referral partner
    — so `referring_org` and the twin pairing are gone."""

    def test_the_source_wins_and_the_referral_partner_is_never_the_witness(self):
        from apps.scholarship.bursary import _resolve_witness_org
        both = make_student(referral_source='smc', source=self.smc, referred_by_org=self.cumig)
        partner_only = make_student(referral_source='', referred_by_org=self.cumig)
        neither = make_student()
        for student, want in ((both, self.smc), (partner_only, None), (neither, None)):
            with self.subTest(want=getattr(want, 'code', None)):
                app = make_application(cohort=make_cohort(programme=self.gift), student=student)
                self.assertEqual(_resolve_witness_org(app), want)
        self.assertEqual(self.cumig_source.pk, self.cumig.pk)    # the twin exists, and is unused
        override_source = make_source(self.tenant, 'wit')
        override = make_application(cohort=make_cohort(programme=self.gift), student=both,
                                    witness_org=override_source)
        self.assertEqual(_resolve_witness_org(override), override_source)

    def test_the_bridge_is_gone(self):
        self.assertFalse(hasattr(referral_links, 'referring_org'))
        self.assertFalse(hasattr(referral_links, 'is_same_organisation'))

    def test_an_id_alone_never_pairs_two_organisations(self):
        """Ids after the copy come from two sequences, so a source and a partner row may share
        one by chance: only the same id AND code is a twin (`source_twin` is still read by the
        invite refusal)."""
        from django.db.models import Max
        from apps.scholarship.models import ReferralSource
        shared = 1000 + max(PartnerOrganisation.objects.aggregate(m=Max('pk'))['m'] or 0,
                            ReferralSource.objects.aggregate(m=Max('pk'))['m'] or 0)
        partner = PartnerOrganisation.objects.create(pk=shared, code='pair-p', name='P',
                                                     is_referral_partner=True)
        make_source(self.tenant, 'stranger', pk=shared)     # same id, another code
        self.assertIsNone(referral_links.source_twin(partner.pk))


class TestWhatTheImageAlreadyServingNeeds(_World):
    def test_an_insert_that_does_not_name_the_new_column_still_works(self):
        """Between the hand-applied migration and the deploy, the OLD image's Sources POST inserts
        rows without `is_referral_partner`: the database default must answer for it."""
        fields = [f for f in PartnerOrganisation._meta.concrete_fields
                  if f.name not in ('id', 'is_referral_partner')]
        probe = PartnerOrganisation(code='old-image', name='Old Image Row')
        values = [f.get_db_prep_save(f.pre_save(probe, add=True), connection) for f in fields]
        cols = ', '.join(connection.ops.quote_name(f.column) for f in fields)
        marks = ', '.join(['%s'] * len(fields))
        with connection.cursor() as cur:
            cur.execute(f'INSERT INTO partner_organisations ({cols}) VALUES ({marks})', values)
        self.assertFalse(PartnerOrganisation.objects.get(code='old-image').is_referral_partner)

    def test_the_snapshot_and_the_cockpit_keep_their_keys(self):
        student = make_shortlistable_student()
        self.assertEqual(self._apply(student, 'smc').status_code, 201)
        app = ScholarshipApplication.objects.get(profile=student)
        self.assertEqual(set(app.intake_snapshot['profile']), {
            'name', 'school', 'preferred_state', 'contact_phone', 'preferred_call_language',
            'guardians', 'referral_source', 'exam_type', 'grades', 'stpm_cgpa', 'spm_a_count',
            'household_income', 'household_size', 'receives_str', 'receives_jkm'})
        self.assertEqual(app.intake_snapshot['profile']['referral_source'], 'smc')
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        data = AdminApplicationDetailSerializer().get_referred_by_org(app)
        # Same key, same shape; the value is the SOURCE this application named (sources Sprint C:
        # the new `source` key carries it too, and the old key stays one release).
        self.assertEqual(data, {'id': self.smc.id, 'code': 'smc', 'name': 'SMC'})
        self.assertEqual(AdminApplicationDetailSerializer().get_source(app), data)

    def test_the_profile_payload_still_serves_the_chip(self):
        student = make_student(referral_source='cumig', referred_by_org=self.cumig)
        body = authed_client(student).get(PROFILE).json()
        self.assertEqual(body['referral_source'], 'cumig')
        self.assertNotIn('source', body)      # nothing new on the student's own payload this sprint
