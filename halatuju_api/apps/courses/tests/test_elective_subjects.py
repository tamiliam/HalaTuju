"""Elective-subjects storage + merit invariance under many electives.

Covers the v2.21 fix: `StudentProfile.elective_subjects` persists *which* SPM
subjects are electives (so the grades form survives logout/login), and the cap
rose 2 -> 7. The merit engine is unchanged — Sec3 still scores only the best 2
electives — so this guards that more electives don't change the formula.
"""
import pytest
from django.test import RequestFactory, SimpleTestCase

from apps.courses.engine import prepare_merit_inputs
from apps.courses.models import StudentProfile
from apps.courses.views import ProfileSyncView


class TestMeritInvariantUnderManyElectives(SimpleTestCase):
    def test_sec3_picks_best_two_of_five_electives(self):
        grades = {
            'bm': 'A', 'eng': 'A', 'math': 'A', 'history': 'A',   # core
            'phy': 'A', 'chem': 'A',                              # stream
            'ekonomi': 'A+', 'poa': 'B', 'geo': 'A', 'business': 'C', 'b_tamil': 'A+',
        }
        _sec1, sec2, sec3 = prepare_merit_inputs(grades, stream_subjects=['phy', 'chem'])
        self.assertEqual(sorted(sec2), ['A', 'A'])         # the 2 stream subjects
        self.assertEqual(sorted(sec3), ['A+', 'A+'])       # best 2 of the 5 electives

    def test_sec3_always_two_even_with_seven_electives(self):
        grades = {'bm': 'A', 'eng': 'A', 'math': 'A', 'history': 'A', 'phy': 'A', 'chem': 'A'}
        for i, g in enumerate(['A+', 'A', 'A-', 'B+', 'B', 'C', 'D']):  # 7 electives
            grades[f'elec{i}'] = g
        _sec1, _sec2, sec3 = prepare_merit_inputs(grades, stream_subjects=['phy', 'chem'])
        self.assertEqual(len(sec3), 2)
        self.assertEqual(sorted(sec3), ['A', 'A+'])        # the two best of the seven


@pytest.mark.django_db
class TestElectiveSubjectsSync:
    def _sync_request(self, data, user_id='elec-user'):
        request = RequestFactory().post('/api/v1/profile/sync/', data=data, content_type='application/json')
        request.user_id = user_id
        request.data = data
        return request

    def test_sync_persists_elective_subjects(self):
        request = self._sync_request({
            'grades': {'bm': 'A', 'eng': 'A', 'math': 'A', 'history': 'A',
                       'phy': 'A', 'chem': 'A', 'ekonomi': 'A', 'poa': 'B'},
            'stream_subjects': ['phy', 'chem'],
            'elective_subjects': ['ekonomi', 'poa'],
        })
        response = ProfileSyncView().post(request)
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='elec-user')
        assert p.elective_subjects == ['ekonomi', 'poa']
        # the elective grades are kept in the grades dict too (not just the selection)
        assert 'ekonomi' in p.grades and 'poa' in p.grades

    def test_sync_accepts_seven_electives(self):
        electives = ['ekonomi', 'poa', 'geo', 'business', 'b_tamil', 'b_cina', 'lukisan']
        request = self._sync_request({
            'grades': {'bm': 'A', **{s: 'A' for s in electives}},
            'elective_subjects': electives,
        }, user_id='elec-7')
        response = ProfileSyncView().post(request)
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='elec-7')
        assert p.elective_subjects == electives          # all 7 persisted

    def test_elective_subjects_defaults_empty(self):
        request = self._sync_request({'grades': {'bm': 'A'}}, user_id='elec-none')
        ProfileSyncView().post(request)
        p = StudentProfile.objects.get(supabase_user_id='elec-none')
        assert p.elective_subjects == []                 # absent -> default, no crash
