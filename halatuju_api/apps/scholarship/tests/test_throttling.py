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
)

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'throttle-test'}}


def _capped(cls, num=2, dur=60):
    """A throttle instance with a forced small limit (num requests / dur seconds)."""
    t = cls()
    t.num_requests, t.duration = num, dur
    return t


class ClientIpTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_prefers_cf_then_xff_then_remote_addr(self):
        req = self.rf.get('/', HTTP_CF_CONNECTING_IP='1.2.3.4',
                          HTTP_X_FORWARDED_FOR='9.9.9.9, 10.0.0.1',
                          REMOTE_ADDR='172.16.0.1')
        self.assertEqual(client_ip(req), '1.2.3.4')

        req = self.rf.get('/', HTTP_X_FORWARDED_FOR='9.9.9.9, 10.0.0.1',
                          REMOTE_ADDR='172.16.0.1')
        self.assertEqual(client_ip(req), '9.9.9.9')  # first hop = the real client

        req = self.rf.get('/', REMOTE_ADDR='172.16.0.1')
        self.assertEqual(client_ip(req), '172.16.0.1')


@override_settings(CACHES=LOCMEM)
class AnonThrottleTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        cache.clear()

    def test_distinct_real_clients_get_distinct_buckets(self):
        """The safety property: two visitors behind the SAME proxy IP but with
        different X-Forwarded-For first hops must NOT share a throttle bucket."""
        t = ClientAnonRateThrottle()
        a = self.rf.get('/', HTTP_X_FORWARDED_FOR='1.1.1.1', REMOTE_ADDR='10.0.0.1')
        b = self.rf.get('/', HTTP_X_FORWARDED_FOR='2.2.2.2', REMOTE_ADDR='10.0.0.1')
        self.assertNotEqual(t.get_cache_key(a, None), t.get_cache_key(b, None))

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
