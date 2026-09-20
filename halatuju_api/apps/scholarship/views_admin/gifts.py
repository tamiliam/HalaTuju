"""Gift programmes and intake years — the shared readers and row builders, moved verbatim
from `views_admin.py` at code health H11. The endpoints are in `gift_programmes.py` and
`intake_years.py`.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
from django.db.models import Q

from .. import branding
from ..models import Donation, ScholarshipApplication


# ── Gift programmes and their intake years (Sabah S2b, 2026-09-02) ───────────────────────────────
#
# Until now neither a Programme nor a ScholarshipCohort could be created anywhere: no endpoint, no
# screen, and `scholarship` registers no models in Django admin either. Standing up a second gift
# meant an engineer writing SQL. That is the whole reason this exists — the owner's acceptance test
# is "Suresh, as org admin, can do everything on his own without any work from me".
#
# ⚠ THE FENCE IS THE ORGANISATION, EXACTLY AS `AdminProgrammeConfigurationView` DOES IT:
# `organisation_id` derived from the caller's own `owning_organisation`, and anything outside it is
# **404, never 403** — a 403 would confirm the tenant exists. A super sees every tenant, because
# they genuinely work across them.
#
# ⚠ THESE SCREENS ARE NOT A SECOND SECURITY BOUNDARY. A programme narrows INSIDE the org wall; it
# never replaces it (`Programme` docstring). Nothing here authorises anything.

def programme_student_queryset(p):
    """Every student this gift has ever taken — the ONE answer to that question.

    ⚠ IT REACHES THROUGH THE COHORT, NOT JUST THE COLUMN.
    `ScholarshipApplication.programme` is copied from the cohort at first save and is **set-once**
    (deliberately — a cohort moved between gifts must not re-home somebody's money). So a cohort
    that has moved leaves its old applications pointing at the OLD gift, and `filter(programme=p)`
    alone would call this gift empty while its own round still held people.

    ⚠ TWO READERS, AND THEY MUST NOT DRIFT: `programme_delete_blocker` (may this gift be deleted?)
    and `programme_lifecycle` (is a switched-off gift a DRAFT or an ARCHIVE?). Both are asking the
    same question — "has anybody ever applied?" — and a disagreement would put a **Draft** badge on
    a gift whose Delete button is greyed because students applied.
    """
    from ..models import ScholarshipApplication
    # org-fence: `p` reached every caller through `_programmes_for` / `_programme_or_404`, so it is
    # already inside the caller's organisation and the join cannot widen past it.
    return ScholarshipApplication.objects.filter(
        Q(programme=p) | Q(cohort__programme=p)).distinct()


def programme_lifecycle(p, has_students):
    """Where a gift is in its life: `active` · `draft` · `archived`.

    ⚠⚠ SERVED, NOT DERIVED IN THE BROWSER (owner ruling, 2026-09-07). The card carries an
    `applications` count, so a client COULD work this out — and that is exactly the mistake
    `delete_blocked_by` exists to avoid. It lives here so the rule has one home beside the other
    gift rules, and so it can be tested in Python.

    ⚠ THE THIRD STATE IS WORKED OUT, NOT STORED — the owner chose that (option A of two, 2026-09-07)
    over a migration. The database knows only on/off; `is_active` false splits by whether anybody
    ever applied. **The known edge:** a gift switched on, applied to by nobody, then switched off
    reads DRAFT rather than ARCHIVED. Accepted, because the alternative is a stored column and a
    production data step for a distinction nothing acts on yet.

    ⚠ WHY THE SPLIT MATTERS AT ALL. "Inactive" was doing two jobs that look identical on screen and
    are nothing alike: a gift still being SET UP (born switched off — every gift starts here) and a
    gift that has FINISHED (retired, holding real students). The owner's report was that the control
    read as a duplicate of the intake year's Open/Close; naming the three states is what separates
    a lifecycle from an applications switch.
    """
    if p.is_active:
        return 'active'
    return 'archived' if has_students else 'draft'


def programme_delete_blocker(p):
    """What is holding this gift, as ``(code, count)`` — or ``(None, 0)`` if nothing is.

    ⚠⚠ ONE FUNCTION, TWO READERS, AND THAT IS THE WHOLE POINT (owner, 2026-09-07). The list row
    calls it so the Delete button can be DISABLED with the reason showing, and the delete handler
    calls it to REFUSE. If these were two pieces of code they would drift, and the drift would show
    up as the worst possible shape: a button that looks safe, a phrase typed out in full, and only
    then a refusal.

    ⚠ THE CLIENT CANNOT WORK THIS OUT FOR ITSELF, which is why it is served rather than derived.
    The list payload carries `intake_years` and `applications`; it has never carried benefactors,
    money or payment runs. A button disabled on what the client happens to know would go green for
    a gift held by a donation and refuse after the typing — rarer, and more surprising.

    ⚠⚠ AN INTAKE YEAR IS NOT A HOLDER, AND THAT IS THE OWNER'S RULING (2026-09-07): *"I don't
    [want] the ability to delete a gift programme that has students, and not merely intake years."*
    A year on its own holds nothing but the rules somebody typed a minute ago; **STUDENTS** are what
    make a gift undeletable. It used to be checked FIRST, so a gift created by mistake and given one
    stray year could never be removed, and neither could the year (TD-232). An empty year now goes
    WITH the gift, in the delete handler, inside one transaction.

    ⚠ SO THE APPLICATION QUERY MUST REACH THROUGH THE COHORT, not only the denormalised column.
    `ScholarshipApplication.programme` is copied from the cohort at first save and is **set-once**,
    so a cohort moved between gifts leaves its old applications pointing at the old gift. Filtering
    on `programme=p` alone would then call this gift empty while its own year still held somebody
    else's students — and the DB's `PROTECT` would refuse after the phrase had been typed in full.

    ⚠ THE RULE IS THE MODEL'S, NOT THIS FUNCTION'S. Every relation below is `on_delete=PROTECT`:
    the database refuses regardless. This only names WHICH, in the order a person is most likely to
    be able to act on — students, before money they cannot undo.
    """
    from ..models import Donation, PaymentRun, SponsorProgrammeMembership
    holders = (
        # org-fence: every query filters on `p`, which every caller reached through the fence
        # (`_programmes_for` / `_programme_or_404`) — already inside the caller's organisation.
        ('has_applications', programme_student_queryset(p)),
        # org-fence: as above — narrowed by the already-fenced `p`.
        ('has_benefactors', SponsorProgrammeMembership.objects.filter(programme=p)),
        # org-fence: as above.
        ('has_money', Donation.objects.filter(programme=p)),
        # org-fence: as above.
        ('has_payment_runs', PaymentRun.objects.filter(programme=p)),
    )
    for code, qs in holders:
        count = qs.count()
        if count:
            return code, count
    return None, 0


def _apply_copy_terms(p):
    """Race/ethnicity/religion words anywhere in this gift's stored apply copy. Advisory."""
    from .. import apply_copy as ac
    parts = []
    for block in (p.apply_copy or {}).values():
        if isinstance(block, dict):
            parts.append(block.get('title') or '')
            parts.append(block.get('intro') or '')
            parts.extend(b for b in (block.get('criteria') or []) if isinstance(b, str))
    return ac.sensitive_terms(*parts)


def _programme_row(p):
    """One gift, with the counts its card shows. Deliberately not a serializer: the shape is three
    joins wide and exists only here."""
    from ..models import ScholarshipCohort
    cohorts = ScholarshipCohort.objects.filter(programme=p)
    students = programme_student_queryset(p)
    open_year = cohorts.filter(is_open=True, is_active=True).values_list('year', flat=True).first()
    blocked_by, blocked_count = programme_delete_blocker(p)
    return {
        'id': p.id, 'code': p.code,
        'name_en': p.name_en, 'name_ms': p.name_ms, 'name_ta': p.name_ta,
        'is_active': p.is_active,
        # ⚠ THE BADGE'S ANSWER, SERVED. `is_active` stays beside it because it is what the PATCH
        # writes — the control still flips a boolean; `lifecycle` is only how it READS. Do not
        # re-derive this from `applications` in the browser (the `delete_blocked_by` rule).
        'lifecycle': programme_lifecycle(p, students.exists()),
        # ⚠ SERVED, NOT GUESSED. The Delete control is disabled from THIS, and the delete endpoint
        # refuses from the same function — so the button and the refusal cannot disagree. `null`
        # means nothing is holding it and it may be deleted.
        'delete_blocked_by': blocked_by,
        'delete_blocked_count': blocked_count,
        # ⚠ THE STORED MAP, VERBATIM — not `apply_copy.for_wire`, which folds ms/ta onto English
        # for a READER. The tab is an EDITOR: it has to show a blank Malay box as blank, or the
        # first save would silently promote the English text into a Malay field nobody typed.
        'apply_copy': p.apply_copy or {},
        # ⚠ ADVISORY, AND PERSISTENT RATHER THAN ONLY-ON-SAVE. `decisions.md` 2026-05-25 removed
        # ethnicity from the public copy because MyNadi's s44(6) status requires the programme not
        # to discriminate by race. The owner ruled 2026-09-09 that this WARNS and does not refuse
        # (option A) — a tenant may lawfully run an ethnicity-scoped gift. Serving it on every read
        # means the caution is on screen when somebody opens the tab, not only after they save.
        'apply_copy_sensitive': list(_apply_copy_terms(p)),
        'intake_years': cohorts.count(),
        # ⚠ COUNTED THROUGH `programme_student_queryset`, NOT `filter(programme=p)` (2026-09-08).
        # `ScholarshipApplication.programme` is denormalised and SET ONCE, so a cohort moved between
        # gifts leaves its old applications on the OLD gift — the column alone would call a gift's
        # own round empty. The Applications LIST already narrows through that same predicate, so a
        # card counting the column would disagree with the list it links to. Identical today (no
        # cohort has moved); the point is that it stays identical when one does.
        # Counted on a programme ALREADY narrowed to the caller's own `owning_organisation`, so it
        # cannot be handed another tenant's programme in the first place.
        'applications': students.count(),
        # ⚠ "HAS EVER BEEN AWARDED", NEVER `status='awarded'`. `awarded` is one stage in a chain
        # (awarded → active → maintenance → closed), so counting the status alone would make the
        # number FALL as students progress — twelve today, three next month, with nobody having
        # lost anything. `awarded_at` is stamped set-if-null by `stamp_first` and never cleared, so
        # it is the durable answer; the status arm catches any row awarded before that stamp
        # existed (`vircle.py` notes such rows exist). `closed` is deliberately absent from the
        # status arm — a closed case that was awarded carries the stamp, and one that was not is
        # not an award.
        'awarded': students.filter(
            Q(awarded_at__isnull=False)
            | Q(status__in=('awarded', 'active', 'maintenance'))).count(),
        # The year currently taking applications, or None. Named `open_year` rather than `is_open`
        # because a PROGRAMME is never open — one of its years is.
        'open_year': open_year,
        # ⚠ SERVED WHOLE, NEVER ASSEMBLED IN THE BROWSER. The console and the student site are the
        # same origin today, so `window.location.origin + …` would be right — and would silently
        # become wrong the day a tenant is served from its own domain, which is exactly what
        # `branding.frontend_url` already answers per organisation. It is also the ONE string a
        # person copies onto a poster; a half-built one is worse than none.
        # PER GIFT, NOT PER YEAR (owner ruling): the code is the gift's permanent identifier, so a
        # printed link survives every intake. `resolve_open_cohort` picks the year.
        'apply_url': '%s/scholarship/apply?p=%s' % (
            branding.for_organisation(p.organisation).frontend_url, p.code),
    }


# The requirement columns the screens tick and fill. NULL means "not applied" (S2a) — the value IS
# the switch, so unticking is writing null and there is no companion boolean to disagree with it.
REQUIREMENT_FIELDS = (
    'min_spm_a_count', 'min_spm_bplus_count', 'min_stpm_pngk', 'min_merit_score',
    'income_ceiling', 'per_capita_ceiling',
)


def _window_from(data, current=(None, None)):
    """Read `opens_on` / `closes_on` off a payload.

    Returns ``(fields, error)`` — ``fields`` is a dict of only the keys the caller actually sent,
    so a PATCH that mentions neither changes neither.

    ⚠ THREE STATES PER FIELD, AND THE MIDDLE ONE IS THE POINT: absent (leave alone), empty string
    or null (CLEAR it), or a date (set it). Without an explicit clear there is no way to withdraw
    a window once stated, and a date somebody can only ever change is a trap — the same reasoning
    as the nullable requirement thresholds (Sabah S2a).

    ⚠ THE ORDER CHECK READS THE RESULT, NOT THE PAYLOAD. `current` carries what the row holds now,
    so PATCHing only `closes_on` is still validated against the stored `opens_on`. Checking the
    payload alone would let two valid-looking edits arrive in sequence and leave the row backwards.

    ⚠ IT REFUSES, IT DOES NOT SWAP. A silent swap turns a typo into a stated fact that nobody was
    told about, on a date students are shown.
    """
    from datetime import date as _date
    fields, opens, closes = {}, current[0], current[1]
    for key in ('opens_on', 'closes_on'):
        if key not in data:
            continue
        raw = data.get(key)
        if raw in (None, ''):
            fields[key] = None
        else:
            try:
                parsed = _date.fromisoformat(str(raw).strip())
            except (TypeError, ValueError):
                return None, key
            fields[key] = parsed
        if key == 'opens_on':
            opens = fields[key]
        else:
            closes = fields[key]
    if opens and closes and closes < opens:
        return None, 'window_backwards'
    return fields, None


def round_state(c):
    """Where an intake round is in its life: `draft` · `open` · `closed` · `finished`.

    ⚠ SERVED, NEVER DERIVED IN THE BROWSER — the same rule as the gift card's `lifecycle`. Two
    copies of this would eventually disagree, and the shape of that disagreement is a badge saying
    one thing beside a control doing another.

    ⚠⚠ THE FOUR STATES ARE THREE BEHAVIOURS, AND THE MIDDLE ONE IS LOAD-BEARING:
      · `open`     — anyone may start an application and submit it.
      · `closed`   — no NEW applications; **anyone already started may still finish**. That is not
                     an oversight, it is where the intake gate sits (`ApplicationCreateView`), and
                     production relied on it: the 2026 round's switch went off on 1 July and THIRTY
                     students who were already part-way through submitted between then and 7 July.
      · `finished` — the grace period is over. A late submission is refused. **TERMINAL.**
      · `draft`    — never opened and nobody has applied. A round on its first day.

    `draft` vs `closed` is a display distinction only (both refuse new applications); it exists so a
    round being set up does not read as one that has run and stopped, which is the same confusion
    "inactive" caused on the gift card.
    """
    from ..models import ScholarshipApplication
    if c.finished_at:
        return 'finished'
    if c.is_open:
        return 'open'
    # org-fence: `c` was reached through `_programmes_for` / `_cohort_or_404`, so it is already
    # inside the caller's organisation and this count cannot widen past it.
    if ScholarshipApplication.objects.filter(cohort=c).exists():
        return 'closed'
    return 'draft'


def _cohort_row(c):
    from ..models import ScholarshipApplication
    return {
        'id': c.id, 'code': c.code, 'name': c.name, 'year': c.year,
        'is_open': c.is_open, 'is_active': c.is_active,
        # ⚠ THE STATE IS SERVED. See `round_state` — do not re-derive it in the browser.
        'state': round_state(c),
        'finished_at': c.finished_at.isoformat() if c.finished_at else None,
        'finished_by': c.finished_by,
        # ⚠ THE STATED WINDOW, AND IT IS DESCRIPTIVE (owner, 2026-09-06). Serialised beside
        # `is_open` and never instead of it: `is_open` is what decides whether a student may
        # apply, these two say when the round is MEANT to run. ISO or None — a round with no
        # stated window is normal, so the client renders a dash, not an error.
        'opens_on': c.opens_on.isoformat() if c.opens_on else None,
        'closes_on': c.closes_on.isoformat() if c.closes_on else None,
        # org-fence: same reasoning — the cohort reached here was selected through
        # `programme__in=self._programmes_for(admin)`, so it is already inside the caller's org.
        'applications': ScholarshipApplication.objects.filter(cohort=c).count(),
        # ⚠ THE PEOPLE FINISHING WOULD SHUT OUT. Served because the "close for good" dialog has to
        # name it: a closed round still lets anyone already started submit, and finishing ends that.
        #
        # ⚠⚠ `shortlisted` IS THE NOT-YET-SUBMITTED STATUS. **DO NOT reach for `submitted_at` —
        # it is `auto_now_add`, so it is stamped at CREATION and is never null.** The field that
        # records a real submission is `profile_completed_at`, and the status that gates
        # `services.confirm_profile` is `shortlisted`; that is precisely the population a finish
        # would shut out, so it is the population to count.
        # org-fence: as above.
        'unsubmitted': ScholarshipApplication.objects.filter(
            cohort=c, status='shortlisted').count(),
        'requirements': {f: getattr(c, f) for f in REQUIREMENT_FIELDS},
    }
