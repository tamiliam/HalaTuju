"""TD-055 (2026-10-03): the apply form MERGES its one guardian into the stored list.

The characterisation table first: for every list the apply form can have written ITSELF (`[]` or
one `{name, phone}`), the merged answer equals the old overwrite — so no student whose guardians
only ever came from this form stores anything different. Then the rows where it does differ: a
richer first entry keeps its other keys when the form names the SAME person (a different name drops
them — review F4), and a second entry survives.
"""
from django.test import SimpleTestCase, TestCase

from apps.scholarship.services import sync_profile_fields
from apps.scholarship.services.profile_sync import merge_guardians
from apps.scholarship.tests.factories import make_student

A = {'name': 'Devaraj', 'phone': '012-3456789'}
B = {'name': 'Kamala', 'phone': '019-8765432'}
RICH = {'name': 'Devaraj', 'phone': '012-3456789', 'relationship': 'father',
        'occupation': 'driver', 'income': 1800}
SECOND = {'name': 'Suppiah', 'relationship': 'grandfather'}


class TheFormsOwnShapesStoreWhatTheyAlwaysStored(SimpleTestCase):
    """merge == overwrite on every (stored, sent) pair the apply form alone can produce."""

    def test_the_characterisation_table(self):
        form_shapes = ([], [A], [B])
        for stored in form_shapes:
            for sent in form_shapes:
                with self.subTest(stored=stored, sent=sent):
                    self.assertEqual(merge_guardians(stored, sent), sent)   # == the old overwrite


class WhatTheMergeKeeps(SimpleTestCase):

    def test_the_same_person_keeps_their_other_keys(self):
        self.assertEqual(merge_guardians([RICH], [{'name': ' devaraj ', 'phone': '011-1111111'}]),
                         [{'name': ' devaraj ', 'phone': '011-1111111', 'relationship': 'father',
                           'occupation': 'driver', 'income': 1800}])

    def test_a_different_person_does_not_inherit_the_old_guardians_keys(self):
        # Superseded 2026-10-03 (review F4): this used to pin the MIXED entry — Kamala's name under
        # Devaraj's relationship/occupation/income. A new name is a new guardian.
        self.assertEqual(merge_guardians([RICH], [B]), [B])
        self.assertEqual(merge_guardians([RICH, SECOND], [B]), [B, SECOND])

    def test_a_second_entry_survives(self):
        self.assertEqual(merge_guardians([A, SECOND], [B]), [B, SECOND])

    def test_a_blanked_form_clears_only_what_it_owns(self):
        self.assertEqual(merge_guardians([RICH, SECOND], []),
                         [{'relationship': 'father', 'occupation': 'driver', 'income': 1800},
                          SECOND])
        self.assertEqual(merge_guardians([A, SECOND], []), [SECOND])

    def test_a_shape_that_is_not_the_forms_is_written_as_sent(self):
        self.assertEqual(merge_guardians([A], 'not a list'), 'not a list')
        self.assertEqual(merge_guardians('junk', [B]), [B])

    def test_the_stored_list_is_not_mutated(self):
        stored = [dict(RICH)]
        merge_guardians(stored, [B])
        self.assertEqual(stored, [RICH])


class ThroughTheWriteBack(TestCase):

    def test_submit_merges_onto_the_profile(self):
        profile = make_student(guardians=[RICH, SECOND])
        changed = sync_profile_fields(profile, {'guardians': [{'name': 'Devaraj', 'phone': '011'}]})
        profile.refresh_from_db()
        self.assertIn('guardians', changed)
        self.assertEqual(profile.guardians[0]['phone'], '011')
        self.assertEqual(profile.guardians[0]['relationship'], 'father')
        self.assertEqual(profile.guardians[1], SECOND)

    def test_an_unchanged_guardian_is_not_rewritten(self):
        profile = make_student(guardians=[RICH])
        self.assertNotIn('guardians', sync_profile_fields(
            profile, {'guardians': [{'name': RICH['name'], 'phone': RICH['phone']}]}))
