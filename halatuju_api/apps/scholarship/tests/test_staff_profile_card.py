"""Common profile S2 (2026-10-31) — every person's own card: `PATCH admin/me/`, the photo, the Team
page's photo + shared phone, a source user's phone for its inviting organisation, and the places a
staff photo must NEVER reach (student, sponsor, source-console payloads).
"""
import io
import os
from unittest import mock

from django.test import TestCase, override_settings
from PIL import Image

from apps.scholarship import staff_photo, storage
from apps.scholarship.models import ReviewerProfile, StaffProfile
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_source,
)

ME = '/api/v1/admin/me/'
PHOTO = '/api/v1/admin/me/photo/'


def image_bytes(fmt='JPEG', size=(1200, 900), exif_gps=False, mode='RGB'):
    img = Image.new(mode, size, (200, 30, 30) if mode == 'RGB' else None)
    out = io.BytesIO()
    kwargs = {}
    if exif_gps:
        exif = Image.Exif()
        exif[0x010F] = 'PhoneMaker'                    # Make
        exif[0x8825] = {1: 'N', 2: (3.0, 8.0, 0.0)}    # GPSInfo
        kwargs['exif'] = exif
    img.save(out, format=fmt, **kwargs)
    return out.getvalue()


def upload(data, name='me.jpg', content_type='image/jpeg'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, data, content_type=content_type)


class TheModelIsOneTableWithTwoNames(TestCase):
    def test_staff_profile_is_the_reviewer_profile_class(self):
        self.assertIs(StaffProfile, ReviewerProfile)
        self.assertEqual(StaffProfile._meta.db_table, 'reviewer_profiles')

    def test_each_new_column_has_a_database_default(self):
        """Migrate-first: the OLD image inserts rows without naming these, so NOT NULL needs a
        DATABASE default (lessons.md 2026-10-19)."""
        from django.db.models.fields import NOT_PROVIDED
        for name in ('job_title', 'about', 'photo_path', 'share_phone_with_team', 'other_language',
                     'other_language_fluency'):
            with self.subTest(name=name):
                self.assertIsNot(StaffProfile._meta.get_field(name).db_default, NOT_PROVIDED)

    def test_the_migration_only_adds_columns(self):
        from importlib import import_module
        from django.db.migrations import AddField
        ops = import_module('apps.scholarship.migrations.0193_staff_profile_card').Migration.operations
        self.assertEqual({type(op) for op in ops}, {AddField})
        self.assertEqual(sorted(op.name for op in ops),
                         ['about', 'job_title', 'other_language', 'other_language_fluency', 'photo_path',
                          'share_phone_with_team'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestPatchMe(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def _patch(self, admin, body):
        return authed_client(admin).patch(ME, body, format='json')

    def test_only_the_keys_sent_are_written(self):
        me = make_admin('admin', owning_org=self.org, name='Priya')
        StaffProfile.objects.create(partner_admin=me, phone='012-345 6789', about='Kept')
        resp = self._patch(me, {'job_title': '  Programme officer  ', 'share_phone_with_team': True})
        self.assertEqual(resp.status_code, 200)
        p = StaffProfile.objects.get(partner_admin=me)
        self.assertEqual((p.job_title, p.share_phone_with_team, p.about, p.phone),
                         ('Programme officer', True, 'Kept', '012-345 6789'))
        me.refresh_from_db()
        self.assertEqual(me.name, 'Priya')
        self.assertEqual(resp.json()['job_title'], 'Programme officer')

    def test_the_name_saves_on_the_account(self):
        me = make_admin('admin', owning_org=self.org)
        self.assertEqual(self._patch(me, {'name': ' New Name '}).json()['name'], 'New Name')
        self.assertEqual(self._patch(me, {'name': '  '}).json()['error'], 'name_required')

    def test_an_unknown_key_is_refused_and_nothing_is_written(self):
        me = make_admin('admin', owning_org=self.org)
        resp = self._patch(me, {'job_title': 'X', 'street_address': '1 Jalan', 'role': 'super'})
        self.assertEqual((resp.status_code, resp.json()['error']), (400, 'not_editable'))
        self.assertEqual(resp.json()['fields'], ['role', 'street_address'])
        self.assertFalse(StaffProfile.objects.filter(partner_admin=me).exists())

    def test_about_is_capped_at_600(self):
        me = make_admin('admin', owning_org=self.org)
        self.assertEqual(self._patch(me, {'about': 'x' * 601}).json()['error'], 'about_too_long')
        self.assertEqual(self._patch(me, {'about': 'x' * 600}).status_code, 200)
        self.assertEqual(self._patch(me, {'job_title': 'x' * 121}).json()['error'], 'job_title_too_long')

    def test_a_review_holder_must_keep_a_phone_everybody_else_may_clear_it(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(self._patch(reviewer, {'phone': ''}).json()['error'], 'phone_required')
        admin = make_admin('admin', owning_org=self.org, permissions=['review', 'see_all'])
        self.assertEqual(self._patch(admin, {'phone': ''}).json()['error'], 'phone_required')
        plain = make_admin('finance', owning_org=self.org)
        self.assertEqual(self._patch(plain, {'phone': ''}).status_code, 200)

    def test_share_with_students_is_only_a_review_holders_switch(self):
        plain = make_admin('finance', owning_org=self.org)
        resp = self._patch(plain, {'share_phone_with_students': False})
        self.assertEqual((resp.status_code, resp.json()['fields']), (400, ['share_phone_with_students']))
        reviewer = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(self._patch(reviewer, {'share_phone_with_students': False}).status_code, 200)
        self.assertFalse(StaffProfile.objects.get(partner_admin=reviewer).share_phone_with_students)
        sup = make_admin('super', super_admin=True)
        self.assertEqual(self._patch(sup, {'share_phone_with_students': False}).status_code, 400)

    def test_a_switch_must_be_a_boolean(self):
        me = make_admin('admin', owning_org=self.org)
        self.assertEqual(self._patch(me, {'share_phone_with_team': 'yes'}).json()['error'], 'bad_request')

    def test_a_source_user_saves_its_name_and_phone_here(self):
        source_user = make_admin('source_partner', owning_org=self.org)
        resp = self._patch(source_user, {'name': 'Audrey K', 'phone': '016-845 1270'})
        self.assertEqual(resp.status_code, 200)
        source_user.refresh_from_db()
        self.assertEqual(source_user.name, 'Audrey K')
        self.assertEqual(StaffProfile.objects.get(partner_admin=source_user).phone, '016-845 1270')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestPhoto(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.me = make_admin('admin', owning_org=make_org())
        self.stored = {}
        self.deleted = []
        patches = [
            mock.patch('apps.scholarship.storage.upload_object',
                       side_effect=lambda path, data, ct: self.stored.__setitem__(path, (data, ct)) or True),
            mock.patch('apps.scholarship.storage.delete_objects',
                       side_effect=lambda paths: self.deleted.extend(paths) or True),
            mock.patch('apps.scholarship.storage.create_signed_download_url',
                       side_effect=lambda path, expires_in=3600: f'https://signed/{path}?e={expires_in}'),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _post(self, f, admin=None):
        return authed_client(admin or self.me).post(PHOTO, {'photo': f}, format='multipart')

    def test_a_jpeg_is_reencoded_to_a_small_webp_without_metadata(self):
        resp = self._post(upload(image_bytes('JPEG', (1600, 1200), exif_gps=True)))
        self.assertEqual(resp.status_code, 200)
        (path, (data, ct)), = self.stored.items()
        self.assertRegex(path, rf'^staff-photos/{self.me.id}/[0-9a-f]{{32}}\.webp$')
        self.assertEqual(ct, 'image/webp')
        with Image.open(io.BytesIO(data)) as out:
            self.assertEqual(out.format, 'WEBP')
            self.assertLessEqual(max(out.size), 512)
            self.assertEqual(len(out.getexif()), 0)                  # no GPS, no camera
            self.assertNotIn('exif', out.info)
        self.assertEqual(StaffProfile.objects.get(partner_admin=self.me).photo_path, path)
        self.assertEqual(resp.json()['photo_url'], f'https://signed/{path}?e=3600')
        self.assertEqual(authed_client(self.me).get(ME).json()['photo_url'], f'https://signed/{path}?e=3600')

    def test_the_content_decides_not_the_name(self):
        self.assertEqual(self._post(upload(image_bytes('PNG'), name='me.jpg')).status_code, 200)
        self.assertEqual(self._post(upload(image_bytes('WEBP'), name='x.txt',
                                           content_type='text/plain')).status_code, 200)
        self.assertEqual(self._post(upload(b'%PDF-1.4 not an image', name='me.png',
                                           content_type='image/png')).json()['error'], 'not_an_image')
        self.assertEqual(self._post(upload(image_bytes('GIF', mode='P'), name='me.png',
                                           content_type='image/png')).json()['error'], 'unsupported_type')

    def test_over_two_megabytes_is_refused(self):
        big = upload(b'\xff\xd8' + os.urandom(2 * 1024 * 1024))
        self.assertEqual(self._post(big).json()['error'], 'too_large')
        self.assertEqual(self.stored, {})

    def test_one_file_only(self):
        a, b = upload(image_bytes()), upload(image_bytes(), name='b.jpg')
        resp = authed_client(self.me).post(PHOTO, {'photo': [a, b]}, format='multipart')
        self.assertEqual(resp.json()['error'], 'one_file')
        self.assertEqual(authed_client(self.me).post(PHOTO, {}, format='multipart').json()['error'], 'no_file')

    def test_replacing_deletes_the_old_object_and_delete_removes_both(self):
        self._post(upload(image_bytes()))
        first = StaffProfile.objects.get(partner_admin=self.me).photo_path
        self._post(upload(image_bytes('PNG')))
        second = StaffProfile.objects.get(partner_admin=self.me).photo_path
        self.assertNotEqual(first, second)
        self.assertEqual(self.deleted, [first])
        resp = authed_client(self.me).delete(PHOTO)
        self.assertEqual(resp.json(), {'photo_url': None})
        self.assertEqual(self.deleted, [first, second])
        self.assertEqual(StaffProfile.objects.get(partner_admin=self.me).photo_path, '')
        self.assertIsNone(authed_client(self.me).get(ME).json()['photo_url'])

    def test_a_storage_failure_is_503_and_changes_nothing(self):
        with mock.patch('apps.scholarship.storage.upload_object', return_value=False):
            resp = self._post(upload(image_bytes()))
        self.assertEqual((resp.status_code, resp.json()['error']), (503, 'storage_unavailable'))
        self.assertEqual(StaffProfile.objects.get(partner_admin=self.me).photo_path, '')

    def test_a_source_user_may_have_a_photo(self):
        source_user = make_admin('source_partner', owning_org=make_org())
        self.assertEqual(self._post(upload(image_bytes()), admin=source_user).status_code, 200)

    def test_deleting_the_account_deletes_the_photo_after_the_commit(self):
        self._post(upload(image_bytes()))
        path = StaffProfile.objects.get(partner_admin=self.me).photo_path
        with self.captureOnCommitCallbacks(execute=True):
            self.me.delete()                       # what AdminDeleteView does (target.delete())
        self.assertIn(path, self.deleted)

    def test_the_key_is_not_a_tenant_file(self):
        self.assertIsNone(storage.resolve_org_for_path(f'staff-photos/{self.me.id}/abc.webp'))

    def test_the_orphan_sweep_knows_a_photo(self):
        from apps.scholarship.management.commands.cleanup_orphan_blobs import known_paths
        self._post(upload(image_bytes()))
        self.assertIn(StaffProfile.objects.get(partner_admin=self.me).photo_path, known_paths())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTeamAndSourcePhones(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.shown = make_admin('reviewer', owning_org=cls.org, name='Shown')
        cls.hidden = make_admin('reviewer', owning_org=cls.org, name='Hidden')
        StaffProfile.objects.create(partner_admin=cls.shown, phone='011-1111 1111', share_phone_with_team=True,
                                    photo_path=f'staff-photos/{cls.shown.id}/a.webp', street_address='1 Jalan Rahsia')
        StaffProfile.objects.create(partner_admin=cls.hidden, phone='012-2222 2222',
                                    photo_path=f'staff-photos/{cls.hidden.id}/b.webp')

    def setUp(self):
        signer = mock.patch('apps.scholarship.storage.create_signed_download_urls',
                            side_effect=lambda paths, expires_in=3600: {p: f'https://signed/{p}' for p in paths})
        self.sign = signer.start()
        self.addCleanup(signer.stop)

    def _rows(self, url, key):
        return {r['name']: r for r in authed_client(self.lead).get(url).json()[key]}

    def test_the_people_lists_show_a_phone_only_when_shared_and_sign_in_one_batch(self):
        for url, key in (('/api/v1/admin/reviewers/', 'reviewers'), ('/api/v1/admin/admins/', 'admins')):
            with self.subTest(url=url):
                self.sign.reset_mock()
                rows = self._rows(url, key)
                self.assertEqual(rows['Shown']['phone'], '011-1111 1111')
                self.assertIsNone(rows['Hidden']['phone'])
                self.assertEqual(rows['Hidden']['photo_url'], f'https://signed/staff-photos/{self.hidden.id}/b.webp')
                self.assertEqual(self.sign.call_count, 1)                    # ONE call for the page
                self.assertNotIn('street_address', rows['Shown'])
                self.assertNotIn('1 Jalan Rahsia', str(rows))

    def test_a_source_users_own_phone_reaches_its_inviting_organisation(self):
        source = make_source(organisation=self.org)
        person = make_admin('source_partner', owning_org=self.org, source=source, name='Audrey')
        StaffProfile.objects.create(partner_admin=person, phone='016-845 1270')
        rows = authed_client(self.lead).get('/api/v1/admin/invitations/?kind=source').json()['source_users']
        self.assertEqual(next(r for r in rows if r['name'] == 'Audrey')['phone'], '016-845 1270')



class TheBatchSigner(TestCase):
    def test_the_batch_sign_helper_reads_supabases_list(self):
        reply = [{'path': 'staff-photos/1/a.webp', 'signedURL': '/object/sign/b40-documents/x?token=t', 'error': None},
                 {'path': 'staff-photos/2/b.webp', 'signedURL': None, 'error': 'not found'}]
        with mock.patch('apps.scholarship.storage._post', return_value=reply) as post, \
                override_settings(SUPABASE_URL='https://supa.test'):
            got = storage.create_signed_download_urls(['staff-photos/2/b.webp', 'staff-photos/1/a.webp'])
        self.assertEqual(got, {'staff-photos/1/a.webp': 'https://supa.test/storage/v1/object/sign/b40-documents/x?token=t'})
        self.assertEqual(post.call_args.args[1]['paths'], ['staff-photos/1/a.webp', 'staff-photos/2/b.webp'])
        self.assertEqual(storage.create_signed_download_urls([]), {})


class AStaffPhotoNeverReachesAnOutwardPayload(TestCase):
    """Staff only (owner, 2026-10-31): the header, the person's own Profile, the Team page. No
    student, sponsor or source-console module may name a photo or the profile row at all."""

    OUTWARD = ('serializers.py', 'pool.py', 'sponsorship.py', 'sponsor_feed.py', 'sponsor_comms.py',
               'spend_sponsor.py', 'views_sponsor.py', 'source_console.py', 'views.py')
    NAMES = ('photo_path', 'photo_url', 'staff_photo', 'staff-photos', 'StaffProfile', 'ReviewerProfile',
             'reviewer_profile')

    def test_no_outward_module_names_a_staff_photo(self):
        base = os.path.dirname(staff_photo.__file__)
        found = []
        for name in self.OUTWARD:
            src = open(os.path.join(base, name), encoding='utf-8').read()
            found += [f'{name}: {n}' for n in self.NAMES if n in src]
        self.assertEqual(found, [])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheFourthLanguage(TestCase):
    """Owner, 2026-10-31: ONE optional extra language (Mandarin, Kadazandusun, Bajau…), by name."""

    RP = '/api/v1/admin/reviewer-profile/'

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def test_it_saves_through_the_reviewer_profile_trimmed(self):
        me = make_admin('reviewer', owning_org=self.org)
        resp = authed_client(me).patch(self.RP, {'other_language': '  Kadazandusun ',
                                                 'other_language_fluency': 'fluent'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual((resp.json()['other_language'], resp.json()['other_language_fluency']),
                         ('Kadazandusun', 'fluent'))

    def test_a_language_without_fluency_or_a_fluency_without_language_is_refused(self):
        me = make_admin('reviewer', owning_org=self.org)
        client = authed_client(me)
        for body in ({'other_language': 'Bajau'}, {'other_language_fluency': 'fluent'},
                     {'other_language': '   ', 'other_language_fluency': 'conversational'}):
            with self.subTest(body=body):
                resp = client.patch(self.RP, body, format='json')
                self.assertEqual(resp.status_code, 400)
                self.assertIn('other_language_incomplete', str(resp.json()))
        self.assertEqual(client.patch(self.RP, {'other_language': 'x' * 61,
                                                'other_language_fluency': 'fluent'}, format='json').status_code, 400)
        # Clearing both together is fine.
        client.patch(self.RP, {'other_language': 'Bajau', 'other_language_fluency': 'fluent'}, format='json')
        self.assertEqual(client.patch(self.RP, {'other_language': '', 'other_language_fluency': ''},
                                      format='json').status_code, 200)

    def test_it_does_not_count_for_the_onboarding_hold(self):
        """A reviewer interviews in English, BM or Tamil: a fourth language alone never releases the hold."""
        from apps.scholarship.reviewer_onboarding import reviewer_profile_complete
        me = make_admin('reviewer', owning_org=self.org)
        StaffProfile.objects.create(partner_admin=me, highest_qualification='PhD', university='UM',
                                    graduation_year=2010, field_of_study='Law', phone='012-345 6789',
                                    other_language='Mandarin', other_language_fluency='fluent')
        self.assertFalse(reviewer_profile_complete(me))
        StaffProfile.objects.filter(partner_admin=me).update(bm_fluency='conversational')
        self.assertTrue(reviewer_profile_complete(me))

    def test_the_people_list_and_the_picker_name_it_beside_the_codes(self):
        me = make_admin('reviewer', owning_org=self.org, name='Lina')
        StaffProfile.objects.create(partner_admin=me, english_fluency='fluent',
                                    other_language='Kadazandusun', other_language_fluency='conversational')
        quiet = make_admin('reviewer', owning_org=self.org, name='Quiet')
        StaffProfile.objects.create(partner_admin=quiet, other_language='Bajau', other_language_fluency='')
        client = authed_client(self.lead)
        with mock.patch('apps.scholarship.storage.create_signed_download_urls', return_value={}):
            rows = {r['name']: r for r in client.get('/api/v1/admin/reviewers/').json()['reviewers']}
        self.assertEqual((rows['Lina']['languages'], rows['Lina']['other_language']), (['en'], 'Kadazandusun'))
        self.assertEqual(rows['Quiet']['other_language'], '')
        picker = {r['name']: r for r in client.get('/api/v1/admin/scholarship/assignable-admins/').json()['admins']}
        self.assertEqual((picker['Lina']['languages'], picker['Lina']['other_language']), (['en'], 'Kadazandusun'))


class ReviewFixL1TheDecodeGuard(TestCase):
    def test_a_compressible_oversized_png_is_refused_from_its_header_without_a_decode(self):
        img = Image.new('L', (5000, 4000), 0)                    # 20 MP of one colour: a few KB
        out = io.BytesIO()
        img.save(out, format='PNG', optimize=True)
        data = out.getvalue()
        self.assertLess(len(data), staff_photo.MAX_BYTES)
        with mock.patch('PIL.Image.Image.load', side_effect=AssertionError('decoded')):
            with self.assertRaises(staff_photo.PhotoError) as caught:
                staff_photo.reencode(data)
        self.assertEqual(caught.exception.code, 'too_large')
        self.assertEqual(staff_photo.MAX_PIXELS, 16_000_000)

    def test_a_large_jpeg_is_decoded_at_a_reduced_scale(self):
        seen = []
        real = Image.Image.draft

        def spy(self, mode, size):
            seen.append(size)
            return real(self, mode, size)
        with mock.patch('PIL.Image.Image.draft', spy):
            out = staff_photo.reencode(image_bytes('JPEG', (3000, 2000)))
        self.assertEqual(seen, [(1024, 1024)])
        with Image.open(io.BytesIO(out)) as done:
            self.assertEqual(max(done.size), 512)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ReviewFixesM1L2L3(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def _detail(self, target):
        return authed_client(self.lead).get(f'/api/v1/admin/reviewers/{target.id}/').json()

    def test_m1_the_detail_serves_a_phone_only_to_reach_a_reviewer_or_when_shared(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        StaffProfile.objects.create(partner_admin=reviewer, phone='011-1111 1111')
        qc = make_admin('qc', owning_org=self.org)
        StaffProfile.objects.create(partner_admin=qc, phone='012-2222 2222')
        shown_qc = make_admin('qc', owning_org=self.org)
        StaffProfile.objects.create(partner_admin=shown_qc, phone='013-3333 3333', share_phone_with_team=True)
        self.assertEqual(self._detail(reviewer)['phone'], '011-1111 1111')      # can be assigned cases
        self.assertEqual(self._detail(qc)['phone'], '')                          # no review, not shared
        self.assertEqual(self._detail(shown_qc)['phone'], '013-3333 3333')       # shared with the team

    def test_l2_a_new_row_shares_with_students_only_for_a_review_holder(self):
        finance = make_admin('finance', owning_org=self.org)
        authed_client(finance).patch(ME, {'job_title': 'Bursar'}, format='json')
        self.assertFalse(StaffProfile.objects.get(partner_admin=finance).share_phone_with_students)
        reviewer = make_admin('reviewer', owning_org=self.org)
        authed_client(reviewer).patch(ME, {'job_title': 'Volunteer'}, format='json')
        self.assertTrue(StaffProfile.objects.get(partner_admin=reviewer).share_phone_with_students)
        sup = make_admin('super', super_admin=True)
        authed_client(sup).get('/api/v1/admin/reviewer-profile/')
        self.assertFalse(StaffProfile.objects.get(partner_admin=sup).share_phone_with_students)

    def test_l3_the_old_web_cannot_blank_a_review_holders_phone_through_the_reviewer_profile(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        StaffProfile.objects.create(partner_admin=reviewer, phone='011-1111 1111')
        resp = authed_client(reviewer).patch('/api/v1/admin/reviewer-profile/', {'phone': '  '}, format='json')
        self.assertEqual((resp.status_code, resp.json()['error']), (400, 'phone_required'))
        self.assertEqual(StaffProfile.objects.get(partner_admin=reviewer).phone, '011-1111 1111')
        # Still accepted there during the rollout (TD-439): a non-blank phone saves.
        self.assertEqual(authed_client(reviewer).patch('/api/v1/admin/reviewer-profile/',
                                                       {'phone': '019-999 9999'}, format='json').status_code, 200)
