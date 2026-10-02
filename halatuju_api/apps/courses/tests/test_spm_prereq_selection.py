"""TD-069 — the STPM path's SPM prerequisites survive a logout/login (Now sprint 4, 2026-10-02).

v2.21.0 gave the main SPM flow a durable `elective_subjects`. The STPM results page enters SPM
prerequisites through a separate subsystem whose grades (`spm_prereq_grades`) were accepted by the
sync but never SENT by the web app, and whose elective picks lived only in the browser. This pins
the server half: the sync accepts and stores the three things the form needs to rebuild itself —
the grades, which keys are electives, and the stream pill — and the profile GET serves them back.
The aliran picks are deliberately NOT stored: they are the grades minus the four compulsory
subjects minus the electives (the web form derives them; see `stpm-grades/page.test.tsx`).

Also pinned here: the profile GET serves `results_exam_type` (TD-218). The web's results-held
reader and its login hydrate were written against that key, and it was never on the payload.
"""
import pytest
from django.test import RequestFactory

from apps.courses.models import StudentProfile
from apps.courses.views import ProfileSyncView, ProfileView

PREREQ = {'bm': 'A', 'eng': 'A', 'hist': 'B+', 'math': 'A', 'phy': 'A', 'ekonomi': 'A-', 'poa': 'B'}


def _sync(data, user_id):
    request = RequestFactory().post('/api/v1/profile/sync/', data=data, content_type='application/json')
    request.user_id = user_id
    request.data = data
    return ProfileSyncView().post(request)


def _get(user_id):
    request = RequestFactory().get('/api/v1/profile/')
    request.user_id = user_id
    return ProfileView().get(request)


@pytest.mark.django_db
class TestTheStpmPathPersists:
    def test_sync_stores_the_grades_the_electives_and_the_stream(self):
        response = _sync({'exam_type': 'stpm', 'spm_prereq_grades': PREREQ,
                          'spm_elective_subjects': ['ekonomi', 'poa'], 'spm_stream': 'science'},
                         'stpm-prereq-1')
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='stpm-prereq-1')
        assert p.spm_prereq_grades == PREREQ
        assert p.spm_elective_subjects == ['ekonomi', 'poa']
        assert p.spm_stream == 'science'
        # the main SPM flow's field is a DIFFERENT record and is not touched
        assert p.elective_subjects == []

    def test_seven_electives_are_kept(self):
        seven = ['ekonomi', 'poa', 'geo', 'business', 'b_tamil', 'b_cina', 'lukisan']
        assert _sync({'spm_elective_subjects': seven}, 'stpm-prereq-7').status_code == 200
        assert StudentProfile.objects.get(
            supabase_user_id='stpm-prereq-7').spm_elective_subjects == seven

    def test_the_get_serves_it_all_back(self):
        StudentProfile.objects.create(
            supabase_user_id='stpm-prereq-get', exam_type='stpm', results_exam_type='stpm',
            stpm_grades={'PA': 'A'}, stpm_cgpa=3.5, spm_prereq_grades=PREREQ,
            spm_elective_subjects=['ekonomi', 'poa'], spm_stream='technical')
        data = _get('stpm-prereq-get').data
        assert data['spm_prereq_grades'] == PREREQ
        assert data['spm_elective_subjects'] == ['ekonomi', 'poa']
        assert data['spm_stream'] == 'technical'
        assert data['results_exam_type'] == 'stpm'
        assert data['results_held'] == 'stpm'

    def test_the_get_serves_the_server_answer_for_the_form_six_explorer(self):
        # Review F1: the web reads THIS, so the apply form and the review card cannot disagree.
        StudentProfile.objects.create(supabase_user_id='stpm-explorer-get', exam_type='stpm',
                                      grades={'bm': 'A', 'eng': 'A'})
        data = _get('stpm-explorer-get').data
        assert data['exam_type'] == 'stpm'          # what she is heading for, untouched
        assert data['results_held'] == 'spm'        # what she holds

    def test_a_profile_that_never_entered_any_reads_empty(self):
        StudentProfile.objects.create(supabase_user_id='stpm-prereq-none', exam_type='spm')
        data = _get('stpm-prereq-none').data
        assert data['spm_elective_subjects'] == []
        assert data['spm_stream'] == ''
        assert data['results_exam_type'] == ''
        assert data['results_held'] == 'spm'


@pytest.mark.django_db
class TestTheShapeIsChecked:
    def test_duplicates_and_blanks_are_dropped(self):
        _sync({'spm_elective_subjects': ['poa', ' poa ', '', 'geo']}, 'stpm-prereq-dup')
        assert StudentProfile.objects.get(
            supabase_user_id='stpm-prereq-dup').spm_elective_subjects == ['poa', 'geo']

    @pytest.mark.parametrize('bad', ['ekonomi', {'ekonomi': 'A'}, [1, 2], ['DROP TABLE x;'],
                                     [f'subject_{i}' for i in range(21)]])
    def test_anything_but_a_list_of_subject_keys_is_refused(self, bad):
        response = _sync({'spm_elective_subjects': bad}, 'stpm-prereq-bad')
        assert response.status_code == 400
        assert 'spm_elective_subjects' in response.data

    def test_an_unreadable_stream_label_is_dropped_not_fatal(self):
        # Failing the whole sync over a pill label would lose the student's grades with it.
        response = _sync({'spm_stream': 'Sains / Sastera', 'spm_prereq_grades': PREREQ},
                         'stpm-prereq-stream')
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='stpm-prereq-stream')
        assert p.spm_stream == ''
        assert p.spm_prereq_grades == PREREQ

    def test_a_25_character_stream_label_is_dropped_not_fatal(self):
        # Review F3: the model's max_length=20 used to run FIRST and 400 the whole sync.
        response = _sync({'spm_stream': 'a' * 25, 'spm_prereq_grades': PREREQ}, 'stpm-prereq-25')
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='stpm-prereq-25')
        assert p.spm_stream == ''
        assert p.spm_prereq_grades == PREREQ

    def test_bad_prereq_cells_are_dropped_and_the_rest_kept(self):
        # Review F4: a non-SPM grade or a non-key subject loses that cell, never the others.
        _sync({'spm_prereq_grades': {**PREREQ, 'Bad Key': 'A', 'geo': 'Z', 'bio': 'A+'}},
              'stpm-prereq-cells')
        assert StudentProfile.objects.get(
            supabase_user_id='stpm-prereq-cells').spm_prereq_grades == {**PREREQ, 'bio': 'A+'}

    @pytest.mark.parametrize('bad', [['bm', 'A'], 'A', {f's{i}': 'A' for i in range(21)}])
    def test_prereq_grades_of_the_wrong_shape_are_refused(self, bad):
        response = _sync({'spm_prereq_grades': bad}, 'stpm-prereq-shape')
        assert response.status_code == 400
        assert 'spm_prereq_grades' in response.data
