"""Code-health S1 #4 guardrail: the backend subject map must MIRROR the frontend's.

``academic_engine._SUBJECT_BM`` claims to mirror ``halatuju-web/src/lib/subjects.ts``
(``SUBJECT_NAMES``) — but nothing enforced it, and 64 keys the grades form offers had
drifted out (every arts/performance elective, all ``voc_*`` vocational subjects, the
Islamic-stream extras). A student who took one was told their slip was "missing" a
subject they'd already entered — an unfixable loop; their academic check could never
reach 'verified'.

This test parses subjects.ts directly (monorepo layout — the web repo sits beside
halatuju_api) and FAILS LOUDLY if it can't, rather than skipping: a silently-skipped
drift test is how the drift happened (lessons.md, Test Health Sprint).
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.scholarship.academic_engine import _SUBJECT_BM

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SUBJECTS_TS = _REPO_ROOT / 'halatuju-web' / 'src' / 'lib' / 'subjects.ts'


def _parse_subjects_ts():
    text = _SUBJECTS_TS.read_text(encoding='utf-8')
    names_block = text.split('SUBJECT_NAMES')[1].split('\n}')[0]
    subject_names = dict(re.findall(r"^\s*(\w+):\s*\{\s*bm:\s*'([^']+)'", names_block, re.M))
    spm_block = text.split('SPM_SUBJECTS')[1].split('\n]')[0]
    spm_ids = re.findall(r"\{\s*id:\s*'(\w+)'", spm_block)
    return subject_names, spm_ids


class TestSubjectDrift(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _SUBJECTS_TS.exists():
            raise AssertionError(
                f'subjects.ts not found at {_SUBJECTS_TS} — the drift guard needs the '
                f'monorepo layout. Do NOT convert this to a skip: a silently-skipped '
                f'drift test is how the 64-subject drift shipped.')
        cls.subject_names, cls.spm_ids = _parse_subjects_ts()

    def test_parse_sanity(self):
        # Guard the parser itself — if subjects.ts is restructured, fail here with a
        # clear message instead of "0 missing" false-greens below.
        self.assertGreater(len(self.subject_names), 100,
                           'SUBJECT_NAMES parse looks broken (too few keys)')
        self.assertGreater(len(self.spm_ids), 40,
                           'SPM_SUBJECTS parse looks broken (too few ids)')

    def test_every_web_subject_known_to_engine(self):
        missing = sorted(set(self.subject_names) - set(_SUBJECT_BM))
        self.assertEqual(missing, [],
                         f'subjects.ts keys unknown to academic_engine._SUBJECT_BM '
                         f'(a student picking one enters the "missing subject" loop): {missing}')

    def test_bm_names_match_exactly(self):
        # Same key, different BM string = the slip row and the profile subject will
        # normalise differently and never match.
        drifted = {k: (v, _SUBJECT_BM[k]) for k, v in self.subject_names.items()
                   if k in _SUBJECT_BM and v != _SUBJECT_BM[k]}
        self.assertEqual(drifted, {},
                         f'BM names drifted between subjects.ts and _SUBJECT_BM: {drifted}')

    def test_every_form_subject_resolves(self):
        # Web-internal coherence: every id the grades form offers must have a display
        # name (else the form shows a humanised raw key).
        unresolved = sorted(set(self.spm_ids) - set(self.subject_names))
        self.assertEqual(unresolved, [],
                         f'SPM_SUBJECTS ids missing from SUBJECT_NAMES: {unresolved}')

    def test_engine_only_keys_are_intentional(self):
        # Keys the engine knows but the web doesn't — should stay empty-ish; a growing
        # list means someone added to the engine side only (the mirror cuts both ways).
        engine_only = sorted(set(_SUBJECT_BM) - set(self.subject_names))
        self.assertEqual(engine_only, [],
                         f'_SUBJECT_BM keys absent from subjects.ts: {engine_only}')
