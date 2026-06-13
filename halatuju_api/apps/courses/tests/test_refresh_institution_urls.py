"""Tests for refresh_institution_urls — the authoritative-index URL refresher (pure logic)."""
from django.test import SimpleTestCase

from apps.courses.management.commands.refresh_institution_urls import (
    _subdomain, _norm_name, _parse_matrikulasi, _parse_polycc, build_proposals,
)


def _alive(url):
    return ('dead', 404) if 'dead' in url else ('alive', 200)


class HelpersTest(SimpleTestCase):
    def test_subdomain_drops_www(self):
        self.assertEqual(_subdomain('https://www.kmm.matrik.edu.my'), 'kmm')
        self.assertEqual(_subdomain('https://kmm.matrik.edu.my/'), 'kmm')

    def test_norm_name_strips_acronym_and_punct(self):
        self.assertEqual(_norm_name('Politeknik Ungku Omar (PUO)'), 'politeknik ungku omar')

    def test_parse_matrikulasi_keys_by_subdomain(self):
        m = _parse_matrikulasi([('x', 'http://www.kmm.matrik.edu.my'), ('y', 'https://kmns.matrik.edu.my'),
                                ('nav', 'https://moe.gov.my/x')])
        self.assertEqual(m, {'kmm': 'http://www.kmm.matrik.edu.my', 'kmns': 'https://kmns.matrik.edu.my'})

    def test_parse_polycc_keys_by_name_first_url(self):
        m = _parse_polycc([('Politeknik Ungku Omar (PUO)', 'https://www.puo.edu.my'),
                           ('Politeknik Merlimau', 'http://www.pmm.edu.my @ http://jhep.com'),
                           ('No link here', '')])
        self.assertEqual(m['politeknik ungku omar'], 'https://www.puo.edu.my')
        self.assertEqual(m['politeknik merlimau'], 'http://www.pmm.edu.my')  # took the first of "a @ b"
        self.assertNotIn('no link here', m)


class BuildProposalsSubdomainTest(SimpleTestCase):
    def setUp(self):
        self.insts = [
            ('kmm', 'KM Melaka', 'https://kmm.matrik.edu.my'),       # differs from index → canonicalise
            ('kms', 'KM Selangor', 'http://www.kms.matrik.edu.my'),  # same as index → no change
            ('kmkk', 'KMK Kedah', 'https://kmkk.matrik.edu.my'),     # not in index → missing
        ]
        self.index = {'kmm': 'http://www.kmm.matrik.edu.my', 'kms': 'http://www.kms.matrik.edu.my',
                      'kmtk': 'http://www.kmtk.matrik.edu.my'}       # kmtk not ours → extra

    def test_classifies(self):
        p = build_proposals(self.insts, self.index, 'subdomain', reachable=_alive)
        self.assertEqual([c['id'] for c in p['canonicalise']], ['kmm'])
        self.assertEqual(p['canonicalise'][0]['proposed'], 'http://www.kmm.matrik.edu.my')
        self.assertIn('kmkk', [m['id'] for m in p['missing']])
        self.assertIn('kmtk', [e['key'] for e in p['extra']])
        # kms unchanged (same URL ignoring trailing slash) → not in any bucket
        self.assertNotIn('kms', [c['id'] for c in p['canonicalise']])

    def test_unreachable_index_url_is_missing_not_canonicalise(self):
        insts = [('kmm', 'KM Melaka', 'https://kmm.matrik.edu.my')]
        index = {'kmm': 'http://dead.kmm.matrik.edu.my'}  # _alive() → dead
        p = build_proposals(insts, index, 'subdomain', reachable=_alive)
        self.assertEqual(p['canonicalise'], [])
        self.assertEqual(p['missing'][0]['id'], 'kmm')
        self.assertIn('not reachable', p['missing'][0]['note'])


class BuildProposalsNameTest(SimpleTestCase):
    def test_name_match(self):
        insts = [('POLY-1', 'Politeknik Ungku Omar', 'https://old.example')]
        index = {'politeknik ungku omar': 'https://www.puo.edu.my'}
        p = build_proposals(insts, index, 'name', reachable=_alive)
        self.assertEqual(p['canonicalise'][0]['proposed'], 'https://www.puo.edu.my')
