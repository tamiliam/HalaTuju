"""Pathway (offer-letter) verification — the student-facing clinical check.

Mirrors ``academic_engine`` for the results slip: a single pure source
(``student_offer_check``) that the FE OfferLetterChecklist AND Cikgu Gopal both
consume, so the checklist and the coach can never disagree. Reads ONLY the
student's own document + profile (never admin data).

Two real identity checks — **Name** and **IC** (the IC is the strong one; names can
coincide, the NRIC can't) — plus a set of surfaced **data points** (programme,
institution, issuer, offer date, intake, address) the officer eyeballs. The
programme/institution can legitimately differ from what the student declared at
apply time (they may have changed their plan), so those are NOT hard checks.
"""
from __future__ import annotations

import re

from .vision import name_match, nric_match


# ── Lenient offer-vs-declared pathway matcher ────────────────────────────────
# The student declares a *specific* college/programme at apply time (via the
# eligibility filter, or a pre-U school/track). The offer letter names the same
# two facts. We compare them leniently: an offer counts as "matching" the
# declaration unless it is TOTALLY off (a different place / a different field),
# because catalogue names and printed offer-letter wording differ in harmless
# ways ("KM Melaka" vs "Kolej Matrikulasi Melaka"). We only flag a real clash —
# SMK Temerloh vs SMK Mentakab, Asasi Pertanian vs Asasi Pintar, Dip Horticulture
# vs Dip Electricity at the same UPM — so the student is never nagged on a match.

# Words that carry NO distinguishing signal — institution-type, qualification-type,
# and connectors. Field words (pertanian/pintar/sains/electricity…) and place names
# (melaka/temerloh/mentakab…) are deliberately NOT here: those are what distinguish.
_GENERIC_TOKENS = frozenset({
    # institution type
    'kolej', 'college', 'matrikulasi', 'smk', 'sekolah', 'menengah', 'kebangsaan',
    'kampus', 'campus', 'universiti', 'university', 'uni', 'politeknik', 'polytechnic',
    'institut', 'institute', 'pusat', 'akademi', 'academy', 'tinggi', 'harian',
    'jabatan', 'fakulti', 'faculty', 'school',
    # qualification / pathway type
    'asasi', 'foundation', 'diploma', 'ijazah', 'sarjana', 'muda', 'degree', 'bachelor',
    'program', 'programme', 'sijil', 'certificate', 'persediaan', 'pengajian',
    'tingkatan', 'form', 'stpm', 'matrik', 'matriculation', 'pra',
    # issuer / ministry / administrative boilerplate printed on official letters. NONE of these
    # name a field or a place, so they must never count as a distinguishing token — else an
    # offer whose programme line reads "PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN" would
    # falsely "clash" with a declared stream like "Sains" (#30). Place names + real fields are
    # still kept; only the ministry/administrative wrapper is dropped.
    'kementerian', 'ministry', 'pendidikan', 'pelajaran', 'bahagian', 'malaysia',
    'kpm', 'kpt', 'rasmi', 'surat',
    # enrolment-structure wording on an offer (a Form-6 offer reads "Tingkatan Enam
    # Semester 1 Tahun 2026" — none of which is a FIELD, so it must not "clash" with a
    # declared field like "sains sosial"). Cardinals cover "Semester Satu/Dua", "Tingkatan Enam".
    'semester', 'sesi', 'session', 'intake', 'pengambilan', 'kemasukan', 'tawaran',
    'tahun', 'year', 'satu', 'dua', 'tiga', 'empat', 'lima', 'enam', 'tujuh', 'lapan',
    'sembilan', 'sepuluh',
    # connectors / filler
    'of', 'in', 'the', 'dan', 'and', 'di', 'ke', 'dengan', 'untuk', 'bagi',
    'with', 'for',
})


def distinctive_tokens(text: str) -> set:
    """The place/field tokens that actually distinguish one offer from another:
    lowercase words 3+ chars, excluding pure digits and the generic stopwords."""
    if not text:
        return set()
    toks = re.split(r'[^a-z0-9]+', text.lower())
    return {t for t in toks if len(t) > 2 and not t.isdigit() and t not in _GENERIC_TOKENS}


def _field_status(declared: str, offer: str) -> str:
    """Compare one field (institution OR programme): 'match' (share a distinctive
    token), 'clash' (both distinctive, none shared), or 'unknown' (one side has
    nothing distinctive to compare)."""
    d = distinctive_tokens(declared)
    o = distinctive_tokens(offer)
    if not d or not o:
        return 'unknown'
    return 'match' if (d & o) else 'clash'


def offer_pathway_match(declared_programme: str, declared_institution: str,
                        offer_programme: str, offer_institution: str,
                        declared_track: str = '', offer_stream: str = '') -> str:
    """'match' / 'mismatch' / 'unknown' for an offer vs the declared pathway.

    A clash on the institution, the programme, OR the STREAM/TRACK makes it a mismatch (the
    offer is for a genuinely different place, field, or stream). Otherwise a shared distinctive
    token — or an agreeing canonical track — makes it a match. 'unknown' means there was nothing
    specific enough to compare (the student declared only a pathway type, or the offer body didn't
    read) — treated as no-conflict downstream.

    #117 (b) — the STREAM was never in the comparison, so an offer summoning the student to
    ``Bidang SAINS`` against a declared ``sains_sosial`` (#33 / #99 / #117) read as no-conflict.
    Both sides are canonicalised through ``parse_stpm_stream`` (``SAINS`` → ``sains`` vs
    ``SAINS SOSIAL`` → ``sains_sosial`` — distinct codes, so the shared 'sains' substring can't
    produce a false match), and the clash is counted ONLY when BOTH read a stream: a letter that
    prints no stream (``''``) never clashes."""
    from .offer_pathway import parse_stpm_stream
    inst = _field_status(declared_institution, offer_institution)
    prog = _field_status(declared_programme, offer_programme)
    dtrack, otrack = parse_stpm_stream(declared_track), parse_stpm_stream(offer_stream)
    track_clash = bool(dtrack and otrack and dtrack != otrack)
    track_match = bool(dtrack and otrack and dtrack == otrack)
    if inst == 'clash' or prog == 'clash' or track_clash:
        return 'mismatch'
    if inst == 'match' or prog == 'match' or track_match:
        return 'match'
    return 'unknown'


def _declared_pathway(application) -> tuple:
    """The student's declared (programme, institution) from the apply-form fields.
    Prefers the structured ``chosen_programme`` (eligibility-filter pick), falling
    back to the pre-U school/track for STPM/Matriculation. Either may be ''.

    #117 (c) — break the circularity. ``services.autofill_pathway_from_offer`` writes
    ``chosen_programme`` FROM the offer letter and stamps ``source='offer_letter_auto'``; using that
    value AS "the declaration" means ``offer_pathway_match`` compares the offer against ITSELF (45
    live applications carry this source, so their pathway clash is invisible). When the pick came
    from the offer it is NOT a student declaration — fall back to the student's own pre-U
    school/track. This can only REVEAL clashes we are currently blind to, never create a false one."""
    cp = getattr(application, 'chosen_programme', None)
    cp = cp if isinstance(cp, dict) else {}
    from_offer = cp.get('source') == 'offer_letter_auto'
    prog = '' if from_offer else (cp.get('course_name') or '').strip()
    inst = '' if from_offer else (cp.get('institution') or '').strip()
    if not inst:
        inst = (getattr(application, 'pre_u_institution', '') or '').strip()
    if not prog:
        prog = (getattr(application, 'pre_u_track', '') or '').strip()
    return prog, inst


def _name_status(candidate: str, profile_name: str, extracted: bool) -> str:
    """'match' / 'partial' / 'mismatch' / 'unreadable' / 'pending'.

    Identity is ANCHORED on the IC (exact ``name_match`` there); the offer-letter name is soft
    corroboration read by image OCR, which echoes/doubles letters ("LAKSMITHAA" for LAKSMITHA,
    #48). So a ``name_match`` mismatch is RESCUED when the tolerant same-person-across-two-
    documents matcher reads a clean match (doubled letter / w–v / boundary noise) — the exact
    counterpart of ``_nric_close`` below for the offer NRIC. Only a full tolerant 'match'
    rescues; a genuinely different name still flags."""
    if not candidate:
        return 'unreadable' if extracted else 'pending'
    if not profile_name:
        return 'pending'           # nothing on file to check against
    verdict = name_match(candidate, profile_name)
    if verdict == 'mismatch':
        from .vision import relationship_name_match
        if relationship_name_match(candidate, profile_name) == 'match':
            return 'match'
    return verdict


def _nric_digits(s: str) -> str:
    return ''.join(c for c in str(s or '') if c.isdigit())


def _nric_close(a: str, b: str, max_edits: int = 2) -> bool:
    """True if two NRICs differ only by a few digit edits — i.e. OCR noise, not a different
    person. The offer-letter NRIC is read by image-Gemini, which non-deterministically drops or
    garbles a digit (observed: 0806201578 vs 080620101578 — a dropped pair). Two DIFFERENT people's
    NRICs differ in many digits (birthdate + state + serial), so a small bounded edit distance
    distinguishes an OCR slip from a real mismatch. Pure; bounded 12×12 DP."""
    a, b = _nric_digits(a), _nric_digits(b)
    if not a or not b or abs(len(a) - len(b)) > max_edits:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1] <= max_edits


def _ic_status(candidate_nric: str, profile_nric: str, extracted: bool) -> str:
    """'match' / 'mismatch' / 'unreadable' / 'pending'.

    Identity is ANCHORED on the IC (read reliably + matched to the profile in the IC path); the
    offer-letter NRIC is only soft corroboration. So an exact match OR an OCR-close near-match
    (``_nric_close`` — a dropped/garbled digit) is 'match'; only a GROSS difference is 'mismatch'
    (a genuinely different person). This prevents a flaky offer-NRIC OCR from raising a false
    wrong-person flag while still catching a real one."""
    if not candidate_nric:
        return 'unreadable' if extracted else 'pending'
    if not profile_nric:
        return 'pending'
    if nric_match(candidate_nric, profile_nric) or _nric_close(candidate_nric, profile_nric):
        return 'match'
    return 'mismatch'


# ── Reporting-date BONUS (owner 2026-07-08) — a positive per-issuer fingerprint ──────────
# A genuine government letter SUMMONS the student to register under a precise Malay label
# (docs/scholarship/offer-letter-catalogue.md); private letters, pemakluman, interview slips and
# notices almost never carry one (live validation: 6 of 7 no-date offers were non-genuine). A
# validated official registration summons is therefore GENUINENESS evidence: it lifts the offer's
# effective genuineness step one band in the verdict ladder (suspect→treated-genuine, fake→treated-
# suspect) — so a cropped/thin-scanned OFFICIAL letter isn't punished like a private one. It NEVER
# offsets the Name/IC/pathway-mismatch content chips (it is not identity evidence), never changes
# the Official chip's colour, and never silences the Check-2 official-doc request
# (offer_official_status is untouched).
#
# Three gates, ALL required (each one kills a known bypass):
#   1. LABEL — the reporting date sits under the issuer family's own Malay label (catalogue).
#      Kills: English letters, letter-issue dates, docs with no registration summons.
#   2. PUBLIC ISSUER — the family's issuer SIGNATURE was actually found on the page (stored in
#      authenticity.present): the ministry body for STPM/matric/poly/PISMP, or one of the fixed
#      20 UA names. Kills: private letters junk-fitting a family at low probability (#93 UniMAIWP
#      best-fits a family but its page carries no public-issuer marker; #84 Swinburne likewise).
#   3. NO PRIVATE MARKER — "Sdn. Bhd." in the extracted issuer/institution hard-blocks (no public
#      university is a private company; mirrors the payslip "Pte Ltd" structural test).
_REPORTING_LABELS = {
    'stpm':          ('tarikh lapor diri',),
    'matriculation': ('tarikh kemasukan ke kolej', 'tarikh kemasukan'),
    'polytechnic':   ('tarikh dan masa daftar', 'tarikh daftar'),
    'pismp':         ('tarikh pendaftaran',),
    # UA letterheads diverge: UPSI "Tarikh Mendaftar", UMP/UTeM/UPNM "Tarikh Pendaftaran",
    # UKM "Tarikh Lapor Diri", UTHM/UTeM a bare "Tarikh" (inside the mendaftar clause — the
    # extraction prompt guards against the letter-issue Tarikh; the UA-name gate does the rest).
    'ua_offer':      ('tarikh mendaftar', 'tarikh pendaftaran', 'tarikh lapor diri',
                      'tarikh dan masa', 'tarikh'),
}
# The family's ISSUER signature label (as stored in authenticity.present) — gate 2. These are the
# weight-3 identity lines of each family in genuineness/results_doc.py; for ua_offer the entry is
# the 20-UA name signature, so "present" implies the letter names a real public university.
_FAMILY_ISSUER_SIG = {
    'stpm':          'Sektor Operasi Sekolah',
    'matriculation': 'Bahagian Matrikulasi',
    'polytechnic':   'Jabatan Pend. Politeknik & KK',
    'pismp':         'Institut Pendidikan Guru',
    'ua_offer':      'public university (UA) name',
}


def offer_reporting_bonus(doc) -> bool:
    """True when the offer carries a VALIDATED official registration summons — the reporting-date
    bonus (owner 2026-07-08). Reads only stored vision_fields; pure."""
    vf = getattr(doc, 'vision_fields', None)
    vf = vf if isinstance(vf, dict) else {}
    f = vf.get('fields', {}) if isinstance(vf.get('fields'), dict) else {}
    auth = vf.get('authenticity') if isinstance(vf.get('authenticity'), dict) else {}
    date = (f.get('reporting_date') or '').strip()
    label = (f.get('reporting_date_label') or '').strip().lower().rstrip(':').strip()
    if not date or not label:
        return False
    family = (auth.get('doc_seen') or '').strip().lower()
    allowed = _REPORTING_LABELS.get(family)
    if not allowed or not any(label.startswith(a) for a in allowed):
        return False                                    # gate 1: family's own Malay label
    issuer_sig = _FAMILY_ISSUER_SIG.get(family, '')
    present = auth.get('present') if isinstance(auth.get('present'), list) else []
    if issuer_sig not in present:
        return False                                    # gate 2: public issuer actually on the page
    haystack = ' '.join(((f.get('issuer') or ''), (f.get('institution') or ''))).upper()
    if 'SDN' in haystack and 'BHD' in haystack:
        return False                                    # gate 3: a private company is never a UA
    # gate 3b (owner 2026-07-10): a public university's PRIVATE continuing-education arm (UTM SPACE,
    # UM CCE, …) is an IPTS option — the scorer vetoes it to not_offer_letter (1.6.0), and the +1
    # date bonus must never lift it back to amber. Reads the extracted issuer/institution, so it bites
    # on DEPLOY (before any re-run). 'SPACE' padded so it never matches AEROSPACE.
    if ('PENDIDIKAN BERTERUSAN' in haystack or 'CONTINUING EDUCATION' in haystack
            or ' SPACE ' in f' {haystack} '):
        return False                                    # gate 3b: private continuing-education arm
    return True


def offer_pathway_switch(application):
    """The reviewer-facing "course switched" signal (owner 2026-07-10): the LIVE offer is for a
    genuinely DIFFERENT pathway than the most-recently superseded offer it replaced. Returns
    ``{from_programme, from_institution, to_programme, to_institution}`` or None. Surfaced ALWAYS —
    even after the student confirms the new pathway — so a switch never passes unnoticed (a confirmed
    switch used to read a silent Certain green). Pure read; no writes."""
    from .models import ApplicantDocument
    live = _latest_offer(application)
    if live is None:
        return None
    prev = (ApplicantDocument.objects.filter(
                application=application, doc_type='offer_letter', superseded_at__isnull=False)
            .order_by('-superseded_at').first())
    if prev is None:
        return None
    lc, pc = student_offer_check(live), student_offer_check(prev)
    if _field_status(pc['programme'], lc['programme']) == 'clash' \
            or _field_status(pc['institution'], lc['institution']) == 'clash':
        return {'from_programme': pc['programme'], 'from_institution': pc['institution'],
                'to_programme': lc['programme'], 'to_institution': lc['institution']}
    return None


def offer_official_status(doc) -> str:
    """Whether an offer is a genuine OFFICIAL offer for gating purposes, from its stored
    signature-genuineness (``vision_fields['authenticity']``):
      * 'genuine'     — a genuine official offer from a supported PUBLIC issuer (ua_offer / stpm /
                        matriculation / polytechnic / pismp). The only kind we can support.
      * 'not_genuine' — anything else the scorer judged: a CONDITIONAL offer / a non-official
                        notification (pemakluman / UPU-semakan) → suspect; a PRIVATE/IPTS offer →
                        unrecognised (stored as suspect); a private continuing-education ARM (SPACE
                        etc.) → not_offer_letter via the 1.6.0 scorer veto. Owner policy: cannot
                        support these.
      * 'unknown'     — genuineness not computed yet (flag off / AI outage / not re-run since the
                        signature model shipped). Never gate on our own gap — defer to the reviewer.
    """
    vf = getattr(doc, 'vision_fields', None)
    auth = vf.get('authenticity') if isinstance(vf, dict) else None
    if not isinstance(auth, dict) or not auth.get('status'):
        return 'unknown'
    return 'genuine' if auth.get('status') == 'genuine' else 'not_genuine'


def student_offer_check(doc) -> dict:
    """The clinical read of ONE offer letter against the student's own profile.

    Returns ``{name, ic}`` (each a status above) + the surfaced data-point strings
    ``{candidate_name, candidate_nric, programme, institution, issuer, offer_date,
    intake, address}``."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    sv = vf.get('student_verdict')
    f = vf.get('fields', {}) if isinstance(vf.get('fields'), dict) else {}
    # 'review_manually' = Gemini was skipped (rate-limited) → genuinely not extracted.
    extracted = bool(sv) and sv != 'review_manually'

    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    pname = getattr(profile, 'name', '') or ''
    pnric = getattr(profile, 'nric', '') or ''

    cn = (f.get('candidate_name') or '').strip()
    cnric = (f.get('candidate_nric') or '').strip()
    programme = (f.get('programme') or '').strip()
    institution = (f.get('institution') or '').strip()
    stream = (f.get('stream') or '').strip()          # #117 (b) — the offer's Bidang / stream

    # Reconcile the offer against what the student declared at apply time. Lenient:
    # only a genuine clash (different place / field / STREAM) is 'mismatch' — a naming quirk
    # is 'match', and 'unknown' when there's nothing specific declared to compare.
    application = getattr(doc, 'application', None)
    decl_prog, decl_inst = _declared_pathway(application) if application is not None else ('', '')
    # The declared TRACK is the student's own pre_u_track (a stream, e.g. 'sains_sosial'). Compared
    # against the offer's stream, both canonicalised inside offer_pathway_match. (When pre_u_track was
    # itself autofilled from the offer for a stream-less declaration, the two agree → a match, never a
    # false clash — the same benign direction as _declared_pathway's circularity break.)
    decl_track = (getattr(application, 'pre_u_track', '') or '').strip() if application is not None else ''
    pathway = offer_pathway_match(decl_prog, decl_inst, programme, institution,
                                  declared_track=decl_track, offer_stream=stream)

    intake = (f.get('intake') or '').strip()
    reporting_date = (f.get('reporting_date') or '').strip()   # report/registration = course start
    # Course-start year: prefer the intake/session year, fall back to the reporting date's year.
    iym = re.search(r'\b(20\d{2})\b', intake) or re.search(r'\b(20\d{2})\b', reporting_date)
    intake_year = iym.group(1) if iym else ''
    # Currency vs the cohort: a current intake matches the cohort's OWN year. 'current'→green / 'off'→amber
    # / '' → no signal (no year / no cohort).
    _cy = getattr(getattr(application, 'cohort', None), 'year', None) if application is not None else None
    intake_year_status = ('current' if intake_year == str(_cy) else 'off') if (intake_year and _cy) else ''

    return {
        'name': _name_status(cn, pname, extracted),
        'ic': _ic_status(cnric, pnric, extracted),
        'candidate_name': cn,
        'candidate_nric': cnric,
        'programme': programme,
        'institution': institution,
        'stream': stream,                         # #117 (b) — the offer's Bidang, for the track compare
        'issuer': (f.get('issuer') or '').strip(),
        'offer_date': (f.get('offer_date') or '').strip(),
        'intake': intake,
        'reporting_date': reporting_date,         # report/registration = course start (data point)
        'reporting_official': offer_reporting_bonus(doc),  # validated official registration summons
        'intake_year': intake_year,               # parsed course-start year
        'intake_year_status': intake_year_status, # 'current' | 'off' | '' (vs cohort year)
        'address': (f.get('candidate_address') or '').strip(),
        # Offer-vs-declared reconciliation (Check-1 pathway).
        'pathway': pathway,                       # 'match' | 'mismatch' | 'unknown'
        # Does the offer's institution match the pre-U institution SHOWN on the cockpit? Compared
        # against `pre_u_institution` (the displayed field) specifically — NOT `decl_inst`, which
        # prefers a CONFIRMED chosen_programme institution and so can diverge from what's displayed
        # (#117: chosen_programme='Kolej Tingkatan Enam Gombak' but pre_u_institution shows the
        # student's declared 'SMK P Temenggong Ibrahim'). Drives the Pre-U Institution tick.
        'institution_status': _field_status(
            (getattr(application, 'pre_u_institution', '') or '').strip() if application is not None else '',
            institution),                         # 'match' | 'clash' | 'unknown'
        'declared_programme': decl_prog,
        'declared_institution': decl_inst,
    }


# ── Reporting-date normalisation (reviewer-query S3) ─────────────────────────
# The offer letter's "report/registration" date is OCR'd as free text in many forms
# ("8 JUN 2026", "08 Jun 2026 (Isnin)", "8 HINGGA 9 JUN 2026", "20 JULAI 2026",
# "10 OGOS 2026", "28 JULAI 2024 2:30 PETANG"). This turns it into a real, sortable
# date so it can be stored on the application (a DateField) instead of re-parsed on read.
import datetime as _dt

_RD_MONTHS = {
    'januari': 1, 'jan': 1, 'february': 2, 'februari': 2, 'feb': 2,
    'march': 3, 'mac': 3, 'mar': 3, 'april': 4, 'apr': 4, 'mei': 5, 'may': 5,
    'june': 6, 'jun': 6, 'july': 7, 'julai': 7, 'jul': 7,
    'august': 8, 'ogos': 8, 'ogo': 8, 'aug': 8,
    'september': 9, 'septembar': 9, 'sept': 9, 'sep': 9,
    'october': 10, 'oktober': 10, 'okt': 10, 'oct': 10,
    'november': 11, 'novembar': 11, 'nov': 11,
    'december': 12, 'disember': 12, 'dis': 12, 'dec': 12,
}
# Longest names first so 'julai' wins over 'jul', 'jun' doesn't pre-empt 'june', etc.
_RD_MONTH_RE = re.compile('|'.join(sorted(_RD_MONTHS, key=len, reverse=True)))


def parse_reporting_date(raw):
    """Best-effort normalise an offer-letter reporting date to a ``datetime.date``, or None
    when no day/month/year can be read. Tolerant of Malay/English month names, a leading
    day range ('8 HINGGA 9 JUN 2026' → the 8th), and trailing time/day-of-week noise."""
    s = (raw or '').strip().lower()
    if not s:
        return None
    s = re.sub(r'hingga\s*\d{1,2}', ' ', s)        # date range → keep the first day
    ym = re.search(r'\b(20\d{2})\b', s)
    mm = _RD_MONTH_RE.search(s)
    if not ym or not mm:
        return None
    year, month = int(ym.group(1)), _RD_MONTHS[mm.group()]
    days = re.findall(r'\d{1,2}', s[:mm.start()])  # the day sits before the month token
    if not days:
        return None
    try:
        return _dt.date(year, month, int(days[-1]))
    except ValueError:
        return None


def _latest_offer(application):
    from .models import ApplicantDocument
    return (ApplicantDocument.objects.filter(
                application=application, doc_type='offer_letter', superseded_at__isnull=True)
            .order_by('-uploaded_at').first())


def offer_reporting_date(application):
    """The normalised reporting date from the application's latest offer letter, or None."""
    offer = _latest_offer(application)
    if offer is None:
        return None
    return parse_reporting_date(student_offer_check(offer).get('reporting_date'))


def offer_reporting_date_unknown(application):
    """True when an EXTRACTED offer letter is on file but it carries NO parseable reporting
    date — the reviewer's recurring "do you know when/where to report?" query. False when
    there's no offer, the offer wasn't read/extracted yet (a different gap), or a date is present."""
    offer = _latest_offer(application)
    if offer is None:
        return False
    vf = offer.vision_fields if isinstance(getattr(offer, 'vision_fields', None), dict) else {}
    sv = vf.get('student_verdict')
    if not sv or sv == 'review_manually':          # not extracted yet → not this gap
        return False
    return parse_reporting_date(student_offer_check(offer).get('reporting_date')) is None
