"""TD-254 — the two tables behind claiming a profile whose IC is already registered.

**PLATFORM-IDENTITY TABLES, NOT TENANT DATA.** The build-for-tenancy convention that a new
model must be FK-reachable from `ScholarshipApplication` or `ScholarshipCohort` (rule 4) exists
so that programme data can be fenced to an owning organisation. Neither table here is programme
data: one records which LOGIN acts as which profile, the other records who tried to take over
whose record. Both belong to the platform's identity layer, beside `StudentProfile` itself, and
both are deliberately outside the org fence — a takeover attempt is not a tenant's business and
an organisation must never be able to hide one.

They live in `courses` because `StudentProfile` does, and in their own module because
`models.py` is a ledgered oversize file (see `halatuju_api/CLAUDE.md`, `## Code standards`).

**A CLAIM IS A LINK, NOT A MOVE.** The old endpoint moved the profile's primary key in raw SQL,
which could not even work for a target carrying a scholarship application (its FK is never
repointed) and destroyed the record's continuity when it did. `ProfileLoginAlias` replaces that
with one row meaning *"the login `alias_uid` acts as this profile"*, resolved at the auth seam
(`halatuju/middleware/supabase_auth.py`). Deleting the row fully reverses the claim; nothing is
ever deleted or renumbered by a claim.
"""
from django.db import models


class ProfileClaimEvent(models.Model):
    """One line per branch that touched somebody else's profile. **APPEND-ONLY.**

    ⚠ There is no code path anywhere that updates or deletes a row here, and there must never
    be one: before this table the question *"has a profile ever been taken over?"* had no
    answer at all, which is half of why TD-254 was rated HIGH. Even the plain look-up writes a
    row, so *"has anybody been probing IC numbers?"* is answerable for the first time.

    ⚠ `target_profile_id` is a PLAIN VALUE, not a foreign key, on purpose: the record has to
    survive the deletion of the profile it names. The IC is held here deliberately — it is the
    one place it belongs. It must never reach an application LOG.
    """

    #: Every branch that can touch another person's record. `refused_*` carries the same stable
    #: code the API serves the browser, so a refusal on screen and a row here are the same word.
    EXISTS_SHOWN = 'exists_shown'
    CODE_SENT = 'code_sent'
    CODE_FAILED = 'code_failed'
    CLAIMED = 'claimed'
    ALIAS_REVOKED = 'alias_revoked'

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    #: The REAL JWT `sub` of the caller — never an alias target. For `alias_revoked` it is the
    #: login whose access was withdrawn.
    caller_sub = models.CharField(max_length=100, db_index=True)
    #: The `supabase_user_id` of the profile that was looked at. Plain, not an FK (see above).
    target_profile_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    nric = models.CharField(max_length=20, blank=True, default='', db_index=True)
    #: `exists_shown` | `code_sent` | `code_failed` | `claimed` | `refused_<reason>` |
    #: `alias_revoked`.
    event = models.CharField(max_length=40)
    #: `phone` | `email` | '' — a bare channel TYPE, never an address or a number.
    channel = models.CharField(max_length=16, blank=True, default='')
    #: Who acted, when that is not the caller — today only `revoke_alias(..., by=…)`. An audit
    #: line with no accountable actor is half a line.
    actor = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        db_table = 'profile_claim_events'
        indexes = [models.Index(fields=['nric', 'created_at'])]

    def __str__(self):
        return f'{self.event} by {self.caller_sub}'


class ProfileLoginAlias(models.Model):
    """*"The login `alias_uid` acts as this profile."* One row is a whole claim.

    ⚠ **RESOLVED AT THE AUTH SEAM, NOT PER ENDPOINT.** `SupabaseAuthMiddleware` looks the JWT
    `sub` up here and, on a hit, sets `request.user_id` to the target's primary key (keeping the
    real sub on `request.auth_sub`). That is the only reason every student endpoint follows
    without being edited one by one — and the only reason a future endpoint cannot forget.

    ⚠ **NEVER A STAFF OR SPONSOR IDENTITY.** `PartnerAdmin` and `Sponsor` key on the same
    `sub`, so an alias that redirected one of those would be a privilege path. Creation refuses
    such a sub, and the seam re-checks on the rare request where a row is found, because a staff
    row can be created later against a sub that is already an alias.
    """

    alias_uid = models.CharField(max_length=100, primary_key=True)
    profile = models.ForeignKey(
        'courses.StudentProfile', on_delete=models.CASCADE, related_name='login_aliases',
        help_text='The profile this login acts as. Deleting THIS row reverses the claim.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    claim_event = models.ForeignKey(
        ProfileClaimEvent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='aliases',
        help_text='The `claimed` event that created this alias.',
    )

    class Meta:
        db_table = 'profile_login_aliases'

    def __str__(self):
        return f'{self.alias_uid} -> {self.profile_id}'
