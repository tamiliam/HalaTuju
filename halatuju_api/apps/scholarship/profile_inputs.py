"""The INPUTS of the AI sponsor profile: how each line of the draft and final prompts is read off
the application (pronouns, pathway, grades summary, region, quiz interests, the student's answers,
funding, the interview findings, the officer's decision, today's date).

Moved verbatim out of `profile_engine.py` (audit sprint A3.6, a moves-only split: the file was a
ledgered 1043-line oversize file). `profile_engine.py` re-exports every name, so each
`from apps.scholarship.profile_engine import ...` is unchanged, and `_build_prompt` /
`refine_sponsor_profile` still look each helper up on `profile_engine`. The readers that open the
application's documents (the STR / JKM claim gates and the Statement of Intent) stayed in
`profile_engine.py`, under the superseded-document guard. Nothing here changed.
"""
import re

from apps.courses.exam_questions import spm_grades_for, spm_grades_none_label

from .models import FundingNeed
from .profile_prompts import _BUCKET_LABELS, _BUCKET_ORDER


def _today_str():
    """Today's date as a plain 'DD Month YYYY' string, fed to the prompt so the model reasons about
    time correctly (it has no innate 'now'). MALAYSIAN date — `timezone.now()` is an aware UTC
    instant that `strftime` prints without converting, so a profile drafted after 8pm local time
    used to be stamped with YESTERDAY. Harmless for the model's purposes, which is why the old
    comment called UTC good enough; corrected with TD-209 because it is the same one-word mistake
    and there is no reason to keep an off-by-a-day date in a document. Windows-safe (no %-d)."""
    from django.utils import timezone
    return timezone.localtime().strftime('%d %B %Y')


def _yesno(v):
    if v is None:
        return 'not provided'
    return 'yes' if v else 'no'


def _alias(application):
    """The stable, non-identifying handle used everywhere this profile is read (the
    same alias the sponsor pool uses), e.g. 'S-A3F9C1'."""
    from .pool import pool_ref
    return pool_ref(application.id)


def _pronouns(application):
    """'she/her' or 'he/him' for the student, from the recorded gender (falling back to
    the Malaysian NRIC last digit: odd = male, even = female). 'not provided' if unknown —
    the model is told to avoid 'they', so it picks a sensible default rather than hedge."""
    profile = getattr(application, 'profile', None)
    g = (getattr(profile, 'gender', '') or '').strip().lower() if profile else ''
    if g in ('female', 'f', 'perempuan'):
        return 'she/her'
    if g in ('male', 'm', 'lelaki'):
        return 'he/him'
    nric = re.sub(r'\D', '', getattr(profile, 'nric', '') or '') if profile else ''
    if nric:
        return 'he/him' if int(nric[-1]) % 2 else 'she/her'
    return 'not provided'


def _pathway(application):
    """Describe the pathway, preferring the CONCRETE chosen programme + institution and
    whether it's confirmed (an offer the student holds), so the profile can name the real
    place rather than a vague 'pre-university'."""
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    bits = []
    programme = (cp.get('course_name') or '').strip()
    if programme:
        bits.append(programme)
    elif application.field_of_study:
        bits.append(str(application.field_of_study))
    institution = (cp.get('institution') or getattr(application, 'pre_u_institution', '') or '').strip()
    if institution:
        bits.append(f'at {institution}')
    if getattr(application, 'pathway_confirmed_at', None) or cp.get('source', '').startswith('offer_letter'):
        bits.append('(confirmed place — the student holds the offer)')
    track = (getattr(application, 'pre_u_track', '') or '').strip()
    if track:
        bits.append(f'stream/track: {track}')
    pc = application.pathways_considered
    if not programme and isinstance(pc, list) and pc:
        bits.append('pathways considered: ' + ', '.join(str(x) for x in pc))
    return ' '.join(bits).strip() or 'not specified'


def _reporting_date(application):
    """The offer's normalised reporting/enrolment date (S3 `reporting_date`), as
    '13 May 2026'. Lets the profile state when the student is due to report — part of the
    pathway & enrolment-confidence picture a sponsor weighs. 'not provided' when unknown."""
    d = getattr(application, 'reporting_date', None)
    if not d:
        return 'not provided'
    try:
        return f'{d.day} {d:%B %Y}'
    except (AttributeError, ValueError):
        return 'not provided'


def _siblings_studying_display(application):
    count = getattr(application, 'siblings_studying_count', None)
    return str(count) if count is not None else ''


def _income_evidence(application):
    """Documented monthly income read from any salary slip / EPF on file — usable
    authoritatively even on the STR track (a student may submit payslips/EPF as extra
    proof). Covers the salary-route members AND the STR-route earner. 'none on file' when
    no readable income document exists, so the model falls back to the reported figure."""
    # Code-health S4 #16: use effective_working_members — the #90 fix (prefill accepted
    # but never persisted leaves income_working_members empty while the docs exist) was
    # applied to verdict_engine + the blockers but this call site was missed, so the
    # sponsor/reviewer profile said "Documented income: none on file" over a readable slip.
    from .income_engine import effective_working_members, earner_monthly_income
    members = list(effective_working_members(application))
    earner = (getattr(application, 'income_earner', '') or '').strip()
    if earner and earner not in members:
        members.append(earner)
    lines = []
    for m in members:
        amt, src = earner_monthly_income(application, m)
        if amt:
            label = {'salary': 'salary slip', 'epf_estimate': 'EPF statement'}.get(src, 'document')
            lines.append(f"{m}'s {label} shows about RM{int(round(amt))}/month")
    return '; '.join(lines) if lines else 'none on file'


def _merit(application):
    """The merit on ONE 0-100 scale for every route (`exam_questions.merit_100`; STPM = overall
    CGPA / 4 x 100 since third results route S1), or 'not provided'."""
    from .serializers_admin import _application_merit_score
    m = _application_merit_score(application)
    return 'not provided' if m in (None, '') else str(m)


# Subject key → broad GROUP. We summarise results by group, never by individual subject:
# it keeps the profile readable AND avoids revealing ethnicity via a vernacular-language or
# literature subject (Bahasa Tamil/Cina, Kesusasteraan Tamil/Cina all fold into "languages"/
# "humanities"). Keys mirror the canonical list in halatuju-web/src/lib/subjects.ts. Any key
# not listed falls back to the generic "other subjects" — a raw key can never reach the prompt.
_SUBJECT_GROUP = {
    'math': 'mathematics', 'addmath': 'mathematics',
    'sci': 'sciences', 'science': 'sciences', 'addsci': 'sciences', 'phy': 'sciences',
    'chem': 'sciences', 'bio': 'sciences', 'comp_sci': 'sciences', 'sports_sci': 'sciences',
    'srt': 'sciences',
    'bm': 'languages', 'eng': 'languages', 'b_cina': 'languages', 'b_tamil': 'languages',
    'bahasa_cina': 'languages', 'bahasa_tamil': 'languages', 'bahasa_arab': 'languages',
    'bahasa_arab_tinggi': 'languages', 'bahasa_iban': 'languages',
    'bahasa_kadazandusun': 'languages', 'bahasa_semai': 'languages',
    'bahasa_punjabi': 'languages', 'bahasa_perancis': 'languages', 'bahasa_jepun': 'languages',
    'bahasa_jerman': 'languages',
    'hist': 'humanities', 'history': 'humanities', 'moral': 'humanities',
    'lit_bm': 'humanities', 'lit_eng': 'humanities', 'lit_cina': 'humanities',
    'lit_tamil': 'humanities', 'sejarah_seni': 'humanities', 'islam': 'humanities',
    'agama': 'humanities', 'pqs': 'humanities', 'psi': 'humanities',
    'tasawwur_islam': 'humanities', 'usul_aldin': 'humanities', 'al_syariah': 'humanities',
    'manahij': 'humanities', 'bible_knowledge': 'humanities',
    'geo': 'social sciences', 'ekonomi': 'social sciences', 'econ': 'social sciences',
    'poa': 'social sciences', 'acc': 'social sciences', 'business': 'social sciences',
    'keusahawanan': 'social sciences',
    'psv': 'the arts', 'music': 'the arts', 'lukisan': 'the arts', 'multimedia': 'the arts',
    'digital_gfx': 'the arts', 'reka_cipta': 'the arts', 'gkt': 'the arts',
    'eng_civil': 'technical subjects', 'eng_mech': 'technical subjects',
    'eng_elec': 'technical subjects', 'eng_draw': 'technical subjects',
    'lukisan_kejuruteraan': 'technical subjects', 'kelestarian': 'technical subjects',
    'pertanian': 'technical subjects',
}
_GROUP_ORDER = ['sciences', 'mathematics', 'languages', 'social sciences', 'humanities',
                'the arts', 'technical subjects', 'other subjects']


def _join_human(items):
    """['a','b','c'] -> 'a, b and c'."""
    items = list(items)
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def _grades_summary(profile):
    """Summarise SPM results (`spm_grades_for`: a tertiary holder's SPM prereq only) WITHOUT naming
    subjects: the A-grade count, the band mix and the broad subject GROUPS they span (no ethnicity
    via vernacular subjects). None: 'not provided', or `spm_grades_none_label` for tertiary."""
    grades = spm_grades_for(profile)
    if not grades:
        return spm_grades_none_label(profile, 'not provided')
    bands = {'A+': 0, 'A': 0, 'A-': 0}
    total = 0
    groups_seen = set()
    for key, grade in grades.items():
        if not grade:
            continue
        total += 1
        g = str(grade).strip().upper().replace('−', '-')   # normalise unicode minus
        if g in bands:
            bands[g] += 1
            groups_seen.add(_SUBJECT_GROUP.get(str(key).lower(), 'other subjects'))
    a_count = bands['A+'] + bands['A'] + bands['A-']
    if a_count == 0:
        return f'{total} subjects sat; no A-grade subjects recorded'
    band_bits = [f'{bands[b]} {b.replace("-", "−")}' for b in ('A+', 'A', 'A-') if bands[b]]
    groups = _join_human([g for g in _GROUP_ORDER if g in groups_seen])
    spanning = f' spanning {groups}' if groups else ''
    return f'{a_count} A-grade subjects out of {total} ({", ".join(band_bits)}){spanning}'


def _region(profile):
    """Town + state where available (both allowed under the redaction policy)."""
    if not profile:
        return 'not provided'
    city = (getattr(profile, 'city', '') or '').strip()
    state = (getattr(profile, 'preferred_state', '') or '').strip()
    region = ', '.join(p for p in (city, state) if p)
    return region or 'not provided'


# Human labels for the interest-quiz signals (profile.student_signals). Only the two most
# communicative categories — what FIELDS interest the student, and their WORK STYLE.
_SIGNAL_LABELS = {
    'field_mechanical': 'building & fixing', 'field_digital': 'technology & digital',
    'field_business': 'business', 'field_health': 'health & care',
    'field_creative': 'creative & design', 'field_hospitality': 'hospitality & service',
    'field_agriculture': 'agriculture', 'field_heavy_industry': 'heavy industry',
    'field_electrical': 'electrical', 'field_civil': 'civil & construction',
    'field_aero_marine': 'aeronautical & marine', 'field_oil_gas': 'oil & gas',
    'hands_on': 'hands-on work', 'problem_solving': 'problem-solving',
    'people_helping': 'helping people', 'creative': 'creative work',
}
_SIGNAL_CATEGORIES = ('field_interest', 'work_preference_signals')


def _quiz_interests(application):
    """A short, POSITIVE read of the student's interest-quiz result (profile.student_signals):
    their strongest field interests + work-style. Accretive context only — never used to doubt
    a pathway. '' when no quiz on file."""
    profile = application.profile
    signals = getattr(profile, 'student_signals', None) if profile else None
    if not isinstance(signals, dict) or not signals:
        return 'not provided'
    labels = []
    for cat in _SIGNAL_CATEGORIES:
        bucket = signals.get(cat)
        if not isinstance(bucket, dict):
            continue
        # strongest first (score desc), keep the meaningful ones (score >= 1), cap at 3/category
        ranked = sorted(((s, sc) for s, sc in bucket.items() if isinstance(sc, (int, float)) and sc > 0),
                        key=lambda kv: kv[1], reverse=True)
        for sig, _score in ranked[:3]:
            lbl = _SIGNAL_LABELS.get(sig)
            if lbl and lbl not in labels:
                labels.append(lbl)
    return ', '.join(labels) if labels else 'not provided'


def _render_qa(application):
    """The student's answers to clarifying questions — the answered Check-2 + reviewer
    resolution items (those carrying a typed response). Question = the officer-written
    prompt if present, else the item code; answer = the student's resolution_text.
    Empty marker when none, so the prompt block is never blank."""
    lines = []
    items = (application.resolution_items
             .exclude(resolution_text='')
             .order_by('resolved_at', 'created_at'))
    for it in items:
        ans = (it.resolution_text or '').strip()
        if not ans:
            continue
        q = (it.prompt or '').strip() or it.code
        lines.append(f'- Q ({it.fact}): {q}\n  A: {ans}')
    return '\n'.join(lines) if lines else 'none recorded'


def _funding(application):
    """(categories_str, programme_months, funding_note) from the simplified FundingNeed.
    (programme_months is unused by the profile prose but kept in the tuple — gap_engine
    shares this helper.)"""
    try:
        fn = application.funding_need
    except FundingNeed.DoesNotExist:
        return 'not provided', 'not provided', 'not provided'
    cats = fn.categories if isinstance(fn.categories, list) else []
    cats_str = ', '.join(str(c) for c in cats) if cats else 'not provided'
    months = fn.programme_months if fn.programme_months else 'not provided'
    note = fn.funding_note.strip() if fn.funding_note else 'not provided'
    return cats_str, months, note


def _top_choices(application):
    """The student's ranked top course choices (apply form) — 'Course at Institution (choice 1)'."""
    tc = application.top_choices if isinstance(application.top_choices, list) else []
    bits = []
    for c in tc:
        if not isinstance(c, dict):
            continue
        name = (c.get('course_name') or '').strip()
        if not name:
            continue
        inst = (c.get('institution') or '').strip()
        rank = c.get('rank')
        label = name + (f' at {inst}' if inst else '')
        if rank:
            label += f' (choice {rank})'
        bits.append(label)
    return '; '.join(bits) if bits else 'not provided'


def _other_scholarships(application):
    """Other scholarships the student has applied for / holds (keys + their free text)."""
    keys = application.other_scholarships if isinstance(application.other_scholarships, list) else []
    parts = [str(k) for k in keys if k]
    txt = (getattr(application, 'other_scholarships_text', '') or '').strip()
    if txt:
        parts.append(txt)
    return ', '.join(parts) if parts else 'none mentioned'


def _help_wanted(application):
    """What support the student asked us for on the apply form ('help with…')."""
    wants = []
    if (getattr(application, 'help_university', '') or '') == 'yes':
        wants.append('university applications')
    if (getattr(application, 'help_scholarship', '') or '') == 'yes':
        wants.append('scholarship applications & interviews')
    return ', '.join(wants) if wants else 'none indicated'


def _deliberation(application):
    """When the student is still deciding their pathway — their reasons + their own words."""
    reasons = application.uncertainty_reasons if isinstance(application.uncertainty_reasons, list) else []
    note = (getattr(application, 'uncertainty_note', '') or '').strip()
    bits = []
    if reasons:
        bits.append('reasons: ' + ', '.join(str(r) for r in reasons))
    if note:
        bits.append(note)
    return ' — '.join(bits) if bits else 'not applicable'


_VERDICT_LABELS = {
    'resolved': 'resolved at interview',
    'still_unclear': 'still unclear after interview',
    'new_concern': 'new concern raised at interview',
}


def _render_interview(application, session):
    """Render a submitted InterviewSession's findings/rubric/note as plain text for the
    refine prompt, GROUPED under the sponsor's three areas (the S4 gap `bucket`) so each
    finding lands in the matching part of the narrative. The interviewer's free-text
    rationale carries the meaning; a finding whose gap has no bucket falls under 'other'."""
    gaps_by_code, bucket_by_code = {}, {}
    for g in (application.interview_gaps or []):
        if isinstance(g, dict) and g.get('code'):
            gaps_by_code[g['code']] = g.get('question', '')
            bucket_by_code[g['code']] = (g.get('bucket') or 'other')

    grouped = {}
    for code, val in (session.findings or {}).items():
        if not isinstance(val, dict):
            continue
        verdict = _VERDICT_LABELS.get(val.get('verdict', ''), val.get('verdict', '') or 'noted')
        rationale = (val.get('rationale') or '').strip()
        context = gaps_by_code.get(code, '')
        prefix = f'On "{context}" — ' if context else ''
        bucket = bucket_by_code.get(code, 'other')
        if bucket not in _BUCKET_LABELS:
            bucket = 'other'
        grouped.setdefault(bucket, []).append(f'- [{verdict}] {prefix}{rationale}'.rstrip())

    if grouped:
        sections = [f'{_BUCKET_LABELS[b]}:\n' + '\n'.join(grouped[b])
                    for b in _BUCKET_ORDER if grouped.get(b)]
        findings_str = '\n'.join(sections)
    else:
        findings_str = 'No specific findings recorded.'

    rubric = session.rubric if isinstance(session.rubric, dict) else {}
    rubric_str = ', '.join(f'{k}: {v}' for k, v in rubric.items()) or 'not scored'
    note = (session.overall_note or '').strip() or 'none'
    return findings_str, rubric_str, note


_OFFICER_FACT_LABELS = {
    'identity': 'Identity',
    'academic': 'Academic record',
    'pathway': 'Pathway / offer',
    'income': 'Household income (B40 need)',
}


def _render_officer_decision(application):
    """Render the officer's four-fact verdict and written conclusion as plain text — so the
    FINAL reflects the actual decision. The monetary amount is deliberately NOT included: the
    recommended sum is shown to the sponsor separately (a header figure), and the profile prose
    must not state it or advocate (owner decision 2026-06-29)."""
    ov = application.officer_verdict if isinstance(application.officer_verdict, dict) else {}
    lines = []
    for fact in ('identity', 'academic', 'pathway', 'income'):
        val = (ov.get(fact) or '').strip()
        if val:
            lines.append(f'- {_OFFICER_FACT_LABELS[fact]}: {val}')
    verdict_str = '\n'.join(lines) if lines else '- not recorded'

    conclusion = (getattr(application, 'verdict_reason', '') or '').strip() or 'none recorded'

    return (
        f'Four-fact verification verdict:\n{verdict_str}\n'
        f"Officer's conclusion: {conclusion}"
    )
