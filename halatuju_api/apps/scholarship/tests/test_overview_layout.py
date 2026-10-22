"""The organisation's Overview layout — the validator, the model's own fence, and the endpoint.

Three claims: (1) the stored list is EXACTLY an ordered permutation of the five widgets with
boolean flags — the validator refuses everything else, and the model's `save()` runs it, so a
shell caller passes the same fence; (2) only `org_admin` and super may read or write, on the
organisation derived from their own account (a super names `?org=`), cross-tenant is 404 never
403; (3) a save writes one audit line in the compact form and a no-change save writes none.
"""
from django.test import TestCase

from apps.courses.models import PartnerOrganisation
from apps.scholarship import overview_layout
from apps.scholarship.models import OrganisationOverviewLayout, ProgrammeOverviewLayout

from .test_programme_overview import _Base

LAYOUT_URL = '/api/v1/admin/scholarship/organisation/overview-layout/'
WIDGETS = list(overview_layout.CUSTOMISABLE)


def rows(order=None, off=()):
    return [{'key': k, 'on': k not in off} for k in (order or WIDGETS)]


class ValidatorTests(TestCase):
    def test_the_default_is_every_widget_on_in_order(self):
        self.assertEqual(overview_layout.default(), rows())

    def test_accepts_a_permutation_with_flags(self):
        overview_layout.validate_sections(rows(['money', 'funnel', 'money_series', 'attention',
                                                'applications_series'], off=('funnel',)))

    def test_refuses_each_malformation_by_name(self):
        cases = {
            'bad_layout': 'not a list',
            'bad_layout ': [1, 2],
            'bad_section': rows() + [{'key': 'mine', 'on': True}],
            'duplicate_section': rows() + [{'key': 'money', 'on': False}],
            'missing_section': rows()[:-1],
            'bad_flag': [{'key': k, 'on': 1} for k in WIDGETS],
        }
        for code, value in cases.items():
            with self.subTest(code=code):
                with self.assertRaises(overview_layout.OverviewLayoutError) as ctx:
                    overview_layout.validate_sections(value)
                self.assertEqual(ctx.exception.code, code.strip())

    def test_normalised_keeps_only_key_and_on(self):
        value = [{'key': k, 'on': True, 'extra': 'x'} for k in WIDGETS]
        self.assertEqual(overview_layout.normalised(value), rows())

    def test_the_model_refuses_a_bad_list_from_the_shell(self):
        org = PartnerOrganisation.objects.get(code='brightpath')
        row = OrganisationOverviewLayout(organisation=org, sections=rows()[:-1])
        with self.assertRaises(overview_layout.OverviewLayoutError):
            row.save()
        self.assertFalse(OrganisationOverviewLayout.objects.filter(organisation=org).exists())

    def test_a_hand_edited_bad_row_falls_back_to_the_default(self):
        """Only reachable by editing the table by hand; the page is worth more than the row."""
        org = PartnerOrganisation.objects.get(code='brightpath')
        OrganisationOverviewLayout.objects.bulk_create(
            [OrganisationOverviewLayout(organisation=org, sections=[{'key': 'nonsense'}])])
        self.assertEqual(overview_layout.for_org(org), rows())


class EndpointTests(_Base):
    def _put(self, uid, sections, query=''):
        return self._client(uid).put(LAYOUT_URL + query, {'sections': sections}, format='json')

    def test_anonymous_is_401(self):
        self.assertEqual(self._client().get(LAYOUT_URL).status_code, 401)

    def test_only_org_admin_and_super_may_read_or_write(self):
        for uid in ('ov-adm', 'ov-fin', 'ov-qc', 'ov-rev', 'ov-ptr'):
            with self.subTest(uid=uid):
                self.assertEqual(self._client(uid).get(LAYOUT_URL).status_code, 403)
                self.assertEqual(self._put(uid, rows()).status_code, 403)

    def test_get_serves_the_default_when_nothing_was_saved(self):
        body = self._client('ov-oa').get(LAYOUT_URL).json()
        self.assertEqual(body['organisation']['code'], 'brightpath')
        self.assertEqual(body['sections'], rows())
        self.assertEqual(body['updated_by_email'], '')
        self.assertIsNone(body['updated_at'])

    def test_put_stores_the_full_ordered_list_and_echoes_it(self):
        wanted = rows(['money_series', 'money', 'funnel', 'attention', 'applications_series'],
                      off=('attention',))
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._put('ov-oa', wanted)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['sections'], wanted)
        self.assertEqual(r.json()['updated_by_email'], 'ov-oa@ov.test')
        self.assertEqual(OrganisationOverviewLayout.objects.get(organisation=self.org).sections,
                         wanted)
        line = [l for l in logs.output if 'AUDIT overview_layout_set' in l][0]
        self.assertIn('was=funnel+,money+,attention+,applications_series+,money_series+', line)
        self.assertIn('now=money_series+,money+,funnel+,attention-,applications_series+', line)
        self.assertIn('by=ov-oa@ov.test', line)
        # …and the Overview itself now reads it.
        self.assertEqual(self._body('ov-oa')['sections'],
                         ['money_series', 'money', 'funnel', 'applications_series'])

    def test_a_no_change_save_writes_no_audit_line(self):
        self._put('ov-oa', rows())
        with self.assertNoLogs('apps.scholarship.views_admin', level='INFO'):
            self.assertEqual(self._put('ov-oa', rows()).status_code, 200)

    def test_put_refuses_a_bad_list_all_or_nothing(self):
        r = self._put('ov-oa', rows()[:-1])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'error': 'missing_section', 'code': 'missing_section',
                                    'key': 'money_series'})
        self.assertFalse(OrganisationOverviewLayout.objects.filter(organisation=self.org).exists())
        r = self._put('ov-oa', {'not': 'a list'})
        self.assertEqual(r.json()['code'], 'bad_layout')

    def test_the_organisation_is_derived_and_cross_tenant_is_404(self):
        # An org_admin cannot name another tenant, and naming their own changes nothing.
        self.assertEqual(self._client('ov-oa').get(LAYOUT_URL + '?org=ov-other').status_code, 404)
        self.assertEqual(self._client('ov-oa').get(LAYOUT_URL + '?org=brightpath').status_code, 200)
        # A super with more than one tenant must say which; naming one resolves it.
        r = self._client('ov-su').get(LAYOUT_URL)
        if r.status_code == 400:
            self.assertEqual(r.json()['code'], 'organisation_required')
        r = self._put('ov-su', rows(off=('funnel',)), '?org=brightpath')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('funnel', self._body('ov-oa')['sections'])


class GiftEndpointTests(_Base):
    """Request #42 (2026-10-22): `?programme=<gift code>` reads, writes and resets ONE gift's own
    layout; the organisation's row is the default every gift without one falls back to."""

    def _put(self, uid, sections, query='?programme=ov-gift'):
        return self._client(uid).put(LAYOUT_URL + query, {'sections': sections}, format='json')

    def _delete(self, uid, query='?programme=ov-gift'):
        return self._client(uid).delete(LAYOUT_URL + query)

    def _org_row(self, sections):
        OrganisationOverviewLayout.objects.create(organisation=self.org, sections=sections)

    def test_a_gift_with_no_rows_reads_the_default(self):
        body = self._client('ov-oa').get(LAYOUT_URL + '?programme=ov-gift').json()
        self.assertEqual(body['source'], 'default')
        self.assertEqual(body['programme'], {'code': 'ov-gift', 'name': 'Overview Gift'})
        self.assertEqual(body['sections'], rows())

    def test_a_gift_with_no_row_reads_the_organisation_layout(self):
        self._org_row(rows(off=('money',)))
        body = self._client('ov-oa').get(LAYOUT_URL + '?programme=ov-gift').json()
        self.assertEqual(body['source'], 'organisation')
        self.assertEqual(body['sections'], rows(off=('money',)))
        # ...and the all-gifts read is the organisation's own, with no gift named.
        body = self._client('ov-oa').get(LAYOUT_URL).json()
        self.assertEqual(body['source'], 'organisation')
        self.assertIsNone(body['programme'])

    def test_put_writes_the_gift_row_only(self):
        self._org_row(rows(off=('money',)))
        wanted = rows(['money', 'funnel', 'attention', 'applications_series', 'money_series'],
                      off=('funnel',))
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._put('ov-oa', wanted)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['source'], 'gift')
        self.assertEqual(r.json()['sections'], wanted)
        self.assertEqual(r.json()['updated_by_email'], 'ov-oa@ov.test')
        self.assertEqual(ProgrammeOverviewLayout.objects.get(programme=self.gift).sections, wanted)
        # The organisation's row is untouched, and so is the other gift.
        self.assertEqual(OrganisationOverviewLayout.objects.get(organisation=self.org).sections,
                         rows(off=('money',)))
        self.assertFalse(ProgrammeOverviewLayout.objects.filter(programme=self.gift2).exists())
        line = [l for l in logs.output if 'AUDIT overview_layout_set' in l][0]
        self.assertIn(f'programme={self.gift.id}', line)
        self.assertIn('was=funnel+,money-,', line)
        self.assertIn('now=money+,funnel-,', line)

    def test_a_first_gift_save_equal_to_the_org_layout_still_audits_and_stores(self):
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._put('ov-oa', rows())
        self.assertEqual(r.json()['source'], 'gift')
        self.assertTrue(any('AUDIT overview_layout_set' in l for l in logs.output))
        with self.assertNoLogs('apps.scholarship.views_admin', level='INFO'):
            self._put('ov-oa', rows())

    def test_put_refuses_a_bad_list_for_a_gift_too(self):
        r = self._put('ov-oa', rows()[:-1])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'missing_section')
        self.assertFalse(ProgrammeOverviewLayout.objects.exists())

    def test_the_model_refuses_a_bad_gift_list_from_the_shell(self):
        row = ProgrammeOverviewLayout(programme=self.gift, sections=[{'key': 'mine', 'on': True}])
        with self.assertRaises(overview_layout.OverviewLayoutError):
            row.save()

    def test_delete_removes_the_gift_row_and_never_the_org_row(self):
        self._org_row(rows(off=('money',)))
        self._put('ov-oa', rows(off=('funnel',)))
        self._put('ov-oa', rows(off=('attention',)), '?programme=ov-gift2')
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._delete('ov-oa')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['source'], 'organisation')
        self.assertEqual(r.json()['sections'], rows(off=('money',)))
        self.assertFalse(ProgrammeOverviewLayout.objects.filter(programme=self.gift).exists())
        self.assertTrue(ProgrammeOverviewLayout.objects.filter(programme=self.gift2).exists())
        self.assertTrue(OrganisationOverviewLayout.objects.filter(organisation=self.org).exists())
        line = [l for l in logs.output if 'AUDIT overview_layout_reset' in l][0]
        self.assertIn(f'programme={self.gift.id}', line)
        # The gift's Overview now shows the organisation's layout again.
        self.assertNotIn('money', self._body('ov-oa')['sections'])
        # A second reset is harmless and writes no audit line.
        with self.assertNoLogs('apps.scholarship.views_admin', level='INFO'):
            self.assertEqual(self._delete('ov-oa').status_code, 200)

    def test_delete_without_a_gift_is_a_400_and_deletes_nothing(self):
        self._org_row(rows(off=('money',)))
        r = self._delete('ov-oa', '')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'programme_required')
        self.assertTrue(OrganisationOverviewLayout.objects.filter(organisation=self.org).exists())

    def test_another_organisations_gift_is_404_for_org_staff(self):
        self.assertEqual(
            self._client('ov-oa').get(LAYOUT_URL + '?programme=ov-other-gift').status_code, 404)
        self.assertEqual(self._put('ov-oa', rows(), '?programme=ov-other-gift').status_code, 404)
        self.assertEqual(self._delete('ov-oa', '?programme=ov-other-gift').status_code, 404)
        self.assertEqual(self._put('ov-oa', rows(), '?programme=no-such-gift').status_code, 404)
        self.assertFalse(ProgrammeOverviewLayout.objects.exists())

    def test_only_org_admin_and_super_may_write_a_gift_layout(self):
        for uid in ('ov-adm', 'ov-fin', 'ov-qc', 'ov-rev', 'ov-ptr'):
            with self.subTest(uid=uid):
                self.assertEqual(self._put(uid, rows()).status_code, 403)
                self.assertEqual(self._delete(uid).status_code, 403)
                self.assertEqual(
                    self._client(uid).get(LAYOUT_URL + '?programme=ov-gift').status_code, 403)
        self.assertFalse(ProgrammeOverviewLayout.objects.exists())

    def test_a_super_may_act_on_any_gift(self):
        r = self._put('ov-su', rows(off=('money',)), '?programme=ov-other-gift')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['organisation']['code'], 'ov-other')
        self.assertTrue(ProgrammeOverviewLayout.objects.filter(programme=self.other_gift).exists())
        self.assertEqual(self._delete('ov-su', '?programme=ov-other-gift').status_code, 200)
        self.assertFalse(ProgrammeOverviewLayout.objects.exists())
