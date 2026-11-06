"""Owner, 2026-11-06 ("They have served their purpose"): the cockpit no longer shows the TEAM's
housekeeping notes — a split of a combined upload (`team_split`) and a refile the team did
(`refiled_higher` / `refiled_spm` with `by: 'team'`). The student's own notes are still served, and
the STORED list is never touched (`wrong_slip` reads the team's `refiled_higher` notes)."""
from django.test import TestCase

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.results_route import cockpit_notes
from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
from apps.scholarship.tests.factories import make_application

STUDENT = [
    {'at': '2026-10-26T00:00:00', 'kind': 'only_spm', 'cleared': 'stpm', 'cgpa': 3.5},
    {'at': '2026-10-26T00:00:00', 'kind': 'refiled_spm', 'document_id': 1},
    {'at': '2026-10-27T00:00:00', 'kind': 'refiled_higher', 'results_kind': 'stpm', 'document_id': 2},
]
TEAM = [
    {'at': '2026-10-27T00:00:00', 'kind': 'refiled_higher', 'by': 'team', 'results_kind': 'stpm',
     'document_id': 3},
    {'at': '2026-10-27T00:00:00', 'kind': 'refiled_higher', 'by': 'team', 'from': 'semester_result',
     'document_id': 4},
    {'at': '2026-10-27T00:00:00', 'kind': 'refiled_spm', 'by': 'team', 'document_id': 5},
    {'at': '2026-10-28T00:00:00', 'kind': 'team_split', 'by': 'team', 'slot': 'results_slip',
     'document_id': 6, 'pages': [1]},
    {'at': '2026-10-28T00:00:00', 'kind': 'team_split', 'slot': 'higher_results', 'document_id': 7},
]


class TheCockpitIsServedOnlyTheStudentsNotes(TestCase):
    def test_team_notes_are_not_served_and_student_notes_are(self):
        app = make_application('submitted')
        app.results_change_notes = [TEAM[0], STUDENT[0], TEAM[3], STUDENT[1], TEAM[1], STUDENT[2],
                                    TEAM[2], TEAM[4]]
        app.save(update_fields=['results_change_notes'])
        data = AdminApplicationDetailSerializer(ScholarshipApplication.objects.get(pk=app.pk)).data
        self.assertEqual(data['results_change_notes'], STUDENT)
        # the stored notes are kept, every one of them
        self.assertEqual(len(ScholarshipApplication.objects.get(pk=app.pk).results_change_notes), 8)

    def test_no_notes_serves_an_empty_list(self):
        self.assertEqual(cockpit_notes(None), [])
        self.assertEqual(cockpit_notes([]), [])
        self.assertEqual(cockpit_notes(TEAM), [])
