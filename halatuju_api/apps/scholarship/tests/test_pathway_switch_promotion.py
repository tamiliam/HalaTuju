"""A pathway SWITCH promotes even when the new offer letter reads worse (owner 2026-07-23).

`should_promote` compares quality, which assumes both documents describe the SAME fact -- true for
a re-scan of one offer, false when the student has changed course. Real cases:

  #13  switched Asasi Teknologi (Politeknik Nilai) -> Diploma Sains Komputer. The NEW letter read
       WORSE (its institution extracted as bare "KUALA LUMPUR"). It promoted only because it still
       cleared the quality bar; had it not, the old letter would have kept the live slot and every
       downstream verdict would have described a course the student had left.
  #107 uploaded the SAME PISMP letter twice. The institution extracted differently on each pass
       ("...GURU MALAYSIA" vs "...GURU KAMPUS KOTA BHARU" -- letterhead vs campus), which is why
       the switch test reads the PROGRAMME, not the institution.

`usable` remains a floor: an unreadable upload can never displace a good live document.
"""
from django.test import TestCase

from apps.scholarship import promotion


class _Doc:
    """A stand-in with only what promotion reads -- the module is pure by contract."""

    def __init__(self, doc_id, programme, *, official='genuine', doc_type='offer_letter'):
        self.id = doc_id
        self.doc_type = doc_type
        self.vision_fields = {
            'fields': {'programme': programme},
            'authenticity': {'status': official},
        }


class TestIsPathwaySwitch(TestCase):
    def test_different_programmes_read_as_a_switch(self):
        a = _Doc(1, 'FTV - ASASI TEKNOLOGI KEJURUTERAAN')
        b = _Doc(2, 'DSPD - DIPLOMA SAINS KOMPUTER')
        self.assertTrue(promotion.is_pathway_switch(b, a))

    def test_the_same_programme_is_a_re_scan(self):
        a = _Doc(1, 'PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP)')
        b = _Doc(2, 'PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP)')
        self.assertFalse(promotion.is_pathway_switch(b, a))

    def test_casing_and_whitespace_do_not_make_a_switch(self):
        a = _Doc(1, 'Diploma  Sains Komputer')
        b = _Doc(2, 'DIPLOMA SAINS KOMPUTER')
        self.assertFalse(promotion.is_pathway_switch(b, a))

    def test_an_unread_programme_is_not_evidence_of_a_switch(self):
        read = _Doc(1, 'DIPLOMA SAINS KOMPUTER')
        blank = _Doc(2, '')
        self.assertFalse(promotion.is_pathway_switch(blank, read))
        self.assertFalse(promotion.is_pathway_switch(read, blank))

    def test_only_offer_letters_are_switch_tested(self):
        a = _Doc(1, 'X', doc_type='results_slip')
        b = _Doc(2, 'Y', doc_type='results_slip')
        self.assertFalse(promotion.is_pathway_switch(b, a))


class TestSwitchPromotesDespiteLowerQuality(TestCase):
    def test_a_worse_reading_switch_still_takes_the_slot(self):
        """THE #13 CASE: the new letter is a different course and scores LOWER."""
        live = _Doc(10, 'FTV - ASASI TEKNOLOGI KEJURUTERAAN', official='genuine')
        switch = _Doc(11, 'DSPD - DIPLOMA SAINS KOMPUTER', official='not_genuine')
        self.assertLess(promotion.doc_quality(switch), promotion.doc_quality(live))
        self.assertTrue(promotion.should_promote(switch, live, usable=True))

    def test_a_worse_re_scan_of_the_SAME_programme_is_still_refused(self):
        """The guard the quality bar exists for -- unchanged."""
        live = _Doc(10, 'PISMP', official='genuine')
        rescan = _Doc(11, 'PISMP', official='not_genuine')
        self.assertLess(promotion.doc_quality(rescan), promotion.doc_quality(live))
        self.assertFalse(promotion.should_promote(rescan, live, usable=True))

    def test_an_unreadable_switch_cannot_displace_a_good_letter(self):
        """`usable` is a FLOOR the switch does not bypass -- it bypasses the COMPARISON."""
        live = _Doc(10, 'FTV - ASASI TEKNOLOGI KEJURUTERAAN')
        switch = _Doc(11, 'DSPD - DIPLOMA SAINS KOMPUTER')
        self.assertFalse(promotion.should_promote(switch, live, usable=False))

    def test_an_equal_or_better_switch_promotes_as_before(self):
        live = _Doc(10, 'FTV - ASASI TEKNOLOGI KEJURUTERAAN', official='not_genuine')
        switch = _Doc(11, 'DSPD - DIPLOMA SAINS KOMPUTER', official='genuine')
        self.assertTrue(promotion.should_promote(switch, live, usable=True))
