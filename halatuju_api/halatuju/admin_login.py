"""The Django admin's sign-in, with a throttle in front (SEC-06, A1.9).

The Django admin is mounted on the api host (`/admin/`) and its login form took any number of
password guesses: DRF's throttles cover only the API views, and Django's own login has none.
This wraps `admin.site.login` (same form, same CSRF and session handling) and refuses a POST once
one caller has made ``MAX_POSTS`` in ``WINDOW_SECONDS``. A GET (showing the form) is never counted.

The caller is the rightmost X-Forwarded-For hop (`throttling.client_ip`, TD-514), so a forged
header cannot buy a fresh bucket; the counter is the atomic `take_slot` (SEC-08).
"""
from django.contrib import admin
from django.http import HttpResponse

from .throttling import take_slot, throttle_ip

MAX_POSTS = 10
WINDOW_SECONDS = 15 * 60


def throttled_login(request, extra_context=None):
    if request.method == 'POST' and not take_slot(
            'admin-login:%s' % throttle_ip(request), MAX_POSTS, WINDOW_SECONDS):
        return HttpResponse('Too many sign-in attempts. Please try again in 15 minutes.',
                            status=429, content_type='text/plain; charset=utf-8')
    return admin.site.login(request, extra_context)
