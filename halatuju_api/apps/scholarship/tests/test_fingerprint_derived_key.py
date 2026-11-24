"""LL5: the replay recomputes evidence fingerprints with a ONE-WAY DERIVED key, never ``SECRET_KEY``.

`verdict_context._fingerprint_key` takes the derived key (`sha256(salt + SECRET_KEY)`, 64 hex) from the
setting `VERDICT_FINGERPRINT_DERIVED_KEY` when it is set, and otherwise derives it from ``SECRET_KEY``
exactly as Django's `salted_hmac` does, so the live service's fingerprints do not move. The replay's
settings carry the derived key from `REPLAY_FINGERPRINT_KEY` and nothing else, and the scrubber never lets
it out. Made-up keys only: no real secret anywhere in this file."""
import contextlib
import datetime
import hashlib
import importlib
import io
import json
import os
import traceback
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.utils.crypto import salted_hmac

from apps.scholarship import verdict_context as vc
from apps.scholarship.eval.replay import scrub

#: The salt, written out here (not read from the module), so a changed salt fails this file.
SALT = 'halatuju.scholarship.verdict_context.evidence_fingerprint'
#: A made-up "real" secret and the values captured with it by running the code AS IT WAS AT HEAD
#: 26bbc39c5 (before this change, `salted_hmac` itself): `key_check()` and `_pinned_fingerprint()`.
MADE_UP_SECRET = 'made-up-ll5-secret-key-not-real-0123456789abcdefghijklmn'
HEAD_KEY_CHECK = '5bdbc603'
HEAD_FINGERPRINT = '2145b4d3b7753d52942c7ad27c05e7d77217cecbc9121edd7dc04e89fdaaabfd'
#: The secret of `test_verdict_context.test_the_canonical_form_is_pinned` and its pinned key check.
PINNED_SECRET = 'made-up-key-for-the-pinned-fingerprint-0000000000'
PINNED_KEY_CHECK = 'cad1960c'
DUMMY_SECRET = 'made-up-dummy-secret-the-replay-throwaway-0000000000'
SETTING = 'VERDICT_FINGERPRINT_DERIVED_KEY'
ENV = 'REPLAY_FINGERPRINT_KEY'
REPLAY_SETTINGS = 'apps.scholarship.eval.replay.settings'


def _derived(secret):
    """The derived key, computed here with hashlib (never with the code under test)."""
    return hashlib.sha256(SALT.encode('utf-8') + secret.encode('utf-8')).hexdigest()


def _pinned_fingerprint():
    """The fixed input the HEAD values were captured with."""
    row = {c: '' for c in vc._DOC_COLUMNS}
    row.update(id=11, doc_type='payslip', household_member='father', verification_status='verified',
               vision_fields={'authenticity': {'status': 'genuine', 'model_version': '2.1.0'}},
               uploaded_at=datetime.datetime(2026, 5, 6, 7, 8, 9, tzinfo=datetime.timezone.utc),
               vision_fields_run_at=None, vision_run_at=None)
    declared = dict({name: None for name in vc.DECLARED_FIELDS}, **{vc.MOVED_TO_HIGHER: [3]})
    declared['income_route'] = 'salary'
    profile = {name: None for name in vc.PROFILE_FIELDS}
    intake = dict({name: None for name in vc.INTAKE_FIELDS}, cohort_id=4)
    stage = {'submitted_year': 2026, 'pre_submit_status': None, 'in_review_status': True,
             'decided_status': False}
    return vc.evidence_fingerprint([row], declared, profile, intake, stage)


class TheDerivedKeyGivesTheSameHashes(SimpleTestCase):
    def test_the_salt_is_the_one_written_here(self):
        self.assertEqual(vc._KEY_SALT, SALT)

    def test_the_derived_key_matches_djangos_salted_hmac(self):
        secrets_ = ('made-up-secret-one', 'made-up-sécret-two-ünicode', 'x' * 120, 'short')
        messages = ('', 'verdict_context key check', '{"a":1,"b":[2,3]}', 'ünïcode ✓', 'y' * 500)
        for secret in secrets_:
            for message in messages:
                expected = salted_hmac(SALT, message, secret=secret, algorithm='sha256').hexdigest()
                for given in (_derived(secret), _derived(secret).upper()):
                    with self.subTest(secret=secret, message=message), \
                            override_settings(SECRET_KEY=DUMMY_SECRET, **{SETTING: given}):
                        self.assertEqual(vc._keyed_hash(message), expected)

    def test_key_check_and_fingerprint_under_the_derived_key_equal_the_secret_keys(self):
        with override_settings(SECRET_KEY=DUMMY_SECRET, **{SETTING: _derived(MADE_UP_SECRET)}):
            self.assertEqual((vc.key_check(), _pinned_fingerprint()), (HEAD_KEY_CHECK, HEAD_FINGERPRINT))
        with override_settings(SECRET_KEY=DUMMY_SECRET, **{SETTING: _derived(PINNED_SECRET)}):
            self.assertEqual(vc.key_check(), PINNED_KEY_CHECK)


class TheLiveServiceDoesNotMove(SimpleTestCase):
    @override_settings(SECRET_KEY=MADE_UP_SECRET)
    def test_no_setting_gives_the_values_of_head(self):
        self.assertFalse(hasattr(settings, SETTING))        # the main settings never define it
        self.assertEqual(vc.key_check(), HEAD_KEY_CHECK)
        self.assertEqual(_pinned_fingerprint(), HEAD_FINGERPRINT)

    def test_a_blank_setting_is_the_same_as_none(self):
        for blank in ('', '   ', None):
            with self.subTest(blank=blank), override_settings(SECRET_KEY=MADE_UP_SECRET, **{SETTING: blank}):
                self.assertEqual((vc.key_check(), _pinned_fingerprint()), (HEAD_KEY_CHECK, HEAD_FINGERPRINT))

    def test_the_replays_key_free_default_mismatches(self):
        """Blank setting + the replay's throwaway SECRET_KEY: a different key check, so nothing compares."""
        with override_settings(SECRET_KEY=DUMMY_SECRET, **{SETTING: ''}):
            self.assertNotEqual(vc.key_check(), HEAD_KEY_CHECK)
            self.assertNotEqual(_pinned_fingerprint(), HEAD_FINGERPRINT)


#: Set but bad: 63, 65, not hex, a newline, a space, raw bytes, hex as bytes, numbers, a list.
BAD_VALUES = ('ab' * 31 + 'c', 'ab' * 32 + 'c', 'zq' * 32, 'ab' * 32 + '\n', ' ' + 'ab' * 32,
              'ab' * 16 + ' ' + 'ab' * 16, b'\xab' * 32, b'ab' * 32, 987654321, 3.25, True, ['ab' * 32])


def _texts(exc):
    return (str(exc), repr(exc), ''.join(traceback.format_exception(exc)))


class ABadSettingRefuses(SimpleTestCase):
    def test_a_bad_setting_raises_and_never_falls_back_or_quotes_the_value(self):
        for bad in BAD_VALUES:
            with self.subTest(bad=bad), override_settings(SECRET_KEY=MADE_UP_SECRET, **{SETTING: bad}):
                with self.assertRaises(ImproperlyConfigured) as caught:
                    vc.key_check()
                shown = str(bad).strip() if not isinstance(bad, bytes) else bad.hex()
                for text in _texts(caught.exception):
                    self.assertNotIn(shown, text)
                    self.assertNotIn(repr(bad), text)
                    self.assertNotIn('abababab', text)


class TheReplaySettings(SimpleTestCase):
    """The job's settings carry the derived key from the environment and nothing else."""

    def setUp(self):
        self.addCleanup(self._load, {})

    def _load(self, env):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': 'should-not-survive', **env}):
            if ENV not in env:
                os.environ.pop(ENV, None)
            return importlib.reload(importlib.import_module(REPLAY_SETTINGS))

    def _assert_every_other_secret_is_blank(self, mod):
        words = ('KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'DSN', 'CREDENTIAL')
        names = [n for n in vars(mod) if n.isupper() and any(w in n for w in words)]
        self.assertIn('GEMINI_API_KEY', names)
        for name in names:
            value = getattr(mod, name)
            if name in ('SECRET_KEY', SETTING):
                continue
            if isinstance(value, str):
                self.assertEqual(value, '', name)
            elif isinstance(value, dict):
                self.assertEqual(set(value.values()) - {''}, set(), name)

    def test_absent_is_blank(self):
        mod = self._load({})
        self.assertEqual(getattr(mod, SETTING), '')
        self._assert_every_other_secret_is_blank(mod)

    def test_blank_is_blank(self):
        for blank in ('', '  '):
            with self.subTest(blank=blank):
                self.assertEqual(getattr(self._load({ENV: blank}), SETTING), '')

    def test_a_valid_value_is_carried_and_secret_key_stays_the_throwaway(self):
        for given in ('ab' * 32, 'C0FFEE15' * 8):
            with self.subTest(given=given):
                mod = self._load({ENV: given})
                self.assertEqual(getattr(mod, SETTING), given)
                self.assertNotIn(mod.SECRET_KEY.lower(), (given.lower(), ''))
                self.assertEqual(len(mod.SECRET_KEY), 64)
                self._assert_every_other_secret_is_blank(mod)

    def test_a_bad_value_refuses_to_load_without_quoting_it(self):
        for bad in ('ab' * 31 + 'c', 'ab' * 32 + 'c', 'zq' * 32, 'ab' * 32 + '\n', 'ab' * 16 + '-' + 'ab' * 16):
            with self.subTest(bad=bad):
                with self.assertRaises(ImproperlyConfigured) as caught:
                    self._load({ENV: bad})
                for text in _texts(caught.exception):
                    self.assertNotIn(bad.strip(), text)
                    self.assertNotIn('abababab', text)
                    self.assertNotIn('zqzqzqzq', text)

    def test_loading_prints_nothing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self._load({ENV: 'ab' * 32})
        self.assertEqual(out.getvalue(), '')


#: Made-up derived keys: one with letters only in its hex, one with digits.
KEYS = ('ab' * 32, 'c0ffee1500d15ea5e' * 3 + 'ba5eba11c0de0')


class TheKeyNeverLeavesTheJob(SimpleTestCase):
    """The scrubber's allow-list hashes any text it does not know, and drops bytes, so the key cannot
    leave in a report line under any key, in either case, whole or as raw bytes."""

    def setUp(self):
        for patcher in (mock.patch.object(scrub, '_REGISTERED', set()),
                        mock.patch.dict(scrub._STATE, frozen=False)):      # engine_map froze it on import
            patcher.start()
            self.addCleanup(patcher.stop)
        scrub.register_codes(('status', 'unresolved', 'eligible_courses', 'amount'))

    def _assert_absent(self, key, line):
        text = json.dumps(line).lower()
        for i in range(len(key) - 15):
            self.assertNotIn(key[i:i + 16].lower(), text)

    def test_the_key_is_hashed_or_dropped_in_every_slot(self):
        self.assertEqual(len(KEYS[1]), 64)
        for key in KEYS:
            for given in (key, key.upper(), bytes.fromhex(key), key.encode('ascii')):
                records = (
                    {'status': given}, {'unresolved': [given, {'status': given}]},
                    {'eligible_courses': [given]}, {'amount': given}, {'key': given},
                    {'event': 'start', 'old_commit': given, 'new_commit': given},
                    {'error': given}, {'event': 'fatal', 'error': given}, {'fields': {'value': given}},
                )
                for rec in records:
                    with self.subTest(key=key, given=given, rec=sorted(rec)):
                        line = scrub.scrub(rec)
                        self._assert_absent(key, line)
                        self.assertGreater(scrub.count_dropped(line), 0)
                if isinstance(given, str):
                    self._assert_absent(key, scrub.scrub({given: 'status'}))       # as a dict key
                    self.assertFalse(scrub.is_code(given))

    def test_an_exception_leaves_as_its_class_name_only(self):
        for key in KEYS:
            line = scrub.scrub(scrub.error_record(ValueError(f'replay: bad {key}')))
            self.assertEqual(line, {'error': 'ValueError'})

    def test_hashing_under_the_key_prints_and_logs_nothing(self):
        out = io.StringIO()
        with override_settings(SECRET_KEY=DUMMY_SECRET, **{SETTING: KEYS[1]}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), \
                self.assertNoLogs('apps.scholarship.verdict_context'):
            check = vc.key_check()
        self.assertEqual(out.getvalue(), '')
        self.assertRegex(check, r'^[0-9a-f]{8}$')
