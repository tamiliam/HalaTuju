"""H3b - an OLD offer / confirmation letter asks for a RECENT confirmation letter (soft).

Pins: the window edge (exactly N months ago is still recent; one day more is old), an unreadable date
(no ask - never guess), ANY recent letter already on file (no ask: offer or confirmation, any
institution, live or kept out of the live slot), no ask before the course should have started, the
organisation tunable, a failing letter (left to its own ask), the upload resolution (a recent letter
closes it, an old letter re-sent leaves it open), the one document read for both letter asks, and that
the ask NEVER blocks: no submission blocker, no verdict change, no status change, no assignment hold.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.courses import org_config
from apps.courses.org_config_registry import SETTINGS as REGISTRY
from apps.scholarship import recent_letter
from apps.scholarship.check2_queries import DOC_SPECS, GOVERNED_BY, sync_check2_queries
from apps.scholarship.tests.factories import create_document, make_application
from apps.scholarship.tests.test_org_config import _configure

TODAY = datetime.date(2026, 6, 30)
CODE = recent_letter.CODE


def _iso(d):
    return d.strftime('%d/%m/%Y')


class _Base(TestCase):
    def _app(self, suffix='1', **kw):
        """A Completed-stage application (Check 2 may ask). ``suffix`` only labels the call site."""
        defaults = dict(chosen_pathway='diploma', father_occupation='gov',
                        mother_occupation='homemaker', siblings_in_tertiary=0)
        defaults.update(kw)
        return make_application('profile_complete', **defaults)

    def _letter(self, app, offer_date, *, seen='ua_offer', status='genuine', **kw):
        fields = {'candidate_name': app.profile.name, 'programme': 'DIPLOMA KEJURUTERAAN AWAM',
                  'institution': 'POLITEKNIK UNGKU OMAR'}
        if offer_date is not None:
            fields['offer_date'] = offer_date
        return create_document(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/{offer_date}',
            vision_fields={'fields': fields, 'student_verdict': 'ok', 'warnings': [], 'error': '',
                           'authenticity': {'status': status, 'doc_seen': seen, 'probability': 0.9}},
            vision_run_at=timezone.now(), **kw)


class TestLetterDate(TestCase):
    """The strict reader: one exact date, or None."""

    def _read(self, raw):
        return recent_letter.letter_date(type('D', (), {'vision_fields': {'fields': {'offer_date': raw}}})())

    def test_readable_forms(self):
        want = datetime.date(2026, 3, 5)
        for raw in ('05/03/2026', '5.3.2026', '5-3-2026', '2026-03-05', '5 Mac 2026', '5th March 2026',
                    'March 5, 2026', '05 MAC 2026', '5hb Mac 2026'):
            self.assertEqual(self._read(raw), want, raw)
        self.assertEqual(self._read('1 January 2026'), datetime.date(2026, 1, 1))

    def test_unreadable_is_none(self):
        for raw in (None, '', 'Mac 2026', '2026', '5/3/26', '31/02/2026', 'sometime in March',
                    '5 Mac 2026 dan 6 Mac 2026', '5 Smarch 2026', 20260305, '13/13/2026'):
            self.assertIsNone(self._read(raw), raw)

    def test_no_fields_is_none(self):
        for vf in (None, {}, {'fields': None}, 'junk'):
            doc = type('D', (), {'vision_fields': vf})()
            self.assertIsNone(recent_letter.letter_date(doc))


class TestCutoff(TestCase):
    def test_plain_and_clamped(self):
        self.assertEqual(recent_letter.cutoff(TODAY, 3), datetime.date(2026, 3, 30))
        self.assertEqual(recent_letter.cutoff(datetime.date(2026, 5, 31), 3), datetime.date(2026, 2, 28))
        self.assertEqual(recent_letter.cutoff(datetime.date(2026, 2, 15), 3), datetime.date(2025, 11, 15))
        self.assertEqual(recent_letter.cutoff(datetime.date(2026, 1, 10), 12), datetime.date(2025, 1, 10))


class TestWanted(_Base):
    def test_exactly_three_months_is_recent(self):
        app = self._app('edge')
        self._letter(app, _iso(datetime.date(2026, 3, 30)))
        self.assertFalse(recent_letter.wanted(app, today=TODAY))

    def test_three_months_and_a_day_is_old(self):
        app = self._app('edge1')
        self._letter(app, _iso(datetime.date(2026, 3, 29)))
        self.assertTrue(recent_letter.wanted(app, today=TODAY))

    def test_confirmation_letter_old_is_also_asked(self):
        app = self._app('conf-old')
        self._letter(app, '1 Januari 2026', seen='confirmation_polytechnic')
        self.assertTrue(recent_letter.wanted(app, today=TODAY))

    def test_unreadable_date_never_asks(self):
        for i, raw in enumerate((None, 'Januari 2025', '1/1/25', 'tarikh tidak jelas')):
            app = self._app(f'unread{i}')
            self._letter(app, raw)
            self.assertFalse(recent_letter.wanted(app, today=TODAY), raw)

    def test_no_letter_never_asks(self):
        self.assertFalse(recent_letter.wanted(self._app('none'), today=TODAY))

    def test_failing_letter_is_left_to_its_own_ask(self):
        app = self._app('fail')
        self._letter(app, '1 Januari 2025', status='not_offer_letter')
        self.assertFalse(recent_letter.wanted(app, today=TODAY))

    def test_superseded_old_letter_is_not_the_live_one(self):
        app = self._app('sup')
        self._letter(app, '1 Januari 2025', superseded_at=timezone.now())
        self._letter(app, '1 Jun 2026')
        self.assertFalse(recent_letter.wanted(app, today=TODAY))

    def test_recent_confirmation_kept_out_of_the_live_slot_still_answers(self):
        """The keep-better promotion can keep an official OFFER live and her new confirmation letter
        out of the slot (superseded). She did what was asked: no loop."""
        app = self._app('kept')
        self._letter(app, '1 Jun 2026', seen='confirmation_polytechnic', superseded_at=timezone.now())
        self._letter(app, '1 Januari 2025')
        self.assertFalse(recent_letter.wanted(app, today=TODAY))

    def test_recent_confirmation_on_file_live_answers(self):
        app = self._app('live-conf')
        self._letter(app, '1 Januari 2025')
        self._letter(app, '20 Jun 2026', seen='confirmation_polytechnic')   # its own slot, both live
        self.assertFalse(recent_letter.wanted(app, today=TODAY))

    def test_old_or_failing_or_undated_confirmation_does_not_answer(self):
        app = self._app('bad-conf')
        self._letter(app, '1 Januari 2025')
        self._letter(app, '1 Januari 2026', seen='confirmation_polytechnic', superseded_at=timezone.now())
        self._letter(app, '1 Jun 2026', seen='confirmation_polytechnic', status='not_offer_letter',
                     superseded_at=timezone.now())
        self._letter(app, 'Jun 2026', seen='confirmation_polytechnic', superseded_at=timezone.now())
        self.assertTrue(recent_letter.wanted(app, today=TODAY))

    def test_a_university_confirmation_scored_suspect_answers(self):
        """Fix round 1: ANY recent letter closes it, whatever institution - a university's "Surat
        Pengesahan Pelajar" scored suspect, live or kept out of the slot."""
        for i, kept_out in enumerate((False, True)):
            app = self._app(f'ua-conf{i}')
            if kept_out:
                self._letter(app, '20 Jun 2026', seen='ua_offer', status='suspect', superseded_at=timezone.now())
                self._letter(app, '1 Januari 2025')
            else:
                self._letter(app, '1 Januari 2025', superseded_at=timezone.now())
                self._letter(app, '20 Jun 2026', seen='ua_offer', status='suspect')
            self.assertFalse(recent_letter.wanted(app, today=TODAY), kept_out)

    def test_a_matriculation_confirmation_answers(self):
        app = self._app('matric-conf')
        self._letter(app, '20 Jun 2026', seen='matriculation', status='suspect', superseded_at=timezone.now())
        self._letter(app, '1 Januari 2025', seen='matriculation')
        self.assertFalse(recent_letter.wanted(app, today=TODAY))

    def test_a_recent_offer_kept_out_of_the_slot_answers(self):
        """The old TD-634: a recent official OFFER kept out of the live slot now answers too."""
        app = self._app('kept-offer')
        self._letter(app, '20 Jun 2026', status='unknown', superseded_at=timezone.now())
        self._letter(app, '1 Januari 2025')
        self.assertFalse(recent_letter.wanted(app, today=TODAY))


class TestCourseStart(_Base):
    """Fix round 1: no ask before the course should have started - an offer is naturally old then."""

    def _with_report(self, label, reporting_date):
        app = self._app(label)
        doc = self._letter(app, '1 Januari 2026')                    # old against TODAY (30 Jun 2026)
        doc.vision_fields['fields']['reporting_date'] = reporting_date
        doc.save(update_fields=['vision_fields'])
        return app

    def test_a_reporting_date_still_to_come_never_asks(self):
        for i, rd in enumerate(('8 JULAI 2026', '30 JUN 2026', '8 HINGGA 9 OGOS 2026', '1 Jan 2027')):
            self.assertFalse(recent_letter.wanted(self._with_report(f'future{i}', rd), today=TODAY), rd)

    def test_a_reporting_date_in_the_past_asks(self):
        for i, rd in enumerate(('29 JUN 2026', '10 Februari 2026 (Isnin)', '28 JULAI 2025 2:30 PETANG')):
            self.assertTrue(recent_letter.wanted(self._with_report(f'past{i}', rd), today=TODAY), rd)

    def test_a_reporting_date_not_read_to_a_day(self):
        """Might it still be to come? Then no ask. Only a year before this one is surely past."""
        for i, rd in enumerate(('JUN 2026', 'Sesi 2026/2027', 'akan dimaklumkan', 'MINGGU PERTAMA')):
            self.assertFalse(recent_letter.wanted(self._with_report(f'unknown{i}', rd), today=TODAY), rd)
        for i, rd in enumerate(('SEPT 2025', 'Sesi 2024/2025')):
            self.assertTrue(recent_letter.wanted(self._with_report(f'pastyr{i}', rd), today=TODAY), rd)

    def test_no_reporting_date_keeps_the_plain_rule(self):
        for i, rd in enumerate(('', '   ')):
            self.assertTrue(recent_letter.wanted(self._with_report(f'none{i}', rd), today=TODAY), repr(rd))


class TestTunable(_Base):
    def test_registry_spec_and_default(self):
        spec = REGISTRY[recent_letter.WINDOW_KEY]
        self.assertEqual((spec['group'], spec['unit'], spec['min'], spec['max']), ('check2', 'months', 1, 12))
        self.assertEqual(org_config.default(recent_letter.WINDOW_KEY), 3)
        self.assertEqual(recent_letter.window_months(self._app('unchanged')), 3)

    def test_the_organisation_window_moves_the_edge(self):
        app = self._app('org')
        org = app.owning_organisation
        self.assertIsNotNone(org)
        self._letter(app, _iso(datetime.date(2026, 2, 1)))          # five months old
        self.assertTrue(recent_letter.wanted(app, today=TODAY))
        _configure(org, recent_letter.WINDOW_KEY, 6)
        app.refresh_from_db()
        self.assertEqual(recent_letter.window_months(app), 6)
        self.assertFalse(recent_letter.wanted(app, today=TODAY))
        _configure(org, recent_letter.WINDOW_KEY, 1)
        other = self._app('org2', cohort=app.cohort)
        self._letter(other, _iso(datetime.date(2026, 5, 29)))      # one month and a day
        self.assertTrue(recent_letter.wanted(other, today=TODAY))


class TestCheck2(_Base):
    """Integration: `sync_check2_queries` reads the REAL clock, so dates are relative to today."""

    def _old(self):
        return _iso(recent_letter.cutoff(timezone.localdate(), 3) - datetime.timedelta(days=1))

    def _codes(self, app):
        return {r.code: r for r in app.resolution_items.filter(source='check2', status='open')}

    def test_classified_core_doc_request(self):
        self.assertEqual(DOC_SPECS[CODE]['doc_type'], 'offer_letter')
        self.assertIsNone(GOVERNED_BY[CODE])

    def test_old_letter_raises_one_doc_request(self):
        app = self._app('sync')
        self._letter(app, self._old())
        sync_check2_queries(app)
        items = self._codes(app)
        self.assertIn(CODE, items)
        self.assertEqual((items[CODE].kind, items[CODE].doc_type), ('doc', 'offer_letter'))
        sync_check2_queries(app)
        self.assertEqual(app.resolution_items.filter(code=CODE).count(), 1)

    def test_recent_letter_raises_nothing(self):
        app = self._app('sync-recent')
        self._letter(app, _iso(timezone.localdate()))
        sync_check2_queries(app)
        self.assertNotIn(CODE, self._codes(app))

    def test_resolves_when_a_recent_confirmation_arrives(self):
        app = self._app('sync-res')
        old = self._letter(app, self._old())
        sync_check2_queries(app)
        self.assertIn(CODE, self._codes(app))
        old.superseded_at = timezone.now()
        old.save(update_fields=['superseded_at'])
        self._letter(app, _iso(timezone.localdate()), seen='confirmation_polytechnic')
        sync_check2_queries(app)
        self.assertNotIn(CODE, self._codes(app))

    def test_an_old_letter_re_sent_leaves_the_ask_open(self):
        from apps.scholarship.resolution import doc_match_verdict, resolve_doc_items_for_upload
        app = self._app('upload')
        old = self._letter(app, self._old())
        sync_check2_queries(app)
        self.assertEqual(doc_match_verdict(old), 'ok')
        resolve_doc_items_for_upload(app, old)
        self.assertIn(CODE, self._codes(app))

    def test_an_upload_closes_the_ask(self):
        """A recent letter uploaded in answer closes it through ``resolve_doc_items_for_upload``."""
        from apps.scholarship.resolution import resolve_doc_items_for_upload
        app = self._app('upload-close')
        self._letter(app, self._old(), superseded_at=timezone.now())
        new = self._letter(app, _iso(timezone.localdate()), seen='confirmation_polytechnic')
        app.resolution_items.create(source='check2', code=CODE, kind='doc', doc_type='offer_letter',
                                    fact='pathway', status='open')
        self.assertEqual(resolve_doc_items_for_upload(app, new), 'ok')
        self.assertNotIn(CODE, self._codes(app))

    def test_a_suspect_upload_closes_it_at_the_next_sync(self):
        """A suspect letter (a university confirmation) reads 'mismatch' on upload - the offer slot's own
        rule, unchanged - so it closes the ask at the next Check-2 sync (her next Action Centre read)."""
        from apps.scholarship.resolution import resolve_doc_items_for_upload
        app = self._app('upload-suspect')
        self._letter(app, self._old())
        sync_check2_queries(app)
        self.assertIn(CODE, self._codes(app))
        new = self._letter(app, _iso(timezone.localdate()), seen='ua_offer', status='suspect',
                           superseded_at=timezone.now())        # kept out: the genuine offer outranks it
        self.assertEqual(resolve_doc_items_for_upload(app, new), 'mismatch')
        self.assertIn(CODE, self._codes(app))
        sync_check2_queries(app)
        self.assertNotIn(CODE, self._codes(app))

    def test_the_ask_never_blocks(self):
        """No submission blocker, no verdict change, no status change: the ask is a request only."""
        from apps.scholarship.services import blockers
        from apps.scholarship.verdict_engine import build_verdict
        app = self._app('soft')
        self._letter(app, self._old())

        def snapshot():
            app.refresh_from_db()
            return (build_verdict(app), blockers._offer_blocks(app), blockers.document_red_blockers(app),
                    blockers.document_unreadable_blockers(app), app.status)

        before = snapshot()
        sync_check2_queries(app)
        self.assertIn(CODE, self._codes(app))
        after = snapshot()
        self.assertEqual(before, after)
        self.assertNotIn(CODE, repr(after))


class TestOfferAsks(_Base):
    """The Check-2 pass reads the documents ONCE for both letter asks (TD-308 budget) by calling the
    money module's own ``offer_reporting_date_unknown`` and ``wanted`` under one document snapshot.
    ON == OFF: the pair answers exactly as the two calls do with no snapshot."""

    def test_the_pair_equals_the_two_calls_without_a_snapshot(self):
        from apps.scholarship import pathway_engine
        cases = [None, {'fields': {'reporting_date': '8 JUN 2026'}, 'student_verdict': 'ok'},
                 {'fields': {'reporting_date': ''}, 'student_verdict': 'ok'},
                 {'fields': {'reporting_date': ''}}, {'fields': {'reporting_date': ''},
                                                       'student_verdict': 'review_manually'},
                 {'fields': {'reporting_date': 'sometime', 'offer_date': '1 Januari 2025'},
                  'student_verdict': 'ok'},
                 {'fields': {'offer_date': '1 Januari 2025'}, 'student_verdict': 'ok'}, 'junk']
        for i, vf in enumerate(cases):
            app = self._app(f'pair{i}')
            if vf is not None:
                create_document(application=app, doc_type='offer_letter', storage_path=f'd/{i}',
                                vision_fields=vf)
            self.assertEqual(recent_letter.offer_asks(app),
                             (pathway_engine.offer_reporting_date_unknown(app), recent_letter.wanted(app)), vf)

    def test_no_letter_costs_one_read(self):
        app = self._app('one-read')
        with self.assertNumQueries(1):
            self.assertEqual(recent_letter.offer_asks(app), (False, False))


class TestAssignmentHold(_Base):
    """Lead's decision (fix round 1): the ask is NON-HOLDING - it never holds reviewer assignment;
    any other open student request still does."""

    def _fresh(self, label):
        app = self._app(label)
        app.profile_completed_at = timezone.now()          # inside the answer window
        app.save(update_fields=['profile_completed_at'])
        return app

    def _ready(self, app):
        from apps.scholarship.models import ScholarshipApplication
        from apps.scholarship.services.queries_sla import is_ready_for_assignment, with_open_student_tasks
        annotated = with_open_student_tasks(ScholarshipApplication.objects.filter(pk=app.pk)).get()
        return is_ready_for_assignment(app), is_ready_for_assignment(annotated)

    def test_the_excluded_code_is_this_one(self):
        from apps.scholarship.services import queries_sla
        self.assertEqual(queries_sla._NON_HOLDING_CODES, (CODE,))

    def test_an_open_recent_letter_ask_alone_does_not_hold(self):
        app = self._fresh('hold-alone')
        self._letter(app, _iso(recent_letter.cutoff(timezone.localdate(), 3) - datetime.timedelta(days=1)))
        sync_check2_queries(app)
        self.assertTrue(app.resolution_items.filter(code=CODE, status='open').exists())
        app.resolution_items.exclude(code=CODE).delete()     # only the recent-letter ask is left open
        self.assertEqual(self._ready(app), (True, True))

    def test_another_open_request_still_holds(self):
        from apps.scholarship.models import ResolutionItem
        app = self._fresh('hold-other')
        ResolutionItem.objects.create(application=app, source='check2', code=CODE, kind='doc',
                                      doc_type='offer_letter', fact='pathway', status='open')
        ResolutionItem.objects.create(application=app, source='officer', code='officer_1', kind='clarify',
                                      fact='other', status='open')
        self.assertEqual(self._ready(app), (False, False))
