"""TD-315 — an EXPLICIT tag is overridden only by a FULL-name match.

The upload guard (`income_engine.name_contradicts_tag`, called from `DocumentListCreateView.post`)
corrects a tag the name on the document contradicts — the #80/#112 class, a father's document
stamped onto the mother. It used to accept a 'partial' name match, and the patronymic of a child's
name IS the father's given name: `relationship_name_match('ARUN A/L RAJU', 'Raju')` is 'partial'.
So with a bare `father_name = 'Raju'` and the brother not named in the roster, an IC uploaded to the
BROTHER's card was re-filed as the father's and superseded the father's live IC.

Rule since 2026-09-30, tightened by the review of 2026-10-01 (decisions.md): a 'partial' may FILL
a blank tag but never OVERRULE one; an override needs the document's NRIC to equal exactly one
member's IC on file, or — with no readable NRIC — a full-name match whose given name agrees. Both directions are pinned here, and through the real POST view (lessons.md,
TD-309: an upload card's member is a REQUEST — only an api test that POSTs sees what is stored).
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.income_engine import name_contradicts_tag, resolved_member_for
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_student,
)
from apps.scholarship.vision import relationship_name_match


def _doc(app, member, name, doc_type='parent_ic'):
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, household_member=member,
        storage_path=f'{app.id}/{doc_type}/{member or "blank"}-{name[:4]}', vision_name=name)


class FullNameMatchRuleTest(TestCase):
    """The pure rule, on `name_contradicts_tag` and `resolved_member_for`."""

    def _app(self, father='', mother='', others=None):
        app = make_application('profile_complete')
        app.father_name, app.mother_name = father, mother
        app.other_family_members = others or []
        app.save(update_fields=['father_name', 'mother_name', 'other_family_members'])
        return app

    def test_the_premise_a_sons_name_partially_matches_his_fathers_given_name(self):
        self.assertEqual(relationship_name_match('ARUN A/L RAJU', 'Raju'), 'partial')

    def test_a_brothers_ic_is_NOT_refiled_as_the_fathers(self):
        app = self._app(father='Raju', mother='Selvi')
        brother_ic = _doc(app, 'brother', 'ARUN A/L RAJU')
        self.assertEqual(name_contradicts_tag(app, brother_ic), '')

    def test_the_80_112_correction_still_happens_on_a_full_name(self):
        app = self._app(father='RAVI A/L PERIAKARUPPAN', mother='SELVI A/P VELLAYAN')
        fathers_doc_on_mother = _doc(app, 'mother', 'RAVI A/L PERIAKARUPPAN')
        self.assertEqual(name_contradicts_tag(app, fathers_doc_on_mother), 'father')

    def test_a_fathers_ic_on_the_brothers_card_is_still_corrected(self):
        app = self._app(father='RAJU A/L MUNUSAMY', mother='SELVI A/P VELLAYAN')
        fathers_ic = _doc(app, 'brother', 'RAJU A/L MUNUSAMY')
        self.assertEqual(name_contradicts_tag(app, fathers_ic), 'father')

    def test_a_partial_may_still_FILL_a_blank_tag(self):
        app = self._app(father='Raju', mother='Selvi')
        blank = _doc(app, '', 'ARUN A/L RAJU')
        self.assertEqual(resolved_member_for(app, blank), 'father')   # unchanged, by decision

    def test_a_partial_still_counts_toward_ambiguity(self):
        # Full match on the father AND a partial on a named brother "Ravi": two members, so the
        # tag stands, exactly as before. The new rule only ever REFUSES corrections.
        app = self._app(father='RAVI A/L PERIAKARUPPAN', mother='SELVI A/P VELLAYAN',
                        others=[{'name': 'Ravi', 'relationship': 'brother'}])
        doc = _doc(app, 'mother', 'RAVI A/L PERIAKARUPPAN')
        self.assertEqual(name_contradicts_tag(app, doc), '')


FATHER_NRIC = '750101-10-1111'
MOTHER_NRIC = '780202-10-2222'


class NricFirstRuleTest(TestCase):
    """Review F1+F2 (2026-10-01): the NUMBER decides first. A readable NRIC on the document that
    equals exactly ONE member's IC on file re-files it, whatever the roster name says; only a
    document with NO readable NRIC falls back to the name — a full match with one member whose
    GIVEN name (the first token) also matches, in order."""

    def _app(self, father, mother='LETCHUMI A/P SAMY'):
        app = make_application('profile_complete')
        app.father_name, app.mother_name = father, mother
        app.save(update_fields=['father_name', 'mother_name'])
        return app

    def _ic_on_file(self, app, member, nric, name='ON FILE'):
        return ApplicantDocument.objects.create(
            application=app, doc_type='parent_ic', household_member=member,
            storage_path=f'{app.id}/parent_ic/{member}-file', vision_name=name, vision_nric=nric)

    def _slip(self, app, member, name, nric=''):
        fields = {'name': name}
        if nric:
            fields['nric'] = nric
        return ApplicantDocument.objects.create(
            application=app, doc_type='salary_slip', household_member=member,
            storage_path=f'{app.id}/salary_slip/{member}-{name[:4]}',
            vision_fields={'fields': fields})

    def test_a_grandfather_named_son_is_NOT_refiled_as_the_father(self):
        # "ARUN A/L RAJU" and "Raju A/L Arun" are the same two words; the given names differ.
        app = self._app(father='Raju A/L Arun')
        brother_ic = _doc(app, 'brother', 'ARUN A/L RAJU')
        self.assertEqual(name_contradicts_tag(app, brother_ic), '')

    def test_the_fathers_nric_refiles_his_slip_whatever_the_roster_name(self):
        app = self._app(father='Raju', mother='Letchumi')           # bare given names
        self._ic_on_file(app, 'father', FATHER_NRIC)
        slip = self._slip(app, 'mother', 'RAJU A/L MUTHU', nric='750101101111')
        self.assertEqual(name_contradicts_tag(app, slip), 'father')

    def test_no_nric_and_a_bare_roster_name_leaves_the_tag(self):
        app = self._app(father='Raju', mother='Letchumi')
        slip = self._slip(app, 'mother', 'RAJU A/L MUTHU')
        self.assertEqual(name_contradicts_tag(app, slip), '')

    def test_no_nric_and_full_names_in_order_refiles_it(self):
        app = self._app(father='RAJU A/L MUTHU')
        slip = self._slip(app, 'mother', 'RAJU A/L MUTHU')
        self.assertEqual(name_contradicts_tag(app, slip), 'father')

    def test_an_nric_matching_TWO_members_ics_leaves_the_tag(self):
        app = self._app(father='RAJU A/L MUTHU')
        self._ic_on_file(app, 'father', FATHER_NRIC)
        self._ic_on_file(app, 'guardian', FATHER_NRIC)                # bad data: one number twice
        slip = self._slip(app, 'mother', 'RAJU A/L MUTHU', nric=FATHER_NRIC)
        self.assertEqual(name_contradicts_tag(app, slip), '')

    def test_the_nric_wins_over_the_name(self):
        app = self._app(father='RAJU A/L MUTHU')
        self._ic_on_file(app, 'father', FATHER_NRIC)
        self._ic_on_file(app, 'mother', MOTHER_NRIC)
        # The NAME reads the mother's (a full match, in order) but the NUMBER is the father's.
        slip = self._slip(app, 'mother', 'LETCHUMI A/P SAMY', nric=FATHER_NRIC)
        self.assertEqual(name_contradicts_tag(app, slip), 'father')

    def test_a_readable_nric_matching_nobody_leaves_the_tag(self):
        app = self._app(father='RAJU A/L MUTHU')
        slip = self._slip(app, 'mother', 'RAJU A/L MUTHU', nric='600101-10-9999')
        self.assertEqual(name_contradicts_tag(app, slip), '')

    def test_an_ic_never_counts_its_own_number(self):
        # The father's IC uploaded to the BROTHER's card, his IC already on file: the number is
        # his alone. Counting the document under test as "on file" would make it two members'
        # number (father + brother) and wrongly leave the tag.
        app = self._app(father='Raju')
        self._ic_on_file(app, 'father', FATHER_NRIC)
        again = ApplicantDocument.objects.create(
            application=app, doc_type='parent_ic', household_member='brother',
            storage_path=f'{app.id}/parent_ic/again', vision_name='RAJU A/L MUTHU',
            vision_nric=FATHER_NRIC)
        self.assertEqual(name_contradicts_tag(app, again), 'father')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class FullNameMatchThroughTheUploadViewTest(TestCase):
    """The same rule where it bites: POST through `DocumentListCreateView` and read what is STORED,
    and that the OTHER slot's live row survives."""

    def setUp(self):
        self.student = make_student()
        self.app = make_application('profile_complete', student=self.student)
        self.app.income_route = 'salary'
        self.app.save(update_fields=['income_route'])

    def _roster(self, father, mother='SELVI A/P VELLAYAN'):
        self.app.father_name, self.app.mother_name = father, mother
        self.app.save(update_fields=['father_name', 'mother_name'])

    def _upload(self, member, read_name, suffix):
        def _read(doc):
            doc.vision_name = read_name
            doc.vision_run_at = timezone.now()
            doc.save(update_fields=['vision_name', 'vision_run_at'])
        with patch('apps.scholarship.vision.run_vision_for_document', side_effect=_read), \
             patch('apps.scholarship.storage.create_signed_download_url',
                   return_value='https://s/dl'):
            resp = authed_client(self.student).post('/api/v1/scholarship/documents/', {
                'doc_type': 'parent_ic', 'household_member': member,
                'storage_path': f'{self.app.id}/parent_ic/{suffix}',
                'original_filename': 'ic.jpg', 'size': 1000,
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return ApplicantDocument.objects.get(id=resp.json()['id'])

    def test_a_brothers_ic_stays_the_brothers_and_the_fathers_ic_survives(self):
        self._roster(father='Raju')
        fathers_ic = ApplicantDocument.objects.create(
            application=self.app, doc_type='parent_ic', household_member='father',
            storage_path=f'{self.app.id}/parent_ic/father-live', vision_name='RAJU A/L MUNUSAMY')
        doc = self._upload('brother', 'ARUN A/L RAJU', 'brother')
        self.assertEqual(doc.household_member, 'brother')
        fathers_ic.refresh_from_db()
        self.assertIsNone(fathers_ic.superseded_at)          # the father's live IC is untouched

    def test_a_fathers_ic_on_the_mothers_card_is_still_refiled(self):
        self._roster(father='RAVI A/L PERIAKARUPPAN')
        doc = self._upload('mother', 'RAVI A/L PERIAKARUPPAN', 'mis')
        self.assertEqual(doc.household_member, 'father')
