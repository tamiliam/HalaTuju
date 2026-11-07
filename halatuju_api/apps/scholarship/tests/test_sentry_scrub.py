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

    def test_frame_local_raw_is_scrubbed_and_other_locals_kept(self):
        event = {'exception': {'values': [{'stacktrace': {'frames': [
            {'function': 'people_search_term', 'vars': {'raw': '900101-14-5678', 'param': "'q'"}}]}}]}}
        build_event_scrubber().scrub_event(event)
        self.assertNotIn('900101', str(event))
        self.assertEqual(event['exception']['values'][0]['stacktrace']['frames'][0]['vars']['param'], "'q'")

    @staticmethod
    def _event_from(call):
        """The event Sentry would build for an error raised inside call(); this frame holds only call."""
        import sys

        from sentry_sdk.utils import event_from_exception
        try:
            call()
        except RuntimeError:
            return event_from_exception(sys.exc_info())[0]

    def test_a_real_error_inside_the_searches_carries_no_term_in_its_frames(self):
        """The locals Sentry really captures (include_local_variables is on by default)."""
        from apps.courses.search import apply_people_search
        from apps.scholarship.scholars import filter_rows

        class Boom:
            def annotate(self, **kw):
                raise RuntimeError('db down')
            filter = annotate

        # Built at run time: Sentry also sends the SOURCE lines around each frame, so a literal
        # here would show up in the event through the test's own code, not through a variable.
        self._term = ' 9001' + '01-14-5678 '
        self._needles = (self._term.strip(), ''.join(c for c in self._term if c.isdigit()))
        for call in (
            lambda: apply_people_search(Boom(), self._term, name='n', nric='i', phone='p', email='e'),
            lambda: filter_rows(Boom(), search=self._term),
        ):
            event = self._event_from(call)
            for needle in self._needles:
                self.assertIn(needle, str(event))      # the frames really held it before scrubbing
            build_event_scrubber().scrub_event(event)
            for needle in self._needles:
                self.assertNotIn(needle, str(event))
