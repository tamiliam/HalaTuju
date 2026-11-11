"""Internal cron entry points (Cloud Scheduler) and the Vircle Airtable hook."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class CronRunView(APIView):
    """Internal endpoint for Cloud Scheduler to run a whitelisted management command
    inside the already-running api service (which holds all DB/email config), so we
    avoid a separate Cloud Run Job that would have to replicate plain-env secrets.
    Auth is a secret header compared in constant time, one key per job family (SEC-05,
    cron_auth.py). Public route, but inert
    without the secret. Never 500s the scheduler (that just causes retries)."""
    permission_classes = [AllowAny]

    JOBS = {
        'vision-outage': 'alert_vision_outage',
        'read-outage-start': ('alert_vision_outage', ('--hourly',)),  # hourly: mail a Vision/Gemini outage the hour it starts (2026-10-24)
        'decision-emails': 'send_pending_decision_emails',
        'read-documents': 'run_pending_reads',  # EVERY 15 MIN (A2.3): the upload reads nobody asked for (upload_read)
        'assign-emails': 'send_pending_assign_emails',  # EVERY 15 MIN (A2.3): the assignment emails assign queued (assign_notify)
        'application-reminders': 'send_application_reminders',
        'application-nudges': 'send_application_nudges',  # frequent (~15 min): one-time auto "you haven't submitted yet" nudge (shortlisted, consented, unsubmitted)
        'query-emails': 'send_due_query_emails',
        'query-reminders': 'send_query_reminders',
        'autogenerate-profiles': 'autogenerate_profiles',
        'backfill-assigned-profiles': 'backfill_assigned_profiles',  # one-off: drafts for already-assigned
        'refresh-profiles': 'refresh_sponsor_profiles',  # roll a prompt bump across draft+final (scope via PROFILE_REFRESH_APP_IDS)
        'award-students-batch': 'award_students_batch',  # admin batch-award to a sponsor (scope via SEED_SPONSOR_ID + SEED_AWARD_APP_IDS)
        'send-award-offer-emails': 'send_award_offer_emails',  # owner-forced award email send (scope via AWARD_EMAIL_APP_IDS)
        'send-sign-invitation-emails': 'send_sign_invitation_emails',  # owner-forced "ready to sign" follow-up (scope via SIGN_INVITE_APP_IDS)
        'send-vircle-install-emails': 'send_vircle_install_emails',  # owner-forced Vircle setup email + task (scope via VIRCLE_EMAIL_APP_IDS)
        'sync-vircle-sheet': 'sync_vircle_sheet',  # rewrite the Vircle relay sheet (My Drive / 03 Vircle) from the DB
        # ⚠ 'vircle-activation-request' + 'vircle-activation-sync' were RETIRED 2026-09-11 (owner:
        # "the 48 hour chaser is no longer necessary — we are communicating with Vircle via
        # webhooks, to and fro"). Activation now arrives on the inbound webhook. Pause their Cloud
        # Scheduler jobs; re-registering either one would email Vircle about accounts that are
        # already live and re-open a second writer of `vircle_activated_at`.
        'bursary-signing-reminders': 'send_bursary_signing_reminders',  # daily: nudge a pending witness/countersignature (SLA)
        'release-award-offer-emails': 'release_award_offer_emails',  # hourly: send award emails past the cool-off window
        'sponsor-realtime': 'send_sponsor_realtime',   # F3: hourly
        'sponsor-digests': 'send_sponsor_digests',     # F3: weekly
        'issue-monthly-invoices': 'issue_monthly_invoices',  # monthly, 15th 09:00 MYT: issue LAST month's tenant invoices (sends nothing; idempotent)
        # TD-247 (A4.5): the supplier bills (Workspace, Supabase, Twilio, Anthropic PDFs) from the
        # Drive folder in SUPPLIER_BILLS_FOLDER into the cost ledger. NOT SCHEDULED by the build:
        # the owner adds the Scheduler job (suggested daily 08:00 MYT from the 8th to the 14th).
        # INSERT-ONLY, so a repeat writes nothing; `-report` is the dry run and must never gain
        # `--apply`. Flags live here, never in the request.
        'supplier-bills-import': ('import_invoices', ('--drive', '--apply')),
        'supplier-bills-report': ('import_invoices', ('--drive',)),
        'auto-sponsor': 'auto_sponsor',                # R6: hourly AutoSponsor allocation
        'purge-referrals': 'purge_sponsor_referrals',  # F4: daily PDPA purge (60-day)
        'lapse-expired-offers': 'lapse_expired_offers',  # TD-252: daily; armed unpaid offers past deadline lapse, paid ones are flagged, never lapsed
        'rescore-pending': 'rescore_pending_decisions',  # on-demand after a policy change
        'backfill-verdict-engine-version': 'backfill_verdict_engine_version',  # one-off: label the 88 predictions banked before verdict_engine had a version (DRY RUN unless --apply)
        'backup-documents': 'backup_documents',  # weekly: mirror the private doc bucket to GCS
        'refresh-reminder': 'send_refresh_reminder',  # annual: nudge the admin to refresh the course catalogue
        'course-data-check': 'course_data_check',  # weekly: READ-ONLY audit + link reachability for the dashboard
        'interview-reminders': 'send_interview_reminders',  # frequent (~15 min): 1-day + 1-hour interview reminders
        'results-overdue-flag': 'flag_results_overdue',  # daily (maintenance S4b): terms made + overdue flagged
        'results-due-reminders': 'send_results_due_reminders',  # daily (maintenance S4b): "your result is due"
        'announcement-emails': 'send_announcement_emails',  # hourly (maintenance S8): an announcement's email, once each
        'survey-emails': 'send_survey_emails',  # hourly (maintenance S9): a survey's opening email + reminder, once each
        'module-emails': 'send_module_emails',  # hourly (maintenance S10): a module's published email + reminder, once each
        'review-nudges': 'send_review_nudges',  # daily (TD-131): verdict due/overdue reviewer nudges + super escalation
        'expire-temp-passwords': 'expire_temp_passwords',  # daily: rotate partner temp passwords unchanged past the 7-day TTL
        'notify-contact-submissions': 'notify_contact_submissions',  # frequent: email unread contact-form messages
        'reextract-documents': 'reextract_documents',  # one-off batches (20/run): re-read stale docs with current parsers
        'reextract-offers': 'reextract_offers',  # one-off batches (20/run): re-score offers with missing/below-genuine (<0.70) authenticity under the current MODEL_VERSION
        'finalise-profiles': 'run_pending_finalise',  # EVERY 5 MIN (A2.1): the final profile record-verdict queued (profile_finalise), then the first-assign drafts (A2.3b, assign_draft)
        'reprocess-ic-vision': 'reprocess_unread_ic',  # HOURLY (0 * * * *): self-heal reads stuck unprocessed or deferred by OUR outage (services.read_retry)
        'backfill-anon-blurbs': 'backfill_anon_blurbs',  # one-off (billable): card blurb for published profiles missing one
        'backfill-reporting-dates': 'backfill_reporting_dates',  # one-off: normalise offer reporting dates into the column (S3)
        'backfill-confirmed-profiles': 'backfill_confirmed_profiles',  # one-off TD-210: confirmed pathway onto the profile (DRY RUN unless BACKFILL_CONFIRMED_PROFILES_APPLY=1)
        # One-off/idempotent. ELEVEN kinds: 5 partner + `student_assigned` (#3) + 5 reviewer (#10). ⚠ RUN IT
        # AFTER A DEPLOY THAT ADDS A KIND, never before — it seeds what the RUNNING code knows (else skips the new).
        'seed-partner-emails': 'seed_partner_email_templates',
        # DAILY, and it is a NEW-FILE trigger, not a calendar one: a BrightPath officer extracts
        # the week from Vircle's Data Studio and uploads it BY HAND, "not exactly at the same time
        # every week … not even the same day" (owner, 2026-09-10). A day with nothing new does
        # nothing and says nothing. ⚠ `--apply` is what makes it write; without it the job is a
        # report. It emails ONLY when a human is needed — never an all-clear.
        'spending-ingest': ('ingest_spending', ('--drive', '--apply')),
        # ⚠ THE DOOR FOR THE SORTER, AND IT IS NOT ON A SCHEDULE. `spending-ingest` already
        # sorts what it stores, so the daily job stays a single Scheduler entry. This entry
        # exists for the OTHER case: a keyword rule is tuned and every already-sorted row must
        # be reconsidered. Without a door that would be a command that can only run on a laptop
        # with no database - finished and unreachable, which from the outside looks exactly like
        # finished (BrightPath #20). `--all` never touches an `owner` row.
        'spending-sort': ('sort_spending', ('--all', '--apply')),
        # ⚠⚠ THE READ-ONLY DOORS, AND THEY ARE NOT SCHEDULED. Added at the first deploy
        # (2026-09-10), when the plan's own verification step turned out to be impossible: it
        # says "run it WITHOUT --apply once and read it" — the only real proof of the Drive
        # hop and of the model rung, neither of which can run on a laptop — and every
        # registered job carried `--apply`. Flags come from THIS registry and never from the
        # request (accepting them there would let anyone holding the secret choose the
        # command's behaviour), so a read-only run needs its own entry.
        # ⚠ NEITHER MAY EVER GAIN `--apply`. They exist to be safe to run at any moment.
        # `ingest_spending` with no `--apply` cannot write and `--no-email` keeps a manual
        # rehearsal from alerting anybody; `sort_spending` with no flags is report-only AND
        # still calls the model, which is exactly what makes it the proof.
        'spending-ingest-report': ('ingest_spending', ('--drive', '--no-email')),
        # ⚠ IMPORT ONLY — store the rows, sort NOTHING, file NOTHING. Also not scheduled.
        # The daily job sorts and files a summary straight after importing, which is right for
        # a routine week and wrong for the FIRST run: the first sort is the first time the
        # model is asked anything AND the moment the sponsor card goes live, and the first
        # summary is the first file we have ever written into the owner's Drive. This lets the
        # first run stop after the import so both can be looked at before they happen.
        'spending-import-only': ('ingest_spending',
                                 ('--drive', '--apply', '--no-sort', '--no-summary',
                                  '--no-email')),
        'spending-sort-report': 'sort_spending',
        # ⚠⚠ RECOVERY DOOR — re-read EVERY file in the folder, not only the new or changed ones.
        # NOT SCHEDULED, and it must never be: it downloads the whole archive.
        #
        # It exists because a PARSER bug drops rows from a file we then mark as read, and no
        # amount of fixing the parser brings them back on its own. The `Sept` date bug
        # (2026-09-12) lost every September transaction that way — the file had been imported
        # that morning, so the nightly "new or changed" rule would have skipped it until somebody
        # edited the sheet by hand.
        #
        # ⚠ Safe because `ingest` dedups on `txn_id`: a re-read of stored rows adds nothing and
        # reports them as already stored. Expensive, not dangerous — which is why it is a door a
        # person opens, never a default.
        'spending-reread': ('ingest_spending', ('--drive', '--apply', '--reread')),
        'partner-digests': 'send_partner_digests',  # weekly (Mon 08:00 MYT): partner stage summary + chase list
        'partner-milestones': 'send_partner_milestones',  # hourly: awaiting-review + awarded, batched per organisation
        # one-off/idempotent (S3): create the nine sponsor-email templates. The three that
        # already send arrive ON, the six new ones OFF for review; SPONSOR_COMMS_ENABLED
        # gates the lot, so running this changes nothing a sponsor receives.
        'seed-sponsor-emails': 'seed_sponsor_email_templates',
        # one-off (requests #7/#8): re-settle the pre-U stream/school on applications whose
        # CONFIRMED offer left them blank. Reads the offer already on file — no re-extraction.
        # Scope a run with PATHWAY_REPAIR_APP_IDS; idempotent, so a repeat is a no-op.
        'repair-confirmed-pathway': 'repair_confirmed_pathway',
        # READ-ONLY (request #9): the Pathway chip + Institution tick as they read now, beside how
        # they read before the fix. Writes nothing; safe to run any time.
        'audit-pathway-ticks': 'audit_pathway_ticks',
        # one-off (Layer 0, 2026-08-30): freeze the requirement set on applications submitted
        # before `requirements_snapshot` existed. Report-only unless REQUIREMENTS_SNAPSHOT_APPLY=1
        # is set on the service; idempotent, so a repeat is a no-op.
        'backfill-requirements-snapshots': 'backfill_requirements_snapshots',
        # one-off (request #20): tag the income documents left with a blank `household_member`,
        # and settle the slot each one lands in. Reads STORED fields only — no re-extraction.
        # Report-only unless INCOME_DOC_TAG_APPLY=1 is set on the service; idempotent, so a
        # repeat is a no-op.
        'backfill-untagged-income-docs': 'backfill_untagged_income_docs',
    }

    def post(self, request, job):
        from .. import cron_auth, cron_health
        # SEC-05: the job's FAMILY key, or the shared CRON_SECRET while it is set (cron_auth.py).
        if not cron_auth.allowed(job, request.headers.get('X-Cron-Secret', '')):
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        command = self.JOBS.get(job)
        if not command:
            return Response({'error': 'unknown job'}, status=status.HTTP_404_NOT_FOUND)
        # A job is a command NAME, or a (name, [args]) pair when the cron behaviour needs flags.
        # ⚠ ADDITIVE — a plain string behaves exactly as before, which is what every other job is.
        # The pair exists so a recurring job's flags live HERE, visible in the registry, instead of
        # in an env var somebody has to set and then remember to unset. That env-var shape is
        # deliberate for dangerous ONE-OFFS (`REEXTRACT_DOC_TYPE`, `PARTNER_EMAIL_RESET_KINDS`) —
        # a door you can close — and is the wrong tool for a job that runs every day.
        args = []
        if isinstance(command, tuple):
            command, args = command[0], list(command[1])
        # Runs it, never raises (no 500 into scheduler retries), and records the outcome for the
        # admin System health light, whose expected cadences sit beside it (cron_health.py).
        return Response(cron_health.run_job(job, command, args), status=status.HTTP_200_OK)


class VircleAirtableUpdateView(APIView):
    """POST /api/v1/internal/vircle/airtable/ — Vircle's Airtable automation calls US.

    The inbound half of the two-webhook flow (vircle_airtable.py): when a BrightPath row in
    Vircle's Recipients table gains its Principal Wallet ID or activation, their automation
    POSTs the row here and we store `vircle_id` + `vircle_activated_at` — the student never
    types a wallet id. Auth mirrors CronRunView: public route, shared-secret header
    (X-Vircle-Secret vs VIRCLE_AIRTABLE_SECRET) compared in constant time, inert while the
    secret is unset. Always 200 on a matched-or-not payload (a 4xx would put Vircle's
    automation into retries about OUR data question); 403 only for a bad secret."""
    permission_classes = [AllowAny]

    def post(self, request):
        import hmac
        from django.conf import settings as _s
        from .. import vircle_airtable
        secret = getattr(_s, 'VIRCLE_AIRTABLE_SECRET', '') or ''
        provided = request.headers.get('X-Vircle-Secret', '') or ''
        if not secret or not hmac.compare_digest(secret, provided):
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        payload = request.data if isinstance(request.data, dict) else {}
        return Response(vircle_airtable.apply_update(payload))
