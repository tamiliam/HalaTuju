"""SEC-06 (A1.9): the Django admin sign-in on the api host refuses a flood of password guesses."""
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from halatuju import admin_login

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'admin-login-test'}}
LOGIN = '/admin/login/'


@override_settings(ROOT_URLCONF='halatuju.urls', CACHES=LOCMEM)
class TestAdminLoginThrottle(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def _guess(self, caller='203.0.113.9', forged='1.1.1.1'):
        return self.client.post(LOGIN, {'username': 'nobody', 'password': 'wrong'},
                                HTTP_X_FORWARDED_FOR=f'{forged}, {caller}')

    def test_the_form_still_shows(self):
        resp = self.client.get(LOGIN)
        self.assertEqual(resp.status_code, 200)

    def test_guesses_past_the_limit_are_refused(self):
        for _ in range(admin_login.MAX_POSTS):
            self.assertEqual(self._guess().status_code, 200)   # the form, with an error
        self.assertEqual(self._guess().status_code, 429)

    def test_a_new_forged_hop_does_not_buy_more_guesses(self):
        for i in range(admin_login.MAX_POSTS):
            self._guess(forged=f'10.0.0.{i}')
        self.assertEqual(self._guess(forged='10.9.9.9').status_code, 429)

    def test_another_caller_is_not_blocked(self):
        for _ in range(admin_login.MAX_POSTS + 1):
            self._guess()
        self.assertEqual(self._guess(caller='198.51.100.4').status_code, 200)

    def test_viewing_the_form_is_never_counted(self):
        for _ in range(admin_login.MAX_POSTS + 5):
            self.client.get(LOGIN)
        self.assertEqual(self._guess().status_code, 200)
