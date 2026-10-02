"""TD-114 — a NEVER-SCORED anchor document holds its fact at Probable, never Certain.

The owner's approved design (2026-06-13, `docs/scholarship/verification-genuineness-gating-plan.md`
rule 1): a fact cannot be Certain unless a genuineness check RAN and passed on its anchor document;
not-run → Probable at most. A floor, not a step — it does not stack with red chips the way a
`suspect` score does. Inert while `DOC_GENUINENESS_CHECK_ENABLED` is off.

The fixtures borrow `test_verdict_engine`'s helpers through the MODULE, never by binding its
`TestCase` classes to a name here (lessons.md, 2026-09-30: pytest would collect them twice).
"""
from django.test import override_settings

from apps.scholarship.tests import test_verdict_engine as tve

_ON = override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
_OFF = override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)


def _auth(doc, status):
    doc.vision_fields = dict(doc.vision_fields or {}, authenticity={'status': status, 'reason': 'x'})
    doc.save(update_fields=['vision_fields'])
    return doc


class UnscoredAnchorFloorTest(tve._Base):

    def _ic(self):
        return tve._add_ic(self.app, nric=self.profile.nric, name=self.profile.name)

    def _slip(self, results):
        return tve._add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found',
                            fields={'results': results})

    def _offer(self):
        return tve._add_doc(self.app, 'offer_letter', student_verdict='ok',
                            fields={'candidate_name': self.profile.name,
                                    'candidate_nric': self.profile.nric,
                                    'institution': 'KOLEJ MATRIKULASI MELAKA',
                                    'programme': 'PROGRAM MATRIKULASI'})

    # ── identity ───────────────────────────────────────────────────────────────
    @_ON
    def test_an_unscored_ic_is_probable_not_certain(self):
        self._ic()
        self.assertEqual(tve._facts(self.app)['identity']['status'], 'review')

    @_ON
    def test_a_genuine_ic_still_reads_certain(self):
        _auth(self._ic(), 'genuine')
        self.assertEqual(tve._facts(self.app)['identity']['status'], 'verified')

    @_OFF
    def test_inert_while_genuineness_checking_is_off(self):
        self._ic()
        self.assertEqual(tve._facts(self.app)['identity']['status'], 'verified')

    @_ON
    def test_an_unscored_ic_adds_no_not_genuine_caveat(self):
        # Not scored is not "suspect": nothing says the card may be fake.
        self._ic()
        codes = tve._codes(tve._facts(self.app)['identity']['unresolved'])
        self.assertNotIn('ic_low_confidence', codes)

    # ── academic ───────────────────────────────────────────────────────────────
    @_ON
    def test_an_unscored_slip_is_probable_not_certain(self):
        self.profile.grades = {'bm': 'A-'}; self.profile.save()
        self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'}])
        self.assertEqual(tve._facts(self.app)['academic']['status'], 'review')

    @_ON
    def test_the_floor_does_not_stack_with_a_red_chip(self):
        # One red Results chip on an UNSCORED slip = Probable (0 + 1, floor 1) — a `suspect`
        # slip with the same chip would be Unsure (1 + 1). The floor is not a step.
        self.profile.grades = {'bm': 'A-', 'math': 'B+'}; self.profile.save()
        self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'},
                    {'subject': 'Matematik', 'grade': 'A'}])
        self.assertEqual(tve._facts(self.app)['academic']['status'], 'review')

    @_ON
    def test_a_legacy_unknown_status_counts_as_unscored(self):
        # Any stored value that folds to no signal ('' after canonical_status) is unscored.
        self.profile.grades = {'bm': 'A-'}; self.profile.save()
        _auth(self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'}]), '')
        self.assertEqual(tve._facts(self.app)['academic']['status'], 'review')

    # ── pathway ────────────────────────────────────────────────────────────────
    @_ON
    def test_an_unscored_offer_is_probable_and_a_genuine_one_certain(self):
        offer = self._offer()
        self.assertEqual(tve._facts(self.app)['pathway']['status'], 'review')
        _auth(offer, 'genuine')
        self.assertEqual(tve._facts(self.app)['pathway']['status'], 'verified')
