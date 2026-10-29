"""Student maintenance Sprint 4a — results recorded with a slip, REVIEWED, and the one rule that only an
ACCEPTED result counts — for standing and for every sponsor reader. The doors (decisions.md, S4a):

  WRITERS  in_programme.record_semester_result (student; starts `pending`; the slip recorded by
           results_review.record_slip, never the pre-award document pipeline) ·
           results_review.review (officer; accept / query, `result_reviewed` logged)
  READERS  standing.standing_of / scholars list (staff) · pool.derive_progress_state (sponsor band) ·
           pool.sponsor_portfolio_status (badge + semester count) · serializers SponsorshipSerializer
           .get_semesters · sponsorship impact `semesters_completed` · sponsor_feed events ·
           the student's own list (every status, so she sees a query).
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import OrganisationConfiguration
from apps.scholarship import in_programme, pool, results_review, standing
from apps.scholarship.in_programme import InProgrammeError
from apps.scholarship.models import ApplicantDocument, SemesterResult, StudentActivity
from apps.scholarship.models.activity import EVENT_RESULT_REVIEWED
from apps.scholarship.storage import build_doc_key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

API = '/api/v1/admin/scholarship/scholars/'


def _slip(app, **over):
    return {'storage_path': build_doc_key(app, app.id, 'semester_result', 'abc123'),
            'original_filename': 'slip.pdf', 'content_type': 'application/pdf', 'size': 1000, **over}


class TestRecordWithSlip(TestCase):
    def setUp(self):
        self.app = make_application('awarded', vircle_activated_at=timezone.now())

    @mock.patch('apps.scholarship.storage.object_exists', return_value=True)
    def test_a_result_with_its_slip_starts_pending(self, _exists):
        row = in_programme.record_semester_result(self.app, semester='Sem 2', cgpa='3.10',
                                                  slip_upload=_slip(self.app))
        self.assertEqual(row.review_status, 'pending')
        doc = row.results_slip
        self.assertEqual((doc.doc_type, doc.request_code, doc.original_filename),
                         ('semester_result', results_review.SLIP_REQUEST_CODE, 'slip.pdf'))
        self.assertEqual(doc.vision_fields or {}, {})      # never read by the pre-award pipeline

    @mock.patch('apps.scholarship.storage.object_exists', return_value=True)
    def test_a_slip_outside_her_own_prefix_is_refused(self, _exists):
        other = make_application('maintenance')
        for upload, code in ((_slip(other), 'bad_slip'),
                             (_slip(self.app, content_type='video/mp4', original_filename='x.mp4'),
                              'unsupported_format'),
                             (_slip(self.app, size=10 ** 9), 'file_too_large'),
                             ('not-a-dict', 'bad_slip')):
            with self.subTest(code=code):
                with self.assertRaises(InProgrammeError) as ctx:
                    in_programme.record_semester_result(self.app, semester='S', slip_upload=upload)
                self.assertEqual(ctx.exception.code, code)
        self.assertFalse(SemesterResult.objects.filter(application=self.app).exists())

    @mock.patch('apps.scholarship.storage.object_exists', return_value=False)
    def test_a_slip_that_never_landed_is_refused(self, _exists):
        with self.assertRaises(InProgrammeError) as ctx:
            in_programme.record_semester_result(self.app, semester='S', slip_upload=_slip(self.app))
        self.assertEqual(ctx.exception.code, 'upload_incomplete')
        self.assertFalse(ApplicantDocument.objects.filter(application=self.app).exists())


class TestReview(TestCase):
    def setUp(self):
        self.app = make_application('maintenance')
        self.row = in_programme.record_semester_result(self.app, semester='Sem 1', cgpa='2.50')

    def test_accept_stamps_and_logs(self):
        results_review.review(self.row, decision='accepted', by_email='o@example.test')
        self.row.refresh_from_db()
        self.assertEqual((self.row.review_status, self.row.reviewed_by), ('accepted', 'o@example.test'))
        log = StudentActivity.objects.get(application=self.app, event=EVENT_RESULT_REVIEWED)
        self.assertEqual((log.meta['old'], log.meta['new']), ('pending', 'accepted'))

    def test_a_query_needs_a_note(self):
        with self.assertRaises(results_review.ResultsError) as ctx:
            results_review.review(self.row, decision='queried', note='  ')
        self.assertEqual(ctx.exception.code, 'note_required')
        results_review.review(self.row, decision='queried', note='The slip is unreadable.')
        self.row.refresh_from_db()
        self.assertEqual((self.row.review_status, self.row.review_note),
                         ('queried', 'The slip is unreadable.'))

    def test_an_unknown_decision_is_refused(self):
        with self.assertRaises(results_review.ResultsError):
            results_review.review(self.row, decision='pending')


class TestStanding(TestCase):
    def setUp(self):
        self.app = make_application('maintenance')

    def _accepted(self, cgpa, graduated=False):
        return results_review.review(in_programme.record_semester_result(
            self.app, semester='S', cgpa=cgpa, graduated=graduated), decision='accepted')

    def test_the_ladder_at_the_defaults(self):
        self.assertEqual(standing.standing_of(self.app), 'no_result_yet')
        in_programme.record_semester_result(self.app, semester='S', cgpa='3.90')
        self.assertEqual(standing.standing_of(self.app), 'awaiting_review')     # pending only
        for cgpa, want in (('3.00', 'performing'), ('2.99', 'underperforming'),
                           ('2.00', 'underperforming'), ('1.99', 'failing')):
            with self.subTest(cgpa=cgpa):
                self._accepted(cgpa)
                self.assertEqual(standing.standing_of(self.app), want)
        self._accepted('1.00', graduated=True)
        self.assertEqual(standing.standing_of(self.app), 'performing')

    def test_changing_the_minimum_moves_the_chip_with_no_deploy(self):
        self._accepted('3.20')
        self.assertEqual(standing.standing_of(self.app), 'performing')
        OrganisationConfiguration.objects.create(organisation=self.app.owning_organisation,
                                                 values={'maintenance_min_cgpa': 3.5})
        self.app.owning_organisation.refresh_from_db()
        fresh = type(self.app).objects.get(pk=self.app.pk)
        self.assertEqual(standing.standing_of(fresh), 'underperforming')


class TestSettings(TestCase):
    def test_the_cgpa_keys_take_two_decimals_and_failing_stays_below_minimum(self):
        from apps.courses import org_config
        org_config.validate_values({'maintenance_min_cgpa': 3.25, 'maintenance_failing_cgpa': 2.5})
        for bad in ({'maintenance_min_cgpa': 3.255}, {'maintenance_min_cgpa': True},
                    {'maintenance_min_cgpa': 4.5}, {'results_terms_per_year': 2.5}):
            with self.subTest(bad=str(bad)):
                with self.assertRaises(org_config.OrgConfigError):
                    org_config.validate_values(bad)
        with self.assertRaises(org_config.OrgConfigError) as ctx:
            org_config.validate_values({'maintenance_min_cgpa': 2.0, 'maintenance_failing_cgpa': 2.0})
        self.assertEqual(ctx.exception.code, 'failing_not_below_min')

    def test_the_contract_guard(self):
        """The shipped BrightPath template states no CGPA in its progress standard — the settings
        page warns `contract_unstated`; a template stating another CGPA warns `contract_differs`."""
        import json
        import os
        from apps.scholarship.models import ContractTemplate
        here = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(here, 'fixtures', 'brightpath_contract_v1.json'), encoding='utf-8') as fh:
            shipped = json.load(fh)
        text = next(v for k, v in _walk(shipped) if k == 'progress_standard')['en']
        self.assertIsNone(standing.cgpa_in_text(text))
        self.assertEqual(standing.cgpa_in_text('Keep a CGPA of at least 3.00 each semester'),
                         Decimal('3.00'))
        cohort = make_cohort()
        org = cohort.owning_organisation
        ContractTemplate.objects.create(organisation=org, programme=cohort.programme, version=1,
                                        status='active', title_en='T', progress_standard_en=text)
        self.assertEqual([w['code'] for w in standing.contract_warnings(org)], ['contract_unstated'])
        ContractTemplate.objects.filter(organisation=org).update(
            progress_standard_en='A CGPA of 2.75 or above')
        self.assertEqual([(w['code'], w['stated']) for w in standing.contract_warnings(org)],
                         [('contract_differs', '2.75')])


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


class TestOnlyAcceptedReachesASponsor(TestCase):
    """THE CROSS-READER TEST: a pending (or queried) result moves NO sponsor reader; accepting it
    moves every one of them, the same way."""

    def setUp(self):
        from apps.scholarship.models import Sponsor, Sponsorship
        self.app = make_application('maintenance', supported_semesters=1)
        self.sponsor = Sponsor.objects.create(supabase_user_id='spn-r', name='S', email='s@e.test',
                                              status='approved')
        self.sp = Sponsorship.objects.create(sponsor=self.sponsor, application=self.app,
                                             amount=Decimal('2000'), status='active',
                                             decided_at=timezone.now())

    def _readings(self):
        from apps.scholarship import sponsor_feed, sponsorship
        from apps.scholarship.serializers import SponsorSponsorshipSerializer
        app = type(self.app).objects.get(pk=self.app.pk)
        return {
            'band': pool.derive_progress_state(app),
            'badge': pool.sponsor_portfolio_status(app),
            'semesters': SponsorSponsorshipSerializer(self.sp).data.get('semesters'),
            'impact': sponsorship.sponsor_impact(self.sponsor)['semesters_completed'],
            'feed': sorted(e['type'] for e in sponsor_feed.sponsor_activity(self.sponsor)
                           if e['type'] in ('semester', 'graduated')),
        }

    def test_pending_and_queried_move_nothing_accepted_moves_everything(self):
        before = self._readings()
        row = in_programme.record_semester_result(self.app, semester='S1', cgpa='1.50')
        self.assertEqual(self._readings(), before)
        results_review.review(row, decision='queried', note='Please re-upload.')
        self.assertEqual(self._readings(), before)
        results_review.review(row, decision='accepted')
        after = self._readings()
        self.assertEqual(after['band'], 'needs_attention')
        self.assertEqual(after['badge'], 'semester_completed')       # 1 accepted >= supported 1
        self.assertEqual((after['semesters'], after['impact'], after['feed']), (1, 1, ['semester']))


class TestTheDoorsAreTheListedOnes(TestCase):
    """The doors list (decisions.md, S4a) as a static fence: a NEW module that writes or reads
    `semester_results` must be added here on purpose — and answer whether it reads accepted-only."""

    DOORS = {
        'in_programme.py', 'maintenance.py', 'pool.py', 'results_review.py', 'scholars.py',
        'serializers.py', 'sponsor_feed.py', 'sponsorship.py', 'standing.py', 'urls.py', 'views.py',
        'views_admin/scholars.py', 'views_bursary.py', 'models/review.py', 'models/__init__.py',
        'models/documents.py',
    }
    WRITE_DOORS = {'in_programme.py', 'results_review.py'}

    def _sources(self):
        import pathlib
        root = pathlib.Path(in_programme.__file__).parent
        for f in root.rglob('*.py'):
            rel = f.relative_to(root).as_posix()
            if rel.startswith(('tests/', 'migrations/', 'management/')):
                continue
            yield rel, f.read_text(encoding='utf-8')

    def test_every_reader_and_writer_is_a_listed_door(self):
        found = {rel for rel, text in self._sources()
                 if 'SemesterResult' in text or 'semester_results' in text}
        self.assertEqual(found - self.DOORS, set())

    def test_only_the_two_writers_create_or_change_a_result(self):
        import re
        writes = re.compile(r'SemesterResult\.objects\.(create|update|bulk_create|update_or_create|get_or_create)'
                            r'|semester_results\.(create|update)|\.review_status\s*=(?!=)')
        found = {rel for rel, text in self._sources() if writes.search(text)}
        self.assertEqual(found, self.WRITE_DOORS)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestResultsEndpoints(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        org = self.cohort.owning_organisation
        self.reviewer = make_admin('reviewer', owning_org=org)
        self.officer = make_admin('admin', owning_org=org)
        self.org_admin = make_admin('org_admin', owning_org=org)
        self.finance = make_admin('finance', owning_org=org)
        self.app = make_application('maintenance', cohort=self.cohort, reviewer=self.reviewer)
        self.row = in_programme.record_semester_result(self.app, semester='Sem 1', cgpa='3.40')

    def _review(self, admin, decision='accepted', note=''):
        return authed_client(admin).post(f'{API}{self.app.id}/results/{self.row.id}/review/',
                                         {'decision': decision, 'note': note}, format='json')

    def test_the_results_tab_lists_every_result_with_its_review(self):
        rows = authed_client(self.officer).get(f'{API}{self.app.id}/results/').json()['results']
        self.assertEqual([(r['semester'], r['review_status'], r['slip']) for r in rows],
                         [('Sem 1', 'pending', None)])

    def test_the_assignee_and_the_org_admin_review_a_reader_cannot(self):
        self.assertEqual(self._review(self.officer).status_code, 403)       # see_all, not assigned
        self.assertEqual(self._review(self.finance).status_code, 403)
        r = self._review(self.reviewer)
        self.assertEqual((r.status_code, r.json()['review_status']), (200, 'accepted'))
        r = self._review(self.org_admin, decision='queried', note='Unclear slip.')
        self.assertEqual((r.status_code, r.json()['review_note']), (200, 'Unclear slip.'))

    def test_refusals(self):
        r = self._review(self.org_admin, decision='queried')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'note_required'))
        other = make_application('maintenance', cohort=self.cohort)
        r = authed_client(self.org_admin).post(f'{API}{other.id}/results/{self.row.id}/review/',
                                               {'decision': 'accepted'}, format='json')
        self.assertEqual(r.status_code, 404)                                # not her result

    def test_the_student_sees_her_own_review(self):
        results_review.review(self.row, decision='queried', note='Please re-upload.')
        body = authed_client(self.app.profile.supabase_user_id).get(
            f'/api/v1/scholarship/applications/{self.app.id}/semester-results/').json()
        self.assertEqual((body['results'][0]['review_status'], body['results'][0]['review_note']),
                         ('queried', 'Please re-upload.'))
        self.assertNotIn('reviewed_by', body['results'][0])

    def test_the_list_standing_and_underperforming_filter(self):
        low = make_application('maintenance', cohort=self.cohort)
        results_review.review(in_programme.record_semester_result(low, semester='S', cgpa='2.40'),
                              decision='accepted')
        body = authed_client(self.org_admin).get(API).json()
        by_id = {r['id']: r for r in body['results']}
        self.assertEqual((by_id[self.app.id]['standing'], by_id[low.id]['standing']),
                         ('awaiting_review', 'underperforming'))
        self.assertEqual(body['summary']['below_minimum'], 1)
        rows = authed_client(self.org_admin).get(API, {'standing': 'below_minimum'}).json()['results']
        self.assertEqual([r['id'] for r in rows], [low.id])
