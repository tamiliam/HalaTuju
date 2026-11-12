"""C2 pins: banned_phrases / unknown_placeholders / render, as each caller sees them.

Written BEFORE the three copies were collapsed onto one home (code health `dup`), so the move
is proved to change nothing.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship import email_templates, partner_comms, sponsor_comms


class C2PinTests(SimpleTestCase):
    def test_engine_unknown_placeholders(self):
        self.assertEqual(email_templates.unknown_placeholders({'a'}, 'x {a} {b} {c}', None), ('b', 'c'))
        self.assertEqual(email_templates.unknown_placeholders(None, '{z}'), ('z',))

    def test_engine_banned_phrases(self):
        self.assertEqual(email_templates.banned_phrases(('foo', 'bar'), 'FOO', 'x'), ('foo',))
        self.assertEqual(email_templates.banned_phrases(None, 'foo'), ())

    def test_partner_unknown_placeholders(self):
        self.assertEqual(partner_comms.unknown_placeholders('no_such_kind', '{x} {y}'), ('x', 'y'))
        self.assertEqual(partner_comms.unknown_placeholders('invite_admin', '{access}', '{zzz}'), ('zzz',))

    def test_sponsor_unknown_placeholders(self):
        self.assertEqual(sponsor_comms.unknown_placeholders('no_such_kind', '{x}'), ('x',))
        self.assertEqual(sponsor_comms.unknown_placeholders('welcome', '{zzz}'), ('zzz',))

    def test_family_banned_phrases(self):
        self.assertEqual(partner_comms.banned_phrases('Act now', 'your students'),
                         ('act now', 'your students'))
        self.assertEqual(sponsor_comms.banned_phrases('tax deductible', 'your child'),
                         ('tax deductible', 'your child'))
        self.assertEqual(partner_comms.banned_phrases('your child'), ())
        self.assertEqual(sponsor_comms.banned_phrases('students you send'), ())

    def test_family_render_thin_context(self):
        for mod, kinds in ((partner_comms, partner_comms.PLACEHOLDERS), (sponsor_comms, sponsor_comms.PLACEHOLDERS)):
            for kind, tokens in kinds.items():
                body = '\n\n'.join('{%s}' % t for t in sorted(tokens))
                tpl = SimpleNamespace(subject='S ' + ' '.join('{%s}' % t for t in sorted(tokens)), body=body)
                out = mod.render(kind, tpl, {})
                self.assertEqual(len(out), 3)
                self.assertEqual(out, mod.render(kind, tpl, {}))
                for part in out[:2]:
                    for t in mod.STRUCTURAL_TOKENS:
                        self.assertNotIn('{%s}' % t, part)
