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
import logging
import os
import tempfile
import traceback
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.utils.crypto import salted_hmac

from apps.scholarship import verdict_context as vc
from apps.scholarship.eval.replay import child, guards, parent, scrub

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
BASE_SETTINGS = 'halatuju.settings.base'


def _restore_settings_modules(test):
    """After the test (and after its environment patches end): the base settings, then the replay
    settings, reloaded under the ambient environment, so no other test file sees a made-up value."""
    test.addCleanup(importlib.reload, importlib.import_module(REPLAY_SETTINGS))
    test.addCleanup(importlib.reload, importlib.import_module(BASE_SETTINGS))


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
        _restore_settings_modules(self)

    def _load(self, env):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': 'should-not-survive', **env}):
            if ENV not in env:
                os.environ.pop(ENV, None)
            base = importlib.reload(importlib.import_module(BASE_SETTINGS))     # the value really arrives
            self.assertEqual(base.GEMINI_API_KEY, 'should-not-survive')
            return importlib.reload(importlib.import_module(REPLAY_SETTINGS))

    def _assert_every_other_secret_is_blank(self, mod):
        words = ('KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'DSN', 'CREDENTIAL')
        names = [n for n in vars(mod) if n.isupper() and any(w in n for w in words)]
        self.assertIn('GEMINI_API_KEY', names)
        self.assertEqual(mod.GEMINI_API_KEY, '')
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

    def test_exactly_empty_is_blank(self):
        self.assertEqual(getattr(self._load({ENV: ''}), SETTING), '')

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


# --- the review notes, closed (LL5 B1 fix round) ------------------------------------------------

#: A made-up SECRET_KEY that "slipped" into the job's environment.
ENV_SECRET_KEY = 'made-up-ll5-env-secret-key-never-real-9876543210zyxwvu'
#: The base settings' own default when SECRET_KEY is absent.
BASE_DEFAULT_SECRET_KEY = 'django-insecure-dev-key-change-in-production'
REPLAY_URL = 'postgresql://replay_ro.abcdefgh:pw-not-real@pooler.example.test:5432/postgres'
INSTANT = '2026-11-20T18:00:00+00:00'
#: Made-up values for names `halatuju.settings.base` really reads from the environment.
MADE_UP_ENV = {
    'SECRET_KEY': ENV_SECRET_KEY,
    'GEMINI_API_KEY': 'made-up-gemini-key-aaaa1111',
    'OPENAI_API_KEY': 'made-up-openai-key-bbbb2222',
    'SUPABASE_JWT_SECRET': 'made-up-jwt-secret-cccc3333',
    'SUPABASE_SERVICE_ROLE_KEY': 'made-up-service-role-dddd4444',
    'TWILIO_AUTH_TOKEN': 'made-up-twilio-token-eeee5555',
    'CRON_SECRET': 'made-up-cron-secret-ffff6666',
    'CRON_SECRET_MONEY': 'made-up-cron-money-gggg7777',
    'VIRCLE_AIRTABLE_SECRET': 'made-up-airtable-hhhh8888',
}
#: Secret-like settings no base setting has today, put into the base module by hand: an exemption by a
#: pattern (any name starting VERDICT_ or REPLAY_, or holding FINGERPRINT or DERIVED) lets one through.
CANARIES = {
    'VERDICT_MADE_UP_API_KEY': 'made-up-canary-verdict-iiii9999',
    'VERDICT_FINGERPRINT_MADE_UP_SECRET': 'made-up-canary-fingerprint-jjjj0000',
    'REPLAY_MADE_UP_TOKEN': 'made-up-canary-replay-kkkk1212',
    'MADE_UP_DERIVED_KEY': 'made-up-canary-derived-llll3434',
}
SECRET_WORDS = ('KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'DSN', 'CREDENTIAL')
REPLAY_KEY_MESSAGE = 'replay: REPLAY_FINGERPRINT_KEY must be 64 hex characters'


def _load_replay(test, env, canaries=None):
    """(base, replay settings): the base settings reloaded under ``env`` (so the values REALLY arrive
    there), the ``canaries`` put into the base module, then the replay settings reloaded. ``env``
    without the key variable means it is absent. Every change is undone after the test, in order:
    canaries out, environment back, base reloaded, replay reloaded (the reloads once per test, LAST, so
    a test that loads several times reloads under the ambient environment only)."""
    if not getattr(test, '_settings_restore_registered', False):
        _restore_settings_modules(test)
        test._settings_restore_registered = True
    patcher = mock.patch.dict(os.environ, env)
    patcher.start()
    test.addCleanup(patcher.stop)
    if ENV not in env:
        os.environ.pop(ENV, None)
    base = importlib.reload(importlib.import_module(BASE_SETTINGS))
    for name, value in (canaries or {}).items():
        setattr(base, name, value)
        test.addCleanup(delattr, base, name)
    return base, importlib.reload(importlib.import_module(REPLAY_SETTINGS))


def _pieces(key):
    """Every 16-character piece of ``key``, lower case."""
    return [key[i:i + 16].lower() for i in range(len(key) - 15)]


class TheBlankingIsReallyTested(SimpleTestCase):
    """The made-up secrets REALLY arrive in the base settings, and none survives in the replay's."""

    def test_every_secret_like_setting_is_blank_but_the_two_named(self):
        key = KEYS[1]
        base, mod = _load_replay(self, dict(MADE_UP_ENV, **{ENV: key}), CANARIES)
        arrived = (base.SECRET_KEY, base.GEMINI_API_KEY, base.OPENAI_API_KEY, base.SUPABASE_JWT_SECRET,
                   base.SUPABASE_SERVICE_ROLE_KEY, base.TWILIO_AUTH_TOKEN, base.CRON_SECRET,
                   base.CRON_FAMILY_SECRETS['money'], base.VIRCLE_AIRTABLE_SECRET)
        self.assertEqual(arrived, (
            'made-up-ll5-env-secret-key-never-real-9876543210zyxwvu', 'made-up-gemini-key-aaaa1111',
            'made-up-openai-key-bbbb2222', 'made-up-jwt-secret-cccc3333', 'made-up-service-role-dddd4444',
            'made-up-twilio-token-eeee5555', 'made-up-cron-secret-ffff6666', 'made-up-cron-money-gggg7777',
            'made-up-airtable-hhhh8888'))
        names = [n for n in vars(mod) if n.isupper() and any(w in n for w in SECRET_WORDS)]
        for required in ('GEMINI_API_KEY', 'OPENAI_API_KEY', 'SUPABASE_JWT_SECRET', 'SUPABASE_SERVICE_ROLE_KEY',
                         'TWILIO_AUTH_TOKEN', 'CRON_SECRET', 'CRON_FAMILY_SECRETS', 'VIRCLE_AIRTABLE_SECRET',
                         *CANARIES):
            self.assertIn(required, names)
        for name in names:
            if name in ('SECRET_KEY', SETTING):
                continue
            value = getattr(mod, name)
            if isinstance(value, str):
                self.assertEqual(value, '', name)
            elif isinstance(value, dict):
                self.assertEqual(set(value.values()) - {''}, set(), name)
        self.assertEqual(mod.CRON_FAMILY_SECRETS,
                         {'money': '', 'paid': '', 'email': '', 'maintenance': ''})
        self.assertRegex(mod.SECRET_KEY, r'^[0-9a-f]{64}$')
        self.assertNotIn(mod.SECRET_KEY, (ENV_SECRET_KEY, BASE_DEFAULT_SECRET_KEY, key))
        self.assertEqual(getattr(mod, SETTING), 'c0ffee1500d15ea5ec0ffee1500d15ea5ec0ffee1500d15ea5eba5eba11c0de0')
        made_up = [v.lower() for v in (*MADE_UP_ENV.values(), *CANARIES.values())]
        for name in [n for n in vars(mod) if n.isupper() and n != SETTING]:
            text = repr(getattr(mod, name)).lower()
            for piece in _pieces(key):
                self.assertNotIn(piece, text, name)            # the key is held under ONE name only
            for value in made_up:
                self.assertNotIn(value, text, name)


class TheReplaysSecretKeyIsNeverTheEnvironments(SimpleTestCase):
    """Even past the guard (which refuses a SECRET_KEY in the job's environment first), the replay's
    settings never adopt one: the base settings read it, the replay's SECRET_KEY stays the throwaway."""

    def test_a_secret_key_in_the_environment_is_not_the_replays(self):
        base, mod = _load_replay(self, {'SECRET_KEY': ENV_SECRET_KEY})
        self.assertEqual(base.SECRET_KEY, 'made-up-ll5-env-secret-key-never-real-9876543210zyxwvu')
        self.assertNotEqual(mod.SECRET_KEY, 'made-up-ll5-env-secret-key-never-real-9876543210zyxwvu')
        self.assertRegex(mod.SECRET_KEY, r'^[0-9a-f]{64}$')
        for name in [n for n in vars(mod) if n.isupper()]:
            self.assertNotIn(ENV_SECRET_KEY, repr(getattr(mod, name)), name)


class AMangledKeyIsLoud(SimpleTestCase):
    """Absent or exactly '' is blank; whitespace only is a mangled key, and the settings refuse."""

    def test_whitespace_only_refuses_without_the_value(self):
        for value in ('\n', ' ', ' \t', '　', '\xa0', '\r\n', '\t'):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ImproperlyConfigured) as caught:
                    _load_replay(self, {ENV: value})
                self.assertEqual(str(caught.exception), 'replay: REPLAY_FINGERPRINT_KEY must be 64 hex characters')
                for text in _texts(caught.exception):
                    self.assertNotIn(repr(value), text)
                for ch in set(value) - {' '}:
                    self.assertNotIn(ch, str(caught.exception))
                    self.assertNotIn(ch, repr(caught.exception))

    def test_absent_and_exactly_empty_stay_blank(self):
        self.assertEqual(getattr(_load_replay(self, {})[1], SETTING), '')
        self.assertEqual(getattr(_load_replay(self, {ENV: ''})[1], SETTING), '')


class _CatchEveryRecord:
    """Every log record of every logger at every level, DEBUG included, while the block runs: no level,
    `disabled` flag or `logging.disable` can hide one. Nothing is emitted."""

    def __init__(self, test):
        self.records = []
        records = self.records
        for patcher in (mock.patch.object(logging.Logger, 'isEnabledFor', lambda self, level: True),
                        mock.patch.object(logging.Logger, 'handle', lambda self, record: records.append(record))):
            patcher.start()
            test.addCleanup(patcher.stop)

    def texts(self):
        out = []
        for record in self.records:
            try:
                message = record.getMessage()
            except Exception:                          # a bad format string still counts as text
                message = ''
            out.append((repr(vars(record)) + message).lower())
        return out


class TheKeyNeverReachesALogOrTheEnvironment(SimpleTestCase):
    def test_no_record_at_any_level_holds_a_piece_of_the_key(self):
        key = KEYS[1]
        catch = _CatchEveryRecord(self)
        logging.getLogger('apps.scholarship.verdict_context').debug('made-up probe')   # the catch works
        with override_settings(SECRET_KEY=DUMMY_SECRET, **{SETTING: key}):
            vc.key_check()
            vc._keyed_hash('made-up message')
            _pinned_fingerprint()
        _load_replay(self, {ENV: key})
        self.assertIn('made-up probe', catch.texts()[0])
        for text in catch.texts():
            for piece in _pieces(key):
                self.assertNotIn(piece, text)

    def test_the_helper_and_the_settings_never_write_the_key_into_the_environment(self):
        key = KEYS[1]
        before = dict(os.environ)
        with override_settings(SECRET_KEY=DUMMY_SECRET, **{SETTING: key}):
            vc.key_check()
            _pinned_fingerprint()
        self.assertEqual(dict(os.environ), before)
        expected = dict(before, **{ENV: key})
        _load_replay(self, {ENV: key})
        self.assertEqual(dict(os.environ), expected)            # only the variable it was given holds it
        for name, value in os.environ.items():
            if name != ENV:
                for piece in _pieces(key):
                    self.assertNotIn(piece, value.lower(), name)


#: Secrets beyond ASCII, and a SECRET_KEY_FALLBACKS list, with the setting absent (the live service).
NON_ASCII_SECRET = 'made-up-sécret-ünïcode-ключ-秘密-✓-0000'
LONG_SECRET = 'made-up-long-secret-' * 40
FALLBACK_SECRET = 'made-up-ll5-secret-with-fallbacks-0000000000'
FALLBACKS = ['made-up-old-fallback-key-1111111111', 'made-up-older-fallback-2222222222']
EQ_MESSAGE = '{"made":"up","ü":[1,2]}'
#: (key_check(), _keyed_hash(EQ_MESSAGE)) captured by running verdict_context AS IT WAS at 26bbc39c5 (the
#: commit before the key work; it called salted_hmac itself): rebuilt in a scratch copy with
#: `git show 26bbc39c5:halatuju_api/apps/scholarship/verdict_context.py`, loaded beside this tree under
#: the same override_settings, and its output pasted here.
HEAD_EQUIVALENCE = {
    'non_ascii': ('8382faf0', '7262494d0eefea3182619dcc3241297caaadcb4ce098fd8d16fa686af1cc1ed3'),
    'long': ('076ecff7', '558f54080fc7bb83a7bcba7a047af64436f8e193d128ab8b86361e876479346f'),
    'fallbacks': ('76c5c765', '370cdf75469d0cf659981f1490eb00f071144820c7d197a4d8f0e6e0d9e8a189'),
}


class TheLiveServiceDoesNotMoveBeyondAscii(SimpleTestCase):
    def test_non_ascii_long_and_fallback_secrets_give_the_values_of_26bbc39c5(self):
        self.assertFalse(NON_ASCII_SECRET.isascii())
        self.assertEqual(len(LONG_SECRET), 800)
        cases = (('non_ascii', NON_ASCII_SECRET, {}), ('long', LONG_SECRET, {}),
                 ('fallbacks', FALLBACK_SECRET, {'SECRET_KEY_FALLBACKS': FALLBACKS}))
        for name, secret, extra in cases:
            with self.subTest(name=name), override_settings(SECRET_KEY=secret, **extra):
                self.assertFalse(hasattr(settings, SETTING))
                got = (vc.key_check(), vc._keyed_hash(EQ_MESSAGE))
                self.assertEqual(got, HEAD_EQUIVALENCE[name])
                self.assertEqual(got[1], salted_hmac(SALT, EQ_MESSAGE, algorithm='sha256').hexdigest())
                self.assertEqual(got[1], salted_hmac(SALT, EQ_MESSAGE, secret=secret, algorithm='sha256').hexdigest())
                self.assertEqual(got[0], salted_hmac(SALT, 'verdict_context key check', secret=secret,
                                                     algorithm='sha256').hexdigest()[:8])


class ASetButFalsySettingRefuses(SimpleTestCase):
    def test_falsy_values_that_are_not_blank_text_raise(self):
        for falsy in (0, False, [], b'', 0.0, (), {}):
            with self.subTest(falsy=repr(falsy)), override_settings(SECRET_KEY=MADE_UP_SECRET, **{SETTING: falsy}):
                with self.assertRaises(ImproperlyConfigured):
                    vc.key_check()


class TheJobRefusesSecretKey(SimpleTestCase):
    """`guards.check_environment` refuses SECRET_KEY by its exact name, never quoting the value, in the
    parent (before Django) and in each child."""

    def test_the_check_refuses_secret_key_by_name_never_value(self):
        for env in ({'SECRET_KEY': ENV_SECRET_KEY},
                    {guards.DB_ENV: REPLAY_URL, 'PATH': '/bin', ENV: KEYS[1], 'SECRET_KEY': ENV_SECRET_KEY}):
            with self.subTest(names=sorted(env)):
                with self.assertRaises(guards.WriteRefused) as caught:
                    guards.check_environment(env)
                self.assertEqual(str(caught.exception), 'replay: forbidden variables in the environment: SECRET_KEY')
                for text in _texts(caught.exception):
                    self.assertNotIn(ENV_SECRET_KEY, text)

    def test_without_it_the_check_passes_as_before(self):
        self.assertTrue(guards.check_environment({guards.DB_ENV: REPLAY_URL, 'PATH': '/bin', ENV: KEYS[1]}))
        self.assertTrue(guards.check_environment({guards.DB_ENV: REPLAY_URL, 'PATH': '/bin', 'GEMINI_API_KEY': ''}))

    def test_a_job_environment_with_secret_key_refuses_to_start(self):
        level = logging.root.manager.disable
        self.addCleanup(logging.disable, level)            # main() switches logging off
        env = {guards.DB_ENV: REPLAY_URL, 'PATH': os.environ.get('PATH', ''), 'SECRET_KEY': ENV_SECRET_KEY}
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(parent, 'setup_django', side_effect=AssertionError) as setup, \
                contextlib.redirect_stdout(buf):
            code = parent.main(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', tmp])
        self.assertEqual(code, 3)
        setup.assert_not_called()                          # refused before Django is set up
        self.assertEqual(json.loads(buf.getvalue()), {'event': 'fatal', 'error': 'WriteRefused'})
        self.assertNotIn(ENV_SECRET_KEY, buf.getvalue())

    def test_a_child_given_secret_key_refuses_to_start_and_child_env_never_passes_it(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(child, 'setup_django', side_effect=AssertionError) as setup:
            out = os.path.join(tmp, 'old.jsonl')
            code = child.main(['--side', 'old', '--instant', INSTANT, '--months', '2026-11,2026-12', '--out', out],
                              env={guards.DB_ENV: REPLAY_URL, 'SECRET_KEY': ENV_SECRET_KEY})
            with open(out, encoding='utf-8') as fh:
                text = fh.read()
        self.assertEqual(code, 3)
        setup.assert_not_called()
        self.assertEqual(json.loads(text), {'side': 'old', 'event': 'fatal', 'error': 'WriteRefused'})
        self.assertNotIn(ENV_SECRET_KEY, text)
        given = parent.child_env({'SECRET_KEY': ENV_SECRET_KEY, guards.DB_ENV: REPLAY_URL}, '/r', '/h')
        self.assertNotIn('SECRET_KEY', given)
        self.assertNotIn(ENV_SECRET_KEY, repr(given))
