"""Request #67 scope 3 (2026-11-14): one name — align it to the IC, lock it, and the 559 short read.

The owner's decisions D1-D6 (docs/plans/req67-scope3-ic-name-alignment-brief.md):

* D1/D2 — the name read off the student's OWN MyKad becomes ``profile.name`` when that is safe:
  exact NRIC, a clean read, and the card's name the SAME RAW WORDS as the typed profile name or one
  of the profile's signatures (only case, spaces and marker spacing tidied: a glued or split word, a
  dropped or different connector, BIN for BINTI, a missing apostrophe are not). On an upload it runs
  once the staged card is promoted. ``declaration_name`` is never rewritten.
* D3 — once ``nric_verified`` is on, a STUDENT write may change the name only to the card's own
  (the student's own genuine card, exact NRIC, clean read; the card's name as written, or with a
  word glued or split): the /profile PUT is refused 403 ``name_locked``; the apply-form sync and
  the submit-time signature promotion keep the stored name silently.
* D4 — a student card whose name reads SHORT of the typed name (a strict subset) asks the AI second
  reader, and the AI's full name is taken when it matches; so does a read SHORT of a name the
  student signed. A deterministic match, or a read LONGER than the typed name, is never replaced;
  parent cards keep their rule.
* D5 — ``align_profile_names_to_ic``: dry run by default, ids and counts only.
* D6 — align before the lock, so the lock compares the card with the name it will hold; two
  separate never-raise steps, so a failed alignment never costs the lock.

Every name and NRIC here is invented. No model is ever called (Storage, Vision and Gemini are mocked).
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses import profile_claim
from apps.courses.models import StudentProfile
from apps.scholarship import identity, upload_read, vision
from apps.scholarship.models import ApplicantDocument, StudentActivity
from apps.scholarship.models.activity import EVENT_NAME_ALIGNED_TO_IC
from apps.scholarship.read_errors import IC_SECOND_OPINION_ERROR
from apps.scholarship.services.profile_sync import sync_profile_fields
from apps.scholarship.tests.doc_keys import issued_key
from apps.scholarship.tests.factories import (
    auth_token, create_document, make_application, make_cohort, make_student,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
_IMAGE = b'\xff\xd8\xff\xe0 not a real jpeg, never decoded'

# 177's shape: the signature (5 words) is exactly the card; the profile was edited to 3 of them.
CARD = 'NIRMALA DEVI A/P GANESAN MOORTHY'
SHORT_EDIT = 'NIRMALA DEVI GANESAN'
NRIC = '080515-10-4426'
OTHER_NRIC = '080515-10-4427'          # one digit off: maybe not her card

# 559's shape: a 7-word name on two card lines; the layout read kept only the first 4 words.
FULL7 = 'THIVYA SHREE A/P MUNIANDY ARUMUGAM PILLAI KRISHNAN'
FIRST4 = 'THIVYA SHREE A/P MUNIANDY'
NRIC7 = '071203-08-5512'


def _student(name, nric, **kw):
    return make_student(name=name, nric=nric, **kw)


def _ic(app, *, name=CARD, nric=NRIC, doc_type='ic', member='', error='', vf=None, **kw):
    """A card whose read is already stored (genuine, so the lock can be taken)."""
    fields = {'authenticity': {'status': 'genuine'}, 'capture': 'deterministic'}
    fields.update(vf or {})
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    kw.setdefault('content_type', 'image/jpeg')
    return create_document(application=app, doc_type=doc_type, household_member=member,
                           vision_name=name, vision_nric=nric, vision_run_at=timezone.now(),
                           vision_error=error, vision_fields=fields, **kw)


def _read(doc, *, name, nric, second=None):
    """The real MyKad pipeline: Vision answers ``name``/``nric``; the mocked Gemini answers ``second``
    (``None``: it must not be asked). Returns the Gemini mock."""
    ocr = {'nric': nric, 'name': name, 'address': '', 'error': None}
    g_side = (lambda *a, **k: dict(second)) if second is not None else AssertionError('no second opinion')
    with patch('apps.scholarship.vision._fetch_image_bytes', return_value=_IMAGE), \
            patch('apps.scholarship.vision.extract_mykad', return_value=ocr), \
            patch('apps.scholarship.vision._gemini_ic_second_opinion', side_effect=g_side) as g:
        vision.run_vision_for_document(doc)
    doc.refresh_from_db()
    return g


def _name_of(profile):
    profile.refresh_from_db()
    return profile.name


# ── D2: the alignment rule ─────────────────────────────────────────────────────────────────────


class The177Shape(TestCase):
    """Short profile name, signature == card: aligned, then the check is `match` and it locks."""

    def setUp(self):
        self.profile = _student(SHORT_EDIT, NRIC)
        self.app = make_application(student=self.profile, declaration_name=CARD)

    def test_aligned_then_a_match_and_locked(self):
        doc = _ic(self.app)
        self.assertEqual(identity.compare(doc, self.profile)['name'], 'partial')   # "partly matches"
        self.assertEqual(identity.align_name_to_ic(doc), identity.ALIGNED)
        self.assertEqual(_name_of(self.profile), CARD)
        vision._lock_nric_if_confirmed(doc)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.nric_verified)
        cmp_ = identity.compare(doc, self.profile)
        self.assertEqual((cmp_['name'], cmp_['nric']), ('match', 'match'))
        self.assertEqual(identity.flags(cmp_), [])

    def test_the_signature_is_never_rewritten(self):
        self.app.declaration_name = 'nirmala devi a/p ganesan moorthy'      # typed in lower case
        self.app.save(update_fields=['declaration_name'])
        identity.align_name_to_ic(_ic(self.app))
        self.app.refresh_from_db()
        self.assertEqual(self.app.declaration_name, 'nirmala devi a/p ganesan moorthy')
        self.assertEqual(_name_of(self.profile), CARD)

    def test_the_old_name_is_kept_on_an_internal_activity_row(self):
        doc = _ic(self.app)
        identity.align_name_to_ic(doc)
        row = StudentActivity.objects.get(application=self.app, event=EVENT_NAME_ALIGNED_TO_IC)
        self.assertTrue(row.internal)
        self.assertEqual(row.body, '')
        self.assertEqual(row.meta, {'old': SHORT_EDIT, 'new': CARD, 'document_id': doc.pk,
                                    'source': 'ic_read'})

    def test_through_the_ic_read_it_aligns_before_the_lock(self):
        """D6: the pipeline aligns, then locks — a 5-word read of a 3-word typed name is LONGER than
        the typed name, so no second opinion is asked."""
        doc = _ic(self.app, name='', nric='')
        g = _read(doc, name=CARD, nric=NRIC)
        g.assert_not_called()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, CARD)
        self.assertTrue(self.profile.nric_verified)
        self.assertEqual(identity.compare(doc, self.profile)['name'], 'match')

    def test_a_failed_alignment_never_costs_the_upload_or_the_lock_step(self):
        doc = _ic(self.app, name='', nric='')
        with patch.object(identity, 'align_name_to_ic', side_effect=RuntimeError('boom')):
            _read(doc, name=CARD, nric=NRIC)
        self.assertEqual(doc.vision_name, CARD)                  # the read is stored regardless
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.nric_verified)              # and the lock is still taken
        self.assertEqual(self.profile.name, SHORT_EDIT)          # (the alignment did not run)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET='test-supabase-jwt-secret',
                   DOC_GENUINENESS_CHECK_ENABLED=True, IC_GEMINI_FALLBACK_ENABLED=True)
class ThroughARealUpload(TestCase):
    """Review fix 1: an IC upload is STAGED (not live) while it is read, so the in-read alignment
    answers ``not_latest``; the name aligns when the judged card is promoted into the slot. Through
    the real API: the upload is queued, then ``upload_read.run_read`` reads, judges and promotes.
    Only Storage, Vision, Gemini and the genuineness model are mocked."""

    def setUp(self):
        self.profile = _student(SHORT_EDIT, NRIC, supabase_user_id='req67-real-upload')
        self.app = make_application('shortlisted', student=self.profile, declaration_name=CARD)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_token(self.profile)}')

    def _upload_and_read(self, tag):
        ocr = {'nric': NRIC, 'name': CARD, 'address': '', 'error': None}
        with patch('apps.scholarship.storage.object_exists', return_value=True), \
                patch('apps.scholarship.vision._fetch_image_bytes', return_value=_IMAGE), \
                patch('apps.scholarship.vision.extract_mykad', return_value=ocr), \
                patch('apps.scholarship.vision.ic_genuineness', return_value={'status': 'genuine'}), \
                patch('apps.scholarship.vision._gemini_ic_second_opinion',
                      side_effect=AssertionError('no second opinion')):
            r = self.client.post('/api/v1/scholarship/documents/', {
                'doc_type': 'ic', 'storage_path': issued_key(self.app, 'ic', tag),
                'content_type': 'image/jpeg', 'original_filename': f'{tag}.jpg', 'size': 1000},
                format='json')
            self.assertEqual(r.status_code, 201, r.content)
            outcome, _ = upload_read.run_read(r.json()['id'])
        self.assertEqual(outcome, 'done')
        return ApplicantDocument.objects.get(pk=r.json()['id'])

    def test_a_short_profile_name_with_the_signature_on_the_card_ends_aligned_and_locked(self):
        doc = self._upload_and_read('first')
        self.assertIsNone(doc.superseded_at)                     # promoted into the live slot
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, CARD)
        self.assertTrue(self.profile.nric_verified)
        self.assertEqual(identity.compare(doc, self.profile)['name'], 'match')
        self.assertTrue(StudentActivity.objects.filter(
            application=self.app, event=EVENT_NAME_ALIGNED_TO_IC).exists())

    def test_a_replacement_card_aligns_too(self):
        self._upload_and_read('first')
        self.profile.name = SHORT_EDIT          # (an admin edit, say: the system write still aligns)
        self.profile.save(update_fields=['name'])
        doc = self._upload_and_read('second')
        self.assertIsNone(doc.superseded_at)
        self.assertEqual(_name_of(self.profile), CARD)


class WhenItAligns(TestCase):
    def test_a_match_against_the_profile_name_alone_aligns_to_the_cards_order(self):
        profile = _student('MOORTHY NIRMALA DEVI A/P GANESAN', NRIC)      # same words, other order
        app = make_application(student=profile)                           # nothing signed
        self.assertEqual(identity.align_name_to_ic(_ic(app)), identity.ALIGNED)
        self.assertEqual(_name_of(profile), CARD)

    def test_a_signature_on_another_of_her_applications_counts(self):
        profile = _student(SHORT_EDIT, NRIC)
        make_application(student=profile, declaration_name=CARD)
        later = make_application(student=profile, cohort=make_cohort(code='c-req67-later'))
        self.assertEqual(identity.align_name_to_ic(_ic(later)), identity.ALIGNED)

    def test_already_the_cards_name_writes_nothing(self):
        profile = _student(CARD, NRIC)
        app = make_application(student=profile)
        self.assertEqual(identity.align_name_to_ic(_ic(app)), identity.ALREADY)
        self.assertFalse(StudentActivity.objects.filter(event=EVENT_NAME_ALIGNED_TO_IC).exists())

    def test_a_dry_run_writes_nothing(self):
        profile = _student(SHORT_EDIT, NRIC)
        app = make_application(student=profile, declaration_name=CARD)
        self.assertEqual(identity.align_name_to_ic(_ic(app), write=False), identity.ALIGNED)
        self.assertEqual(_name_of(profile), SHORT_EDIT)


class WhenItDoesNotAlign(TestCase):
    def setUp(self):
        self.profile = _student(SHORT_EDIT, NRIC)
        self.app = make_application(student=self.profile, declaration_name=CARD)

    def _refused(self, doc, outcome):
        self.assertEqual(identity.align_name_to_ic(doc), outcome)
        self.assertEqual(_name_of(self.profile), SHORT_EDIT)
        self.assertFalse(StudentActivity.objects.filter(event=EVENT_NAME_ALIGNED_TO_IC).exists())

    def test_the_card_number_differs(self):
        self._refused(_ic(self.app, nric=OTHER_NRIC), identity.NRIC_DIFFERS)

    def test_the_read_errored(self):
        self._refused(_ic(self.app, error='could not fetch image'), identity.READ_NOT_CLEAN)

    def test_the_second_opinion_failed_or_is_pending(self):
        for vf in ({'ic_second_opinion': 'theirs'}, {'ic_second_opinion': 'ours'},
                   {IC_SECOND_OPINION_ERROR: 'All AI models failed: 503'}):
            with self.subTest(vf=vf):
                doc = _ic(self.app, vf=vf)
                self._refused(doc, identity.READ_NOT_CLEAN)
                doc.delete()

    def test_neither_the_profile_name_nor_any_signature_is_the_cards_name(self):
        self.app.declaration_name = SHORT_EDIT
        self.app.save(update_fields=['declaration_name'])
        self._refused(_ic(self.app), identity.NO_NAME_MATCH)

    def test_an_older_card_does_not_speak_for_her(self):
        old = _ic(self.app)
        _ic(self.app, name='SOMEBODY ELSE ALTOGETHER', nric=NRIC)
        self._refused(old, identity.NOT_LATEST)

    def test_a_parents_card_never_names_the_student(self):
        self._refused(_ic(self.app, doc_type='parent_ic', member='father'), identity.NOT_STUDENT_IC)

    def test_a_dropped_or_different_connector_or_apostrophe_is_not_the_same_words(self):
        """``name_match`` strips connectors and punctuation, so each pair below is its 'match'; the
        alignment keeps them as words, so none rewrites the typed name."""
        probes = (('KUMAR RAJ', 'KUMAR A/L RAJ'), ('ALI BINTI ABU', 'ALI BIN ABU'),
                  ('KUMAR S/O RAJ', 'KUMAR A/L RAJ'), ("NUR'AIN BINTI ISMAIL", 'NUR AIN BINTI ISMAIL'))
        for n, (typed, card) in enumerate(probes):
            with self.subTest(typed=typed, card=card):
                self.assertEqual(vision.name_match(card, typed), 'match')     # the tolerance exists
                nric = f'060707-07-71{n:02d}'
                profile = _student(typed, nric)
                app = make_application(student=profile, declaration_name=typed)
                doc = _ic(app, name=card, nric=nric)
                self.assertEqual(identity.align_name_to_ic(doc), identity.NO_NAME_MATCH)
                self.assertEqual(_name_of(profile), typed)

    def test_only_case_spaces_and_marker_spacing_are_tidied(self):
        profile = _student('nirmala  devi a / p ganesan moorthy', '060707-07-7180')
        app = make_application(student=profile)
        profile.name = 'NIRMALA DEVI A/P GANESAN'                 # signed in full, edited short
        profile.save(update_fields=['name'])
        app.declaration_name = 'nirmala  devi a / p ganesan moorthy'
        app.save(update_fields=['declaration_name'])
        doc = _ic(app, name=CARD, nric='060707-07-7180')
        self.assertEqual(identity.align_name_to_ic(doc), identity.ALIGNED)
        self.assertEqual(_name_of(profile), CARD)

    def test_a_glued_or_split_word_is_not_the_same_words(self):
        """``name_match`` forgives an OCR space glued or split (MUHAMMAD AMIN ~ MUHAMMADAMIN); the
        alignment does not: it would rewrite a correctly typed name into the card's OCR spacing."""
        for typed, card, nric in (
                ('MUHAMMAD AMIN BIN ZULKIFLI', 'MUHAMMADAMIN BIN ZULKIFLI', '060707-07-7072'),
                ('MUHAMMADAMIN BIN ZULKIFLI', 'MUHAMMAD AMIN BIN ZULKIFLI', '060707-07-7073')):
            with self.subTest(typed=typed, card=card):
                self.assertEqual(vision.name_match(card, typed), 'match')     # the tolerance exists
                profile = _student(typed, nric)
                app = make_application(student=profile, declaration_name=typed)
                doc = _ic(app, name=card, nric=nric)
                self.assertEqual(identity.align_name_to_ic(doc), identity.NO_NAME_MATCH)
                self.assertEqual(_name_of(profile), typed)
                self.assertFalse(StudentActivity.objects.filter(
                    event=EVENT_NAME_ALIGNED_TO_IC, application=app).exists())


# ── D4: the 559 short read ─────────────────────────────────────────────────────────────────────


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class The559Shape(TestCase):
    def setUp(self):
        self.profile = _student(FULL7, NRIC7)
        self.app = make_application(student=self.profile, declaration_name=FULL7)
        self.doc = _ic(self.app, name='', nric='')                 # prior genuine verdict kept (TD-407)

    def test_a_4_of_7_read_asks_the_second_reader_and_takes_its_7_words(self):
        g = _read(self.doc, name=FIRST4, nric=NRIC7,
                  second={'nric': NRIC7, 'name': FULL7, 'address': ''})
        g.assert_called_once()
        self.assertEqual(self.doc.vision_name, FULL7)
        self.assertEqual(self.doc.vision_fields['capture'], 'ai')
        self.profile.refresh_from_db()
        self.assertEqual(identity.compare(self.doc, self.profile)['name'], 'match')
        self.assertTrue(self.profile.nric_verified)

    def test_a_second_reading_that_is_not_her_name_is_not_taken(self):
        g = _read(self.doc, name=FIRST4, nric=NRIC7,
                  second={'nric': NRIC7, 'name': 'THIVYA SHREE A/P MUNIANDY RAJAN', 'address': ''})
        g.assert_called_once()
        self.assertEqual(self.doc.vision_name, FIRST4)             # the deterministic read stands

    def test_a_deterministic_match_never_asks_and_is_never_replaced(self):
        g = _read(self.doc, name=FULL7, nric=NRIC7)
        g.assert_not_called()
        self.assertEqual(self.doc.vision_name, FULL7)

    @override_settings(IC_GEMINI_FALLBACK_ENABLED=False)
    def test_the_switch_still_turns_the_second_reader_off(self):
        _read(self.doc, name=FIRST4, nric=NRIC7)
        self.assertEqual(self.doc.vision_name, FIRST4)

    def test_a_longer_read_is_never_replaced_by_a_shorter_one(self):
        """The deterministic read is LONGER than the typed name (5 words over her 3-word edit); it
        escalates for a missing NRIC, and the AI reads only her 3 typed words. The 5 words stay:
        D4 takes the AI name only over a read SHORT of the typed name."""
        profile = _student(SHORT_EDIT, NRIC)
        app = make_application(student=profile)
        doc = _ic(app, name='', nric='')
        g = _read(doc, name=CARD, nric='', second={'nric': NRIC, 'name': SHORT_EDIT, 'address': ''})
        g.assert_called_once()                                    # escalated: no number was read
        self.assertEqual(doc.vision_nric, NRIC)                   # the AI's number is taken
        self.assertEqual(doc.vision_name, CARD)                   # but not its shorter name
        self.assertEqual(_name_of(profile), SHORT_EDIT)           # and nothing aligns on 'partial'
        out = vision._merge_ic_reads({'nric': '', 'name': CARD}, {'nric': NRIC, 'name': SHORT_EDIT},
                                     profile, own_card=True)
        self.assertEqual(out['name'], CARD)

    def test_the_merge_never_overrides_a_deterministic_match(self):
        out = vision._merge_ic_reads({'nric': NRIC7, 'name': FULL7}, {'nric': NRIC7, 'name': FIRST4},
                                     self.profile, own_card=True)
        self.assertEqual(out['name'], FULL7)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class AShortReadOfHerSignature(TestCase):
    """Review fix 6: the profile name was edited down to the 4 words the layout read, so the read
    'matches' the profile; but she SIGNED the full 7. A read that is a strict subset of a signature
    asks the second reader, and its name is taken when it is the signature's raw words."""

    def setUp(self):
        self.profile = _student(FIRST4, NRIC7)
        self.app = make_application(student=self.profile, declaration_name=FULL7)
        self.doc = _ic(self.app, name='', nric='')

    def test_it_asks_takes_the_signed_words_and_aligns(self):
        g = _read(self.doc, name=FIRST4, nric=NRIC7,
                  second={'nric': NRIC7, 'name': FULL7, 'address': ''})
        g.assert_called_once()
        self.assertEqual(self.doc.vision_name, FULL7)
        self.assertEqual(_name_of(self.profile), FULL7)            # and the profile aligns to it
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.nric_verified)

    def test_a_second_reading_that_is_not_the_signed_words_is_not_taken(self):
        """'match' alone is not enough here: the AI's name must be the signature's own raw words."""
        no_connector = FULL7.replace(' A/P', '')
        self.assertEqual(vision.name_match(no_connector, FULL7), 'match')
        g = _read(self.doc, name=FIRST4, nric=NRIC7,
                  second={'nric': NRIC7, 'name': no_connector, 'address': ''})
        g.assert_called_once()
        self.assertEqual(self.doc.vision_name, FIRST4)
        self.assertEqual(_name_of(self.profile), FIRST4)

    def test_a_signature_on_another_of_her_applications_counts(self):
        self.app.declaration_name = ''
        self.app.save(update_fields=['declaration_name'])
        make_application(student=self.profile, cohort=make_cohort(), declaration_name=FULL7)
        _read(self.doc, name=FIRST4, nric=NRIC7, second={'nric': NRIC7, 'name': FULL7, 'address': ''})
        self.assertEqual(self.doc.vision_name, FULL7)

    def test_a_read_longer_than_the_signature_never_asks_and_is_never_shortened(self):
        self.app.declaration_name = FIRST4
        self.app.save(update_fields=['declaration_name'])
        g = _read(self.doc, name=FULL7, nric=NRIC7)
        g.assert_not_called()
        self.assertEqual(self.doc.vision_name, FULL7)
        out = vision._merge_ic_reads({'nric': NRIC7, 'name': FULL7}, {'nric': NRIC7, 'name': FIRST4},
                                     self.profile, own_card=True)
        self.assertEqual(out['name'], FULL7)

    def test_only_her_own_card_asks_for_her_signature(self):
        read = {'nric': NRIC7, 'name': FIRST4}
        self.assertEqual(vision.name_match(FIRST4, self.profile.name), 'match')    # no other reason
        self.assertFalse(vision._should_gemini_ic(read, self.profile))
        self.assertTrue(vision._should_gemini_ic(read, self.profile, own_card=True))
        out = vision._merge_ic_reads(read, {'nric': NRIC7, 'name': FULL7}, self.profile)
        self.assertEqual(out['name'], FIRST4)                    # not her card: today's merge


class ParentCardsAreUnaffected(TestCase):
    def test_a_short_read_is_not_a_reason_to_escalate_without_own_card(self):
        profile = _student(FULL7, NRIC7)
        self.assertFalse(vision._should_gemini_ic({'nric': NRIC7, 'name': FIRST4}, profile))
        self.assertTrue(vision._should_gemini_ic({'nric': NRIC7, 'name': FIRST4}, profile, own_card=True))

    def test_a_fathers_partial_read_keeps_todays_merge(self):
        """The father's card escalates as it always did; the merge keeps a `partial` deterministic read
        (only a `mismatch` is replaced on a parent's card), and the student's name is never touched."""
        profile = _student(FULL7, NRIC7)
        app = make_application('profile_complete', student=profile, declaration_name=FULL7,
                               income_route='salary', income_earner='father',
                               income_working_members=['father'], other_family_members=[],
                               father_name='KUMAR A/L RAJU SELVAM', mother_name='')
        pic = _ic(app, name='', nric='', doc_type='parent_ic', member='father')
        g = _read(pic, name='KUMAR A/L RAJU', nric='700101-14-5677',
                  second={'nric': '700101-14-5677', 'name': 'KUMAR A/L RAJU SELVAM', 'address': ''})
        g.assert_called_once()
        self.assertEqual(pic.vision_name, 'KUMAR A/L RAJU')
        self.assertEqual(_name_of(profile), FULL7)
        self.assertFalse(profile.nric_verified)


# ── D3: the lock ───────────────────────────────────────────────────────────────────────────────


class NameChangeAllowed(TestCase):
    def setUp(self):
        self.profile = _student(CARD, NRIC, nric_verified=True)
        self.app = make_application(student=self.profile, declaration_name=CARD)
        self.card = _ic(self.app)

    def test_the_rule(self):
        allowed = identity.name_change_allowed
        self.assertTrue(allowed(self.profile, CARD))
        self.assertTrue(allowed(self.profile, '  nirmala  devi a / p ganesan moorthy '))   # unchanged
        self.profile.name = SHORT_EDIT                       # locked on a short name: back to the card
        self.assertTrue(allowed(self.profile, 'nirmala devi a / p ganesan moorthy'))      # the card, tidied
        self.assertTrue(allowed(self.profile, 'NIRMALADEVI A/P GANESAN MOORTHY'))        # a word glued
        self.assertTrue(allowed(self.profile, 'NIRMALA DEVI A/P GANE SAN MOORTHY'))      # a word split
        self.assertFalse(allowed(self.profile, 'NIRMALA DEVI'))                          # partial
        self.assertFalse(allowed(self.profile, 'SOMEONE ELSE ENTIRELY'))
        self.assertFalse(allowed(self.profile, ''))

    def test_name_match_tolerance_does_not_open_the_lock(self):
        """Review fix 5: 'match' forgives digits, reordering, punctuation and titles; the lock does not."""
        profile = _student('SHARMILA RAJU', '060707-07-7190', nric_verified=True)
        _ic(make_application(student=profile, declaration_name='SHARMILA A/P RAJU'),
            name='SHARMILA A/P RAJU', nric='060707-07-7190')
        self.assertTrue(identity.name_change_allowed(profile, 'SHARMILA A/P RAJU'))
        for probe in ('SHARMILA 1204 RAJU', 'RAJU SHARMILA', 'RAJU A/P SHARMILA', 'SHARMILA A/P RAJU!!',
                      'SHARMILA. A/P RAJU', 'DATUK DR SHARMILA A/P RAJU', 'PUAN SHARMILA A/P RAJU'):
            with self.subTest(probe=probe):
                self.assertFalse(identity.name_change_allowed(profile, probe))

    def test_only_her_own_well_read_genuine_card_speaks(self):
        """Review fix 3: the latest live card must be HERS (exact NRIC), cleanly read and genuine."""
        self.profile.name = SHORT_EDIT
        cases = (('another person', {'name': 'SITI AMINAH BINTI YUSOF', 'nric': '991231-14-5550'},
                  'SITI AMINAH BINTI YUSOF'),
                 ('a misread number', {'nric': OTHER_NRIC}, CARD),
                 ('never scored genuine', {'vf': {'authenticity': {}}}, CARD),
                 ('scored not genuine', {'vf': {'authenticity': {'status': 'suspicious'}}}, CARD),
                 ('an errored read', {'error': 'could not fetch image'}, CARD),
                 ('a pending second opinion', {'vf': {'ic_second_opinion': 'ours'}}, CARD))
        for label, kw, name in cases:
            with self.subTest(label):
                newer = _ic(self.app, **kw)
                self.assertFalse(identity.name_change_allowed(self.profile, name))
                newer.delete()
        self.assertTrue(identity.name_change_allowed(self.profile, CARD))

    def test_unlocked_anything_goes(self):
        self.profile.nric_verified = False
        self.assertTrue(identity.name_change_allowed(self.profile, 'SOMEONE ELSE ENTIRELY'))

    def test_a_lock_with_no_card_holds_the_name_as_it_is(self):
        ApplicantDocument.objects.filter(application=self.app).delete()
        self.assertTrue(identity.name_change_allowed(self.profile, CARD))
        self.assertFalse(identity.name_change_allowed(self.profile, 'MOORTHY NIRMALA DEVI A/P GANESAN'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheProfilePut(TestCase):
    def setUp(self):
        self.profile = _student(CARD, NRIC, nric_verified=True, school='SMK ASAL')
        _ic(make_application(student=self.profile, declaration_name=CARD))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_token(self.profile)}')

    def _put(self, **data):
        return self.client.put('/api/v1/profile/', data, format='json')

    def test_a_locked_name_change_is_refused_403_and_nothing_is_saved(self):
        r = self._put(name=SHORT_EDIT, school='SMK BARU')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json(), profile_claim.NAME_LOCKED)
        self.assertEqual(r.json()['code'], 'name_locked')
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.name, self.profile.school), (CARD, 'SMK ASAL'))

    def test_the_cards_own_name_is_accepted(self):
        self.profile.name = SHORT_EDIT
        self.profile.save(update_fields=['name'])
        r = self._put(name='nirmala devi a / p ganesan moorthy')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(_name_of(self.profile), CARD)

    def test_a_reordered_name_is_refused(self):
        self.assertEqual(self._put(name='MOORTHY NIRMALA DEVI A/P GANESAN').status_code, 403)

    def test_another_persons_card_does_not_open_the_lock(self):
        """Review fix 3: a genuine card with someone else's number, uploaded as the latest live IC,
        cannot be used to take that person's name."""
        app = ApplicantDocument.objects.filter(application__profile=self.profile).first().application
        _ic(app, name='SITI AMINAH BINTI YUSOF', nric='991231-14-5550')
        r = self._put(name='SITI AMINAH BINTI YUSOF')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'name_locked')
        self.assertEqual(_name_of(self.profile), CARD)

    def test_an_unchanged_name_always_passes(self):
        r = self._put(name=CARD.lower(), school='SMK BARU')
        self.assertEqual(r.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.school, 'SMK BARU')

    def test_unlocked_the_name_is_editable_as_before(self):
        self.profile.nric_verified = False
        self.profile.save(update_fields=['nric_verified'])
        self.assertEqual(self._put(name=SHORT_EDIT).status_code, 200)
        self.assertEqual(_name_of(self.profile), SHORT_EDIT)

    def test_the_get_serves_name_locked(self):
        d = self.client.get('/api/v1/profile/').json()
        self.assertTrue(d['name_locked'])
        keys = list(d)
        self.assertEqual(keys.index('name_locked'), keys.index('nric_locked') + 1)


class TheFormSyncAndThePromotion(TestCase):
    def setUp(self):
        self.profile = _student(CARD, NRIC, nric_verified=True)
        self.app = make_application(student=self.profile, declaration_name=CARD)
        _ic(self.app)

    def test_the_apply_form_sync_keeps_a_locked_name_and_syncs_the_rest(self):
        updated = sync_profile_fields(self.profile, {'name': SHORT_EDIT, 'school': 'SMK BARU'})
        self.assertEqual(updated, ['school'])
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.name, self.profile.school), (CARD, 'SMK BARU'))

    def test_the_apply_form_sync_takes_the_cards_own_name(self):
        self.profile.name = SHORT_EDIT
        self.profile.save(update_fields=['name'])
        self.assertIn('name', sync_profile_fields(self.profile, {'name': 'Nirmala Devi A/P Ganesan Moorthy'}))
        self.assertEqual(_name_of(self.profile), CARD)

    def test_the_submit_promotion_keeps_a_locked_name_and_stores_the_signature_verbatim(self):
        from apps.scholarship.services.intake import create_application
        app = create_application(profile=self.profile, cohort=make_cohort(code='c-req67-promo'),
                                 validated_data={'declaration_name': SHORT_EDIT, 'consent_to_contact': True},
                                 to_email='', acknowledge=False)
        self.assertEqual(_name_of(self.profile), CARD)
        app.refresh_from_db()
        self.assertEqual(app.declaration_name, SHORT_EDIT)

    def test_unlocked_the_signature_is_promoted_as_before(self):
        from apps.scholarship.services.intake import create_application
        self.profile.nric_verified = False
        self.profile.save(update_fields=['nric_verified'])
        create_application(profile=self.profile, cohort=make_cohort(code='c-req67-promo2'),
                           validated_data={'declaration_name': SHORT_EDIT, 'consent_to_contact': True},
                           to_email='', acknowledge=False)
        self.assertEqual(_name_of(self.profile), SHORT_EDIT)


class TheLockIsStillOneWay(TestCase):
    def test_removing_the_card_unlocks_neither_the_number_nor_the_name(self):
        profile = _student(SHORT_EDIT, NRIC)
        app = make_application(student=profile, declaration_name=CARD)
        doc = _ic(app)
        identity.align_name_to_ic(doc)
        vision._lock_nric_if_confirmed(doc)
        doc.delete()
        profile.refresh_from_db()
        self.assertTrue(profile.nric_verified)
        self.assertTrue(identity.name_locked(profile))
        self.assertFalse(identity.name_change_allowed(profile, SHORT_EDIT))

    def test_a_later_card_that_does_not_align_leaves_the_lock_on(self):
        profile = _student(CARD, NRIC, nric_verified=True)
        app = make_application(student=profile)
        self.assertEqual(identity.align_name_to_ic(_ic(app, nric=OTHER_NRIC)), identity.NRIC_DIFFERS)
        profile.refresh_from_db()
        self.assertTrue(profile.nric_verified)


# ── D5: the one-off pass ───────────────────────────────────────────────────────────────────────


class TheBackfillCommand(TestCase):
    def setUp(self):
        self.drift = _student(SHORT_EDIT, NRIC)                         # 177's shape: will align
        self.drift_app = make_application(student=self.drift, declaration_name=CARD)
        _ic(self.drift_app)
        self.other = _student('SITI AMINAH BINTI YUSOF', '060707-07-7070')   # card number differs
        _ic(make_application(student=self.other), name='SITI AMINAH BINTI YUSOF', nric='060707-07-7071')

    def _run(self, *args):
        out = StringIO()
        call_command('align_profile_names_to_ic', *args, stdout=out)
        return out.getvalue()

    def test_a_dry_run_reports_and_writes_nothing_and_prints_no_names_or_numbers(self):
        out = self._run()
        self.assertIn(f'app {self.drift_app.id}: name would align', out)
        self.assertIn('[dry-run] ic name alignment: 2 checked, 1 to align', out)
        self.assertIn('nric_differs 1', out)
        for secret in (CARD, SHORT_EDIT, NRIC, 'SITI', '060707'):
            self.assertNotIn(secret, out.upper())
        self.assertEqual(_name_of(self.drift), SHORT_EDIT)

    def test_one_bad_row_is_counted_and_never_stops_the_pass(self):
        real = identity.align_name_to_ic

        def flaky(doc, **kw):
            if doc.application_id == self.drift_app.id:
                raise RuntimeError('boom')
            return real(doc, **kw)
        with patch.object(identity, 'align_name_to_ic', side_effect=flaky), \
                self.assertLogs('apps.scholarship.management.commands.align_profile_names_to_ic',
                                level='WARNING'):
            out = self._run('--apply')
        self.assertIn(f'app {self.drift_app.id}: failed (see the log)', out)
        self.assertIn('2 checked, 0 aligned', out)
        self.assertIn('failed 1', out)
        self.assertIn('nric_differs 1', out)                     # the other row was still checked
        for secret in (CARD, SHORT_EDIT, NRIC, 'SITI', '060707', 'BOOM'):
            self.assertNotIn(secret, out.upper())

    def test_apply_writes_once_and_a_second_run_finds_it_already_done(self):
        self.assertIn('2 checked, 1 aligned', self._run('--apply'))
        self.assertEqual(_name_of(self.drift), CARD)
        row = StudentActivity.objects.get(application=self.drift_app, event=EVENT_NAME_ALIGNED_TO_IC)
        self.assertEqual(row.meta['source'], 'backfill')
        again = self._run('--apply')
        self.assertIn('2 checked, 0 aligned', again)
        self.assertIn('already 1', again)
        self.assertEqual(StudentProfile.objects.get(pk=self.other.pk).name, 'SITI AMINAH BINTI YUSOF')
