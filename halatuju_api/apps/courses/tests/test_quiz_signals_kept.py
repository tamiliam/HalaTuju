"""Request #81 (case 513): a sign-in must never wipe a saved interest quiz.

The path that did it: a browser that signed in before the quiz cached the server's `{}`, the STPM
quiz saved real answers under its own browser key, and the next sign-in sync sent `{}` back up.
These tests drive the real sync and PUT doors (`ProfileUpdateSerializer`) with that payload.
"""
import pytest
from django.test import RequestFactory

from apps.courses.models import StudentProfile
from apps.courses.quiz_signals import has_answers, keep_saved
from apps.courses.views import ProfileSyncView

SAVED = {'field_interest': {'field_engineering': 2}, 'work_preference_signals': {}}
RETAKE = {'field_interest': {'field_health': 3}, 'work_preference_signals': {}}
ALL_EMPTY = {'field_interest': {}, 'work_preference_signals': {}}


def _sync(data, user_id='quiz-kept-user'):
    request = RequestFactory().post('/api/v1/profile/sync/', data=data,
                                    content_type='application/json')
    request.user_id = user_id
    request.data = data
    return ProfileSyncView().post(request)


def _saved_profile(user_id='quiz-kept-user', signals=SAVED):
    return StudentProfile.objects.create(supabase_user_id=user_id, student_signals=signals)


def test_has_answers():
    assert has_answers(SAVED)
    assert not has_answers({})
    assert not has_answers(None)
    assert not has_answers(ALL_EMPTY)
    assert not has_answers([])


def test_keep_saved_rule():
    assert keep_saved(SAVED, {}) == SAVED
    assert keep_saved(SAVED, ALL_EMPTY) == SAVED
    assert keep_saved(SAVED, RETAKE) == RETAKE        # a set with answers always wins
    assert keep_saved({}, {}) == {}                   # nothing saved: nothing to protect
    # review round 1: the gate reads `bool(signals)`, so a saved all-empty set is a DONE quiz there;
    # an incoming `{}` (or None) must never flip it back, and a retake with answers still saves
    assert keep_saved(ALL_EMPTY, {}) == ALL_EMPTY
    assert keep_saved(ALL_EMPTY, None) == ALL_EMPTY
    assert keep_saved(ALL_EMPTY, RETAKE) == RETAKE


@pytest.mark.django_db
class TestSignInSyncKeepsTheQuiz:
    def test_empty_signals_from_a_stale_browser_do_not_wipe(self):
        _saved_profile()
        assert _sync({'student_signals': {}, 'gender': 'female'}).status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='quiz-kept-user')
        assert p.student_signals == SAVED
        assert p.gender == 'female'                   # the rest of the sync still lands

    def test_all_empty_categories_do_not_wipe(self):
        _saved_profile()
        _sync({'student_signals': ALL_EMPTY})
        assert StudentProfile.objects.get(supabase_user_id='quiz-kept-user').student_signals == SAVED

    def test_a_retake_still_saves(self):
        _saved_profile()
        _sync({'student_signals': RETAKE})
        assert StudentProfile.objects.get(supabase_user_id='quiz-kept-user').student_signals == RETAKE

    def test_missing_signals_leave_the_saved_set(self):
        _saved_profile()
        _sync({'gender': 'male'})
        assert StudentProfile.objects.get(supabase_user_id='quiz-kept-user').student_signals == SAVED

    def test_first_quiz_is_stored_on_a_blank_profile(self):
        _saved_profile(signals={})
        _sync({'student_signals': SAVED})
        assert StudentProfile.objects.get(supabase_user_id='quiz-kept-user').student_signals == SAVED


@pytest.mark.django_db
class TestTheQuizEndpointNeverStoresAnEmptySet:
    """Review round 1: `_persist_quiz_signals` reads `has_answers`, not truthiness, so a quiz that
    yields only empty categories never overwrites a saved set; one with answers still saves."""

    def _persist(self, signals, user_id='quiz-kept-user'):
        from types import SimpleNamespace

        from apps.courses.views.quiz import _persist_quiz_signals
        _persist_quiz_signals(SimpleNamespace(user_id=user_id, supabase_user={}), signals)
        return StudentProfile.objects.get(supabase_user_id=user_id).student_signals

    def test_a_quiz_with_no_answered_signal_keeps_the_saved_set(self):
        _saved_profile()
        assert self._persist(ALL_EMPTY) == SAVED
        assert self._persist({}) == SAVED

    def test_a_quiz_with_answers_saves(self):
        _saved_profile()
        assert self._persist(RETAKE) == RETAKE

    def test_the_sync_keeps_a_saved_all_empty_set(self):
        _saved_profile(signals=ALL_EMPTY)
        _sync({'student_signals': {}})
        assert StudentProfile.objects.get(supabase_user_id='quiz-kept-user').student_signals == ALL_EMPTY
