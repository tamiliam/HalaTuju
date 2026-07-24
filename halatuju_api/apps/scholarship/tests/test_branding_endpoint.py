"""Sprint 6 — the public GET /api/v1/branding/<code>/ endpoint.

Anonymous, total (unknown/garbage → platform payload, never 404), exact 8-key response, and no
student data reachable. Mirrors the SponsorPoolCountView public rails.
"""
import json

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerOrganisation

# The platform payload the endpoint must return for brightpath / unknown / garbage codes.
# NOTE persona_name.ta is the Tamil SCRIPT form (the backend's email-body persona); the web app in
# platform mode never fetches this (it renders its own Latin PLATFORM), so byte-identity is safe.
PLATFORM_PAYLOAD = {
    'programme_name': {'en': 'BrightPath Bursary', 'ms': 'Bursari BrightPath', 'ta': 'BrightPath Bursary'},
    'persona_name': {'en': 'Cikgu Gopal', 'ms': 'Cikgu Gopal', 'ta': 'சிக்கு கோபால்'},
    'org_short_name': 'BrightPath',
    'brand_colour': '#137fec',
    'logo_url': '',
    'email_support': 'help@halatuju.xyz',
    'sponsor_email': 'sponsor@halatuju.xyz',
    'frontend_domain': 'halatuju.xyz',
}

EXPECTED_KEYS = {
    'programme_name', 'persona_name', 'org_short_name', 'brand_colour', 'logo_url',
    'email_support', 'sponsor_email', 'frontend_domain',
}


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestBrandingEndpoint(TestCase):
    def setUp(self):
        self.client = APIClient()  # anonymous — a pre-login page calls this

    def test_anonymous_200(self):
        r = self.client.get('/api/v1/branding/brightpath/')
        self.assertEqual(r.status_code, 200)

    def test_brightpath_is_platform_payload(self):
        r = self.client.get('/api/v1/branding/brightpath/')
        self.assertEqual(r.json(), PLATFORM_PAYLOAD)

    def test_unknown_code_is_platform_payload(self):
        r = self.client.get('/api/v1/branding/no-such-org/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), PLATFORM_PAYLOAD)

    def test_garbage_code_is_platform_payload(self):
        r = self.client.get('/api/v1/branding/x9z-garbage/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), PLATFORM_PAYLOAD)

    def test_exact_key_set(self):
        r = self.client.get('/api/v1/branding/brightpath/')
        self.assertEqual(set(r.json().keys()), EXPECTED_KEYS)

    def test_inactive_org_falls_through_to_platform(self):
        PartnerOrganisation.objects.create(
            code='dormant', name='Dormant Org', brand_colour='#123456', is_active=False)
        r = self.client.get('/api/v1/branding/dormant/')
        self.assertEqual(r.json(), PLATFORM_PAYLOAD)

    def test_tenant_org_returns_own_columns_with_fallbacks(self):
        # A second tenant: some columns set, some blank (blank → platform fallback).
        PartnerOrganisation.objects.create(
            code='inspire',
            name='Inspire Foundation',
            programme_name_en='Inspire Grant',
            programme_name_ms='',                 # blank → the tenant's OWN _en (D3 chain), not platform
            programme_name_ta='இன்ஸ்பயர் மானியம்',
            persona_name_en='Cikgu Aishah',
            persona_name_ms='Cikgu Aishah',
            persona_name_ta='Cikgu Aishah',
            brand_colour='#a21caf',
            logo_url='https://cdn.inspire.example/logo.png',
            email_support='help@inspire.example',
            frontend_url='https://inspire.example',
            # email_reply_to + email_from blank → the tenant's reply-to resolves to the platform
            # reply-to (help@), and D4 gives a non-platform tenant NO fabricated sponsor@ alias:
            # sponsor_email == the tenant's reply-to.
        )
        body = self.client.get('/api/v1/branding/inspire/').json()
        self.assertEqual(body['programme_name']['en'], 'Inspire Grant')
        # D3 chain: blank ms → the tenant's own _en ('Inspire Grant'), before any platform default.
        self.assertEqual(body['programme_name']['ms'], 'Inspire Grant')
        self.assertEqual(body['programme_name']['ta'], 'இன்ஸ்பயர் மானியம்')
        self.assertEqual(body['persona_name']['en'], 'Cikgu Aishah')
        self.assertEqual(body['org_short_name'], 'Inspire Foundation')  # derived from name
        self.assertEqual(body['brand_colour'], '#a21caf')
        self.assertEqual(body['logo_url'], 'https://cdn.inspire.example/logo.png')
        self.assertEqual(body['email_support'], 'help@inspire.example')
        self.assertEqual(body['frontend_domain'], 'inspire.example')  # host of frontend_url
        # D4: a non-platform tenant gets no sponsor@ alias — sponsor_email = its reply-to, which
        # here (no email_reply_to/email_from set) resolves to the platform reply-to.
        self.assertEqual(body['sponsor_email'], 'help@halatuju.xyz')
        self.assertEqual(set(body.keys()), EXPECTED_KEYS)

    def test_no_student_data_reachable(self):
        # Whatever codes are thrown at it, the payload is 8 brand strings — never a student field.
        for code in ('brightpath', 'inspire', 'garbage', '1', 'admin'):
            body = self.client.get(f'/api/v1/branding/{code}/').json()
            self.assertEqual(set(body.keys()), EXPECTED_KEYS)
            blob = json.dumps(body)
            for banned in ('nric', 'student', 'application', 'email_from', 'household'):
                self.assertNotIn(banned, blob.lower())
