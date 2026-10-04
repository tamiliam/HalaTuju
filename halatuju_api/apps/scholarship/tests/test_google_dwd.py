"""TD-125 (2026-10-03): the Workspace delegation credentials have ONE home, `google_dwd`, and they
are keyless (the runtime identity signs as the DWD account through IAM). TD-329 (2026-10-04)
deleted the old key path; `test_the_key_path_is_gone` keeps it gone.

No network: `google.auth.default` and `google.auth.iam.Signer` are patched, and the callers'
tests patch `google_dwd.dwd_credentials` itself.
"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import google_dwd, meeting, sheets

DWD_SA = 'halatuju-meet@example-project.iam.gserviceaccount.com'
ORGANISER = 'organiser@example.org'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']


@override_settings(MEET_ORGANISER_EMAIL=ORGANISER)
class TestWhichPathIsChosen(SimpleTestCase):

    @override_settings(GOOGLE_DWD_SERVICE_ACCOUNT=DWD_SA)
    def test_keyless_when_the_service_account_email_is_set(self):
        source = mock.Mock(name='runtime-identity')
        with mock.patch('google.auth.default', return_value=(source, 'proj')) as default, \
                mock.patch('google.auth.iam.Signer') as signer_cls, \
                mock.patch('google.oauth2.service_account.Credentials') as creds_cls:
            creds = google_dwd.dwd_credentials(SCOPES)
        default.assert_called_once_with(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        # The signer signs AS the DWD account, authenticated by the runtime identity.
        args = signer_cls.call_args.args
        self.assertIs(args[1], source)
        self.assertEqual(args[2], DWD_SA)
        creds_cls.assert_called_once_with(
            signer_cls.return_value, DWD_SA, 'https://oauth2.googleapis.com/token',
            scopes=SCOPES, subject=ORGANISER)
        self.assertIs(creds, creds_cls.return_value)

    def test_the_real_keyless_credentials_carry_subject_scopes_and_signer(self):
        """Unpatched `service_account.Credentials`: proves the installed google-auth accepts the
        (signer, email, token_uri, scopes=, subject=) shape — no network until a refresh."""
        signer = mock.Mock(key_id=None)
        with override_settings(GOOGLE_DWD_SERVICE_ACCOUNT=DWD_SA), \
                mock.patch('google.auth.default', return_value=(mock.Mock(), 'p')), \
                mock.patch('google.auth.iam.Signer', return_value=signer):
            creds = google_dwd.dwd_credentials(SCOPES)
        self.assertEqual(creds.service_account_email, DWD_SA)
        self.assertEqual(creds.signer, signer)
        self.assertEqual(list(creds.scopes), SCOPES)
        self.assertEqual(creds._subject, ORGANISER)

    @override_settings(GOOGLE_DWD_SERVICE_ACCOUNT='')
    def test_none_and_unavailable_when_not_set(self):
        with mock.patch('google.auth.default') as default:
            self.assertIsNone(google_dwd.dwd_credentials(SCOPES))
        default.assert_not_called()
        self.assertFalse(google_dwd.dwd_available())

    def test_available_only_on_the_keyless_setting(self):
        with override_settings(GOOGLE_DWD_SERVICE_ACCOUNT=DWD_SA):
            self.assertTrue(google_dwd.dwd_available())
        with override_settings(GOOGLE_DWD_SERVICE_ACCOUNT='   '):
            self.assertFalse(google_dwd.dwd_available(), 'whitespace is not a configuration')
        # TD-329: a key setting left behind in some environment configures nothing.
        with override_settings(GOOGLE_DWD_SERVICE_ACCOUNT='', GOOGLE_MEET_SA_JSON='{"type": "x"}'):
            self.assertFalse(google_dwd.dwd_available())
            with mock.patch('google.auth.default') as default:
                self.assertIsNone(google_dwd.dwd_credentials(SCOPES))
            default.assert_not_called()

    @override_settings(GOOGLE_DWD_SERVICE_ACCOUNT=DWD_SA)
    def test_a_broken_runtime_identity_RAISES_so_the_caller_can_tell_failed_from_empty(self):
        """The helper never swallows: each caller's own try/except owns best-effort (TD-242)."""
        import google.auth.exceptions
        with mock.patch('google.auth.default',
                        side_effect=google.auth.exceptions.DefaultCredentialsError('none')):
            with self.assertRaises(google.auth.exceptions.DefaultCredentialsError):
                google_dwd.dwd_credentials(SCOPES)


@override_settings(GOOGLE_DWD_SERVICE_ACCOUNT=DWD_SA, MEET_ORGANISER_EMAIL=ORGANISER)
class TestEveryCallerGoesThroughTheHelper(SimpleTestCase):
    """Each credential site asks the helper for EXACTLY the scopes it asked for before TD-125.
    ⚠ sheets.py's two scope lists are the owner's least-privilege rule — do not simplify."""

    def _build(self):
        return mock.patch('googleapiclient.discovery.build', return_value=mock.Mock())

    @override_settings(INTERVIEW_MEET_ENABLED=True)
    def test_meeting_calendar_service(self):
        with mock.patch.object(google_dwd, 'dwd_credentials') as dwd, self._build():
            self.assertIsNotNone(meeting._calendar_service())
        dwd.assert_called_once_with(['https://www.googleapis.com/auth/calendar.events'])

    @override_settings(INTERVIEW_MEET_ENABLED=True)
    def test_meet_is_enabled_on_the_keyless_setting_alone(self):
        self.assertTrue(meeting.meet_enabled())
        with override_settings(GOOGLE_DWD_SERVICE_ACCOUNT=''):
            self.assertFalse(meeting.meet_enabled())

    @override_settings(VIRCLE_SHEET_ID='pinned-sheet')
    def test_sheets_services_pinned_asks_for_spreadsheets_only(self):
        with mock.patch.object(google_dwd, 'dwd_credentials') as dwd, self._build():
            drive, svc = sheets._services()
        dwd.assert_called_once_with([sheets._SHEETS_SCOPE])
        self.assertIsNone(drive)
        self.assertIsNotNone(svc)

    @override_settings(VIRCLE_SHEET_ID='')
    def test_sheets_services_unpinned_asks_for_spreadsheets_and_drive(self):
        with mock.patch.object(google_dwd, 'dwd_credentials') as dwd, self._build():
            sheets._services()
        dwd.assert_called_once_with([sheets._SHEETS_SCOPE, sheets._DRIVE_SCOPE])

    def test_drive_for_upload_asks_for_drive(self):
        with mock.patch.object(google_dwd, 'dwd_credentials') as dwd, self._build():
            self.assertIsNotNone(sheets._drive_for_upload())
        dwd.assert_called_once_with([sheets._DRIVE_SCOPE])

    def test_sheet_read_asks_for_spreadsheets(self):
        with mock.patch.object(google_dwd, 'dwd_credentials') as dwd, self._build():
            sheets._sheet_values_or_none('sheet-id', 'A1:B2')
        dwd.assert_called_once_with([sheets._SHEETS_SCOPE])

    def test_sheets_enabled_on_the_keyless_setting_alone(self):
        self.assertTrue(sheets.sheets_enabled())
        with override_settings(GOOGLE_DWD_SERVICE_ACCOUNT=''):
            self.assertFalse(sheets.sheets_enabled())

    def test_a_helper_failure_stays_best_effort_at_every_site(self):
        boom = mock.patch.object(google_dwd, 'dwd_credentials', side_effect=RuntimeError('iam'))
        with boom, override_settings(INTERVIEW_MEET_ENABLED=True, VIRCLE_SHEET_ID='x'):
            self.assertIsNone(meeting._calendar_service())
            self.assertEqual(sheets._services(), (None, None))
            self.assertIsNone(sheets._drive_for_upload())
            self.assertIsNone(sheets._sheet_values_or_none('sheet-id', 'A1:B2'),
                              'a failed read is None (a finding), never [] (TD-242)')

    def test_no_credential_build_is_left_outside_the_helper(self):
        """Positive + negative: the helper holds the one credential build, the callers hold none."""
        from apps.scholarship.tests.source_walk import API_ROOT, read_source
        why = 'TD-125: the DWD credentials have one home, apps/scholarship/google_dwd.py'
        helper = read_source(API_ROOT / 'apps/scholarship/google_dwd.py', why)
        self.assertEqual(helper.count('iam.Signer('), 1)
        for rel in ('apps/scholarship/meeting.py', 'apps/scholarship/sheets.py'):
            src = read_source(API_ROOT / rel, why)
            self.assertNotIn('service_account.Credentials', src, rel)
            self.assertGreaterEqual(src.count('google_dwd.dwd_credentials('), 1, rel)

    def test_the_key_path_is_gone(self):
        """TD-329 (2026-10-04): the env var and the GCP key are deleted, so the code that read
        them is too. No source under apps/ or halatuju/ may read the key setting or build
        credentials from key JSON again — a key is a secret we chose not to hold."""
        from apps.scholarship.tests.source_walk import API_ROOT, walk_sources
        why = 'TD-329: the DWD key path was deleted; credentials are keyless (google_dwd.py)'
        files = [f for root, floor in (('apps', 400), ('halatuju', 8))
                 for f in walk_sources(API_ROOT / root, '*.py', floor, why)
                 if 'tests' not in f.parts]
        for f in files:
            src = f.read_text(encoding='utf-8')
            self.assertNotIn("'GOOGLE_MEET_SA_JSON'", src, str(f))
            self.assertNotIn('from_service_account_info', src, str(f))
            self.assertNotIn('from_service_account_file', src, str(f))
