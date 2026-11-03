"""Offer exact-read S6 — every DOOR the genuineness rulings and the chip table reach (sprint-start 3b):
the submission gate (`_offer_blocks`: a fail blocks, a suspect never), the Action Centre (a suspect upload
still never closes an official-offer request), the pick doors (a confirmation of studies never writes a
pick: realign, link / fill, autofill), and the Pathway chip's "set by a genuine offer" flag (chip-only:
`pathway` itself is unchanged). Synthetic records only.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.pathway_engine import (is_confirmation_letter, offer_fails, offer_official_status,
                                             student_offer_check)
from apps.scholarship.tests.factories import make_application


def _offer(app, status, doc_seen='ua_offer', **fields):
    prof = app.profile
    f = {'candidate_name': prof.name, 'candidate_nric': prof.nric, 'programme': 'DIPLOMA KEJURUTERAAN AWAM',
         'institution': 'POLITEKNIK UNGKU OMAR', **fields}
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/{status}',
        vision_fields={'fields': f, 'student_verdict': 'ok', 'warnings': [], 'error': '',
                       'authenticity': {'status': status, 'doc_seen': doc_seen, 'probability': 0.5}},
        vision_run_at=timezone.now())


class TheSubmissionGate(TestCase):
    def _blocks(self, status, **app_kw):
        from apps.scholarship.services.blockers import _offer_blocks
        app = make_application('shortlisted', **{'chosen_pathway': 'diploma', **app_kw})
        _offer(app, status)
        return _offer_blocks(app)

    def test_only_a_fail_blocks(self):                      # owner rulings 1 + 8, 2026-11-01
        self.assertTrue(self._blocks('not_offer_letter'))
        for status in ('suspect', 'genuine', 'unchecked'):
            with self.subTest(status=status):
                self.assertFalse(self._blocks(status))

    def test_the_stpm_route_is_still_exempt(self):
        self.assertFalse(self._blocks('not_offer_letter', **{'chosen_pathway': 'stpm'}))

    def test_offer_fails_reads_the_stored_status(self):
        app = make_application('shortlisted')
        self.assertTrue(offer_fails(_offer(app, 'not_offer_letter')))
        self.assertFalse(offer_fails(_offer(app, 'suspect')))


class TheActionCentre(TestCase):
    def test_a_suspect_upload_still_does_not_close_an_official_offer_request(self):
        from apps.scholarship.resolution import doc_match_verdict
        app = make_application('shortlisted')
        doc = _offer(app, 'suspect')
        self.assertEqual(offer_official_status(doc), 'not_genuine')
        self.assertEqual(doc_match_verdict(doc), 'mismatch')      # ruling 8: a reviewer may still ask


class ThePickDoors(TestCase):
    def _app(self, **cp):
        return make_application('shortlisted', chosen_pathway='diploma', chosen_programme=cp or {})

    def test_a_confirmation_letter_is_recognised(self):
        app = self._app()
        self.assertTrue(is_confirmation_letter(_offer(app, 'genuine', doc_seen='confirmation_polytechnic')))
        self.assertTrue(is_confirmation_letter(_offer(app, 'suspect', doc_seen='confirmation_ua')))
        self.assertFalse(is_confirmation_letter(_offer(app, 'genuine', doc_seen='polytechnic')))

    def test_realign_and_link_refuse_a_genuine_confirmation(self):
        from apps.scholarship.services.offer_link import plan_offer_link
        from apps.scholarship.services.offer_sync import plan_bumi_realign
        app = self._app()
        doc = _offer(app, 'genuine', doc_seen='confirmation_polytechnic')
        chk = student_offer_check(doc)
        self.assertEqual(plan_bumi_realign(app, doc, chk)[0], 'not_genuine')
        self.assertEqual(plan_offer_link(app, doc, chk)[0], 'confirmation_letter')

    def test_autofill_never_adopts_a_confirmation(self):
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer
        app = self._app()
        _offer(app, 'genuine', doc_seen='confirmation_polytechnic')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
        self.assertFalse((cp.get('course_name') or '').strip())


class ThePathwayChipFlag(TestCase):
    """The owner's table: green when she declared nothing and a GENUINE offer set the pick itself."""

    def _app(self, **kw):
        cp = {'source': 'offer_letter_auto', 'course_name': 'Diploma Kejuruteraan Awam',
              'institution': 'Politeknik Ungku Omar'}
        return make_application('shortlisted', chosen_programme=cp, pre_u_institution='', pre_u_track='', **kw)

    def test_set_by_a_genuine_offer_on_an_empty_declaration(self):
        app = self._app()
        chk = student_offer_check(_offer(app, 'genuine', doc_seen='polytechnic'))
        self.assertTrue(chk['pathway_set_by_offer'])
        self.assertNotEqual(chk['pathway'], 'mismatch')            # `pathway` itself is not touched

    def test_not_for_a_suspect_offer(self):
        app = self._app()
        self.assertFalse(student_offer_check(_offer(app, 'suspect'))['pathway_set_by_offer'])

    def test_not_when_she_declared_a_school(self):
        app = self._app()
        app.pre_u_institution = 'SMK Contoh'
        app.save(update_fields=['pre_u_institution'])
        self.assertFalse(student_offer_check(_offer(app, 'genuine', doc_seen='polytechnic'))['pathway_set_by_offer'])

    def test_not_when_the_pick_names_another_course(self):
        app = self._app()
        doc = _offer(app, 'genuine', doc_seen='polytechnic', programme='DIPLOMA AKAUNTANSI',
                     institution='POLITEKNIK SULTAN SALAHUDDIN')
        self.assertFalse(student_offer_check(doc)['pathway_set_by_offer'])

    def test_not_for_a_student_pick(self):
        app = make_application('shortlisted', chosen_programme={'course_name': 'Diploma Kejuruteraan Awam'})
        self.assertFalse(student_offer_check(_offer(app, 'genuine', doc_seen='polytechnic'))['pathway_set_by_offer'])
