"""SEC-01 residue: the AI review never fetches a stored attachment key that fails is_clean_key."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import org_requests_ai


def _req(*keys):
    atts = [SimpleNamespace(storage_path=k, content_type='image/png') for k in keys]
    return SimpleNamespace(pk=1, attachments=SimpleNamespace(all=lambda: atts))


class UncleanKeyGuardTests(SimpleTestCase):
    def test_an_unclean_storage_key_is_never_fetched(self):
        with mock.patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'x') as fetch:
            out = org_requests_ai._review_images(_req('requests/1/2/../../9/secret', '/abs/key'))
        fetch.assert_not_called()
        self.assertEqual(out, [])

    def test_a_clean_key_is_still_fetched(self):
        with mock.patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'x') as fetch:
            out = org_requests_ai._review_images(_req('requests/1/2/abc'))
        fetch.assert_called_once_with('requests/1/2/abc')
        self.assertEqual(out, [(b'x', 'image/png')])
