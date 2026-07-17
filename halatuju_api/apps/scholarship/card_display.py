"""Card display derivation + slot sanity — the ONE home for turning a possibly-corrupt
``chosen_programme`` into a clean programme/institution for the sponsor pool, and for the
guards that keep JUNK (a mis-slotted date, or an offer-body clause number) from ever being
STORED or SHOWN.

Why this exists: offer extraction can mis-slot (app #125 — the JPPKK Asasi-at-Politeknik
letter put the institution into ``course_name`` and the "Tarikh dan Masa Daftar…" line into
``institution``). This module is defence-in-depth: the read-side (``resolve_course`` /
``resolve_institution``) NEVER emits junk to a sponsor even if the stored data is wrong, and
the write-side (``sanitise_offer_slots``) never lets such a value be written.

**Institution policy (owner 2026-07-17):** a sponsor SHOULD see the institution, INCLUDING a
Form-6 secondary school — it is material to the sponsorship. ``resolve_institution`` therefore
shows ``chosen_programme.institution`` as-is (only date/clause junk is suppressed); there is no
school-block. ``SCHOOL_BLOCK_RE`` survives only as a COURSE-slot sanity check (a school name is
never a programme name), never as a privacy block.
"""
import re

# ── pattern constants (each cited by the guards below) ───────────────────────────

# Secondary-school shapes — used ONLY to reject a school that has landed in the COURSE/programme
# slot (a school is never a programme name). NOT a privacy block: an institution that is a Form-6
# school is shown to sponsors (owner 2026-07-17). Post-secondary institutions pass here anyway.
SCHOOL_BLOCK_RE = re.compile(
    r'\bSMK\b|\bSJK\b|\bSMJK\b|\bSABK\b|\bSBP\b|\bSMKA\b|'
    r'Sekolah\s+Menengah|Sekolah\s+Jenis|Sekolah\s+Kebangsaan',
    re.IGNORECASE)

# A value that is really a registration date/time line, not an institution
# (e.g. "Tarikh dan Masa Daftar: 15 JUN 2026 (8.00 PAGI - 11.00 PAGI)").
_MONTH = (r'JAN\w*|FEB\w*|MAC\w*|APR\w*|MEI|JUN\w*|JUL\w*|OGOS?|OKT\w*|NOV\w*|DIS\w*|'
          r'MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPT?\w*|OCTOBER|DECEMBER')
DATE_JUNK_RE = re.compile(
    r'\bTarikh\b|\bMasa\b|\bPAGI\b|\bPETANG\b|\bMALAM\b|\bJam\b|'
    r'\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*20\d{2}|'
    r'\d{1,2}\s+(?:' + _MONTH + r')\s+20\d{2}',
    re.IGNORECASE)

# A value whose SHAPE is an institution (so it must not sit in the course/programme slot).
INSTITUTION_SHAPE_RE = re.compile(
    r'^\s*(Politeknik|Kolej\s+Komuniti|Kolej\s+Matrikulasi|Kolej\s+Tingkatan\s+Enam|'
    r'Universiti|Institut\s+Pendidikan\s+Guru|IPG|Institut|Maktab)\b',
    re.IGNORECASE)

# A value that is really a numbered-clause header / list marker off the offer BODY
# ("2.4.", "2.5.", "3", "(iv)") — never a real stream / institution / programme. It leaks when
# a label-anchored parser latches onto the section numbering instead of the value (#47: a Form-6
# offer whose "2.4. Bidang" / "2.5. Pusat Tingkatan Enam" section labels landed as the values).
# A real value is always a multi-word phrase, so a whole value that is ONLY a numbering token is junk.
CLAUSE_NUMBER_RE = re.compile(
    r'^\s*(?:'
    r'\(?\d+(?:\.\d+)*\)?\.?'       # 2  2.4  2.4.  (3)  3)
    r'|\([ivxlcdm]{1,7}\)\.?'       # (i)  (iv)  (iv). — bracketed roman list markers
    r')\s*$',
    re.IGNORECASE)


def looks_like_school(s):
    return bool(SCHOOL_BLOCK_RE.search(s or ''))


def looks_like_date(s):
    return bool(DATE_JUNK_RE.search(s or ''))


def looks_like_institution(s):
    return bool(INSTITUTION_SHAPE_RE.match((s or '').strip()))


def looks_like_clause_number(s):
    """True when the whole value is only a numbered-clause header / list marker (#47)."""
    return bool(CLAUSE_NUMBER_RE.match((s or '').strip()))


# ── catalogue resolution ─────────────────────────────────────────────────────────

def catalogue_course_name(course_id):
    """The catalogue programme name for a course_id, or '' — never a school, always clean."""
    cid = (course_id or '').strip()
    if not cid:
        return ''
    from apps.courses.models import Course
    return (Course.objects.filter(course_id=cid).values_list('course', flat=True).first() or '').strip()


def catalogue_single_institution(course_id):
    """The catalogue institution ONLY when the course is offered at exactly one — else ''
    (a course offered at many, e.g. Asasi TVET at 10 polytechnics, can't be disambiguated
    from the course_id alone; the real one lives on the offer)."""
    cid = (course_id or '').strip()
    if not cid:
        return ''
    from apps.courses.models import CourseInstitution
    names = list(CourseInstitution.objects.filter(course_id=cid)
                 .values_list('institution__institution_name', flat=True)[:2])
    return names[0].strip() if len(names) == 1 and names[0] else ''


def _taxonomy_name(field_key, lang='en'):
    fk = (field_key or '').strip()
    if not fk:
        return ''
    from apps.courses.models import FieldTaxonomy
    row = FieldTaxonomy.objects.filter(key=fk).values_list('name_en', 'name_ms', 'name_ta').first()
    if not row:
        return ''
    return {'en': row[0], 'ms': row[1], 'ta': row[2]}.get(lang, row[0]) or row[0]


# ── pre-U display labels ─────────────────────────────────────────────────────────

_PREU_PATHWAY_LABEL = {
    'stpm': 'STPM', 'matric': 'Matrikulasi', 'asasi': 'Asasi', 'pismp': 'PISMP',
}
_TRACK_LABEL = {
    'sains': 'Sains', 'sains_sosial': 'Sains Sosial', 'kejuruteraan': 'Kejuruteraan',
    'sains_komputer': 'Sains Komputer', 'perakaunan': 'Perakaunan',
}


def preu_label(chosen_pathway, pre_u_track):
    """A canonical pre-U programme label, British-cased — 'STPM · Sains',
    'Matrikulasi · Perakaunan', 'Asasi'. '' when the pathway isn't a labelled pre-U one."""
    pw = (chosen_pathway or '').strip().lower()
    base = _PREU_PATHWAY_LABEL.get(pw, '')
    if not base:
        return ''
    track = _TRACK_LABEL.get((pre_u_track or '').strip().lower(), '')
    return f'{base} · {track}' if track else base


# ── read-side resolution (the sponsor card / anywhere anonymous) ─────────────────

def resolve_course(app, lang='en'):
    """The programme title a sponsor sees, with the Pre-U TRACK appended for STPM/Matric only
    ("Tingkatan Enam (Sains)", "Program Matrikulasi (Perakaunan)"). Base resolution order
    (never junk, never a school): (a) catalogue name via chosen_programme.course_id;
    (b) chosen_programme.course_name when sane (not institution-shaped/date/school); (c) canonical
    pre-U label; (d) the field taxonomy display name; else ''."""
    cp = app.chosen_programme if isinstance(getattr(app, 'chosen_programme', None), dict) else {}
    base = ''
    cat = catalogue_course_name(cp.get('course_id'))
    if cat:
        base = cat
    else:
        name = (cp.get('course_name') or '').strip()
        if name and not looks_like_institution(name) and not looks_like_date(name) and not looks_like_school(name):
            base = name
        else:
            base = (preu_label(getattr(app, 'chosen_pathway', ''), getattr(app, 'pre_u_track', ''))
                    or _taxonomy_name(getattr(app, 'field_of_study', ''), lang)
                    or (getattr(app, 'field_of_study', '') or '').strip())
    # Append the Pre-U track — STPM/Matric only (a poly/uni/asasi/pismp course name is complete).
    pw = (getattr(app, 'chosen_pathway', '') or '').strip().lower()
    if pw in ('stpm', 'matric'):
        tl = _TRACK_LABEL.get((getattr(app, 'pre_u_track', '') or '').strip().lower(), '')
        if tl and base and f'({tl})' not in base:
            base = f'{base} ({tl})'
    return base


def resolve_institution(app):
    """The institution a sponsor sees — the SINGLE stored ``chosen_programme.institution`` field
    (owner 2026-07-17: sponsors SHOULD see the institution, including a Form-6 secondary school —
    it is material to the sponsorship). One source, applied consistently: there is deliberately no
    ``pre_u_institution`` fallback and no school-block. The ONLY value suppressed is a mis-slotted
    date/clause junk value — a read-side safety net; that corruption is fixed at source and blocked
    write-side. Data aberrations are corrected in ``chosen_programme.institution`` itself, not
    papered over here."""
    cp = app.chosen_programme if isinstance(getattr(app, 'chosen_programme', None), dict) else {}
    inst = (cp.get('institution') or '').strip()
    if inst and not looks_like_date(inst) and not looks_like_clause_number(inst):
        return inst
    return ''


# ── write-side sanity (offer-confirm / autofill / repair) ────────────────────────

def sanitise_offer_slots(programme, institution):
    """Clean a (programme, institution) pair parsed off an offer BEFORE it is stored.
    Returns ``(programme, institution, reporting_date_str)``:
    - a date/'Tarikh' value in the institution slot is NOT stored as institution; its raw
      string is returned as ``reporting_date_str`` (the caller feeds it to
      ``parse_reporting_date`` and fills ``reporting_date`` only when currently null);
    - when ``programme`` is institution-shaped and ``institution`` is empty/junk, the
      institution-shaped value moves to the institution slot and the programme is cleared
      (so a garbage programme is never written; the read-side then resolves the real name
      from the catalogue).
    Never raises; idempotent on already-clean input."""
    prog = (programme or '').strip()
    inst = (institution or '').strip()
    reporting_raw = ''

    # A bare numbered-clause header ("2.4."/"2.5.") that leaked from the offer body's section
    # numbering is never a field value (#47) — drop it from either slot before anything else.
    if prog and looks_like_clause_number(prog):
        prog = ''
    if inst and looks_like_clause_number(inst):
        inst = ''

    if inst and looks_like_date(inst):
        reporting_raw = inst
        inst = ''

    if prog and looks_like_institution(prog):
        # The programme slot holds an institution name.
        if not inst:
            inst = prog          # recover it as the institution
        prog = ''                # never store an institution as the programme

    return prog, inst, reporting_raw
