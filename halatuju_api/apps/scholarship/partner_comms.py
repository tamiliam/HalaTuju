"""Partner-organisation comms — the ONE seam (2026-07-26).

Weekly + milestone emails to the referral organisations that run this bursary alongside us.
Roadmap: docs/plans/2026-07-26-partner-comms-roadmap.md.

Everything this feature decides is decided here: which organisations qualify, which
applications count as theirs, how the stages are counted, who an email would go to, and
whether a kind is switched on.

`render()` (at the foot of this module) turns a stored template into a subject + plain-text
body + inner HTML. **It never sends.** The envelope is `emails.send_partner_email`, the
sequencing is `partner_notify`, and this module talks to SMTP nowhere — which is what keeps
it cheap to test.

Three things that are easy to get wrong and are therefore fixed here:

1. **Attribution is the referral CHIP, never the FK.** `partner_applications` filters on
   `profile__referral_source == org.code`, the same signal the Sources student count and the
   Applications-list Source filter use. The stored `referred_by_org` FK drifts (a self-referral
   chip left pointing at an old partner), which is what previously inflated CUMIG.
   `views_admin._source_application_counts` calls this function, so the digest and the admin
   screen cannot disagree.

2. **Recipients are the organisation's own contact email and nothing else.** NOT
   `PartnerAdmin` rows: the only `partner`-role logins that exist belong to the HalaTuju
   course-selector relationship (created 2026-03-17, `owning_organisation` NULL, no B40 scope
   at all). Emailing them bursary progress would put applicant data in front of an audience
   attached for a different product. Owner correction, 2026-07-26.

3. **"Last activity" is a document upload, never `application.updated_at`.** `updated_at` is
   `auto_now`, so our own background work bumps it — verdict scoring, re-extraction, the
   institution sync, even a notification stamp. A student untouched for a month would read as
   active this morning, and the partner would stop chasing exactly the person who needs it.

Import direction: models + branding only. No view, no command, no email module imports here
(the renderer takes plain data), so this stays cheap to test.
"""
import hashlib
import re
from html import escape as html_escape

from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Max, Q

from . import email_templates
from .models import ApplicantDocument, PartnerEmailTemplate, ScholarshipApplication

# The platform's own bursary programme — the "house" organisation, i.e. us. It is the residual
# bucket in `_source_application_counts` (every applicant no external partner claimed), and it
# is NEVER a partner-email recipient: we have the officer cockpit, and a digest of our own
# students addressed to ourselves is noise. Kept as a code, mirroring views_admin.
HOUSE_ORG_CODE = 'brightpath'

# How many rows the chase table carries before it truncates with a note. Generous: with no
# partner console there is nowhere to go and look the rest up, so the email IS the list.
MAX_CHASE_ROWS = 50

# A date older than this many days is flagged in the chase table, so the reader can see whom
# to ring first without reading every row.
STALE_DAYS = 14

# `weekly_summary` skips a week whose counts are identical to the last one sent. The chase list
# does NOT: a partner whose stragglers have not moved is precisely who needs chasing, so it
# skips only when the list is empty. Owner-flagged interpretation, 2026-07-26 — flip this to
# make the rule literal for both.
SKIP_UNCHANGED = {'weekly_summary'}


# ── the five kinds ────────────────────────────────────────────────────────────

# Per-kind placeholder allowlist. A template saved with anything else is rejected: an unknown
# token would render literally into a partner's inbox as `{whatever}`.
PLACEHOLDERS = {
    'weekly_summary': {'org_name', 'contact_person', 'programme_name', 'counts_table',
                       'team_signoff'},
    'shortlisted_followup': {'org_name', 'contact_person', 'programme_name', 'count',
                             'student_table', 'team_signoff'},
    'awaiting_review': {'org_name', 'contact_person', 'programme_name', 'count',
                        'student_list', 'team_signoff'},
    'awarded': {'org_name', 'contact_person', 'programme_name', 'count', 'student_list',
                'team_signoff'},
    'assigned': {'org_name', 'contact_person', 'programme_name', 'student_name',
                 'team_signoff'},
    # The student's own copy of `assigned`. No `contact_person` — that token is the organisation's
    # named contact and would greet a student by a stranger's name. `support_email` is here because
    # this email names a NEW party who might plausibly contact them, so it carries the safety line.
    'student_assigned': {'org_name', 'programme_name', 'student_name', 'team_signoff',
                         'support_email', 'programme_name_ms', 'team_signoff_ms'},
    # ── the five reviewer emails (request #10, 2026-08-02) ────────────────────────
    # English only — these go to our own volunteers, so no `*_ms` twins. `ref` is the Scholar-code
    # the reviewer triages by; `dashboard_link` is the one CTA every reviewer email shares.
    'reviewer_assigned': {'reviewer_name', 'ref', 'programme', 'review_by', 'dashboard_link',
                          'team_signoff'},
    # ⚠ `qc_comments` is FREE-FORM STAFF PROSE and is therefore a STRUCTURAL BLOCK, not a scalar.
    # A scalar is substituted into the body, so a QC who happens to type `{ref}` in their comments
    # would have it filled in on the next pass — substitution-order injection. A block is placed
    # after every scalar is resolved, so whatever the QC wrote arrives verbatim.
    'qc_returned': {'reviewer_name', 'ref', 'applicant_name', 'qc_comments', 'dashboard_link',
                    'team_signoff'},
    'qc_rejected': {'reviewer_name', 'ref', 'applicant_name', 'qc_comments', 'dashboard_link',
                    'team_signoff'},
    # The old single `verdict_due` email split in two: the engine has no conditionals, and the
    # overdue branch changes both the subject and the opening sentence, so one body cannot say both.
    'verdict_due_soon': {'reviewer_name', 'ref', 'applicant_name', 'due_by', 'dashboard_link',
                         'team_signoff'},
    'verdict_overdue': {'reviewer_name', 'ref', 'applicant_name', 'due_by', 'dashboard_link',
                        'team_signoff'},
}

KINDS = tuple(k for k, _ in PartnerEmailTemplate.KIND_CHOICES)

# The two kinds the weekly cron sends; the rest are event-driven.
WEEKLY_KINDS = ('weekly_summary', 'shortlisted_followup')

_TOKEN_RE = re.compile(r'\{([a-z_]+)\}')


def unknown_placeholders(kind, *parts):
    """Placeholder tokens in `parts` that this kind does not supply — sorted, so an error
    message is stable. Empty tuple means the template is safe to save."""
    return email_templates.unknown_placeholders(PLACEHOLDERS.get(kind, set()), *parts)
# ── the voice guard ───────────────────────────────────────────────────────────

# Owner ruling, 2026-07-26: a partner organisation co-owns this bursary and may market it as
# its own; its students are the ORGANISATION's, not the reader's. These phrasings all cast the
# partner as a conduit or hand the students to the individual reading the email, so they are
# refused on save. A copy rule that lives only in a reviewer's head gets edited away later.
BANNED_PHRASES = (
    'students you send',
    'students you refer',
    'your referral',
    'referred by you',
    'thank you for referring',
    'your students',
)


def banned_phrases(*parts):
    """Conduit/ownership phrasings present in `parts`, sorted. Empty means the copy is clean."""
    return email_templates.banned_phrases(BANNED_PHRASES, *parts)
# ── who qualifies ─────────────────────────────────────────────────────────────

def qualifying_partners():
    """The organisations a partner email can actually reach, ordered by name.

    Active, has a contact email, and is not the house org. Today this is EMPTY on prod — nine
    referral partners, none with an address on file — which the admin screen states plainly
    rather than looking as though it is working.
    """
    from apps.courses.models import PartnerOrganisation
    return list(
        PartnerOrganisation.objects
        .filter(is_active=True)
        .exclude(code=HOUSE_ORG_CODE)
        .exclude(contact_email='')
        .order_by('name')
    )


def recipient_for(org):
    """The single address this organisation is written to, or '' when it has none.

    Deliberately NOT a list built from `PartnerAdmin` — see the module docstring. Returned as a
    list so a caller can log it and so adding a real multi-recipient field later does not
    change the call sites.
    """
    email = (getattr(org, 'contact_email', '') or '').strip().lower()
    return [email] if email else []


def is_enabled(kind):
    """True when this kind may send.

    A PARTNER kind needs BOTH gates: the platform flag and the template's own switch. A STUDENT
    kind needs only its own switch (owner, 2026-08-01) — ``PARTNER_COMMS_ENABLED`` answers "what do
    ORGANISATIONS receive?", and a student's notice that an organisation can see their details must
    not disappear because the partner feature was taken dark for an unrelated reason.
    """
    exempt = PartnerEmailTemplate.STUDENT_KINDS | PartnerEmailTemplate.REVIEWER_KINDS
    if kind not in exempt and not getattr(settings, 'PARTNER_COMMS_ENABLED', False):
        return False
    return PartnerEmailTemplate.objects.filter(kind=kind, enabled=True).exists()


def template_state(kind):
    """`'missing'` / `'off'` / `'on'` — what the stored row says about this kind.

    ⚠ THE THREE STATES ARE NOT TWO. A caller that only asks "is it enabled?" cannot tell a template
    the owner switched OFF from a template that was never seeded, and for the five REVIEWER kinds
    those must behave in opposite directions: `off` means STOP (they are live emails, and a switch
    that does not stop them is a lie the screen tells), while `missing` means fall back to the
    hard-coded sender so a seeding slip cannot silence working mail. See `emails._reviewer_render`.
    """
    tpl = PartnerEmailTemplate.objects.filter(kind=kind).only('enabled').first()
    if tpl is None:
        return 'missing'
    return 'on' if (tpl.enabled and is_enabled(kind)) else 'off'


# ── attribution + counts ──────────────────────────────────────────────────────

# The ONE field that attributes an application to an organisation. Named here so the digest and
# the Sources screen cannot drift onto different signals — see the module docstring.
CHIP_FIELD = 'profile__referral_source'


def partner_applications(org):
    """Every bursary application attributed to this organisation, by referral CHIP.

    THE single definition of "this partner's students". `views_admin._source_application_counts`
    derives from `chip_tally()` below, and a test asserts the two agree for every organisation,
    so the weekly digest and the Sources screen can never report different numbers.
    """
    return ScholarshipApplication.objects.filter(**{CHIP_FIELD: org.code})


def chip_tally():
    """`{chip: n}` across every application — one query. NULL/'' collapse to ''.

    Org-fence: intentionally GLOBAL. The Sources registry lists every organisation and the house
    org's count is the residual (total − claimed), so this tally must span all tenants. Single
    tenant today; revisit the residual split if that changes.
    """
    return {
        (row[CHIP_FIELD] or ''): row['n']
        # org-fence: GLOBAL by design (the house-org residual spans all tenants; see above)
        for row in ScholarshipApplication.objects.values(CHIP_FIELD).annotate(n=Count('pk'))
    }


# The reconciled stage lines. The owner asked for five figures; those five do not sum to the
# total, so three more exist — a partner must never receive numbers that do not add up.
# `recommended` is folded into "Under review" ON PURPOSE: it is masked from the student, so it
# must not reach a partner as a near-certainty either.
STAGE_LINES = (
    ('not_shortlisted', ('submitted',)),
    ('shortlisted', ('shortlisted',)),
    ('awaiting_review', ('profile_complete',)),
    ('under_review', ('interviewing', 'interviewed', 'recommended')),
    ('awarded', ('awarded', 'active', 'maintenance')),
    ('rejected', ('rejected',)),
    ('closed', ('withdrawn', 'expired', 'closed')),
)


def stage_counts(org):
    """`{line: n}` for this organisation, plus `total`. Every line sums to `total`.

    `total` is the sum of the RAW tally, not of the lines, so a status that no line claims
    would break the reconciliation test loudly instead of vanishing from the email.
    """
    rows = dict(
        partner_applications(org)
        .values_list('status')
        .annotate(n=Count('pk'))
        .values_list('status', 'n')
    )
    counts = {line: sum(rows.get(s, 0) for s in statuses) for line, statuses in STAGE_LINES}
    counts['total'] = sum(rows.values())
    return counts


def fingerprint(counts):
    """A short, stable hash of one organisation's counts — the weekly-summary skip test.

    Order-independent (sorted keys) so a dict-ordering change never looks like movement.
    """
    payload = ';'.join(f'{k}={counts[k]}' for k in sorted(counts))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]


def last_fingerprint(org, kind):
    """The fingerprint of the newest logged send for this pair, or '' if never sent.

    Send state has exactly one home — the log — so there is no second copy to drift.
    """
    from .models import PartnerEmailLog
    row = (PartnerEmailLog.objects
           .filter(organisation=org, kind=kind, ok=True)
           .order_by('-sent_at').values_list('fingerprint', flat=True).first())
    return row or ''


# ── the chase table ───────────────────────────────────────────────────────────

def chase_rows(org):
    """The organisation's shortlisted-but-incomplete students, oldest application first.

    Each row is `(name, applied, last_activity)` with both dates as `date` objects (or None):

    * `applied` — `submitted_at`, exact and set once.
    * `last_activity` — the newest LIVE document upload, falling back to `submitted_at` when
      they have uploaded nothing since. **Never `updated_at`** (see the module docstring): a
      system-side save must not make a dormant student look active.
    """
    apps = list(
        partner_applications(org)
        .filter(status='shortlisted')
        .select_related('profile')
        .order_by('submitted_at')
    )
    if not apps:
        return []
    newest = dict(
        ApplicantDocument.objects
        .filter(application__in=apps, superseded_at__isnull=True)
        .values_list('application_id')
        .annotate(last=Max('uploaded_at'))
        .values_list('application_id', 'last')
    )
    rows = []
    for app in apps:
        applied = app.submitted_at
        upload = newest.get(app.id)
        activity = upload if (upload and applied and upload > applied) else applied
        rows.append((
            (getattr(app.profile, 'name', '') or '').strip() or f'Applicant #{app.id}',
            applied.date() if applied else None,
            activity.date() if activity else None,
        ))
    return rows


def milestone_queryset(kind):
    """Applications due a milestone email: in the target state and not yet stamped.

    The state is re-checked here, at send time, rather than trusted from when the transition
    happened — which is what stops a reverted transition
    (`revert_if_profile_incomplete`, `awarded → recommended`) from producing an email.
    """
    if kind == 'awaiting_review':
        return ScholarshipApplication.objects.filter(
            status='profile_complete', partner_awaiting_notified_at__isnull=True,
        )
    if kind == 'awarded':
        return ScholarshipApplication.objects.filter(
            Q(status__in=('awarded', 'active', 'maintenance')),
            partner_awarded_notified_at__isnull=True,
        )
    raise ValueError(f'not a milestone kind: {kind}')


# ── rendering: a stored template becomes a subject + text + HTML ──────────────

# The count lines, in email order, with their English labels. v1 is English-only (as every existing
# staff/partner email is), so these live here rather than in the i18n catalogues; a per-org language
# column is the obvious later extension.
STAGE_LABELS = (
    ('not_shortlisted', 'Not yet shortlisted'),
    ('shortlisted', 'Shortlisted — application incomplete'),
    ('awaiting_review', 'Awaiting review'),
    ('under_review', 'Under review'),
    ('awarded', 'Awarded'),
    ('rejected', 'Rejected'),
    ('closed', 'Closed or lapsed'),
)

TOTAL_LABEL = 'Bursary students in total'

# What the chase table's second date actually measures, stated IN the email so the figure cannot be
# over-read. Deliberately not a template token: it explains the table and must not be editable away
# from it.
CHASE_FOOTNOTE = (
    'Last activity is the date of the student’s most recent document upload — the one '
    'action of theirs we timestamp. Dates more than a fortnight old are marked.'
)

# Greeting fallback when an organisation has given us no contact person. "Dear ," would be worse.
NO_CONTACT_GREETING = 'colleagues'

_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def fmt_date(value):
    """`12 Jun 2026`. British, hand-formatted (never locale-dependent); '' for None."""
    if not value:
        return ''
    return f'{value.day} {_MONTHS[value.month - 1]} {value.year}'


# HTML-escape an interpolated value. Shared with every editable-email family now that sponsor
# comms is the second one — see `email_templates.esc`. The local alias keeps this module's many
# call sites unchanged.
_esc = email_templates.esc
def _counts_blocks(counts):
    """The stage table as `(html, text)` — lines in `STAGE_LABELS` order, then the total."""
    cell = 'padding:5px 0;border-top:1px solid #f3f4f6;'
    rows = ''.join(
        '<tr><td style="' + cell + '">' + _esc(label) + '</td>'
        '<td style="' + cell + 'text-align:right;font-weight:600;">'
        + _esc(counts.get(key, 0)) + '</td></tr>'
        for key, label in STAGE_LABELS
    )
    tcell = 'padding:5px 0;border-top:1px solid #e5e7eb;font-weight:600;'
    total = ('<tr><td style="' + tcell + '">' + _esc(TOTAL_LABEL) + '</td>'
             '<td style="' + tcell + 'text-align:right;">'
             + _esc(counts.get('total', 0)) + '</td></tr>')
    html = ('<table role="presentation" style="width:100%;border-collapse:collapse;'
            'font-size:13px;margin:0 0 12px;">' + rows + total + '</table>')
    labels = [label for _, label in STAGE_LABELS] + [TOTAL_LABEL]
    width = max(len(label) for label in labels)
    lines = [f'{label.ljust(width)}  {counts.get(key, 0)}' for key, label in STAGE_LABELS]
    lines.append(f'{TOTAL_LABEL.ljust(width)}  {counts.get("total", 0)}')
    return html, '\n'.join(lines)


def _chase_blocks(rows, today=None):
    """The chase table as `(html, text)`: Student · Applied · Last activity, both plain dates.

    Capped at `MAX_CHASE_ROWS` with an explicit note — a silent truncation would read as "that is
    everyone". A last-activity date older than `STALE_DAYS` is marked, so the reader can see whom to
    ring first without reading every row.
    """
    today = today or timezone.localdate()
    shown, dropped = list(rows[:MAX_CHASE_ROWS]), max(0, len(rows) - MAX_CHASE_ROWS)
    th = ('font-size:11px;font-weight:600;color:#6b7280;padding:6px 8px 6px 0;'
          'border-bottom:1px solid #e5e7eb;')
    body, text_rows = [], []
    for name, applied, activity in shown:
        stale = bool(activity and (today - activity).days > STALE_DAYS)
        cell = 'padding:5px 8px 5px 0;border-bottom:1px solid #f3f4f6;'
        date_cell = cell + 'text-align:right;white-space:nowrap;'
        last_cell = date_cell + ('color:#b45309;font-weight:600;' if stale else 'color:#6b7280;')
        body.append(
            '<tr><td style="' + cell + '">' + _esc(name) + '</td>'
            '<td style="' + date_cell + 'color:#6b7280;">' + _esc(fmt_date(applied)) + '</td>'
            '<td style="' + last_cell + '">' + _esc(fmt_date(activity)) + '</td></tr>'
        )
        text_rows.append(
            f'{name}  —  applied {fmt_date(applied)}, '
            f'last activity {fmt_date(activity)}{" *" if stale else ""}'
        )
    html = ('<table role="presentation" style="width:100%;border-collapse:collapse;'
            'font-size:12.5px;margin:0 0 10px;">'
            '<tr><th style="' + th + 'text-align:left;">Student</th>'
            '<th style="' + th + 'text-align:right;">Applied</th>'
            '<th style="' + th + 'text-align:right;">Last activity</th></tr>'
            + ''.join(body) + '</table>')
    text = '\n'.join(text_rows)
    if dropped:
        more = f'… and {dropped} more, not listed here.'
        html += ('<p style="margin:0 0 10px;font-size:12.5px;color:#6b7280;">'
                 + _esc(more) + '</p>')
        text += '\n' + more
    html += ('<p style="margin:0 0 12px;font-size:11.5px;color:#9ca3af;">'
             + _esc(CHASE_FOOTNOTE) + '</p>')
    text += '\n\n' + CHASE_FOOTNOTE
    return html, text


def _list_blocks(names):
    """A plain student list as `(html, text)` — the shared bulleted-list block."""
    return email_templates.list_blocks(names)
#: Tokens rendered as a BLOCK (a table, a list, or free prose) rather than substituted as a scalar.
#: `render` guarantees every one a kind declares is filled, so none can survive into an inbox.
STRUCTURAL_TOKENS = frozenset({
    'counts_table', 'student_table', 'student_list', 'qc_comments',
})


def _blocks_for(context):
    """`{token: (html, text)}` for the structural tokens this context supplies."""
    out = {}
    if 'counts' in context:
        out['counts_table'] = _counts_blocks(context['counts'])
    if 'rows' in context:
        out['student_table'] = _chase_blocks(context['rows'], context.get('today'))
    if 'names' in context:
        out['student_list'] = _list_blocks(context['names'])
    if 'qc_comments' in context:
        out['qc_comments'] = _prose_blocks(context['qc_comments'])
    return out


def _prose_blocks(text):
    """Free-form staff prose as `(html, text)` — paragraphs preserved, everything escaped.

    ⚠ A BLOCK, NOT A SCALAR, and that is the security half of the decision. A scalar is substituted
    into the body before the next pass, so a QC who typed a `{token}` in their comments would have
    it resolved as if the template had asked for it. A block is placed after substitution finishes,
    so what the QC wrote reaches the reviewer exactly as written and nothing inside it is read as
    an instruction.
    """
    body = (text or '').strip()
    if not body:
        return ('', '')
    paras = [p.strip() for p in body.split('\n\n') if p.strip()]
    html = ''.join(
        f'<p style="margin:0 0 12px;">{html_escape(p).replace(chr(10), "<br>")}</p>'
        for p in paras)
    return (html, body)


def _scalars(context):
    """`{token: value}` for the plain tokens, with branding + the greeting fallback filled in."""
    from . import branding
    platform = branding.platform()
    contact = (context.get('contact_person') or '').strip() or NO_CONTACT_GREETING
    return {
        'org_name': context.get('org_name', ''),
        'contact_person': contact,
        'programme_name': context.get('programme_name') or platform.programme_name('en'),
        'team_signoff': context.get('team_signoff') or platform.team_signoff('en'),
        'count': context.get('count', ''),
        'student_name': context.get('student_name', ''),
        'support_email': context.get('support_email') or platform.email_support,
        # Malay variants of the two brand tokens. A partner email is English throughout, but a
        # STUDENT email carries both languages in one body, and `programme_name`/`team_signoff`
        # resolve to English — so the Malay half rendered "Program BrightPath Bursary" signed by
        # "The BrightPath Bursary Team". Supplying the ms forms as tokens keeps that half inside
        # per-organisation branding instead of hard-coding a brand literal into the stored copy.
        'programme_name_ms': context.get('programme_name_ms') or platform.programme_name('ms'),
        'team_signoff_ms': context.get('team_signoff_ms') or platform.team_signoff('ms'),
        # ── reviewer tokens (request #10). English only — internal staff mail. ──
        # `reviewer_name` falls back to "there" the way the hard-coded senders always have: a
        # reviewer with no name on file must still get a greeting, not "Dear ,".
        'reviewer_name': (context.get('reviewer_name') or '').strip() or 'there',
        'ref': context.get('ref') or '—',
        'applicant_name': context.get('applicant_name') or '—',
        'programme': context.get('programme') or '',
        'review_by': context.get('review_by') or '',
        'due_by': context.get('due_by') or '',
        'dashboard_link': context.get('dashboard_link') or '',
    }


# Substitute the scalar tokens; the shared implementation. The template text is escaped by the
# caller BEFORE this runs (a `{token}` survives escaping), so `escape` applies to the VALUES.
_fill = email_templates.fill
def render(kind, template, context):
    """A stored template + one organisation's data → `(subject, text_body, html_body)`.

    The mechanics — blank-line paragraphs, structural-token blocks, escaping, subject
    flattening — live in `email_templates.render`, shared with the sponsor family. What stays
    HERE is the partner vocabulary: which scalars and which tables this family supplies.
    """
    # ⚠ EVERY structural token this kind DECLARES gets a block, even when the caller supplied no
    # data for it. Without this, a caller that omits one leaves `{qc_comments}` sitting literally
    # in a reviewer's inbox — the exact failure the placeholder allowlist exists to prevent, and
    # one that no exception reports. Found by the existing "no placeholder survives" test the day
    # the first block-valued token was added, which is the whole reason that test walks EVERY kind
    # with a deliberately thin context.
    blocks = _blocks_for(context)
    for token in PLACEHOLDERS.get(kind, ()):
        if token in STRUCTURAL_TOKENS:
            blocks.setdefault(token, ('', ''))
    return email_templates.render(
        template.subject, template.body, _scalars(context), blocks)
