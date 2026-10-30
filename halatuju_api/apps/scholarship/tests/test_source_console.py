"""Source sign-in S3 (2026-10-30): the source console's API (`views_admin/source_console.py`, payloads
`source_console.py`). What a source user sees, to whom it is served, and what it never contains.

The deny-by-default sweep (`test_source_user_denied_everywhere.py`) proves these are the only admin
routes a source user reaches; this file proves what each one serves.
"""
import datetime

from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship import source_console
from apps.scholarship.models import (
    ApplicantDocument, BursaryAgreement, ProgrammeReferralSource, ScholarshipApplication,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source, make_student,
)

PROFILE = '/api/v1/admin/source/profile/'
OVERVIEW = '/api/v1/admin/source/overview/'
APPLICATIONS = '/api/v1/admin/source/applications/'
SCHOLARS = '/api/v1/admin/source/scholars/'

#: Every key a source payload may never carry, or an obvious synonym of one (roadmap: "Never: NRIC,
#: address, income, family, essays, documents, scores, merit, verdicts, reviewer names, notes,
#: money"). Matched against EVERY key at every depth, lower-cased. `city` is not `state`.
NEVER = (
    r'nric', r'(^|_)ic($|_)', r'address', r'postcode', r'postal', r'city', r'income', r'household',
    r'family', r'father', r'mother', r'sibling', r'guardian', r'parent', r'aspiration', r'plans',
    r'fears', r'justification', r'daily_life', r'document', r'referee', r'consent', r'anomal',
    r'interview', r'verdict', r'^ai_', r'officer', r'merit', r'score', r'cgpa', r'grade', r'^qc_',
    r'rejection', r'note', r'reviewer', r'assigned', r'vircle', r'disburse', r'amount',
    r'payment', r'results', r'semester', r'money', r'bank', r'substate', r'standing', r'nudge',
    r'storage', r'pdf', r'signed_name', r'signatory', r'_by$',
)


def never_keys(payload, path=''):
    """Every key in ``payload`` (any depth) that matches the never-list."""
    import re
    found = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            here = f'{path}.{key}'
            if any(re.search(p, str(key).lower()) for p in NEVER):
                found.append(here)
            found += never_keys(value, here)
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            found += never_keys(value, f'{path}[{i}]')
    return found


class _Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.gift = make_programme(organisation=cls.org, code='gift-a')
        cls.gift2 = make_programme(organisation=cls.org, code='gift-b')
        cohort = make_cohort(programme=cls.gift)
        cohort2 = make_cohort(programme=cls.gift2)
        cls.source = make_source(organisation=cls.org, contact_person='Puan Kala',
                                 contact_email='kala@src.test', phone='012-3456789')
        ProgrammeReferralSource.objects.create(programme=cls.gift, source=cls.source)
        cls.other = make_source(organisation=cls.org)
        cls.org2 = make_org()
        cls.source2 = make_source(organisation=cls.org2)
        cls.user = make_admin('source_partner', owning_org=cls.org, source=cls.source)

        def app(stage, *, name, source=None, c=cohort, **kw):
            student = make_student(name=name, contact_phone='011-1111111',
                                   contact_email=f'{name.split()[0].lower()}@stu.test',
                                   school='SMK Ladang', preferred_state='Perak',
                                   address='1 Jalan Rahsia', postal_code='30000', city='Ipoh',
                                   household_income=900)
            return make_application(stage, cohort=c, student=student, source=source, **kw)

        cls.submitted = app('submitted', name='Anbu Submitted', source=cls.source)
        cls.shortlisted = app('shortlisted', name='Bala Shortlisted', source=cls.source)
        cls.recommended = app('recommended', name='Chitra Recommended', source=cls.source)
        # Declined at QC; the student's email is still embargoed (the 24h cool-off).
        cls.embargoed = app('rejected', name='Devi Embargoed', source=cls.source)
        told = timezone.now()
        cls.told = app('rejected', name='Elan Told', source=cls.source,
                       pending_rejection_category='', decline_email_sent_at=told)
        cls.scholar = app('active', name='Ganesh Scholar', source=cls.source,
                          chosen_programme={'institution': 'Universiti Malaya'})
        cls.scholar_agreement = BursaryAgreement.objects.create(
            application=cls.scholar, version='2026-v1', student_signed_at=told,
            guarantor_signed_at=told, award_amount=5000, guarantor_nric='700101-14-5003')
        cls.in_gift2 = app('submitted', name='Hari Gift Two', source=cls.source, c=cohort2)
        cls.others = app('submitted', name='Indra Other Source', source=cls.other)
        # Another source's student, witnessed by OURS by override (C14): a contract waits for us.
        cls.witnessed = app('active', name='Jaya Witnessed', source=cls.other,
                            witness_org=cls.source)
        BursaryAgreement.objects.create(application=cls.witnessed, version='2026-v1',
                                        student_signed_at=told, guarantor_signed_at=told)
        cls.foreign = app('submitted', name='Kumar Other Org', source=cls.source2,
                          c=make_cohort(programme=make_programme(organisation=cls.org2)))

    def setUp(self):
        self.client = authed_client(self.user)

    def get(self, url, **params):
        resp = self.client.get(url, params)
        return resp, (resp.json() if resp.status_code < 500 else None)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheProfile(_Fixture):
    def test_get_serves_the_caller_and_its_source(self):
        resp, body = self.get(PROFILE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body, {
            'user': {'name': self.user.name, 'email': self.user.email},
            'source': {'name': self.source.name, 'code': self.source.code,
                       'contact_person': 'Puan Kala', 'contact_email': 'kala@src.test',
                       'phone': '012-3456789', 'organisation': self.org.name}})

    def test_patch_changes_the_callers_name_and_the_sources_details(self):
        resp = self.client.patch(PROFILE, {
            'user': {'name': '  Kala Devi '},
            'source': {'name': 'Persatuan Baru', 'contact_person': 'Encik Raj',
                       'contact_email': 'raj@src.test', 'phone': '03-1234 5678'}}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(self.user.name, 'Kala Devi')
        self.assertEqual((self.source.name, self.source.contact_person, self.source.contact_email,
                          self.source.phone),
                         ('Persatuan Baru', 'Encik Raj', 'raj@src.test', '03-1234 5678'))
        self.assertEqual(resp.json()['source']['name'], 'Persatuan Baru')

    def test_an_empty_patch_changes_nothing(self):
        resp = self.client.patch(PROFILE, {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.source.refresh_from_db()
        self.assertEqual(self.source.contact_person, 'Puan Kala')

    def test_the_code_and_the_organisations_switches_are_refused_not_ignored(self):
        code = self.source.code
        for body, field in (({'source': {'code': 'new'}}, 'source.code'),
                            ({'source': {'is_active': False}}, 'source.is_active'),
                            ({'source': {'show_in_apply': False}}, 'source.show_in_apply'),
                            ({'user': {'email': 'x@y.test'}}, 'user.email'),
                            ({'role': 'super'}, 'role')):
            resp = self.client.patch(PROFILE, body, format='json')
            self.assertEqual((resp.status_code, resp.json()['code']), (400, 'not_editable'))
            self.assertIn(field, resp.json()['fields'])
        self.source.refresh_from_db()
        self.assertEqual((self.source.code, self.source.is_active, self.source.show_in_apply),
                         (code, True, True))

    def test_the_validators(self):
        cases = (({'user': {'name': '  '}}, 'name_required'),
                 ({'source': {'name': ''}}, 'source_name_required'),
                 ({'source': {'contact_email': 'not-an-email'}}, 'bad_email'))
        for body, code in cases:
            resp = self.client.patch(PROFILE, body, format='json')
            self.assertEqual((resp.status_code, resp.json()['code']), (400, code))
        # A blank contact email is allowed (the Sources page allows it too).
        self.assertEqual(self.client.patch(PROFILE, {'source': {'contact_email': ''}},
                                           format='json').status_code, 200)

    def test_the_widths_are_the_sources_pages(self):
        self.client.patch(PROFILE, {'source': {'phone': '1' * 50}}, format='json')
        self.source.refresh_from_db()
        self.assertEqual(len(self.source.phone), 30)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheOverview(_Fixture):
    def test_counts_fold_what_the_student_has_not_been_told(self):
        resp, body = self.get(OVERVIEW, p='gift-a')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body['programme'], {'code': 'gift-a', 'name': self.gift.name_en})
        self.assertEqual(body['counts'], {
            'not_shortlisted': 1,        # submitted
            'shortlisted': 1,
            'awaiting_review': 0,
            # `recommended` is masked from the student and an embargoed decline reads as the stage
            # it was declined from: both are still "under review" to the source (C12).
            'under_review': 2,
            'awarded': 1,                # the active scholar
            'rejected': 1,               # only the decline the student was TOLD of
            'closed': 0,
            'total': 6})
        self.assertEqual(body['scholars'], 1)

    def test_the_missing_items_are_the_partner_emails_chase_list(self):
        _resp, body = self.get(OVERVIEW, p='gift-a')
        self.assertEqual([(m['application_id'], m['student_name']) for m in body['missing_items']],
                         [(self.shortlisted.pk, 'BALA SHORTLISTED')])
        self.assertEqual(set(body['missing_items'][0]),
                         {'application_id', 'student_name', 'applied', 'last_activity'})

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_witness_waiting_lists_the_contracts_this_source_witnesses(self):
        _resp, body = self.get(OVERVIEW, p='gift-a')
        # The scholar's own contract waits too: its source is ours and there is no override.
        self.assertEqual(body['witness_waiting'], [
            {'application_id': self.scholar.pk, 'student_name': 'GANESH SCHOLAR'},
            {'application_id': self.witnessed.pk, 'student_name': 'JAYA WITNESSED'}])

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_a_witnessed_contract_or_an_override_elsewhere_is_not_waiting(self):
        BursaryAgreement.objects.filter(application=self.witnessed).update(
            witness_signed_at=timezone.now())
        ScholarshipApplication.objects.filter(pk=self.scholar.pk).update(witness_org=self.other)
        _resp, body = self.get(OVERVIEW, p='gift-a')
        self.assertEqual(body['witness_waiting'], [])

    def test_witness_waiting_is_empty_while_agreements_are_off(self):
        with self.settings(BURSARY_AGREEMENT_ENABLED=False):
            _resp, body = self.get(OVERVIEW, p='gift-a')
        self.assertEqual(body['witness_waiting'], [])

    def test_p_narrows_and_absent_p_does_not(self):
        _r, two = self.get(OVERVIEW, p='gift-b')
        self.assertEqual(two['counts']['total'], 1)
        _r, every = self.get(OVERVIEW)
        self.assertEqual((every['programme'], every['counts']['total']), (None, 7))

    def test_a_gift_outside_the_source_is_404(self):
        self.assertEqual(self.get(OVERVIEW, p='nope')[0].status_code, 404)
        foreign = self.foreign.programme.code
        self.assertEqual(self.get(OVERVIEW, p=foreign)[0].status_code, 404)
        # Another gift of the same organisation with none of our students and no link: 404.
        make_programme(organisation=self.org, code='gift-c')
        self.assertEqual(self.get(OVERVIEW, p='gift-c')[0].status_code, 404)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheApplications(_Fixture):
    ROW = {'id', 'student_name', 'school', 'state', 'level', 'programme', 'submitted_at', 'stage'}

    def test_the_list_is_the_sources_own_students_only(self):
        resp, body = self.get(APPLICATIONS)
        self.assertEqual(resp.status_code, 200)
        ids = {row['id'] for row in body['applications']}
        self.assertEqual(ids, {self.submitted.pk, self.shortlisted.pk, self.recommended.pk,
                               self.embargoed.pk, self.told.pk, self.scholar.pk, self.in_gift2.pk})
        # Never another source's, a witness-only case, or another organisation's.
        self.assertFalse(ids & {self.others.pk, self.witnessed.pk, self.foreign.pk})
        self.assertEqual(body['count'], 7)
        row = next(r for r in body['applications'] if r['id'] == self.submitted.pk)
        self.assertEqual(set(row), self.ROW)
        self.assertEqual((row['student_name'], row['school'], row['state'], row['level'],
                          row['stage']),
                         ('ANBU SUBMITTED', 'SMK Ladang', 'Perak', 'spm', 'not_shortlisted'))

    def test_p_and_stage_narrow(self):
        _r, body = self.get(APPLICATIONS, p='gift-b')
        self.assertEqual([r['id'] for r in body['applications']], [self.in_gift2.pk])
        _r, body = self.get(APPLICATIONS, p='gift-a', stage='under_review')
        self.assertEqual({r['id'] for r in body['applications']},
                         {self.recommended.pk, self.embargoed.pk})
        _r, body = self.get(APPLICATIONS, stage='rejected')
        self.assertEqual([r['id'] for r in body['applications']], [self.told.pk])
        self.assertEqual(self.get(APPLICATIONS, stage='recommended')[0].status_code, 400)

    def test_search_is_by_name_only(self):
        _r, body = self.get(APPLICATIONS, q='bala')
        self.assertEqual([r['id'] for r in body['applications']], [self.shortlisted.pk])
        for probe in (self.shortlisted.profile.nric, '011-1111111', 'bala@stu.test'):
            _r, body = self.get(APPLICATIONS, q=probe)
            self.assertEqual(body['applications'], [], probe)

    def test_it_pages(self):
        _r, body = self.get(APPLICATIONS, page_size=2)
        self.assertEqual((body['count'], body['total_pages'], len(body['applications'])),
                         (7, 4, 2))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestOneApplication(_Fixture):
    LISTED = TestTheApplications.ROW | {'kind', 'phone', 'email', 'told_at', 'missing_items',
                                        'contract'}

    def test_a_listed_application(self):
        resp, body = self.get(f'{APPLICATIONS}{self.submitted.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(body), self.LISTED)
        self.assertEqual((body['kind'], body['phone'], body['email'], body['stage'],
                          body['told_at'], body['missing_items'], body['contract']),
                         ('listed', '011-1111111', 'anbu@stu.test', 'not_shortlisted', None, [],
                          None))

    def test_an_outcome_carries_the_date_the_student_was_told(self):
        _r, body = self.get(f'{APPLICATIONS}{self.told.pk}/')
        self.assertEqual(body['stage'], 'rejected')
        self.assertIsNotNone(body['told_at'])
        _r, body = self.get(f'{APPLICATIONS}{self.embargoed.pk}/')
        self.assertEqual((body['stage'], body['told_at']), ('under_review', None))

    def test_a_shortlisted_application_names_its_open_parts_and_nothing_finer(self):
        _r, body = self.get(f'{APPLICATIONS}{self.shortlisted.pk}/')
        parts = body['missing_items']
        self.assertTrue(parts)          # a bare factory profile has open parts
        self.assertTrue(set(parts) <= {name for _key, name in source_console.PARTS})
        doc_types = {code for code, _label in ApplicantDocument.DOC_TYPES}
        routes = {code for code, _label in ScholarshipApplication.INCOME_ROUTE_CHOICES if code}
        self.assertEqual(set(parts) & (doc_types | routes), set())

    def test_the_contract_block(self):
        _r, body = self.get(f'{APPLICATIONS}{self.scholar.pk}/')
        self.assertEqual(set(body['contract']), {
            'status', 'student_signed_at', 'guarantor_signed_at', 'witness_signed_at',
            'foundation_signed_at', 'witness_is_you', 'can_witness'})   # can_witness: S4
        self.assertEqual((body['contract']['status'], body['contract']['witness_is_you']),
                         ('binds', True))

    def test_a_witness_only_case_shows_the_contract_and_nothing_else(self):
        resp, body = self.get(f'{APPLICATIONS}{self.witnessed.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(body), {'id', 'kind', 'student_name', 'programme', 'contract'})
        self.assertEqual((body['kind'], body['student_name'], body['contract']['witness_is_you']),
                         ('witness_only', 'JAYA WITNESSED', True))

    def test_out_of_scope_is_404(self):
        for app in (self.others, self.foreign):
            self.assertEqual(self.get(f'{APPLICATIONS}{app.pk}/')[0].status_code, 404)
        self.assertEqual(self.get(f'{APPLICATIONS}999999/')[0].status_code, 404)

    def test_reading_one_has_no_side_effects(self):
        before = ScholarshipApplication.objects.get(pk=self.shortlisted.pk).updated_at
        self.get(f'{APPLICATIONS}{self.shortlisted.pk}/')
        self.assertEqual(mail.outbox, [])
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.shortlisted.pk).updated_at,
                         before)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheScholars(_Fixture):
    ROW = {'id', 'student_name', 'programme', 'institution', 'course', 'status', 'contract_stage'}

    def test_the_list_is_the_listed_scholars_only(self):
        resp, body = self.get(SCHOLARS)
        self.assertEqual(resp.status_code, 200)
        # The witnessed student is a scholar too, but another source's: never on this list.
        self.assertEqual([r['id'] for r in body['scholars']], [self.scholar.pk])
        row = body['scholars'][0]
        self.assertEqual(set(row), self.ROW)
        self.assertEqual((row['institution'], row['status'], row['contract_stage']),
                         ('Universiti Malaya', 'active', 'binds'))
        self.assertEqual(self.get(SCHOLARS, p='gift-b')[1]['scholars'], [])

    def test_one_scholar(self):
        resp, body = self.get(f'{SCHOLARS}{self.scholar.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(body), self.ROW | {'phone', 'email', 'contract'})
        self.assertEqual(body['contract']['witness_is_you'], True)

    def test_a_non_scholar_or_a_witness_only_scholar_is_404(self):
        for app in (self.submitted, self.witnessed, self.foreign):
            self.assertEqual(self.get(f'{SCHOLARS}{app.pk}/')[0].status_code, 404)


def _all_urls(t):
    return (PROFILE, OVERVIEW, f'{OVERVIEW}?p=gift-a', APPLICATIONS,
            f'{APPLICATIONS}{t.submitted.pk}/', f'{APPLICATIONS}{t.shortlisted.pk}/',
            f'{APPLICATIONS}{t.told.pk}/', f'{APPLICATIONS}{t.scholar.pk}/',
            f'{APPLICATIONS}{t.witnessed.pk}/', SCHOLARS, f'{SCHOLARS}{t.scholar.pk}/')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestWhoMayCall(_Fixture):
    def test_the_never_list_is_absent_from_every_response(self):
        for url in _all_urls(self):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertEqual(never_keys(resp.json()), [], url)

    def test_the_walker_bites(self):
        self.assertEqual(never_keys({'a': [{'profile': {'nric': 1, 'city': 2}}],
                                     'award_amount': 3, 'application_id': 4}),
                         ['.a[0].profile.nric', '.a[0].profile.city', '.award_amount'])

    def test_staff_are_refused_every_source_endpoint(self):
        staff = (make_admin('super', super_admin=True), make_admin('org_admin', owning_org=self.org),
                 make_admin('admin', owning_org=self.org), make_admin('reviewer', owning_org=self.org))
        for admin in staff:
            client = authed_client(admin)
            for url in _all_urls(self):
                self.assertEqual(client.get(url).status_code, 403, (admin.role, url))
            self.assertEqual(client.patch(PROFILE, {'user': {'name': 'x'}},
                                          format='json').status_code, 403)

    def test_another_source_of_the_same_organisation_sees_none_of_ours(self):
        client = authed_client(make_admin('source_partner', owning_org=self.org, source=self.other))
        ids = {r['id'] for r in client.get(APPLICATIONS).json()['applications']}
        self.assertEqual(ids, {self.others.pk, self.witnessed.pk})
        self.assertEqual(client.get(f'{APPLICATIONS}{self.submitted.pk}/').status_code, 404)
        self.assertEqual(client.get(f'{SCHOLARS}{self.scholar.pk}/').status_code, 404)
        self.assertEqual(client.get(OVERVIEW, {'p': 'gift-a'}).status_code, 200)   # its students' gift

    def test_another_organisations_source_sees_none_of_ours(self):
        client = authed_client(make_admin('source_partner', owning_org=self.org2,
                                          source=self.source2))
        self.assertEqual({r['id'] for r in client.get(APPLICATIONS).json()['applications']},
                         {self.foreign.pk})
        self.assertEqual(client.get(f'{APPLICATIONS}{self.submitted.pk}/').status_code, 404)
        self.assertEqual(client.get(OVERVIEW, {'p': 'gift-a'}).status_code, 404)

    def test_a_revoked_source_user_is_refused(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        for url in _all_urls(self):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_a_switched_off_source_sees_nothing(self):
        self.source.is_active = False
        self.source.save(update_fields=['is_active'])
        for url in _all_urls(self):
            resp = self.client.get(url)
            self.assertEqual((resp.status_code, resp.json()['code']),
                             (403, 'source_unavailable'), url)
        self.assertEqual(self.client.patch(PROFILE, {'user': {'name': 'x'}},
                                           format='json').status_code, 403)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheListsCostNoQueryPerRow(TestCase):
    """No N+1: a list read costs the same with one row as with four (and stays under a bound)."""

    #: Measured 2026-10-30 (SQLite, the test client), equal at both sizes.
    BOUNDS = {APPLICATIONS: 4, SCHOLARS: 5, OVERVIEW: 7}

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(programme=make_programme(organisation=cls.org))
        cls.source = make_source(organisation=cls.org)
        cls.user = make_admin('source_partner', owning_org=cls.org, source=cls.source)

    def _add(self, n):
        for _ in range(n):
            for stage in ('submitted', 'shortlisted', 'active'):
                app = make_application(stage, cohort=self.cohort, source=self.source,
                                       chosen_programme={'institution': 'UM'})
            BursaryAgreement.objects.create(application=app, version='v1',
                                            student_signed_at=timezone.now())

    def _count(self, url):
        client = authed_client(self.user)
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(client.get(url).status_code, 200)
        return len(ctx.captured_queries)

    def test_each_list_costs_the_same_at_two_sizes(self):
        self._add(1)
        small = {url: self._count(url) for url in self.BOUNDS}
        self._add(3)
        large = {url: self._count(url) for url in self.BOUNDS}
        self.assertEqual(small, large)
        for url, bound in self.BOUNDS.items():
            self.assertLessEqual(large[url], bound, url)


class TestTheStageVocabulary(TestCase):
    """The console's stages ARE the partner emails' lines, and every status folds to one."""

    def test_the_stages_are_the_email_lines(self):
        from apps.scholarship.partner_comms import STAGE_LINES
        self.assertEqual(source_console.STAGES, tuple(line for line, _ in STAGE_LINES))

    def test_every_status_folds(self):
        statuses = {code for code, _label in ScholarshipApplication.STATUS_CHOICES}
        self.assertEqual(statuses - set(source_console._LINE_OF), set())

    def test_told_at_only_on_an_outcome(self):
        app = ScholarshipApplication(status='interviewing', awarded_at=datetime.datetime(2026, 1, 1))
        self.assertIsNone(source_console.told_at(app, source_console.stage_of(app)))
