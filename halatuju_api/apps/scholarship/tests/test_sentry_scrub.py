"""A1.9a follow-up F2: Sentry never receives the X-Search-Term header value."""
from django.test import SimpleTestCase

from halatuju.sentry_scrub import build_event_scrubber


class SentryScrubTests(SimpleTestCase):
    def _event(self):
        return {'request': {'url': 'https://api.example/x', 'headers': {
            'X-Search-Term': '900101-14-5678', 'Accept': 'application/json',
            'Authorization': 'Bearer abc'}}}

    def test_search_term_header_is_scrubbed_and_others_kept(self):
        event = self._event()
        build_event_scrubber().scrub_event(event)
        headers = event['request']['headers']
        self.assertNotIn('900101-14-5678', str(event))
        self.assertEqual(headers['Accept'], 'application/json')
        self.assertNotIn('Bearer abc', str(headers['Authorization']))  # default scrubbing kept

    def test_lowercase_header_name_is_scrubbed_too(self):
        event = {'request': {'headers': {'x-search-term': 'secret-name'}}}
        build_event_scrubber().scrub_event(event)
        self.assertNotIn('secret-name', str(event))
