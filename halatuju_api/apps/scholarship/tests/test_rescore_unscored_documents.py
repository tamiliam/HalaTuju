"""TD-114 (b) — `rescore_unscored_documents`: counts never-scored anchor documents and scores, from
stored text and with no paid call, only what the live scorer would answer the same way.

All text here is SYNTHETIC, assembled from the signature lists themselves (lessons.md, 2026-10-01:
a committed test reads only what is committed).
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.scholarship.genuineness import results_doc, signature_genuineness
from apps.scholarship.management.commands import rescore_unscored_documents as cmd
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application


def _text_of(signatures):
    """One line per TEXT signature (its first pattern) — visual ones cannot be typed."""
    return '\n'.join(p[0] for _, p, _, kind in signatures if kind != 'visual')


def _slip_text_needing_the_visuals():
    """A synthetic slip whose text-only score changes band when QR + crest are credited."""
    sigs = [s for s in results_doc._LISTS['results_slip'] if s[3] != 'visual']
    for n in range(1, len(sigs) + 1):
        text = _text_of(sigs[:n])
        if (signature_genuineness(text)['status']
                != signature_genuineness(text, has_qr=True, has_crest=True)['status']):
            return text
    raise AssertionError('no prefix of the slip signatures depends on the visuals')


class RescoreUnscoredDocumentsTest(TestCase):
    def setUp(self):
        self.app = make_application('submitted')

    def _doc(self, doc_type, text='', auth=None):
        vf = {}
        if text:
            vf['text'] = text
        if auth:
            vf['authenticity'] = {'status': auth}
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'x/{doc_type}/{len(text)}',
            vision_fields=vf)

    def _run(self, *args):
        out = StringIO()
        call_command('rescore_unscored_documents', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_counts_and_writes_nothing(self):
        slip = self._doc('results_slip', _text_of(results_doc._LISTS['results_slip']))
        self._doc('ic')
        self._doc('offer_letter')
        out = self._run()
        self.assertIn('DRY-RUN', out)
        self.assertIn('results_slip: unscored=1 unscored_latest=1 scored=1', out)
        self.assertIn('ic: unscored=1 unscored_latest=1 scored=0 paid_read=1', out)
        self.assertIn('offer_letter: unscored=1 unscored_latest=1 scored=0 paid_read=0 no_stored_text=1', out)
        slip.refresh_from_db()
        self.assertNotIn('authenticity', slip.vision_fields)

    def test_apply_scores_a_slip_whose_band_the_visuals_cannot_move(self):
        slip = self._doc('results_slip', _text_of(results_doc._LISTS['results_slip']))
        self._run('--apply')
        slip.refresh_from_db()
        auth = slip.vision_fields['authenticity']
        self.assertEqual(auth['status'], 'genuine')
        self.assertEqual(auth['rescored']['basis'], 'text_only_visuals_unread')
        self.assertEqual(auth['model_version'], results_doc.MODEL_VERSION)

    def test_a_slip_the_visual_read_could_change_is_left_alone(self):
        slip = self._doc('results_slip', _slip_text_needing_the_visuals())
        out = self._run('--apply')
        self.assertIn('indeterminate=1', out)
        slip.refresh_from_db()
        self.assertNotIn('authenticity', slip.vision_fields)

    def test_an_offer_is_scored_from_text_exactly_as_the_live_path(self):
        fam = results_doc._FAMILIES['offer_letter']['matriculation']
        text = _text_of(fam)
        offer = self._doc('offer_letter', text)
        self._run('--apply')
        offer.refresh_from_db()
        live = signature_genuineness(text, doc_type='offer_letter')
        self.assertEqual(offer.vision_fields['authenticity']['status'], live['status'])
        self.assertEqual(offer.vision_fields['authenticity']['rescored']['basis'], 'text')

    def test_counts_the_latest_per_application_and_type_beside_every_live_row(self):
        # Review F4c: the verdict reads the LATEST live document per type (`latest_doc`), so the
        # number of facts that lose Certain is the latest-per-(application, type) count.
        from datetime import timedelta
        from django.utils import timezone
        old = self._doc('offer_letter')                    # unscored, older
        ApplicantDocument.objects.filter(id=old.id).update(
            uploaded_at=timezone.now() - timedelta(days=2))
        self._doc('offer_letter', 'x')                     # unscored, newest → the one read
        o2 = self._doc('ic')                                # unscored, older
        ApplicantDocument.objects.filter(id=o2.id).update(
            uploaded_at=timezone.now() - timedelta(days=2))
        self._doc('ic', 'y', auth='genuine')               # newest IC is scored
        out = self._run()
        self.assertIn('offer_letter: unscored=2 unscored_latest=1', out)
        self.assertIn('ic: unscored=1 unscored_latest=0', out)

    def test_never_touches_an_ic_a_scored_doc_or_a_superseded_one(self):
        ic = self._doc('ic', 'KAD PENGENALAN MALAYSIA')
        scored = self._doc('results_slip', 'whatever', auth='suspect')
        from django.utils import timezone
        old = self._doc('offer_letter', 'old text')
        old.superseded_at = timezone.now()
        old.save(update_fields=['superseded_at'])
        with patch.object(cmd, 'score_from_text', wraps=cmd.score_from_text) as spy:
            out = self._run('--apply')
        spy.assert_not_called()
        self.assertIn('ic: unscored=1 unscored_latest=1 scored=0 paid_read=1', out)
        self.assertIn('results_slip: unscored=0', out)
        self.assertIn('offer_letter: unscored=0', out)
        ic.refresh_from_db(); scored.refresh_from_db()
        self.assertNotIn('authenticity', ic.vision_fields)
        self.assertEqual(scored.vision_fields['authenticity'], {'status': 'suspect'})
