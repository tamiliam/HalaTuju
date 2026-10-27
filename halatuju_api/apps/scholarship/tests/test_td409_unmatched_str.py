"""TD-409 — an STR no household card matched never closes an STR request (owner ruling A).

`doc_match_verdict` answers 'pending' for an STR that read but matched no card and is not provably a
stranger's (a near-miss name, or a recipient nothing could be compared with). The upload then HOLDS
every open STR request it answers for the officer (`needs_officer_eye`, the "our team is checking"
card) and answers 'ok'; the two syncs hold, rather than close, an STR request whose gap cleared while
that STR is live. After submission Check 2 asks for a near-miss STR's IC-number page.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

STUDENT, STUDENT_NRIC = 'Tan Mei Hua', '080808-14-5566'


def _doc(app, doc_type, **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    return ApplicantDocument.objects.create(application=app, doc_type=doc_type, **kw)


class _STRCase(TestCase):
    """STR route, the father the earner; both parents' cards on file and read; submitted."""

    def _app(self, cards=True):
        app = make_application(
            'profile_complete', income_route='str', income_earner='father', income_working_members=[],
            father_name='Tan Ah Kau', mother_name='Lim Mei Ling', father_occupation='private',
            mother_occupation='homemaker', other_family_members=[],
            student=make_student(name=STUDENT, nric=STUDENT_NRIC))
        if cards:
            for member, name, nric in (('father', 'TAN AH KAU', '700707-13-5671'),
                                       ('mother', 'LIM MEI LING', '720808-13-5682')):
                _doc(app, 'parent_ic', household_member=member, vision_run_at=timezone.now(),
                     vision_name=name, vision_nric=nric)
        return app

    def _str(self, app, name, nric='', **kw):
        return _doc(app, 'str', vision_fields={
            'fields': {'recipient_name': name, 'recipient_nric': nric, 'status': 'Lulus', 'year': '2026',
                       'source_type': 'semakan_status'}, 'student_verdict': 'ok', 'error': ''}, **kw)


class TheVerdict(_STRCase):

    def test_an_str_no_card_matched_is_pending_never_ok(self):
        from apps.scholarship.resolution import doc_match_verdict
        for label, cards, name in (('near-miss', True, 'TAN AH KOW'), ('no card on file', False, 'TAN AH KAU')):
            with self.subTest(label):
                self.assertEqual(doc_match_verdict(self._str(self._app(cards=cards), name)), 'pending')

    def test_the_familys_own_str_is_still_ok_and_a_strangers_still_a_mismatch(self):
        from apps.scholarship.resolution import doc_match_verdict
        self.assertEqual(doc_match_verdict(self._str(self._app(), 'TAN AH KAU')), 'ok')
        self.assertEqual(doc_match_verdict(self._str(self._app(), 'TAN AH MENG')), 'mismatch')


class TheUpload(_STRCase):

    def _requests(self, app):
        """A system STR ask (raised while no STR was on file) and an officer's STR request."""
        from apps.scholarship.resolution import add_officer_item, sync_resolution_items
        sync_resolution_items(app)
        system = app.resolution_items.get(source='system', code='income_proof_missing')
        officer = add_officer_item(app, kind='doc', prompt='Upload your STR', admin_email='o@x.org',
                                   doc_type='str', fact='income')
        return system, officer

    def _upload(self, app, name):
        from apps.scholarship.resolution import resolve_doc_items_for_upload, sync_resolution_items
        doc = self._str(app, name)
        sync_resolution_items(app)                       # the upload view's order
        return resolve_doc_items_for_upload(app, doc)

    def test_an_unmatched_str_holds_both_requests_for_the_officer(self):
        app = self._app()
        system, officer = self._requests(app)
        self.assertEqual(self._upload(app, 'TAN AH KOW'), 'ok')       # never "still checking — refresh"
        for item in (system, officer):
            item.refresh_from_db()
            with self.subTest(item.source):
                self.assertEqual(item.status, 'open')
                self.assertIs(item.params.get('needs_officer_eye'), True)

    def test_the_familys_own_str_closes_both(self):
        app = self._app()
        system, officer = self._requests(app)
        self.assertEqual(self._upload(app, 'TAN AH KAU'), 'ok')
        for item in (system, officer):
            item.refresh_from_db()
            with self.subTest(item.source):
                self.assertEqual(item.status, 'resolved')
                self.assertNotIn('needs_officer_eye', item.params)


class ThePromotion(_STRCase):
    """'pending' is usable, so the slot guard keeps an unmatched STR from burying a matched one."""

    def test_an_unmatched_str_never_displaces_a_matched_one(self):
        from apps.scholarship.promotion import should_promote
        app = self._app()
        live = self._str(app, 'TAN AH KAU')
        self.assertIs(should_promote(self._str(app, 'TAN AH KOW'), live, usable=True), False)

    def test_a_matched_str_still_displaces_an_unmatched_one(self):
        from apps.scholarship.promotion import should_promote
        app = self._app()
        live = self._str(app, 'TAN AH KOW')
        self.assertIs(should_promote(self._str(app, 'TAN AH KAU'), live, usable=True), True)


class AStrangersSTR(_STRCase):

    _requests, _upload = TheUpload._requests, TheUpload._upload

    def test_is_a_mismatch_and_holds_nothing_for_the_officer(self):
        """Unchanged: the student is told it is not the family's; the str_recipient_mismatch ask takes over."""
        app = self._app()
        system, officer = self._requests(app)
        self.assertEqual(self._upload(app, 'TAN AH MENG'), 'mismatch')
        for item in (system, officer):
            item.refresh_from_db()
            self.assertNotIn('needs_officer_eye', item.params)
        officer.refresh_from_db()
        self.assertEqual(officer.status, 'open')


class CheckTwo(_STRCase):

    def _ask(self, app):
        from apps.scholarship.check2_queries import sync_check2_queries
        sync_check2_queries(app)
        return app.resolution_items.filter(source='check2', code='str_needs_recipient_ic').first()

    def test_a_near_miss_str_is_asked_for_its_ic_number_page(self):
        app = self._app()
        self._str(app, 'TAN AH KOW')
        item = self._ask(app)
        self.assertIsNotNone(item)
        self.assertEqual((item.status, item.doc_type), ('open', 'str'))

    def test_the_familys_own_str_is_not_asked(self):
        app = self._app()
        self._str(app, 'TAN AH KAU')
        self.assertIsNone(self._ask(app))

    def test_the_ask_closes_on_the_page_that_matches(self):
        app = self._app()
        near = self._str(app, 'TAN AH KOW')
        item = self._ask(app)
        near.delete()
        self._str(app, 'TAN AH KOW', nric='700707-13-5671')           # the IC-number page: the father's
        self._ask(app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')

    def test_the_ask_is_held_not_closed_while_a_still_unmatched_str_is_live(self):
        """The near-miss is gone, but the STR now on file matched nobody either: ruling A."""
        app = self._app()
        near = self._str(app, 'TAN AH KOW')
        item = self._ask(app)
        near.delete()
        self._str(app, 'TAN AH KOW', nric='650303-07-5123')
        app.documents.filter(doc_type='parent_ic').update(vision_nric='')  # no card's number to compare
        self._ask(app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')
        self.assertIs(item.params.get('needs_officer_eye'), True)
