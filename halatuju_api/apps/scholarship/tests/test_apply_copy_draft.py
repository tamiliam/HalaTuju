"""Drafting a gift's Malay/Tamil apply copy from its own English (2026-09-10).

⚠⚠ THE CLAIM THESE TESTS EXIST TO HOLD: **it drafts, it never saves.** A gift's advertised
criteria decide who believes they may apply; the model proposes wording and a person publishes it.
`test_a_draft_NEVER_writes_to_the_gift` is the load-bearing one — if a later change makes this
endpoint persist, that fails.

⚠ THE SECOND CLAIM IS THE BULLET COUNT. Each bullet is one condition. A translation that merges
two or drops one changes the advertised bar in ONE language only, and `apply_copy.normalise` would
store it happily (all-or-nothing is per language, not per bullet). So a miscount is refused rather
than trusted.

Every test patches `_gemini_generate` — the single seam — so no run can make a billable call.
"""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import apply_copy_draft as acd
from apps.scholarship.tests.test_sabah_programme_screens import _Case

PROGRAMMES = '/api/v1/admin/scholarship/programmes/'

ENGLISH = {'en': {'title': 'Apply for the Sabah Bursary',
                  'intro': 'Support for Sabahan school leavers continuing to IPTA.',
                  'criteria': ['Resident in Sabah.',
                               'At least 5 A\'s in SPM.',
                               'Continuing to tertiary study this year.']}}

MALAY_REPLY = json.dumps({
    'title': 'Mohon Biasiswa Sabah',
    'intro': 'Bantuan untuk lepasan sekolah Sabah yang melanjutkan pengajian ke IPTA.',
    'criteria': ['Bermastautin di Sabah.',
                 'Sekurang-kurangnya 5A dalam SPM.',
                 'Melanjutkan pengajian ke peringkat tertiari tahun ini.'],
}, ensure_ascii=False)


def _draft_url(p, ):
    return f'{PROGRAMMES}{p.id}/apply-copy/draft/'


# ── The prompt (pure) ────────────────────────────────────────────────────────────────────────

class TestThePromptCarriesWhatMustNotDrift(TestCase):
    def test_it_names_the_exact_number_of_bullets_expected_back(self):
        prompt = acd.build_prompt(ENGLISH['en'], 'ms')
        self.assertIn('EXACTLY 3 strings', prompt)

    def test_it_refuses_to_let_a_qualification_name_be_translated(self):
        """"SPM" in Tamil words is unrecognisable against the certificate in the student's hand."""
        prompt = acd.build_prompt(ENGLISH['en'], 'ta')
        self.assertIn('SPM', prompt)
        self.assertIn('Keep these terms exactly as written', prompt)

    def test_tamil_carries_the_projects_own_style_rules_and_malay_does_not(self):
        self.assertIn('Tamil style rules', acd.build_prompt(ENGLISH['en'], 'ta'))
        self.assertNotIn('Tamil style rules', acd.build_prompt(ENGLISH['en'], 'ms'))

    def test_the_english_is_passed_verbatim_so_a_threshold_cannot_be_paraphrased_away(self):
        prompt = acd.build_prompt(ENGLISH['en'], 'ms')
        for line in ENGLISH['en']['criteria']:
            self.assertIn(line.replace("'", "'"), prompt)


# ── Parsing the reply (pure) ─────────────────────────────────────────────────────────────────

class TestTheReplyIsCheckedBeforeItIsOffered(TestCase):
    def test_a_clean_reply_parses(self):
        out = acd.parse_reply(MALAY_REPLY, 3)
        self.assertEqual(out['title'], 'Mohon Biasiswa Sabah')
        self.assertEqual(len(out['criteria']), 3)

    def test_a_fenced_reply_parses_because_models_wrap_json_in_backticks(self):
        out = acd.parse_reply(f'```json\n{MALAY_REPLY}\n```', 3)
        self.assertEqual(len(out['criteria']), 3)

    def test_A_MERGED_BULLET_IS_REFUSED(self):
        """⚠ The load-bearing count check: two conditions folded into one is a LOWER bar in Malay
        than in English, and nothing downstream would notice."""
        body = json.loads(MALAY_REPLY)
        body['criteria'] = [body['criteria'][0], body['criteria'][1] + ' ' + body['criteria'][2]]
        with self.assertRaises(acd.DraftError) as e:
            acd.parse_reply(json.dumps(body), 3)
        self.assertEqual(e.exception.code, 'bullet_count')

    def test_an_extra_bullet_is_refused_too(self):
        body = json.loads(MALAY_REPLY)
        body['criteria'].append('Satu syarat tambahan.')
        with self.assertRaises(acd.DraftError):
            acd.parse_reply(json.dumps(body), 3)

    def test_a_line_over_the_stored_limit_is_refused_rather_than_offered(self):
        """The tab would otherwise fill a box the SAVE refuses, leaving the reader to guess which."""
        body = json.loads(MALAY_REPLY)
        body['title'] = 'x' * (acd.ac.MAX_TITLE + 1)
        with self.assertRaises(acd.DraftError) as e:
            acd.parse_reply(json.dumps(body), 3)
        self.assertEqual(e.exception.code, 'draft_too_long')

    def test_angle_brackets_are_refused_because_the_save_would_refuse_them(self):
        body = json.loads(MALAY_REPLY)
        body['intro'] = 'Bantuan <b>istimewa</b>.'
        with self.assertRaises(acd.DraftError):
            acd.parse_reply(json.dumps(body), 3)

    def test_prose_instead_of_json_is_refused(self):
        with self.assertRaises(acd.DraftError) as e:
            acd.parse_reply('Here is your translation!', 3)
        self.assertEqual(e.exception.code, 'bad_reply')

    def test_a_blank_field_is_refused_because_a_half_block_cannot_be_saved(self):
        body = json.loads(MALAY_REPLY)
        body['intro'] = '   '
        with self.assertRaises(acd.DraftError):
            acd.parse_reply(json.dumps(body), 3)


# ── The endpoint ─────────────────────────────────────────────────────────────────────────────

class TestTheDraftEndpoint(_Case):
    def setUp(self):
        super().setUp()
        self.prog_a.apply_copy = dict(ENGLISH)
        self.prog_a.save(update_fields=['apply_copy'])

    @patch.object(acd, '_gemini_generate', return_value=MALAY_REPLY)
    def test_an_org_admin_drafts_malay_for_its_own_gift(self, _m):
        r = self._post(self.admin_a, _draft_url(self.prog_a), {'locale': 'ms'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['locale'], 'ms')
        self.assertEqual(r.json()['block']['title'], 'Mohon Biasiswa Sabah')

    @patch.object(acd, '_gemini_generate', return_value=MALAY_REPLY)
    def test_a_draft_NEVER_writes_to_the_gift(self, _m):
        """⚠⚠ THE RULE THIS WHOLE FEATURE RESTS ON. A machine must not be the last hand on the
        wording a public page advertises; the person presses Save."""
        self._post(self.admin_a, _draft_url(self.prog_a), {'locale': 'ms'})
        self.prog_a.refresh_from_db()
        self.assertNotIn('ms', self.prog_a.apply_copy)
        self.assertEqual(self.prog_a.apply_copy['en']['title'], ENGLISH['en']['title'])

    @patch.object(acd, '_gemini_generate', return_value=MALAY_REPLY)
    def test_another_tenants_gift_is_404_and_no_call_is_made(self, m):
        r = self._post(self.admin_a, _draft_url(self.prog_b), {'locale': 'ms'})
        self.assertEqual(r.status_code, 404)
        m.assert_not_called()

    @patch.object(acd, '_gemini_generate', return_value=MALAY_REPLY)
    def test_a_reviewer_may_not_spend_a_token(self, m):
        r = self._post(self.reviewer_a, _draft_url(self.prog_a), {'locale': 'ms'})
        self.assertIn(r.status_code, (403, 404))
        m.assert_not_called()

    @patch.object(acd, '_gemini_generate', return_value=MALAY_REPLY)
    def test_english_is_not_a_target_because_it_is_the_source(self, m):
        r = self._post(self.admin_a, _draft_url(self.prog_a), {'locale': 'en'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_locale')
        m.assert_not_called()

    @patch.object(acd, '_gemini_generate', return_value=MALAY_REPLY)
    def test_a_gift_with_no_english_is_refused_BEFORE_a_call_is_made(self, m):
        """⚠ Drafting from the PLATFORM default would translate another gift's criteria into this
        gift's Malay — a right-language falsehood, which `applyCopy.ts` exists to prevent."""
        self.prog_a.apply_copy = {}
        self.prog_a.save(update_fields=['apply_copy'])
        r = self._post(self.admin_a, _draft_url(self.prog_a), {'locale': 'ta'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'english_required')
        m.assert_not_called()

    @patch.object(acd, '_gemini_generate', side_effect=RuntimeError('upstream on fire'))
    def test_a_model_outage_is_one_readable_refusal_not_a_500(self, _m):
        r = self._post(self.admin_a, _draft_url(self.prog_a), {'locale': 'ms'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'ai_failed')

    @override_settings(GEMINI_API_KEY='')
    def test_no_key_configured_says_so_rather_than_crashing(self):
        r = self._post(self.admin_a, _draft_url(self.prog_a), {'locale': 'ms'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'ai_unconfigured')
