"""Structured family roster (the "About your family" redesign, 2026-06).

The student now enters a structured roster — Father/Mother (name + coded
profession) plus an optional pool of brother/sister/guardian (coded profession).
This module holds the profession taxonomy + the *pure* derivations that keep the
two legacy columns in sync as OUTPUTS (not inputs):

  - ``first_in_family``    → derived: True iff no sibling is in/through tertiary.
  - ``parents_occupation`` → derived: a human summary built from the roster.

Keeping the legacy columns populated means every downstream reader
(``profile_engine``, ``anomaly_engine``, ``submission_review``) keeps working with
no rewrite. NO Django imports here → safe to import from ``models.py`` for the
field ``choices``.

Profession codes are B40 / lower-M40 focused. The English label feeds the
sponsor-profile prompt + the officer summary; the frontend carries its own
en/ms/ta labels keyed by the same code (``lib/familyRoster.ts``).
"""
import re

# A person's NAME: letters + spaces + the connectors seen in Malaysian names — "/" (A/L, A/P, S/O,
# D/O), "@" (alias), initials (.), apostrophe (D'CRUZ), hyphen (NUR-AIN). NO digits — an IC / phone
# number typed into a name box is the exact error this guards (a father_name once stored as an IC).
# Mirrors lib/familyRoster.ts isValidPersonName — keep IN SYNC.
_PERSON_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\s./@'-]*$")


def is_valid_person_name(name):
    """True when ``name`` is empty (required-ness is checked elsewhere) or a plausible person name
    with no digits. Rejects a bare IC / phone number in a name field."""
    t = (name or '').strip()
    return t == '' or bool(_PERSON_NAME_RE.match(t))


#: (code, English label). Grouped only by comment — Django choices are flat.
PROFESSION_CHOICES = (
    # Employed (formal)
    ('gov', 'Government / civil servant'),
    ('professional', 'Professional / executive (engineer, accountant, manager)'),
    ('teacher', 'Teacher / educator'),
    ('uniform', 'Armed forces / police'),
    ('healthcare', 'Nurse / healthcare staff'),
    ('factory', 'Factory / production operator'),
    ('technician', 'Technician (electrical / IT / machinery)'),
    ('clerk', 'Office / admin / clerk'),
    ('private', 'Private company employee (general)'),
    ('retail', 'Cashier / sales assistant'),
    ('storekeeper', 'Store clerk / shop / warehouse worker'),
    ('fnb', 'Food & beverage / restaurant staff'),
    ('security', 'Security guard'),
    ('cleaner', 'Cleaner / general worker'),
    ('maintenance', 'Maintenance / repair (handyman, plumber, electrician)'),
    ('plantation', 'Plantation / estate worker'),
    # Self-employed / informal
    ('hawker', 'Small trader / stall / hawker'),
    ('farmer', 'Farmer (paddy / vegetables)'),
    ('smallholder', 'Smallholder (rubber / oil palm)'),
    ('fisherman', 'Fisherman'),
    ('livestock', 'Livestock / poultry'),
    ('ehailing', 'E-hailing / delivery rider'),
    ('driver', 'Driver (taxi / bus / lorry)'),
    ('construction', 'Construction / labourer'),
    ('supervisor', 'Supervisor / foreman'),
    ('mechanic', 'Mechanic / workshop'),
    ('craft', 'Tailor / craft / home business'),
    ('hairdresser', 'Hairdresser / beauty / personal care'),
    ('tuition', 'Tuition / freelance teacher'),
    ('caregiver', 'Caregiver / domestic helper'),
    ('agent', 'Insurance / sales agent'),
    ('odd_jobs', 'Odd jobs / daily wage'),
    ('self_employed', 'Self-employed / freelance'),
    # Not working / other
    ('homemaker', 'Homemaker'),
    ('retired', 'Retired / pensioner'),
    ('unemployed', 'Unemployed'),
    ('unable', 'Unable to work (illness / disability)'),
    ('deceased', 'Passed away'),
    ('no_contact', 'Not in contact'),
    ('other', 'Other'),
)
PROFESSION_LABELS = dict(PROFESSION_CHOICES)
PROFESSION_CODES = frozenset(PROFESSION_LABELS)

#: Earning professions — used in Phase 2 (roster → income earners). NOT wired yet.
NON_EARNING = frozenset({'homemaker', 'retired', 'unemployed', 'unable', 'deceased', 'no_contact'})

ROLE_CHOICES = (('brother', 'Brother'), ('sister', 'Sister'), ('guardian', 'Guardian'))
ROLE_LABELS = dict(ROLE_CHOICES)
ROLE_CODES = frozenset(ROLE_LABELS)

#: Hard cap on the optional member pool (mirrors the form).
MAX_OTHER_MEMBERS = 6

#: The structured roster columns shared by StudentProfile (the durable profile-level
#: home) and ScholarshipApplication (the per-application working copy). Same names on
#: both → they copy field-for-field. (family_context is Story-only, not mirrored.)
PROFILE_FAMILY_FIELDS = (
    'father_name', 'father_occupation', 'father_occupation_other',
    'mother_name', 'mother_occupation', 'mother_occupation_other',
    'other_family_members', 'siblings_in_school', 'siblings_in_tertiary',
)

#: Application statuses where the scholarship decision is settled → the application's
#: family copy FREEZES (a later /profile edit no longer syncs into it).
DECIDED_STATUSES = frozenset({'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected', 'withdrawn', 'expired'})


def copy_family_roster(src, dst):
    """Copy the structured roster fields between a StudentProfile and a
    ScholarshipApplication (they share field names). Pure — the caller saves dst."""
    for field in PROFILE_FAMILY_FIELDS:
        setattr(dst, field, getattr(src, field))


#: The pathway / "Your Plans" columns shared by StudentProfile (profile-level home) and
#: ScholarshipApplication (per-application working copy). Same names → copy field-for-field.
PROFILE_PATHWAY_FIELDS = (
    'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
    'chosen_programme', 'pathways_considered', 'uncertainty_reasons', 'uncertainty_note',
)


def copy_pathway(src, dst):
    """Copy the pathway fields between a StudentProfile and a ScholarshipApplication
    (they share field names). Pure — the caller saves dst."""
    for field in PROFILE_PATHWAY_FIELDS:
        setattr(dst, field, getattr(src, field))


def has_pathway(obj):
    """True if any pathway field carries data (used to decide prefill direction)."""
    return bool(
        getattr(obj, 'chosen_pathway', '') or getattr(obj, 'pathway_certainty', '')
        or getattr(obj, 'pathways_considered', None) or getattr(obj, 'pre_u_track', '')
    )


def occupation_label(code, other=''):
    """English label for a profession code; for 'other', the typed text (fallback 'Other')."""
    if code == 'other':
        return (other or '').strip() or 'Other'
    return PROFESSION_LABELS.get(code or '', '')


def derive_first_in_family(application):
    """First-in-family is a CONSEQUENCE, not a self-declared toggle: True iff no
    sibling is in or through tertiary education (the count the student enters as
    "in college or university — now or before")."""
    return (getattr(application, 'siblings_in_tertiary', None) or 0) == 0


def has_structured_roster(application):
    """True once the student has entered ANY structured roster value — the signal
    that the derived ``parents_occupation`` summary should take over from any legacy
    free text (grandfathered apps keep their free text until they re-enter)."""
    if (application.father_occupation or application.mother_occupation
            or application.father_name or application.mother_name):
        return True
    return bool(application.other_family_members)


def earning_members(application):
    """Member roles in the roster whose profession EARNS income — the prefill default
    for the income wizard's "who is working" select (Phase-2-lite harmonisation, so the
    student doesn't re-name the same people). Roles use the income wizard's vocabulary:
    father / mother / guardian / brother / sister."""
    out = []
    if application.father_occupation and application.father_occupation not in NON_EARNING:
        out.append('father')
    if application.mother_occupation and application.mother_occupation not in NON_EARNING:
        out.append('mother')
    for member in (application.other_family_members or []):
        if not isinstance(member, dict):
            continue
        role, occ = member.get('role', ''), member.get('occupation', '')
        if role in ('guardian', 'brother', 'sister') and occ and occ not in NON_EARNING and role not in out:
            out.append(role)
    return out


def parents_occupation_summary(application):
    """Build the legacy ``parents_occupation`` free-text from the structured roster,
    so the sponsor-profile prompt + officer view keep working. Returns '' when nothing
    structured is set (caller then leaves any existing free text untouched)."""
    parts = []
    if application.father_occupation:
        lbl = occupation_label(application.father_occupation, application.father_occupation_other)
        if lbl:
            parts.append(f'Father: {lbl}')
    if application.mother_occupation:
        lbl = occupation_label(application.mother_occupation, application.mother_occupation_other)
        if lbl:
            parts.append(f'Mother: {lbl}')
    for member in (application.other_family_members or []):
        if not isinstance(member, dict):
            continue
        role = ROLE_LABELS.get(member.get('role', ''), '')
        lbl = occupation_label(member.get('occupation', ''), member.get('occupation_other', ''))
        if role and lbl:
            parts.append(f'{role}: {lbl}')
    return '; '.join(parts)


def clean_other_members(raw):
    """Validate/normalise the member pool to a list of {role, occupation,
    occupation_other} dicts with known codes. Drops malformed entries; caps length.
    Pure — used by the serializer."""
    out = []
    if not isinstance(raw, list):
        return out
    for member in raw[:MAX_OTHER_MEMBERS]:
        if not isinstance(member, dict):
            continue
        role = member.get('role', '')
        occ = member.get('occupation', '')
        if role not in ROLE_CODES or occ not in PROFESSION_CODES:
            continue
        entry = {'role': role, 'occupation': occ}
        other = (member.get('occupation_other', '') or '').strip()[:120]
        if occ == 'other' and other:
            entry['occupation_other'] = other
        out.append(entry)
    return out
