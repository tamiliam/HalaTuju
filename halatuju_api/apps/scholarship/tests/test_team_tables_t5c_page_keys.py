"""Team tables T5c P4a — `GET admin/role/` serves `page_keys`: the v2 keys the page doors ask.

The web decides its menus by the same keys the server's doors use (P1/P2). The payload's `page_keys` is
`staff_tables.page_keys` = `effective_v2` in `V2_KEYS` order, never null; an entry shows exactly when its
door (`staff_tables.DOOR_KEYS`) opens. Shapes: the 32 of `test_team_tables_t5c_doors` (the matrix's 20 +
12 extras), built by that file's own builder.
"""
from django.test import TestCase, override_settings

from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.scholarship.tests import test_team_tables_t5c_doors as doors
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class PageKeys(TestCase):

    # The doors test's builder, reused (the module is imported, not its class, so its tests run once).
    setUpTestData = classmethod(doors.DoorParity.setUpTestData.__func__)

    def _payload(self, person):
        r = authed_client(person).get('/api/v1/admin/role/')
        self.assertEqual(r.status_code, 200)
        return r.json()

    def _active(self):
        return {s: p for s, p in self.people.items() if p.is_active}

    def test_the_shapes_are_the_doors_test_shapes(self):
        self.assertEqual(set(self.people), set(doors.SHAPES))
        self.assertEqual(len(self.people), 32)

    def test_the_payload_serves_effective_v2_for_every_active_shape(self):
        for shape, person in self._active().items():
            with self.subTest(shape=shape):
                body = self._payload(person)
                self.assertTrue(body['is_admin'])
                self.assertIsInstance(body['page_keys'], list)          # never null
                self.assertEqual(body['page_keys'], list(v2.effective_v2(person)))
                self.assertEqual(body['page_keys'], list(st.page_keys(person)))
                self.assertEqual(tuple(body['page_keys']), v2.v2_order(body['page_keys']))   # V2_KEYS order

    def test_a_menu_entry_shows_exactly_when_its_door_opens(self):
        for shape, person in self._active().items():
            held = set(self._payload(person)['page_keys'])
            for door, keys in st.DOOR_KEYS.items():
                with self.subTest(shape=shape, door=door):
                    self.assertEqual(st.opens_door(person, door), set(keys) <= held)

    def test_every_edit_and_higher_tier_comes_with_its_view(self):
        for shape, person in self._active().items():
            held = set(st.page_keys(person))
            for key in held:
                with self.subTest(shape=shape, key=key):
                    self.assertEqual(set(v2.IMPLIES.get(key, ())) - held, set())
                    self.assertEqual(set(v2.HAT_IMPLIES.get(key, ())) - held, set())

    def test_the_shapes_differ(self):
        # Equality with effective_v2 proves nothing if every shape served the same list.
        served = {tuple(st.page_keys(p)) for p in self._active().values()}
        self.assertGreaterEqual(len(served), 6)
        self.assertIn((), served)                     # a referral partner / mentor login: no page key
        self.assertIn(v2.V2_KEYS, served)             # a super

    def test_an_inactive_row_or_nobody_holds_no_page_key(self):
        inactive = {s: p for s, p in self.people.items() if not p.is_active}
        self.assertEqual(len(inactive), 5)
        for shape, person in inactive.items():
            with self.subTest(shape=shape):
                self.assertEqual(st.page_keys(person), ())
                self.assertEqual(self._payload(person).get('page_keys', []), [])   # sign-in refuses it
        self.assertEqual(st.page_keys(None), ())

    def test_an_inactive_super_holds_no_page_key(self):
        # `effective_v2` answers every key for a super before it looks at `is_active`; the menu does not.
        ghost = make_admin('reviewer', super_admin=True, is_active=False)
        self.assertEqual(st.page_keys(ghost), ())
