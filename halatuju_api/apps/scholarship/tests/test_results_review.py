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
import ast
import pathlib
import uuid
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import OrganisationConfiguration
from apps.scholarship import standing as standing_module
from apps.scholarship import in_programme, pool, results_review, standing
from apps.scholarship.in_programme import InProgrammeError
from apps.scholarship.models import ApplicantDocument, SemesterResult, StudentActivity
from apps.scholarship.models.activity import EVENT_RESULT_REVIEWED
from apps.scholarship.storage import build_doc_key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, record_result,
)

API = '/api/v1/admin/scholarship/scholars/'


def _slip(app, **over):
    # The shape the sign-upload door issues: `<org>/<app>/semester_result/<uuid4 hex>`.
    return {'storage_path': build_doc_key(app, app.id, 'semester_result', uuid.uuid4().hex),
            'original_filename': 'slip.pdf', 'content_type': 'application/pdf', 'size': 1000, **over}


def _slip_doc(app):
    """A slip recorded the S4a way, with its (pending) result."""
    with mock.patch('apps.scholarship.storage.object_exists', return_value=True):
        return in_programme.record_semester_result(app, semester='S', slip_upload=_slip(app)).results_slip


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

    @mock.patch('apps.scholarship.storage.object_exists', return_value=True)
    def test_only_the_exact_issued_key_shape_is_accepted(self, _exists):
        """L1: `<prefix>/<32 hex>` and nothing else — a traversal, a sub-folder, a short or upper-case
        tail, a long path or a non-string never becomes her slip."""
        prefix = build_doc_key(self.app, self.app.id, 'semester_result')
        good = uuid.uuid4().hex
        for path in (f'{prefix}/../{good}', f'{prefix}/x/{good}', f'{prefix}/{good[:31]}',
                     f'{prefix}/{good.upper()}', f'{prefix}/{good}/', f'{prefix}/{good}' + 'a' * 300,
                     f'{prefix}/..{good[2:]}', 12345, None):
            with self.subTest(path=str(path)[-40:]):
                with self.assertRaises(InProgrammeError) as ctx:
                    in_programme.record_semester_result(
                        self.app, semester='S', slip_upload=_slip(self.app, storage_path=path))
                self.assertEqual(ctx.exception.code, 'bad_slip')
        self.assertFalse(ApplicantDocument.objects.filter(application=self.app).exists())

    def test_a_sixth_result_in_a_day_is_refused(self):
        """L3: five a day leave room to correct a typo; a sixth is `too_many_results`."""
        for n in range(in_programme.MAX_RESULTS_PER_DAY):
            record_result(self.app, semester=f'S{n}', cgpa='3.00')
        with self.assertRaises(InProgrammeError) as ctx:
            record_result(self.app, semester='S6', cgpa='3.00')
        self.assertEqual(ctx.exception.code, 'too_many_results')
        SemesterResult.objects.filter(application=self.app).update(
            created_at=timezone.now() - timezone.timedelta(hours=25))
        record_result(self.app, semester='S6', cgpa='3.00')   # a day later

    @mock.patch('apps.scholarship.storage.object_exists', return_value=False)
    def test_a_slip_that_never_landed_is_refused(self, _exists):
        with self.assertRaises(InProgrammeError) as ctx:
            in_programme.record_semester_result(self.app, semester='S', slip_upload=_slip(self.app))
        self.assertEqual(ctx.exception.code, 'upload_incomplete')
        self.assertFalse(ApplicantDocument.objects.filter(application=self.app).exists())


class TestReview(TestCase):
    def setUp(self):
        self.app = make_application('maintenance')
        self.row = record_result(self.app, semester='Sem 1', cgpa='2.50')

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


class TestNoSlipNoResult(TestCase):
    """OWNER RULING 2026-10-29: "Students must upload at the portal. Emailed docs are not allowed." """

    def setUp(self):
        self.app = make_application('maintenance')

    def test_a_result_without_her_slip_is_refused(self):
        for empty in (None, {}, ''):
            with self.subTest(slip=repr(empty)):
                with self.assertRaises(InProgrammeError) as ctx:
                    in_programme.record_semester_result(self.app, semester='S', cgpa='3.20', slip_upload=empty)
                self.assertEqual(ctx.exception.code, 'slip_required')
        self.assertFalse(SemesterResult.objects.filter(application=self.app).exists())

    def test_a_result_with_no_slip_can_be_queried_never_accepted(self):
        # A pre-ruling typed-only row (the live ones recorded before S4a) has no slip.
        legacy = SemesterResult.objects.create(application=self.app, semester='Old', cgpa=Decimal('3.30'))
        with self.assertRaises(results_review.ResultsError) as ctx:
            results_review.review(legacy, decision='accepted')
        self.assertEqual(ctx.exception.code, 'slip_required')
        legacy.refresh_from_db()
        self.assertEqual(legacy.review_status, 'pending')
        results_review.review(legacy, decision='queried', note='Please upload your slip at the portal.')
        legacy.refresh_from_db()
        self.assertEqual(legacy.review_status, 'queried')


class TestStanding(TestCase):
    def setUp(self):
        self.app = make_application('maintenance')

    def _accepted(self, cgpa, graduated=False):
        return results_review.review(record_result(
            self.app, semester='S', cgpa=cgpa, graduated=graduated), decision='accepted')

    @mock.patch.object(in_programme, 'MAX_RESULTS_PER_DAY', 100)
    def test_the_ladder_at_the_defaults(self):
        self.assertEqual(standing.standing_of(self.app), 'no_result_yet')
        record_result(self.app, semester='S', cgpa='3.90')
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
                    {'maintenance_min_cgpa': 4.5}):
            with self.subTest(bad=str(bad)):
                with self.assertRaises(org_config.OrgConfigError):
                    org_config.validate_values(bad)
        with self.assertRaises(org_config.OrgConfigError) as ctx:
            org_config.validate_values({'maintenance_min_cgpa': 2.0, 'maintenance_failing_cgpa': 2.0})
        self.assertEqual(ctx.exception.code, 'failing_not_below_min')

    def test_a_whole_number_key_takes_an_int_only(self):
        """L2: `decimals` 0 means an int — 2.5 AND 2.0 are refused (the stored JSON stays whole)."""
        from apps.courses import org_config
        org_config.validate_values({'pool_funded_grace_days': 2}, pairs=False)
        for bad in (2.5, 2.0, True, '2'):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(org_config.OrgConfigError) as ctx:
                    org_config.validate_values({'pool_funded_grace_days': bad}, pairs=False)
                self.assertEqual(ctx.exception.code, 'bad_value')

    def test_every_maintenance_key_has_its_reader(self):
        """M1: a setting arrives with its reader. S4b's timing keys are read by
        `results_expectations.settings_for`; the two reminder keys by `send_due_reminders`."""
        from apps.courses.org_config_registry import SETTINGS
        self.assertEqual(sorted(k for k, v in SETTINGS.items() if v['group'] == 'maintenance'),
                         ['maintenance_failing_cgpa', 'maintenance_min_cgpa', 'results_due_days_after_term',
                          'results_overdue_grace_days', 'results_reminder_every_days',
                          'results_reminder_lead_days', 'results_terms_per_year'])

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
        self.assertEqual(standing.cgpas_in_text(text), [])
        self.assertEqual(standing.cgpas_in_text('Keep a CGPA of at least 3.00 each semester.'),
                         [Decimal('3.00')])
        cohort = make_cohort()
        org = cohort.owning_organisation
        ContractTemplate.objects.create(organisation=org, programme=cohort.programme, version=1,
                                        status='active', title_en='T', progress_standard_en=text)
        self.assertEqual([w['code'] for w in standing.contract_warnings(org)], ['contract_unstated'])
        ContractTemplate.objects.filter(organisation=org).update(
            progress_standard_en='A CGPA of 2.75 or above')
        self.assertEqual([(w['code'], w['stated']) for w in standing.contract_warnings(org)],
                         [('contract_differs', '2.75')])

    def test_the_contract_guard_reads_the_clauses_and_needs_a_gpa_phrase(self):
        """L5: the live BrightPath template states its line in a CLAUSE (4.1.V), not the progress
        standard — and a bare "3.1" is a clause number, never a CGPA."""
        from apps.scholarship.models import ContractClause, ContractTemplate
        cohort = make_cohort()
        org = cohort.owning_organisation
        tpl = ContractTemplate.objects.create(
            organisation=org, programme=cohort.programme, version=1, status='active', title_en='T',
            progress_standard_en='Satisfactory academic progress, as clause 3.1 sets out.')
        self.assertEqual([w['code'] for w in standing.contract_warnings(org)], ['contract_unstated'])
        ContractClause.objects.create(template=tpl, order=4, heading_en='4.1 Obligations', body_en=(
            'V. The Student shall maintain a minimum grade point average (CGPA) of 3.0 in each '
            'semester of the Programme.'))
        self.assertEqual(standing.contract_warnings(org), [])          # 3.0 = the 3.00 default
        OrganisationConfiguration.objects.create(organisation=org, values={'maintenance_min_cgpa': 3.25})
        org.refresh_from_db()
        self.assertEqual([(w['code'], w['stated']) for w in standing.contract_warnings(org)],
                         [('contract_differs', '3.00')])
        for text, want in (('PNGK minimum 2.50.', [Decimal('2.50')]), ('3.00 CGPA', [Decimal('3.00')]),
                           ('Clause 4.1 and 3.1 apply.', []), ('a GPA in clause 4.1.5', [])):
            with self.subTest(text=text):
                self.assertEqual(standing.cgpas_in_text(text), want)


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


class TestOneFailingLineForBothAudiences(TestCase):
    """M2: the sponsor band's `needs_attention` IS the staff standing `failing` — strictly below the
    organisation's failing CGPA. At 2.00 (the default line) both read fine-but-not-failing."""

    def _both(self, cgpa, values=None):
        app = make_application('maintenance')
        if values:
            OrganisationConfiguration.objects.create(organisation=app.owning_organisation, values=values)
            app.owning_organisation.refresh_from_db()
        results_review.review(record_result(app, semester='S', cgpa=cgpa),
                              decision='accepted')
        app = type(app).objects.get(pk=app.pk)
        return standing_module.standing_of(app), pool.derive_progress_state(app)

    def test_the_boundary(self):
        custom = {'maintenance_min_cgpa': 3.0, 'maintenance_failing_cgpa': 2.5}
        for cgpa, values, want in (
                ('1.99', None, ('failing', 'needs_attention')),
                ('2.00', None, ('underperforming', 'semester_completed')),
                ('2.49', custom, ('failing', 'needs_attention')),
                ('2.50', custom, ('underperforming', 'semester_completed'))):
            with self.subTest(cgpa=cgpa, custom=bool(values)):
                self.assertEqual(self._both(cgpa, values), want)

    def test_a_tie_on_created_at_never_flips_the_band(self):
        """M3: two accepted results stamped the same instant — the later row (`-id`) wins, always."""
        app = make_application('maintenance')
        first = results_review.review(record_result(app, semester='A', cgpa='3.50'),
                                      decision='accepted')
        second = results_review.review(record_result(app, semester='B', cgpa='1.50'),
                                       decision='accepted')
        SemesterResult.objects.filter(pk__in=[first.pk, second.pk]).update(created_at=first.created_at)
        self.assertEqual(pool.derive_progress_state(app), 'needs_attention')
        self.assertEqual(standing_module.standing_of(app), 'failing')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSlipIsEvidence(TestCase):
    """H1: once recorded, her slip is evidence — she cannot delete or replace it, whatever its
    review says, and it never shows in (or is re-read from) the general documents list."""

    def setUp(self):
        self.app = make_application('maintenance')
        self.doc = _slip_doc(self.app)
        self.client = authed_client(self.app.profile.supabase_user_id)

    def test_she_cannot_delete_it_pending_accepted_or_queried(self):
        result = SemesterResult.objects.get(results_slip=self.doc)
        for status in ('pending', 'accepted', 'queried'):
            with self.subTest(status=status):
                SemesterResult.objects.filter(pk=result.pk).update(review_status=status)
                r = self.client.delete(f'/api/v1/scholarship/documents/{self.doc.id}/')
                self.assertEqual((r.status_code, r.json()['code']), (409, 'slip_locked'))
        self.assertTrue(ApplicantDocument.objects.filter(pk=self.doc.pk).exists())

    def test_a_document_a_result_names_is_locked_whatever_its_slot(self):
        other = ApplicantDocument.objects.create(application=self.app, doc_type='semester_result',
                                                 storage_path='x', original_filename='old.pdf')
        r = self.client.delete(f'/api/v1/scholarship/documents/{other.id}/')
        self.assertNotEqual(r.status_code, 409)                         # nothing names it: deletable
        named = ApplicantDocument.objects.create(application=self.app, doc_type='semester_result',
                                                 storage_path='y', original_filename='named.pdf')
        SemesterResult.objects.filter(results_slip=self.doc).update(results_slip=named)
        self.assertTrue(results_review.slip_locked(named))
        r = self.client.delete(f'/api/v1/scholarship/documents/{named.id}/')
        self.assertEqual(r.status_code, 409)

    def test_it_is_not_in_her_documents_list_and_its_slot_cannot_be_written(self):
        docs = self.client.get('/api/v1/scholarship/documents/').json()['documents']
        self.assertNotIn(self.doc.id, [d['id'] for d in docs])
        r = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'semester_result', 'request_code': results_review.SLIP_REQUEST_CODE,
            'storage_path': self.doc.storage_path, 'original_filename': 'new.pdf',
            'content_type': 'application/pdf', 'size': 10}, format='json')
        self.assertEqual(r.status_code, 409)
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.superseded_at)

    def test_no_sweep_ever_re_reads_it(self):
        """Even with a service-error read stamped on it, no self-heal sweep picks a slip up."""
        from apps.scholarship.services import blockers, read_retry
        ApplicantDocument.objects.filter(pk=self.doc.pk).update(
            vision_fields={'error': read_retry.RATE_LIMITED})
        self.assertNotIn(self.doc.id, [d.id for d in blockers._stuck_unread_documents(500)])
        self.assertNotIn(self.doc.id, [d.id for d in read_retry.service_error_documents(500)])
        self.assertEqual(blockers.reprocess_unread_ic_documents(dry_run=True)['by_type'].get('semester_result', 0), 0)


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
        row = record_result(self.app, semester='S1', cgpa='1.50')
        self.assertEqual(self._readings(), before)
        results_review.review(row, decision='queried', note='Please re-upload.')
        self.assertEqual(self._readings(), before)
        results_review.review(row, decision='accepted')
        after = self._readings()
        self.assertEqual(after['band'], 'needs_attention')
        self.assertEqual(after['badge'], 'semester_completed')       # 1 accepted >= supported 1
        self.assertEqual((after['semesters'], after['impact'], after['feed']), (1, 1, ['semester']))


class TestTheDoorsAreTheListedOnes(TestCase):
    """The doors list (decisions.md, S4a) as a static fence, PER CALL SITE (review M4): every
    function anywhere in `apps/` (management commands included) that touches `semester_results` or
    `SemesterResult.objects` is named here with its role. A `judge` must read through
    `results_review.accepted(...)`; only the two writers create or change a result."""

    DOORS = {
        # writers
        'scholarship/in_programme.py::record_semester_result': 'writer',
        # the ONE rule and its helpers
        'scholarship/results_review.py::latest_accepted': 'judge',
        'scholarship/results_review.py::accepted_count': 'judge',
        'scholarship/results_review.py::has_pending': 'show',
        'scholarship/results_review.py::results_for_file': 'show',
        'scholarship/results_review.py::slip_locked': 'show',
        # judging readers that query directly (a subquery / one feed query)
        'scholarship/scholars.py::_latest': 'judge',
        'scholarship/sponsor_feed.py::sponsor_activity': 'judge',
        'scholarship/results_expectations.py::reconcile': 'judge',         # S4b: accepted results meet terms
        # showing readers (every status, with its review state)
        'scholarship/scholars.py::annotate': 'show',                      # the "a result waits" flag
        'scholarship/views_bursary.py::summary_payload': 'show',           # her own latest, any status
        'scholarship/views_admin/scholars.py::AdminScholarResultReviewView.post': 'show',  # fetch to review
    }
    WRITERS = {'scholarship/in_programme.py::record_semester_result', 'scholarship/results_review.py::review',
               # S4b: the term stamp only (`term_index`), never a review or a CGPA
               'scholarship/results_expectations.py::reconcile', 'scholarship/results_expectations.py::unlink'}
    WRITE_METHODS = {'create', 'update', 'bulk_create', 'bulk_update', 'update_or_create',
                     'get_or_create', 'delete'}
    #: Fields only a SemesterResult carries — assigning one is a write wherever it happens.
    WRITE_ATTRS = {'review_status', 'term_index', 'cgpa'}

    def _scan(self):
        root = pathlib.Path(in_programme.__file__).parent.parent        # apps/
        touches, writes, sources = set(), set(), {}
        for f in sorted(root.rglob('*.py')):
            rel = f.relative_to(root).as_posix()
            if '/tests/' in rel or '/migrations/' in rel:
                continue
            text = f.read_text(encoding='utf-8')
            for name, node, src in self._functions(rel, ast.parse(text), text):
                sources[name] = src
                for sub in self._own_nodes(node):
                    if self._touches(sub):
                        touches.add(name)
                    if (isinstance(sub, ast.Assign) and any(
                            isinstance(t, ast.Attribute) and t.attr in self.WRITE_ATTRS for t in sub.targets)):
                        writes.add(name)
            for name, node, _src in self._functions(rel, ast.parse(text), text):
                if name in touches and any(
                        isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr in self.WRITE_METHODS for sub in self._own_nodes(node)):
                    writes.add(name)
        return touches, writes, sources

    @staticmethod
    def _touches(node):
        return isinstance(node, ast.Attribute) and (
            node.attr == 'semester_results'
            or (node.attr == 'objects' and isinstance(node.value, ast.Name) and node.value.id == 'SemesterResult'))

    @staticmethod
    def _own_nodes(fn):
        """Every node of `fn` except those inside a nested def/class (they are their own door)."""
        stack = list(ast.iter_child_nodes(fn))
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            yield node
            stack.extend(ast.iter_child_nodes(node))

    def _functions(self, rel, tree, text, prefix=''):
        yield f'{rel}::{prefix.rstrip(".") or "<module>"}', tree, ''
        stack = [(n, prefix) for n in tree.body]
        while stack:
            node, pre = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f'{pre}{node.name}'
                if not isinstance(node, ast.ClassDef):
                    yield f'{rel}::{name}', node, ast.get_source_segment(text, node) or ''
                stack.extend((child, f'{name}.') for child in node.body)

    def test_every_call_site_is_a_named_door(self):
        touches, _writes, _src = self._scan()
        self.assertEqual(sorted(touches - set(self.DOORS)), [])
        self.assertEqual(sorted(set(self.DOORS) - touches), [])        # a stale entry is a lie too

    def test_a_judging_reader_reads_accepted_only(self):
        _touches, _writes, sources = self._scan()
        for name, role in self.DOORS.items():
            if role == 'judge':
                with self.subTest(door=name):
                    self.assertIn('accepted(', sources[name])

    def test_only_the_two_writers_create_or_change_a_result(self):
        _touches, writes, _src = self._scan()
        self.assertEqual(writes, self.WRITERS)


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
        self.row = record_result(self.app, semester='Sem 1', cgpa='3.40')

    def _review(self, admin, decision='accepted', note=''):
        return authed_client(admin).post(f'{API}{self.app.id}/results/{self.row.id}/review/',
                                         {'decision': decision, 'note': note}, format='json')

    def test_the_results_tab_lists_every_result_with_its_review(self):
        rows = authed_client(self.officer).get(f'{API}{self.app.id}/results/').json()['results']
        self.assertEqual([(r['semester'], r['review_status'], r['slip']['filename']) for r in rows],
                         [('Sem 1', 'pending', 'slip.pdf')])

    def test_the_assignee_and_the_org_admin_review_a_reader_cannot(self):
        self.assertEqual(self._review(self.officer).status_code, 403)       # see_all, not assigned
        self.assertEqual(self._review(self.finance).status_code, 403)
        r = self._review(self.reviewer)
        self.assertEqual((r.status_code, r.json()['review_status']), (200, 'accepted'))
        r = self._review(self.org_admin, decision='queried', note='Unclear slip.')
        self.assertEqual((r.status_code, r.json()['review_note']), (200, 'Unclear slip.'))

    def test_accept_without_a_slip_is_409_and_staff_cannot_attach_one(self):
        bare = SemesterResult.objects.create(application=self.app, semester='Old', cgpa=Decimal('3.30'))
        other = ApplicantDocument.objects.create(application=self.app, doc_type='semester_result',
                                                 storage_path='z', original_filename='emailed.pdf')
        r = authed_client(self.org_admin).post(f'{API}{self.app.id}/results/{bare.id}/review/', {
            'decision': 'accepted', 'results_slip': other.id, 'slip': {'storage_path': 'z'}}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'slip_required'))
        bare.refresh_from_db()
        self.assertEqual((bare.results_slip_id, bare.review_status), (None, 'pending'))

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
        results_review.review(record_result(low, semester='S', cgpa='2.40'),
                              decision='accepted')
        body = authed_client(self.org_admin).get(API).json()
        by_id = {r['id']: r for r in body['results']}
        self.assertEqual((by_id[self.app.id]['standing'], by_id[low.id]['standing']),
                         ('awaiting_review', 'underperforming'))
        self.assertEqual(body['summary']['below_minimum'], 1)
        rows = authed_client(self.org_admin).get(API, {'standing': 'below_minimum'}).json()['results']
        self.assertEqual([r['id'] for r in rows], [low.id])
