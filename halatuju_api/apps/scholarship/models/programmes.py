"""
A programme, its code aliases, and an intake round (cohort).

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

class Programme(models.Model):
    """A gift programme — THE DURABLE LEVEL of the platform hierarchy (2026-07-26).

    Hierarchy: HalaTuju (platform) -> Organisation -> **Programme** -> Year (intake)
    -> the student's individual award.

    A Programme **IS** the gift ("the BrightPath Bursary", "the Sabah Bursary") — not a
    container for one. **One gift per programme** (owner ruling; see decisions.md
    "One gift per Programme", 2026-07-26). It is the level that NEVER LAPSES: students
    join annually into the same programme, and each annual intake is a
    ``ScholarshipCohort`` hanging beneath it.

    What lives where:
      * **Organisation** — branding, sender identity, staff, and THE SECURITY FENCE.
      * **Programme**    — the gift itself: its rules and (from a later sprint) its fund.
                           Rule DEFAULTS land here; today the tunables still live on the
                           cohort, which is why this model carries none yet.
      * **Year (cohort)** — the annual intake: open/closed, deadlines, per-intake overrides.

    This is NOT a second security boundary. The organisation fence
    (``_AdminBase._org_scoped`` / ``_org_allows``) is unchanged — programme is a
    narrowing INSIDE that wall, never a replacement for it.

    What the award is CALLED ("bursary" / "scholarship" / "assistance") is
    per-ORGANISATION wording resolved through ``branding.py`` — never a property of this
    model and never a behavioural switch. Every award is a GIFT, never a loan
    (platform invariant, decisions.md 2026-07-26).
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='programmes',
        help_text='The tenant organisation that runs this gift programme.',
    )
    code = models.CharField(
        max_length=50, unique=True,
        help_text="URL-safe slug, e.g. 'brightpath-flagship', 'brightpath-sabah'",
    )
    # Trilingual display name, mirroring the organisation's branding columns. A blank
    # ms/ta falls back to _en at render time (the branding.py fallback convention).
    name_en = models.CharField(max_length=200)
    name_ms = models.CharField(max_length=200, blank=True, default='')
    name_ta = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)

    # ── What the PUBLIC apply page says about this gift (2026-09-09) ─────────────────────────
    #
    # ⚠ BLANK MEANS THE PLATFORM DEFAULT, and blank is the correct state for BrightPath. The
    # stored map holds ONLY what an organisation wrote — never a copied default, which rots the
    # day the platform's own wording moves (the `OrganisationConfiguration` rule).
    #
    # ⚠ JSON RATHER THAN NINE COLUMNS, and the reason is the bullets: the criteria list is
    # variable-length (the owner's ruling — a gift may advertise three conditions or five), so a
    # column model needs a JSON column for it anyway; splitting title/intro out would buy six
    # more migrations' worth of drift and nothing else.
    #
    # ⚠ IT IS NOT DERIVED FROM THE ROUND'S THRESHOLDS AND MUST NEVER BE. The advertised bar is
    # deliberately stricter than `shortlisting.evaluate()` — see `apply_copy.py`.
    apply_copy = models.JSONField(
        default=dict, blank=True,
        help_text='Public apply-page copy per language: '
                  '{"en": {"title": …, "intro": …, "criteria": […]}, "ms": {…}, "ta": {…}}. '
                  'Blank means the platform default. Validated by apply_copy.normalise.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scholarship_programmes'
        ordering = ['organisation_id', 'code']

    def __str__(self):
        return f'{self.name_en} ({self.code})'


class ProgrammeCodeAlias(models.Model):
    """A code this gift USED to answer to — so a printed apply link never dies.

    ⚠⚠ THIS TABLE IS THE WHOLE REASON A GIFT CODE MAY BE RENAMED AT ALL.
    `Programme.code` is what `/scholarship/apply?p=<code>` carries, and `resolve_open_cohort`
    narrows on it. An unknown code narrows to NOTHING, which the apply page reads as **"no open
    round"** — so without an alias a rename would make every poster, WhatsApp forward and printed
    flyer already in circulation tell a student *"applications are closed"*, silently, with no
    error anywhere for us to see. The student simply goes away.

    ⚠ THE ALIAS SERVES THE STUDENT PATH ONLY (owner ruling, 2026-09-09). `resolve_open_cohort` is
    the one resolver that consults it. The admin console's own gift switcher
    (`_AdminBase._programme_by_code`) keeps resolving LIVE codes only: an admin's URL is never
    printed on a poster, and letting a stale code work there would hide a rename from the very
    people who performed it.

    ⚠ ONE WRITER, AND NAMING IT IS PART OF THE DESIGN. Rows are created by
    `AdminProgrammeDetailView.patch` at the moment a code changes, and by nothing else. A table
    populated by a backfill with no matching write path is a bug with a delay on it — migration
    `0123` left the 28/07 sponsor with no membership that way (lessons.md, 2026-07-29). There is
    no backfill here BECAUSE no code has ever been renamed; the first rename writes the first row.

    ⚠ UNIQUENESS SPANS BOTH TABLES, AND THE DATABASE CANNOT SAY SO. `code` is unique here, and
    `Programme.code` is unique there, but nothing stops an alias colliding with another gift's LIVE
    code — which would make one link resolve two ways. `code_is_free()` is the one check both the
    create and the rename paths call; it is application-level on purpose, since a cross-table
    constraint would need a trigger this project has no precedent for.
    """
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name='code_aliases',
        help_text='The gift this retired code still points at.',
    )
    code = models.CharField(
        max_length=50, unique=True,
        help_text="A code this gift used to answer to, e.g. 'brightpath-flagship'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text='Email of the admin who renamed the code, for the audit trail.',
    )

    class Meta:
        db_table = 'scholarship_programme_code_aliases'
        ordering = ['programme_id', 'code']

    def __str__(self):
        return f'{self.code} -> {self.programme.code}'


def code_is_free(code, *, exclude_programme=None):
    """Is `code` available — as a live gift code AND as a retired one?

    ⚠ BOTH TABLES, ALWAYS. A code taken by another gift's ALIAS is not free: reusing it would make
    one printed link resolve to two different gifts depending on which query ran first. The two
    unique constraints each guard their own table and neither can see the other, so this function
    is the only place the real rule exists — call it from every path that accepts a code.

    `exclude_programme` lets a gift keep its own code (a no-op rename) and re-claim a code it had
    itself retired earlier, which is the natural "undo a rename" and must not be refused.
    """
    live = Programme.objects.filter(code=code)
    alias = ProgrammeCodeAlias.objects.filter(code=code)
    if exclude_programme is not None:
        live = live.exclude(pk=exclude_programme.pk)
        alias = alias.exclude(programme=exclude_programme)
    return not live.exists() and not alias.exists()


class ScholarshipCohort(models.Model):
    """
    A single application round — the YEAR (intake) level of the hierarchy: one annual
    round of students entering a ``Programme``. Holds the configurable shortlisting
    thresholds and funding parameters so they can be tuned without code changes (the
    shortlisting rules engine in Sprint 3 reads these).

    NOTE (2026-07-26): this model historically did TWO jobs — the programme (rules,
    funding envelope, eligibility) AND the intake year (``b40-2026``, ``year=2026``).
    ``Programme`` above now owns the durable half. Moving the tunables up to become
    programme-level DEFAULTS with per-intake overrides is deliberately a LATER sprint —
    those columns feed the verification engine, so that change is behaviour-sensitive
    and is kept out of the structural one.
    """
    # ── Tenant ownership (platform Sprint 1) ──────────────────────────────────
    # SOURCE OF TRUTH for "which organisation owns this programme". The
    # application-level denormalised copy (platform Sprint 2) must always equal
    # this — never store a second independently-mutable copy. Named
    # owning_organisation deliberately: `PartnerAdmin.org` / `referred_by_org`
    # mean the REFERRING org (attribution), never ownership/access control.
    # Nullable only for additive-migration safety; seeded to BrightPath (org #1)
    # by migration 0098 — NULL carries no meaning and nothing reads it yet.
    owning_organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        null=True, blank=True, related_name='owned_cohorts',
        help_text='The tenant organisation that OWNS this programme (platform Sprint 1). '
                  'SOURCE OF TRUTH for tenancy. ScholarshipApplication.owning_organisation is '
                  'a denormalised copy of this, set in the application save(). A future '
                  '"move a cohort between organisations" flow MUST cascade the new value to '
                  'every one of that cohort.applications.owning_organisation (there is no DB '
                  'trigger — the drift guard test asserts they agree).',
    )
    # Platform programme layer (2026-07-26): the durable gift this intake belongs to.
    # ``organisation`` above stays the SOURCE OF TRUTH for tenancy/security; this is the
    # funding + rules level beneath it. Nullable for additive-migration safety and for
    # bare test fixtures; prod is backfilled. programme.organisation must agree with
    # owning_organisation — the drift guard test asserts it.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT,
        null=True, blank=True, related_name='cohorts',
        help_text='The gift programme this annual intake belongs to (platform '
                  'programme layer). The programme never lapses; intakes cycle.',
    )

    code = models.CharField(
        max_length=50, unique=True,
        help_text="URL-safe slug, e.g. 'b40-2026'",
    )
    name = models.CharField(
        max_length=200,
        help_text="Display name, e.g. 'BrightPath Bursary Programme 2026'",
    )
    year = models.IntegerField()
    is_active = models.BooleanField(default=True)
    is_open = models.BooleanField(
        default=True, help_text="Currently accepting new applications",
    )

    # ── The round's stated window (owner, 2026-09-06) ────────────────────────────────────────
    #
    # ⚠⚠ THESE DATES DESCRIBE. THEY DO NOT OPEN OR CLOSE ANYTHING. `is_open` is the switch and
    # stays the switch; nothing reads these columns to decide whether a student may apply, and
    # nothing may be written that does. Owner ruling, 2026-09-06, taken against the alternative
    # of a scheduled job that opens on the date.
    #
    # Two reasons, and the second is the durable one:
    #   1. `is_open` already means "real students can walk in" (decisions.md, Sabah S2b). A date
    #      that ALSO opened would be a second switch that can disagree with the first, which is
    #      the exact shape `lessons.md` warns about — except here the switch already exists, so
    #      the date must not become a rival to it.
    #   2. A clock can fire BEFORE SETUP IS FINISHED. Create a gift, type a start date, get
    #      interrupted, and on that date the round opens with no rules set and no questions
    #      configured. A person pressing Open cannot do that by accident.
    #
    # ⚠ NULL IS A REAL ANSWER, AND NOTHING WAS BACKFILLED. A round with no stated window is a
    # normal round, not a broken one — every row that existed before this column (the live 2026
    # intake among them) has NULL, and inventing dates for a round that already ran would be
    # fiction on an audited row. Any reader must treat blank as "not stated", never as an error.
    #
    # If a timer is ever wanted, it is a job built ON TOP of these columns and argued on its own
    # merits then; it is not a reinterpretation of them.
    opens_on = models.DateField(
        null=True, blank=True,
        help_text='The date this round is STATED to open. Descriptive only — it opens nothing; '
                  '`is_open` is the switch. NULL means no window was stated.',
    )
    closes_on = models.DateField(
        null=True, blank=True,
        help_text='The date this round is STATED to close. Descriptive only — it closes nothing. '
                  'NULL means no window was stated.',
    )

    # ── Finishing a round for good (owner, 2026-09-08) ───────────────────────────────────────
    #
    # ⚠⚠ CLOSED AND FINISHED ARE DIFFERENT THINGS, AND THE DIFFERENCE IS A REAL BEHAVIOUR THAT
    # PRODUCTION ALREADY RELIED ON. `is_open=False` stops NEW applications and nothing else —
    # a student who had already started keeps their right to finish, because the intake gate
    # lives on the CREATE endpoint and a returning applicant never reaches it again. That is
    # stated at `views.ApplicationCreateView` and it is not an oversight.
    #
    # It is how the 2026 intake actually ran: the switch went off on 1 July, the landing page
    # greyed out, and THIRTY students who were already part-way through submitted between then
    # and 7 July. Nobody designed that grace period into the screen; it fell out of where the
    # gate sits, and for two months nothing said it existed. Reconstructing it needed a database
    # query, because there is no record of the close (this pair is the fix for that too).
    #
    # `finished_at` is the end of the grace period: the round is done, and a late submission is
    # refused. **It is TERMINAL** (owner: *"when an application is finished, can it be opened
    # again? I don't think it should be"*). Nothing in the product clears it — not the open
    # toggle, not the edit dialog. That is why finishing asks for the round's code to be TYPED,
    # the same shape as deleting a gift: an irreversible act gets a deliberate one.
    #
    # ⚠ DO NOT "SIMPLIFY" THIS INTO `is_open`. Three states are needed because the middle one is
    # load-bearing: open (anyone may start), closed (no new starts, those in flight may finish),
    # finished (nobody may submit). Collapsing closed into finished would have shut out those
    # thirty students on 1 July.
    finished_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When this round was closed FOR GOOD. Terminal — nothing in the product '
                  'clears it. NULL means the round can still be reopened.',
    )
    finished_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the administrator who finished the round. Blank for a round "
                  "finished before this was recorded, which is never 'nobody'.",
    )

    # ── Shortlisting requirements (consumed by `shortlisting.evaluate`) ──────────────────────
    #
    # ⚠⚠ NULL MEANS THE TEST IS NOT APPLIED (Sabah S2a, owner 2026-09-02). Every one of these was
    # NOT NULL with a default, so every test always ran and an organisation had no way to say
    # "we do not use this one". BrightPath never asked for an STPM floor, and PNGK >= 2.90 applied
    # to all nine of its STPM applicants for a whole intake regardless.
    #
    # ⚠ THE VALUE **IS** THE SWITCH — there is deliberately no companion `use_x` boolean. Two
    # columns can disagree ("on, but blank"; "off, but 4") and then something has to decide which
    # wins, silently. One column cannot. The admin screen ticks a box by writing a value and
    # unticks it by clearing one.
    #
    # Defaults are kept so that existing rows and every test fixture behave exactly as before —
    # a NEW cohort still arrives with the flagship's floor and is edited from there.
    min_spm_a_count = models.IntegerField(
        null=True, blank=True, default=4,
        help_text="Minimum SPM grades at A- or better (A+/A/A- all count). NULL = not applied.",
    )
    min_spm_bplus_count = models.IntegerField(
        null=True, blank=True, default=5,
        help_text="Minimum SPM grades at B+ or better — the TOTAL strong count, not the extra "
                  "beyond the A's (4 A- plus 1 more B+ is stored as 5). NULL = not applied.",
    )
    min_stpm_pngk = models.FloatField(
        null=True, blank=True, default=2.9,
        help_text="Minimum STPM PNGK. NULL = not applied.",
    )
    min_merit_score = models.FloatField(
        null=True, blank=True, default=None,
        help_text="Minimum UPU merit point out of 100 (grades + co-curriculum). SPM applicants "
                  "only — an STPM applicant's comparable figure is their PNGK, which is "
                  "min_stpm_pngk. NULL = not applied, which is every cohort today.",
    )
    income_ceiling = models.IntegerField(
        null=True, blank=True,
        help_text="B40 monthly household GROSS income ceiling in RM (DOSM B40 line, RM5,860 in 2024). "
                  "PRIMARY income gate: a non-STR applicant at or below this passes regardless of household size. "
                  "NULL together with per_capita_ceiling = the financial test is not applied.",
    )
    per_capita_ceiling = models.IntegerField(
        null=True, blank=True, default=1584,
        help_text="Per-capita monthly income ceiling in RM (household_income / household_size). "
                  "SAFETY NET only — applies to non-STR applicants whose gross income is ABOVE income_ceiling, "
                  "rescuing large households. RM5,860 B40 ceiling / 3.7 avg household = RM1,584 (DOSM 2024). "
                  "NULL = this rescue is not offered.",
    )
    bucket_b_margin = models.IntegerField(
        default=1,
        help_text="DEPRECATED (pre-S8 marginal-miss logic); unused by the current engine",
    )

    # Funding + workflow parameters (consumed by later sprints)
    funding_envelope = models.IntegerField(
        null=True, blank=True, help_text="Per-student funding envelope in RM",
    )
    fail_email_delay_days = models.IntegerField(
        default=3,
        help_text="DEPRECATED (pre-S8); the scheduler now uses success/decline_delay_hours",
    )
    success_delay_hours = models.FloatField(
        default=48,
        help_text="Hours after submit before the shortlist (invitation) email + follow-up unlock (S8 delayed "
                  "reveal). Float so sub-hour delays are possible (e.g. 0.9167 = 55 minutes).",
    )
    decline_delay_hours = models.FloatField(
        default=48,
        help_text="Hours after submit before the warm decline email (S8 delayed reveal). Float (see above).",
    )
    # Check 2 STEP 2/3: days a student has to answer the AI clarify queries after submit
    # before the application proceeds to a reviewer regardless (the SLA clock, design §5).
    query_response_sla_days = models.PositiveSmallIntegerField(
        default=5,
        help_text="Check-2 query SLA: days after submit to answer clarify queries before "
                  "the application is ready for assignment regardless (proceed-as-is, flagged).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scholarship_cohorts'
        ordering = ['-year', 'code']

    def __str__(self):
        return f'{self.name} ({self.code})'
