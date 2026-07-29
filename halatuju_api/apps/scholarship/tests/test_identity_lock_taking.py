"""Taking the IC lock — the branch that actually WRITES it (2026-07-29).

`test_identity_lock.py` covers the rule as a pure decision. This covers the half that touches
the database: `_lock_nric_if_confirmed` runs at the end of every IC read, so the first upload,
the cockpit's Re-run and the bulk re-extract all take the lock at the same moment.

Written because the rule alone is not the feature. The Layer 0 lesson from the day before:
5018 tests passed while a resolver returned "requires nothing", because no fixture exercised
the branch that had just been written. A predicate that returns True is worth nothing if
nothing stores the answer.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.vision import _lock_nric_if_confirmed

CARD = 'THARANI A/P A.UDAYA KUMAR'
NRIC = '080722-14-1140'


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c-lock', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'lock-{self.id()}', name=CARD, nric=NRIC,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
        )

    def _ic(self, *, name=CARD, nric=NRIC, status='genuine', doc_type='ic'):
        vf = {'authenticity': {'status': status}} if status else {}
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'{self.app.id}/{doc_type}/x',
            vision_name=name, vision_nric=nric, vision_run_at=timezone.now(),
            vision_error='', vision_fields=vf,
        )

    def _locked(self):
        self.profile.refresh_from_db()
        return self.profile.nric_verified


class TestTakingTheLock(_Base):
    def test_a_confirming_card_locks_and_the_lock_persists(self):
        self.assertFalse(self._locked())
        _lock_nric_if_confirmed(self._ic())
        self.assertTrue(self._locked())

    def test_an_unscored_card_leaves_it_open(self):
        """The (b) decision: 36 production students sit here until their card is re-scored."""
        _lock_nric_if_confirmed(self._ic(status=None))
        self.assertFalse(self._locked())

    def test_a_wrong_digit_leaves_it_open(self):
        self.profile.nric = '080722-11-1140'      # #106's actual defect
        self.profile.save(update_fields=['nric'])
        _lock_nric_if_confirmed(self._ic())
        self.assertFalse(self._locked())

    def test_a_parents_card_never_locks_the_students_number(self):
        """`run_vision_for_document` serves parent_ic too — a guardian's card must not lock
        the student. The parent's own name and number are on that card, so without the
        doc_type guard this would lock the student's record to their parent's identity."""
        _lock_nric_if_confirmed(
            self._ic(name='A.UDAYA KUMAR A/L ANDIAPPAN', nric='720709-10-5105',
                     doc_type='parent_ic'))
        self.assertFalse(self._locked())
        # …and the student's own card, same call, still does.
        _lock_nric_if_confirmed(self._ic())
        self.assertTrue(self._locked())

    def test_it_never_unlocks(self):
        """One-way. A later bad read must not undo a lock already taken — this is the whole
        reason the lock is stored rather than derived."""
        _lock_nric_if_confirmed(self._ic())
        self.assertTrue(self._locked())
        _lock_nric_if_confirmed(self._ic(name='SOMEBODY ELSE', nric='990101-05-1234'))
        self.assertTrue(self._locked())

    def test_a_clash_with_an_already_verified_holder_is_declined_not_raised(self):
        """Locking arms the partial unique index. Another verified holder of the same number
        would make the save raise — and the student would lose their upload over somebody
        else's duplicate. Leave it open for verify-&-accept to surface as `nric_conflict`."""
        StudentProfile.objects.create(
            supabase_user_id='other-holder', name='SOMEONE ELSE', nric=NRIC, nric_verified=True,
        )
        _lock_nric_if_confirmed(self._ic())        # must not raise
        self.assertFalse(self._locked())

    def test_a_document_with_no_application_is_ignored(self):
        orphan = ApplicantDocument(doc_type='ic', vision_name=CARD, vision_nric=NRIC)
        _lock_nric_if_confirmed(orphan)            # must not raise
        self.assertFalse(self._locked())
