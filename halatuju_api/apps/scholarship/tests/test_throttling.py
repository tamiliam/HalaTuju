"""Tests for the proxy-aware rate throttles (halatuju/throttling.py).

The single most important property: behind a proxy (Cloud Run), distinct real
clients must get distinct throttle buckets — otherwise a per-IP limit would lump
every anonymous visitor under the one proxy IP and throttle the whole site.

The limit (num_requests/duration) is forced on each throttle instance rather
than via override_settings, because DRF caches its settings at import and the
test-time reload is unreliable; in production the rate is read from
settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] at startup. A real LocMemCache
is pinned so the sliding-window history actually persists between requests.
"""
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from halatuju.throttling import (
    ClientAnonRateThrottle,
    PublicCountRateThrottle,
    UploadRateThrottle,
    client_ip,
    forwarded_client_ip,
    take_slot,
    throttle_ip,
    throttle_key_ip,
)

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'throttle-test'}}


def _capped(cls, num=2, dur=60):
    """A throttle instance with a forced small limit (num requests / dur seconds)."""
    t = cls()
    t.num_requests, t.duration = num, dur
    return t


class ClientIpTests(TestCase):
    """TD-514 / SEC-03: Cloud Run APPENDS the address it saw, so only the RIGHTMOST
    X-Forwarded-For hop is ours; every hop to its left is typed by the caller."""
    def setUp(self):
        self.rf = RequestFactory()

    def test_rightmost_hop_then_remote_addr(self):
        req = self.rf.get('/', HTTP_X_FORWARDED_FOR='9.9.9.9, 10.0.0.1',
                          REMOTE_ADDR='172.16.0.1')
        self.assertEqual(client_ip(req), '10.0.0.1')  # the hop Cloud Run wrote

        req = self.rf.get('/', REMOTE_ADDR='172.16.0.1')
        self.assertEqual(client_ip(req), '172.16.0.1')

    def test_a_forged_leftmost_hop_is_ignored(self):
        req = self.rf.get('/', HTTP_X_FORWARDED_FOR='1.2.3.4, 203.0.113.9',
                          REMOTE_ADDR='172.16.0.1')
        self.assertEqual(client_ip(req), '203.0.113.9')

    def test_cloudflare_header_is_not_trusted(self):
        req = self.rf.get('/', HTTP_CF_CONNECTING_IP='1.2.3.4',
                          HTTP_X_FORWARDED_FOR='203.0.113.9', REMOTE_ADDR='172.16.0.1')
        self.assertEqual(client_ip(req), '203.0.113.9')

    def test_blank_hops_are_skipped_and_nothing_reads_unknown(self):
        req = self.rf.get('/', HTTP_X_FORWARDED_FOR='203.0.113.9, ', REMOTE_ADDR='')
        self.assertEqual(client_ip(req), '203.0.113.9')
        req = self.rf.get('/', REMOTE_ADDR='')
        self.assertEqual(client_ip(req), 'unknown')
        self.assertIsNone(forwarded_client_ip(req))


class ThrottleKeyIpTests(TestCase):
    """A1.9a follow-up F1: an IPv6 throttle key is the /64; evidence keeps the full address."""
    def test_ipv4_is_unchanged(self):
        self.assertEqual(throttle_key_ip('203.0.113.9'), '203.0.113.9')

    def test_two_addresses_in_one_slash_64_share_a_key(self):
        a = throttle_key_ip('2001:db8:1:2:aaaa:bbbb:cccc:dddd')
        b = throttle_key_ip('2001:db8:1:2:1111:2222:3333:4444')
        self.assertEqual(a, b)
        self.assertEqual(a, '2001:db8:1:2::/64')

    def test_different_slash_64_give_different_keys(self):
        self.assertNotEqual(throttle_key_ip('2001:db8:1:2::1'), throttle_key_ip('2001:db8:1:3::1'))

    def test_bad_or_empty_input_falls_back_to_the_raw_string(self):
        self.assertEqual(throttle_key_ip('unknown'), 'unknown')
        self.assertEqual(throttle_key_ip('junk'), 'junk')
        self.assertEqual(throttle_key_ip(''), '')
        self.assertIsNone(throttle_key_ip(None))

    def test_throttle_ip_cuts_the_request_address_but_signer_ip_keeps_it(self):
        from apps.scholarship.request_ip import signer_ip
        req = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='2001:db8:1:2:aaaa:bbbb:cccc:dddd')
        self.assertEqual(throttle_ip(req), '2001:db8:1:2::/64')
        self.assertEqual(client_ip(req), '2001:db8:1:2:aaaa:bbbb:cccc:dddd')
        self.assertEqual(signer_ip(req), '2001:db8:1:2:aaaa:bbbb:cccc:dddd')

    @override_settings(CACHES=LOCMEM)
    def test_admin_login_lock_covers_the_whole_slash_64(self):
        from unittest import mock

        from django.http import HttpResponse

        from halatuju.admin_login import MAX_POSTS, throttled_login
        cache.clear()
        rf = RequestFactory()
        with mock.patch('halatuju.admin_login.admin.site.login',
                        return_value=HttpResponse('form')):
            for n in range(MAX_POSTS):
                req = rf.post('/admin/login/', HTTP_X_FORWARDED_FOR='2001:db8:9:9::%x' % (n + 1))
                self.assertEqual(throttled_login(req).status_code, 200)
            req = rf.post('/admin/login/', HTTP_X_FORWARDED_FOR='2001:db8:9:9:ffff::1')
            self.assertEqual(throttled_login(req).status_code, 429)


@override_settings(CACHES=LOCMEM)
class AnonThrottleTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        cache.clear()

    def test_distinct_real_clients_get_distinct_buckets(self):
        """The safety property: two visitors behind the SAME proxy IP but with
        different X-Forwarded-For (Cloud Run-written) hops must NOT share a throttle bucket."""
        t = ClientAnonRateThrottle()
        a = self.rf.get('/', HTTP_X_FORWARDED_FOR='1.1.1.1', REMOTE_ADDR='10.0.0.1')
        b = self.rf.get('/', HTTP_X_FORWARDED_FOR='2.2.2.2', REMOTE_ADDR='10.0.0.1')
        self.assertNotEqual(t.get_cache_key(a, None), t.get_cache_key(b, None))

    def test_a_new_forged_hop_per_request_does_not_buy_a_new_bucket(self):
        """TD-514: before, a caller who varied the leftmost hop skipped every anon limit."""
        def hit(forged):
            r = self.rf.get('/', HTTP_X_FORWARDED_FOR=f'{forged}, 203.0.113.9',
                            REMOTE_ADDR='10.0.0.1')
            return _capped(ClientAnonRateThrottle).allow_request(r, None)

        self.assertTrue(hit('1.1.1.1'))
        self.assertTrue(hit('2.2.2.2'))
        self.assertFalse(hit('3.3.3.3'))  # same real caller -> same bucket -> blocked

    def test_authenticated_requests_skip_the_anon_throttle(self):
        t = ClientAnonRateThrottle()
        req = self.rf.get('/', REMOTE_ADDR='10.0.0.1')
        req.user_id = 'some-supabase-uuid'
        self.assertIsNone(t.get_cache_key(req, None))

    def test_limits_per_client_and_isolates_clients(self):
        def hit(xff):
            r = self.rf.get('/', HTTP_X_FORWARDED_FOR=xff, REMOTE_ADDR='10.0.0.1')
            return _capped(ClientAnonRateThrottle).allow_request(r, None)

        self.assertTrue(hit('1.1.1.1'))   # client A: 1st
        self.assertTrue(hit('1.1.1.1'))   # client A: 2nd (limit = 2)
        self.assertFalse(hit('1.1.1.1'))  # client A: 3rd → blocked
        self.assertTrue(hit('3.3.3.3'))   # client B unaffected → separate bucket


@override_settings(CACHES=LOCMEM)
class UploadThrottleTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        cache.clear()

    def test_get_listing_is_not_throttled(self):
        t = UploadRateThrottle()
        req = self.rf.get('/documents/')
        req.user_id = 'uid-1'
        self.assertIsNone(t.get_cache_key(req, None))  # reading is free

    def test_keys_on_user_id_for_posts(self):
        t = UploadRateThrottle()
        req = self.rf.post('/documents/')
        req.user_id = 'uid-1'
        self.assertIn('user:uid-1', t.get_cache_key(req, None))

    def test_upload_posts_limited_per_user(self):
        def post(uid):
            r = self.rf.post('/documents/')
            r.user_id = uid
            return _capped(UploadRateThrottle).allow_request(r, None)

        self.assertTrue(post('uid-1'))   # 1st
        self.assertTrue(post('uid-1'))   # 2nd (limit = 2)
        self.assertFalse(post('uid-1'))  # 3rd → blocked
        self.assertTrue(post('uid-2'))   # different user → separate bucket


@override_settings(CACHES=LOCMEM)
class PublicCountThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_public_count_limited_per_client_ip(self):
        rf = RequestFactory()

        def hit(ip):
            r = rf.get('/sponsor/pool/count/', REMOTE_ADDR=ip)
            return _capped(PublicCountRateThrottle).allow_request(r, None)

        self.assertTrue(hit('5.5.5.5'))
        self.assertTrue(hit('5.5.5.5'))
        self.assertFalse(hit('5.5.5.5'))  # 3rd from same IP → blocked
        self.assertTrue(hit('6.6.6.6'))   # different IP → ok


@override_settings(CACHES=LOCMEM)
class TakeSlotTests(TestCase):
    """SEC-08: the shared atomic counter (profile_claim, the Django admin sign-in)."""
    def setUp(self):
        cache.clear()

    def test_limit_uses_then_refused_and_a_refusal_consumes_nothing(self):
        self.assertTrue(take_slot('k', 2, 60))
        self.assertTrue(take_slot('k', 2, 60))
        self.assertFalse(take_slot('k', 2, 60))
        self.assertFalse(take_slot('k', 2, 60))
        self.assertTrue(take_slot('other', 2, 60))

    def test_a_freed_slot_is_reused(self):
        take_slot('k', 2, 60)
        take_slot('k', 2, 60)
        cache.delete('k:0')  # as if its window had passed
        self.assertTrue(take_slot('k', 2, 60))
        self.assertFalse(take_slot('k', 2, 60))
