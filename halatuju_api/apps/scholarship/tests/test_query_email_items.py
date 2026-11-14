"""SUP1 (2026-11-14): the "a few things we need" email names each open item by its title, recounts
just before it sends, sends nothing at 0, replies to the support address, and the reminder has its
own subject. ONE helper (`services.query_items`) counts for both the raised email and the reminder.
"""
import json
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship.emails import student_queries as sq
from apps.scholarship.emails.shared import _P
from apps.scholarship.models import ResolutionItem
from apps.scholarship.services import send_due_query_emails, send_query_reminders
from apps.scholarship.services import query_items
from apps.scholarship.services.query_item_titles import (
    GENERIC, PLACEHOLDER_FREE, SENSITIVE_CODES, SENSITIVE_MARKERS, TEAM_QUESTION, TITLES)
from apps.scholarship.tests.factories import make_application

_SYNC = 'apps.scholarship.check2_queries.sync_check2_queries'
_BIRTH_EN = 'Upload your birth certificate'
_TRANSPORT_EN = 'How do you get to your studies?'


class _Base(TestCase):
    def setUp(self):
        mail.outbox = []
        self.app = make_application(
            'profile_complete', notify_email='p@example.com', locale='en',
            profile_completed_at=timezone.now() - timedelta(hours=3))

    def _item(self, **kw):
        base = dict(application=self.app, fact='other', status='open')
        base.update(kw)
        return ResolutionItem.objects.create(**base)

    def _doc(self, code='birth_cert_missing', **kw):
        return self._item(source='system', code=code, kind='doc', **kw)

    def _clarify(self, code='transport_cost_unknown', **kw):
        return self._item(source='check2', code=code, kind='clarify', **kw)

    def _officer(self, prompt='Please send your latest utility bill.', **kw):
        return self._item(source='officer', code='officer_1', kind='doc', prompt=prompt, **kw)


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestRaisedEmailListsTitles(_Base):
    def test_every_open_item_is_named_by_its_title_and_the_count_matches(self):
        self._doc()
        self._clarify()
        self._officer()
        with patch(_SYNC, return_value=[]):
            self.assertEqual(send_due_query_emails()['sent'], 1)
        [msg] = mail.outbox
        for title in (_BIRTH_EN, _TRANSPORT_EN, TEAM_QUESTION[0]):
            self.assertIn(f'- {title}', msg.body)
        self.assertNotIn('utility bill', msg.body)          # a reviewer's own words never go out
        self.assertIn('These 3 items are waiting', msg.body)
        self.assertIn('Action Centre always shows the latest list', msg.body)
        self.assertNotIn('proceed with what we have', msg.body)

    def test_reply_to_is_the_support_address(self):
        self._doc()
        with patch(_SYNC, return_value=[]):
            send_due_query_emails()
        self.assertEqual(mail.outbox[0].reply_to, [_P.email_support])

    def test_a_cancelled_or_resolved_or_reviewer_only_item_is_not_counted_or_named(self):
        self._doc()                                               # the one live item
        self._clarify(status='waived')                            # the reviewer waived it
        self._doc('ic_missing', status='resolved')                # she already did it
        self._item(source='check2', code='sibling_level_unknown', kind='human')   # hidden from her
        with patch(_SYNC, return_value=[]):
            send_due_query_emails()
        [msg] = mail.outbox
        self.assertIn('more from you. 1 item is waiting', msg.body)
        self.assertNotIn('This 1', msg.body)
        self.assertIn(_BIRTH_EN, msg.body)
        self.assertNotIn('Upload your IC', msg.body)
        self.assertNotIn(_TRANSPORT_EN, msg.body)

    def test_the_recount_is_taken_after_the_sync_so_a_cleared_item_is_not_mailed(self):
        item = self._doc()

        def _cleared(app):                       # the sync auto-resolves it a moment before the send
            ResolutionItem.objects.filter(pk=item.pk).update(status='resolved')
            return []
        with patch(_SYNC, side_effect=_cleared):
            self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertEqual(mail.outbox, [])
        self.app.refresh_from_db()
        self.assertIsNone(self.app.query_raised_notified_at)      # not stamped: a later item still reaches her

    def test_nothing_open_sends_nothing(self):
        with patch(_SYNC, return_value=[]):
            self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertEqual(mail.outbox, [])

    def test_the_sender_itself_sends_nothing_for_an_empty_list(self):
        self.assertFalse(sq.send_query_raised_email('p@example.com', 'Priya', 'B40', 0, titles=[]))
        self.assertFalse(sq.send_query_reminder_email('p@example.com', 'Priya', 'B40', 0, 2, titles=[]))
        self.assertEqual(mail.outbox, [])


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestReminder(_Base):
    def setUp(self):
        super().setUp()
        # The sweep now syncs first (as the raised sweep does); hold the sync still so these tests
        # see only the items they made.
        patcher = patch(_SYNC, return_value=[])
        self.sync = patcher.start()
        self.addCleanup(patcher.stop)

    def _due(self, item):
        ResolutionItem.objects.filter(pk=item.pk).update(created_at=timezone.now() - timedelta(days=3))
        self.app.profile_completed_at = timezone.now() - timedelta(days=3)
        self.app.save()

    def test_the_reminder_has_its_own_subject_and_lists_titles_and_replies_to_support(self):
        self._due(self._clarify())
        self._doc()
        self.assertEqual(send_query_reminders()['reminded'], 1)
        [msg] = mail.outbox
        self.assertEqual(msg.subject, sq.QUERY_REMINDER_SUBJECTS['en'].format(programme=self.app.cohort.name))
        self.assertNotEqual(msg.subject, sq.QUERY_RAISED_SUBJECTS['en'].format(programme=self.app.cohort.name))
        for lang in ('en', 'ms', 'ta'):
            self.assertNotEqual(sq.QUERY_REMINDER_SUBJECTS[lang], sq.QUERY_RAISED_SUBJECTS[lang])
        self.assertIn(f'- {_TRANSPORT_EN}', msg.body)
        self.assertIn(f'- {_BIRTH_EN}', msg.body)
        self.assertIn('reminder', msg.body.lower())
        self.assertIn('Action Centre always shows the latest list', msg.body)
        self.assertNotIn('proceed with what we have', msg.body)
        self.assertEqual(msg.reply_to, [_P.email_support])

    def test_the_reminder_and_the_raised_email_count_the_same_way(self):
        """The reminder used to count open CLARIFY items only; with a document request open as well
        it said 1 while the raised email said 2."""
        self._due(self._clarify())
        self._doc()
        self.assertEqual(len(query_items.open_items_for_email(self.app)), 2)
        send_query_reminders()
        self.assertIn('2 items are still waiting', mail.outbox[0].body)

    def test_the_reminder_sends_nothing_and_does_not_stamp_when_nothing_is_open(self):
        item = self._clarify()
        self._due(item)
        with patch.object(query_items, 'open_student_items', return_value=[]):   # cleared just before
            self.assertEqual(send_query_reminders()['reminded'], 0)
        self.assertEqual(mail.outbox, [])
        self.app.refresh_from_db()
        self.assertIsNone(self.app.query_reminder_at)

    def test_the_reminder_syncs_before_it_recounts_so_an_answered_item_is_not_mailed(self):
        live = self._clarify()
        done = self._doc()
        self._due(live)

        def _cleared(app):                       # she answered it; the sync closes it just before
            ResolutionItem.objects.filter(pk=done.pk).update(status='resolved')
            return []
        self.sync.side_effect = _cleared
        send_query_reminders()
        self.sync.assert_called_once()
        self.assertIn('1 item is still waiting', mail.outbox[0].body)
        self.assertNotIn(_BIRTH_EN, mail.outbox[0].body)

    def test_a_sync_that_fails_skips_that_application_and_the_sweep_goes_on(self):
        self._due(self._clarify())
        other = make_application(
            'profile_complete', notify_email='q@example.com', locale='en',
            profile_completed_at=timezone.now() - timedelta(days=3))
        ResolutionItem.objects.create(application=other, fact='other', status='open',
                                      source='check2', kind='clarify',
                                      code='transport_cost_unknown')
        ResolutionItem.objects.filter(application=other).update(
            created_at=timezone.now() - timedelta(days=3))
        bad = self.app.pk

        def _sync(app):
            if app.pk == bad:
                raise RuntimeError('bad data')
            return []
        self.sync.side_effect = _sync
        self.assertEqual(send_query_reminders()['reminded'], 1)
        self.assertEqual(self.sync.call_count, 2)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.query_reminder_at)

    def test_a_cancelled_item_is_not_counted_in_the_reminder(self):
        live = self._clarify()
        self._clarify('device_status_unknown', status='waived')
        self._due(live)
        send_query_reminders()
        self.assertIn('1 item is still waiting', mail.outbox[0].body)
        self.assertNotIn('Do you have a device', mail.outbox[0].body)


class TestOtherSendersReplyToSupport(SimpleTestCase):
    def test_request_info_also_replies_to_support(self):
        mail.outbox = []
        self.assertTrue(sq.send_request_info_email('p@example.com', 'Priya', 'B40', 'your IC'))
        self.assertEqual(mail.outbox[0].reply_to, [_P.email_support])


class TestTitlesInEveryLanguage(TestCase):
    """Fake sample items, rendered as the recipient would read them."""

    def _render(self, lang, send):
        mail.outbox = []
        send(lang)
        return mail.outbox[0]

    def test_the_two_emails_name_the_items_in_en_ms_ta(self):
        items = [ResolutionItem(source='system', code='birth_cert_missing', kind='doc'),
                 ResolutionItem(source='check2', code='transport_cost_unknown', kind='clarify')]
        for lang in ('en', 'ms', 'ta'):
            titles = [query_items.item_title(i, lang) for i in items]
            self.assertEqual(titles, [TITLES['birth_cert_missing'][('en', 'ms', 'ta').index(lang)],
                                      TITLES['transport_cost_unknown'][('en', 'ms', 'ta').index(lang)]])
            raised = self._render(lang, lambda lg: sq.send_query_raised_email(
                'p@example.com', 'Priya', 'B40', 2, lang=lg, titles=titles))
            reminder = self._render(lang, lambda lg: sq.send_query_reminder_email(
                'p@example.com', 'Priya', 'B40', 2, 3, lang=lg, titles=titles))
            for msg in (raised, reminder):
                for t in titles:
                    self.assertIn(f'- {t}', msg.body)
                self.assertEqual(msg.reply_to, [_P.email_support])
            self.assertNotEqual(raised.subject, reminder.subject)

    def test_tamil_copy_has_no_wrong_alphabet_characters(self):
        text = ''.join(sq.QUERY_RAISED_BODIES['ta'] + sq.QUERY_REMINDER_BODIES['ta']
                        + sq.QUERY_RAISED_SUBJECTS['ta'] + sq.QUERY_REMINDER_SUBJECTS['ta']
                        + ''.join(t[2] for t in TITLES.values()) + GENERIC[2] + TEAM_QUESTION[2])
        self.assertNotIn('٘', text)          # lesson 295: the look-alike mark a scripted write leaves
        stray = {c for c in text if ord(c) > 127 and not (0x0B80 <= ord(c) <= 0x0BFF)
                 and c not in '—–…’‘“”‌‍ '}
        self.assertEqual(stray, set())


class TestTitleHelper(SimpleTestCase):
    def test_unknown_code_is_a_generic_title_never_a_key_or_blank(self):
        item = ResolutionItem(source='check2', code='brand_new_code', kind='clarify')
        self.assertEqual(query_items.item_title(item, 'en'), GENERIC[0])
        self.assertEqual(query_items.item_title(item, 'ms'), GENERIC[1])

    def test_an_unknown_language_reads_english(self):
        item = ResolutionItem(source='system', code='ic_missing', kind='doc')
        self.assertEqual(query_items.item_title(item, 'fr'), TITLES['ic_missing'][0])

    def test_a_subject_placeholder_is_filled_from_params_or_drops_to_generic(self):
        item = ResolutionItem(source='check2', code='academic_grade_mismatch', kind='confirm',
                              params={'subject': 'Sejarah'})
        self.assertEqual(query_items.item_title(item, 'en'), 'Check your grade for Sejarah')
        bare = ResolutionItem(source='check2', code='academic_grade_mismatch', kind='confirm')
        self.assertEqual(query_items.item_title(bare, 'en'), GENERIC[0])

    def test_an_officer_item_is_the_plain_team_title_never_its_prompt(self):
        item = ResolutionItem(source='officer', code='officer_3', kind='doc',
                              prompt='Send the page with your father\'s name.\nThen tell us why.')
        for idx, lang in enumerate(('en', 'ms', 'ta')):
            self.assertEqual(query_items.item_title(item, lang), TEAM_QUESTION[idx])

    def test_a_private_item_is_the_plain_team_title_in_every_language(self):
        for code in ('deceased_parent_detail', 'str_not_current', 'father_income_proof_missing',
                     'sibling_tertiary_funding', 'guardianship_letter_missing'):
            item = ResolutionItem(source='check2', code=code, kind='clarify')
            for idx, lang in enumerate(('en', 'ms', 'ta')):
                self.assertEqual(query_items.item_title(item, lang), TEAM_QUESTION[idx], code)

    def test_every_private_code_is_a_real_code(self):
        self.assertEqual(SENSITIVE_CODES - set(TITLES), set())    # a typo would silently leak

    def test_every_code_in_a_private_family_is_on_the_private_list(self):
        """Review round: STR, EPF, an earner's IC and a sibling's details were split, some private
        and some not. A code in one of those families (new ones too) must be listed."""
        leaks = [c for c in TITLES if any(m in c for m in SENSITIVE_MARKERS)
                 and c not in SENSITIVE_CODES]
        self.assertEqual(leaks, [])
        for code in ('brother_ic_for_str_missing', 'father_epf_missing', 'str_needs_recipient_ic',
                     'earner_ic_missing', 'high_utility_expense_str'):
            self.assertIn(code, SENSITIVE_CODES)

    def test_no_placeholder_survives_in_any_title(self):
        for code, row in TITLES.items():
            if code in PLACEHOLDER_FREE:
                for t in row:
                    self.assertNotIn('{', t, code)


class TestTitlesMatchTheActionCentreCopy(SimpleTestCase):
    """The app paints titles from the web message files; this Python copy must not drift."""
    _DIR = Path(__file__).resolve().parents[4] / 'halatuju-web' / 'src' / 'messages'

    def _items(self, lang):
        path = self._DIR / f'{lang}.json'
        self.assertTrue(path.exists(), f'{path} missing: the web tree must sit beside the api')
        data = json.loads(path.read_text(encoding='utf-8'))
        return data['scholarship']['actionCentre']['item']

    def test_every_title_equals_the_message_file_and_none_is_missing(self):
        for idx, lang in enumerate(('en', 'ms', 'ta')):
            items = self._items(lang)
            self.assertEqual(set(TITLES), set(items), lang)
            for code, row in TITLES.items():
                if code in PLACEHOLDER_FREE:
                    self.assertTrue(re.search(r'\{\w+\}', items[code]['title']), code)
                    continue
                self.assertEqual(row[idx], items[code]['title'], f'{lang}.{code}')


class TestTheWording(SimpleTestCase):
    """Owner-approved copy (2026-11-14): no "reply to this email", real plurals, and the pure Tamil
    word for "latest"."""
    _BODIES = (sq.QUERY_RAISED_BODIES, sq.QUERY_REMINDER_BODIES)

    def test_no_body_invites_a_reply_or_says_item_s(self):
        for bodies in self._BODIES:
            for lang, body in bodies.items():
                for gone in ('reply to this', 'balas sahaja', 'மின்னஞ்சலுக்குப் பதிலளி', '(s)', '(கள்)'):
                    self.assertNotIn(gone, body, f'{lang}: {gone}')

    def test_the_tamil_bodies_say_anmaiya(self):
        for bodies in self._BODIES:
            self.assertIn('அண்மைய', bodies['ta'])
            self.assertNotIn('சமீபத்திய', bodies['ta'])

    def test_one_item_and_one_day_read_singular(self):
        mail.outbox = []
        sq.send_query_reminder_email('p@example.com', 'Priya', 'B40', 1, 1, titles=['X'])
        sq.send_query_reminder_email('p@example.com', 'Priya', 'B40', 1, 1, lang='ta', titles=['X'])
        sq.send_query_raised_email('p@example.com', 'Priya', 'B40', 1, lang='ta', titles=['X'])
        en, ta_rem, ta_raised = (m.body for m in mail.outbox)
        self.assertIn('1 item is still waiting', en)
        self.assertIn('within about 1 day:', en)
        self.assertIn('1 விவரம் உங்கள்', ta_rem)
        self.assertIn('காத்திருக்கிறது:', ta_rem)
        self.assertIn('1 நாளுக்குள்', ta_rem)
        self.assertIn('காத்திருக்கிறது:', ta_raised)

    def test_many_items_and_days_read_plural(self):
        mail.outbox = []
        sq.send_query_reminder_email('p@example.com', 'Priya', 'B40', 2, 3, lang='ta', titles=['X', 'Y'])
        sq.send_query_reminder_email('p@example.com', 'Priya', 'B40', 2, 3, titles=['X', 'Y'])
        ta, en = (m.body for m in mail.outbox)
        self.assertIn('2 விவரங்கள்', ta)
        self.assertIn('காத்திருக்கின்றன:', ta)
        self.assertIn('3 நாட்களுக்குள்', ta)
        self.assertIn('within about 3 days:', en)
