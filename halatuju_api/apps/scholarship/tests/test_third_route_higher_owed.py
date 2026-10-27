"""Higher results OWED over a pre-S3 frozen snapshot (third results route follow-up, 2026-10-27;
owner option A, application #388) — `apps/scholarship/higher_owed.py`.

#388's SHAPE (never its data): submitted shortly before S3a, so its `requirements_snapshot` froze
"SPM slip required" with no `higher_results` key; the student holds STPM results, chose a degree,
and uploaded only an SPM slip. Before this change the cockpit showed nothing missing and Academic
read Certain on the SPM slip alone.

Pinned here: the missing slot is SERVED (the Academic fact's reason item), Academic is at most
Probable with the reason named, one Check-2 ask is raised (stage rules, once, idempotent), an
upload of those results closes it, and — above all — no gate reads any of it, so a submitted
application is NEVER sent back to the wizard by it.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import higher_owed, requirements, results_route
from apps.scholarship.check2_queries import DOC_SPECS, GOVERNED_BY, sync_check2_queries
from apps.scholarship.models import ResolutionItem
from apps.scholarship.resolution import resolve_doc_items_for_upload, sync_resolution_items
from apps.scholarship.services import application_completeness, revert_if_profile_incomplete
from apps.scholarship.tests.test_third_route_s4 import (
    DEGREE, POLY, SPM_HELD, SPM_READ, STPM_CERT_READ, STPM_HELD, UNDECIDED, _academic, _app, _doc,
    _fresh,
)
from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION

GENUINE_SPM = {'status': 'genuine', 'doc_seen': 'results_slip', 'probability': 0.95,
               'model_version': '1.9.0', 'reason': 'test'}
STPM_SLIP = {'candidate_name': 'PRIYA', 'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025',
             'cgpa': '3.71', 'cgpa_label': 'PNGK', 'results_kind_detected': 'stpm'}


def _submitted(profile=STPM_HELD, plan=DEGREE, stage='profile_complete', slip=SPM_READ):
    """A submitted application frozen BEFORE S3a (the factory freezes the catalogue's plain
    "SPM slip required" — no `higher_results` key, exactly #388's snapshot), with an SPM slip."""
    app = _app(profile, plan, stage=stage)
    if slip is not None:
        _doc(app, 'results_slip', slip, authenticity=GENUINE_SPM)
    return _fresh(app)


def _ask(app):
    return ResolutionItem.objects.filter(application=app, source='check2',
                                         code=higher_owed.ASK_CODE)


class TestTheShapeIs388s(TestCase):
    def test_the_frozen_snapshot_predates_s3(self):
        app = _submitted()
        docs = app.requirements_snapshot['documents']
        self.assertEqual(docs.get('results_slip'), 'required')
        self.assertNotIn('higher_results', docs)
        self.assertEqual(results_route.destination(app), results_route.DEGREE)
        self.assertEqual(results_route.held_kind(app), 'stpm')

    def test_the_version_moved(self):
        # #388 shipped at 2026-10-27.2; a later bump (TD-404: .3) must not break this pin.
        self.assertGreaterEqual(VERDICT_ENGINE_VERSION, '2026-10-27.2')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestShowTheGapAndCapTheVerdict(TestCase):
    def test_388_reads_probable_with_the_reason_named(self):
        f = _academic(_submitted())
        self.assertEqual(f['status'], 'review')                       # Probable, never Certain
        note = next(i for i in f['unresolved'] if i['code'] == higher_owed.NOTE_CODE)
        self.assertEqual(note['params'], {'held': 'STPM', 'kind': 'stpm'})   # the drawer's slot

    def test_the_same_slip_on_a_post_spm_pathway_stays_certain(self):
        """The control: the cap comes from the owed results, not from the slip."""
        f = _academic(_submitted(plan=POLY))
        self.assertEqual(f['status'], 'verified')
        self.assertNotIn(higher_owed.NOTE_CODE, [i['code'] for i in f['unresolved']])

    def test_an_spm_holder_bound_for_a_degree_gets_nothing_new(self):
        """D14 is for applications not yet submitted; a submitted SPM holder keeps her frozen card."""
        app = _submitted(profile=SPM_HELD)
        f = _academic(app)
        self.assertEqual(f['status'], 'verified')
        self.assertEqual(higher_owed.owed_kind(app), '')

    def test_no_course_chosen_gets_nothing_new(self):
        self.assertEqual(higher_owed.owed_kind(_submitted(plan=UNDECIDED)), '')

    def test_a_worse_band_stands_and_a_missing_spm_slip_is_still_a_gap(self):
        f = _academic(_submitted(slip=None))
        self.assertEqual(f['status'], 'gap')
        self.assertIn(higher_owed.NOTE_CODE, [i['code'] for i in f['unresolved']])

    def test_not_before_submit(self):
        """Before submit the live D12 rule already requires the higher card (S3) — nothing here."""
        app = _app(STPM_HELD, DEGREE, stage='shortlisted')
        self.assertEqual(higher_owed.owed_kind(app), '')

    def test_a_snapshot_already_requiring_them_is_s3s_not_ours(self):
        app = _submitted()
        app.requirements_snapshot = {**app.requirements_snapshot, 'documents': {
            **app.requirements_snapshot['documents'], 'higher_results': 'required',
            'results_slip': 'optional'}}
        app.save(update_fields=['requirements_snapshot'])
        app = _fresh(app)
        self.assertEqual(higher_owed.owed_kind(app), '')
        self.assertEqual(higher_owed.ask_codes(app), set())

    def test_a_programme_asking_no_results_is_left_alone(self):
        app = _submitted()
        app.requirements_snapshot = {**app.requirements_snapshot, 'documents': {
            **app.requirements_snapshot['documents'], 'results_slip': 'off'}}
        app.save(update_fields=['requirements_snapshot'])
        self.assertEqual(higher_owed.owed_kind(_fresh(app)), '')

    def test_stpm_results_already_in_the_spm_card_are_not_asked_again(self):
        """S4's wrong slip (#43): they ARE on file; the SPM card already says so."""
        app = _submitted(slip=STPM_CERT_READ)
        self.assertEqual(higher_owed.owed_kind(app), '')
        self.assertNotIn(higher_owed.NOTE_CODE, [i['code'] for i in _academic(app)['unresolved']])


class TestTheCheck2Ask(TestCase):
    def test_one_ask_raised_with_the_kind_and_idempotent(self):
        app = _submitted()
        sync_check2_queries(app)
        sync_check2_queries(_fresh(app))
        self.assertEqual(_ask(app).count(), 1)
        item = _ask(app).get()
        self.assertEqual((item.status, item.kind, item.doc_type, item.fact, item.params),
                         ('open', 'doc', 'higher_results', 'academic', {'results_kind': 'stpm'}))

    def test_governed_by_the_core_results_item_and_held_through_an_outage(self):
        self.assertEqual(DOC_SPECS[higher_owed.ASK_CODE]['doc_type'], 'higher_results')
        self.assertEqual(GOVERNED_BY[higher_owed.ASK_CODE], (('document', 'results_slip'),))
        from apps.scholarship.check2_deferred import HELD_WHILE_DEFERRED
        self.assertIn(higher_owed.ASK_CODE, HELD_WHILE_DEFERRED)

    def test_the_machine_asks_only_in_the_completed_stage(self):
        app = _submitted(stage='interviewing')
        sync_check2_queries(app)
        self.assertFalse(_ask(app).exists())

    def test_nothing_for_a_post_spm_or_spm_held_application(self):
        for app in (_submitted(plan=POLY), _submitted(profile=SPM_HELD)):
            sync_check2_queries(app)
            self.assertFalse(_ask(app).exists())

    def test_never_an_spm_ask(self):
        """D9 unchanged: nothing asks for an SPM slip, owed or not."""
        app = _submitted(slip=None)
        sync_check2_queries(app)
        self.assertFalse(ResolutionItem.objects.filter(
            application=app, source='check2', doc_type='results_slip').exists())

    def test_the_upload_lands_with_the_kind_and_closes_the_ask(self):
        app = _submitted()
        sync_check2_queries(app)
        self.assertEqual(results_route.upload_kind(app), 'stpm')     # the slot and kind it lands in
        doc = _doc(app, 'higher_results', STPM_SLIP, results_kind=results_route.upload_kind(app))
        resolve_doc_items_for_upload(_fresh(app), doc)                  # the Action-Centre path
        self.assertEqual(_ask(app).get().status, 'resolved')
        sync_check2_queries(_fresh(app))                                # and the sync agrees
        self.assertEqual(_ask(app).get().status, 'resolved')
        f = _academic(app)                                              # the higher card now reads it
        self.assertNotIn(higher_owed.NOTE_CODE, [i['code'] for i in f['unresolved']])
        self.assertIn('higher_results_kind_ok', [i['code'] for i in f['evidence']])

    def test_an_spm_slip_in_the_higher_card_does_not_close_it(self):
        app = _submitted()
        sync_check2_queries(app)
        doc = _doc(app, 'higher_results', {**SPM_READ, 'results_kind_detected': 'spm'},
                   results_kind='stpm')
        resolve_doc_items_for_upload(_fresh(app), doc)
        sync_check2_queries(_fresh(app))
        self.assertEqual(_ask(app).get().status, 'open')

    def test_an_unread_upload_does_not_close_it_yet(self):
        app = _submitted()
        sync_check2_queries(app)
        _doc(app, 'higher_results', None, results_kind='stpm')         # no read yet
        sync_check2_queries(_fresh(app))
        self.assertEqual(_ask(app).get().status, 'open')


class TestOneAskPerDocument(TestCase):
    """Review follow-up: the owed-higher ask is the ONE Action-Centre card for those results."""

    def _semester(self, app):
        return ResolutionItem.objects.filter(application=app, source='check2',
                                             code='semester_result_missing')

    def test_no_semester_result_ask_beside_it(self):
        """#254/#255/#265/#388 had both open — the pairing that put STPM certificates in the
        semester slot. While the higher results are owed, the semester ask is not raised."""
        app = _submitted()
        sync_check2_queries(app)
        self.assertTrue(_ask(app).filter(status='open').exists())
        self.assertFalse(self._semester(app).exists())

    def test_an_open_semester_ask_auto_resolves(self):
        app = _submitted()
        ResolutionItem.objects.create(application=app, source='check2', code='semester_result_missing',
                                      fact='academic', kind='doc', doc_type='semester_result')
        sync_check2_queries(app)
        item = self._semester(app).get()
        self.assertEqual((item.status, item.resolved_by), ('resolved', 'system'))

    def test_the_control_still_gets_its_semester_ask(self):
        """Same STPM holder on a post-SPM pathway: nothing owed, so the semester ask is unchanged."""
        app = _submitted(plan=POLY)
        sync_check2_queries(app)
        self.assertTrue(self._semester(app).filter(status='open').exists())

    def test_no_s3_unreadable_ticket_beside_the_open_ask(self):
        app = _submitted()
        sync_check2_queries(app)
        _doc(app, 'higher_results', {'candidate_name': '', 'exam': ''}, verdict='unreadable',
             results_kind='stpm')
        app = _fresh(app)
        self.assertIn('higher_results_unreadable', [i['code'] for i in _academic(app)['unresolved']])
        sync_resolution_items(app)
        self.assertFalse(ResolutionItem.objects.filter(
            application=app, source='system', doc_type='higher_results').exists())
        self.assertEqual(_ask(app).get().status, 'open')                 # the one card stays

    def test_an_open_s3_ticket_folds_into_the_ask(self):
        app = _submitted()
        sync_check2_queries(app)
        _doc(app, 'higher_results', {'candidate_name': '', 'exam': ''}, verdict='unreadable',
             results_kind='stpm')
        ResolutionItem.objects.create(application=app, source='system', code='higher_results_unreadable',
                                      fact='academic', kind='doc', doc_type='higher_results')
        sync_resolution_items(_fresh(app))
        t = ResolutionItem.objects.get(application=app, source='system', code='higher_results_unreadable')
        self.assertEqual(t.status, 'resolved')


class TestNeverRevertedByThis(TestCase):
    """The owner's hard line: no un-submit, ever. No completeness / revert / gate path reads
    `higher_owed`, and an owing application's completeness equals its non-owing twin's."""

    def test_no_gate_reads_it(self):
        app = _submitted()
        with patch.object(higher_owed, '_owed', side_effect=AssertionError('a gate read higher_owed')):
            application_completeness(_fresh(app))
            requirements.resolve(_fresh(app), 'document')
            from apps.scholarship.services import consent_blockers
            consent_blockers(_fresh(app))
            revert_if_profile_incomplete(_fresh(app))

    def test_completeness_is_the_twins(self):
        owing, twin = _submitted(), _submitted(plan=POLY)
        a, b = application_completeness(owing), application_completeness(twin)
        self.assertEqual(a, b)
        self.assertNotIn('higher_results', owing.requirements_snapshot['documents'])

    def test_a_complete_submitted_application_stays_submitted(self):
        app = _submitted()
        with patch('apps.scholarship.services.offer_sync.application_completeness',
                   return_value={'complete': True}):
            sync_check2_queries(app)
            _academic(app)
            self.assertFalse(revert_if_profile_incomplete(_fresh(app)))
        app = _fresh(app)
        self.assertEqual((app.status, app.profile_completed_at is not None), ('profile_complete', True))
        self.assertNotIn('higher_results', app.requirements_snapshot['documents'])   # snapshot untouched
