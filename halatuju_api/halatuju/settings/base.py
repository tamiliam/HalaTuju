"""
Django base settings for HalaTuju API.

These settings are shared across all environments.
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'corsheaders',

    # Local apps
    'apps.courses',
    'apps.reports',
    'apps.scholarship',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'halatuju.middleware.supabase_auth.SupabaseAuthMiddleware',
    'halatuju.middleware.supabase_auth.NricGateMiddleware',
]

ROOT_URLCONF = 'halatuju.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'halatuju.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'Asia/Kuala_Lumpur'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'halatuju.middleware.supabase_auth.SupabaseAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'halatuju.middleware.supabase_auth.SupabaseIsAuthenticated',
    ],
    # Proxy-aware rate-limiting — see halatuju/throttling.py. The global default
    # is a generous anti-scrape ceiling on ANONYMOUS traffic only; authenticated
    # requests are throttled per-endpoint (e.g. document upload) where it matters.
    'DEFAULT_THROTTLE_CLASSES': [
        'halatuju.throttling.ClientAnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/min',         # anti-runaway-scrape only; safe for shared-NAT classrooms
        'upload': '40/hour',        # document uploads — each triggers a billable Vision-OCR call
        'public_count': '120/min',  # public (AllowAny) sponsor-count endpoint
    },
}

# Supabase Auth settings
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

# AI APIs for reports
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Admin notifications. The env var was set on Cloud Run but never read into
# settings, so getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') silently returned ''
# and every admin-notify email (sponsor interest, profile-complete, Vision-outage
# alert) no-op'd. Reading it here makes those actually send.
ADMIN_NOTIFY_EMAIL = os.environ.get('ADMIN_NOTIFY_EMAIL', '')
# Shared secret guarding the internal cron endpoint (Cloud Scheduler → the running
# api service runs scheduled management commands without a separate Cloud Run Job).
CRON_SECRET = os.environ.get('CRON_SECRET', '')

# Off-platform backup of the private document bucket (security hardening item A).
# A GCS bucket (same GCP project) that `backup_documents` mirrors b40-documents into.
# Empty → the backup command is an explicit no-op (logs a warning, never crashes the cron).
DOCUMENT_BACKUP_BUCKET = os.environ.get('DOCUMENT_BACKUP_BUCKET', '')
# Recipient for the annual "refresh the STPM/UPU course catalogue" reminder
# (CronRunView job 'refresh-reminder'). Empty → falls back to DEFAULT_FROM_EMAIL.
COURSE_REFRESH_REMINDER_EMAIL = os.environ.get('COURSE_REFRESH_REMINDER_EMAIL', '')
# Phase E2: master switch for the anonymised sponsor discovery pool. OFF until the
# lawyer signs off on exposing (anonymised) student data to sponsors. While off,
# every sponsor-pool browse endpoint returns 404. Build + test run on dummy data.
SPONSOR_POOL_ENABLED = os.environ.get('SPONSOR_POOL_ENABLED', '').lower() in ('1', 'true', 'yes')

# WhatsApp outbound comms (Twilio). DARK by default: every send is a no-op unless
# WHATSAPP_ENABLED is true AND the three Twilio creds are set (the billable-API
# "ship disabled first" rule). The sandbox sender is 'whatsapp:+14155238886'.
WHATSAPP_ENABLED = os.environ.get('WHATSAPP_ENABLED', '').lower() in ('1', 'true', 'yes')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')
# Approved Meta template (Twilio Content SID, HX…) for the interview reminder. Required
# for PRODUCTION business-initiated sends; blank in the sandbox (free-text is allowed there).
TWILIO_WHATSAPP_REMINDER_CONTENT_SID = os.environ.get('TWILIO_WHATSAPP_REMINDER_CONTENT_SID', '')
# Reminder v2 (S3): two language variants picked by english_only — EN-only and EN+BM. Each serves
# BOTH the 24h and 1h reminder via a 'when' variable + names the interviewer. While unset, the code
# falls back to the legacy generic SID above (current prod), then to sandbox free-text.
TWILIO_WHATSAPP_REMINDER_CONTENT_SID_EN = os.environ.get('TWILIO_WHATSAPP_REMINDER_CONTENT_SID_EN', '')
TWILIO_WHATSAPP_REMINDER_CONTENT_SID_BM = os.environ.get('TWILIO_WHATSAPP_REMINDER_CONTENT_SID_BM', '')
# Approved template for the "interview times proposed — please pick one" nudge (roadmap S2/TD-138).
# Two language variants picked by english_only — EN-only and EN+BM (both reuse vars {1}name {2}reviewer
# {3}link; no language-specific var). `…_SID` is the legacy single (fallback). Blank → sandbox free-text
# / dark on a real sender until set.
TWILIO_WHATSAPP_PROPOSED_CONTENT_SID = os.environ.get('TWILIO_WHATSAPP_PROPOSED_CONTENT_SID', '')
TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_EN = os.environ.get('TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_EN', '')
TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_BM = os.environ.get('TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_BM', '')
# Twilio Verify Service SID (roadmap S4/TD-136) — phone verification. Blank → the verify
# endpoints report "unconfigured" (503) and the /profile control stays inert. The Verify
# Service is created once in the Twilio console; it manages code lifecycle + rate limits.
TWILIO_VERIFY_SERVICE_SID = os.environ.get('TWILIO_VERIFY_SERVICE_SID', '')
# Delivery channel for the OTP: 'sms' (default — works out of the box) or 'whatsapp'. WhatsApp
# needs Twilio's bring-your-own-sender onboarding (~2-4 weeks, error 60223 until done), so we
# ship on SMS and flip this env var to 'whatsapp' once that clears — no code change. The /profile
# copy is channel-neutral ("to your number") so it stays correct either way.
PHONE_VERIFY_CHANNEL = os.environ.get('PHONE_VERIFY_CHANNEL', 'sms')

# Check 2 STEP 2: the AI clarify queries asked of the STUDENT. While OFF (default), no
# clarify query is shown in the student Action Centre and no query email/reminder is
# sent — but officers still see them in the cockpit, so the questions can be reviewed
# per student before any applicant is asked. Flip to true (env var) to go live.
CHECK2_STUDENT_QUERIES_ENABLED = os.environ.get('CHECK2_STUDENT_QUERIES_ENABLED', '').lower() in ('1', 'true', 'yes')

# Check 2 STEP 3: auto-draft the sponsor profile at the reviewer handoff (and the
# backfill/sweep that share this gate). Billable Gemini, so off by default; flip via the
# env var. (Was referenced in code but never defined here, so it was permanently off.)
CHECK2_AUTO_GENERATE = os.environ.get('CHECK2_AUTO_GENERATE', '').lower() in ('1', 'true', 'yes')

# Optional scoping for the `refresh_sponsor_profiles` command (run via the argless cron
# endpoint): a comma-separated list of application IDs. When set, the refresh is FORCED for
# exactly those applications (ignores the version-idempotency skip) — used to trial/repair a
# single profile on a new prompt without re-running the whole fleet. Empty = full stale sweep.
PROFILE_REFRESH_APP_IDS = os.environ.get('PROFILE_REFRESH_APP_IDS', '')

# Scope for the `award_students_batch` admin tool (run via the argless cron endpoint):
# award the listed applications to the given sponsor via the real award_and_notify path
# (offered Sponsorship + status 'awarded' + the good-news email). Set both to act; clear
# after. SEED_SPONSOR_ID = a Sponsor.id; SEED_AWARD_APP_IDS = csv of application IDs.
SEED_SPONSOR_ID = os.environ.get('SEED_SPONSOR_ID', '')
SEED_AWARD_APP_IDS = os.environ.get('SEED_AWARD_APP_IDS', '')

# Award good-news email — COOL-OFF model (owner, 2026-06-29): a sponsor award does NOT email
# inline. The release cron (`release-award-offer-emails`) sends the email once the award is this
# many hours old, leaving a window to reconsider — cancelling the award before then stops the
# email. 24h default; 0 = send on the next cron tick (no cool-off). The owner can still force a
# send for explicit application IDs via the manual `send_award_offer_emails` command
# (AWARD_EMAIL_APP_IDS); both paths stamp `Sponsorship.offer_emailed_at` so nothing double-sends.
try:
    AWARD_OFFER_EMAIL_COOLOFF_HOURS = int(os.environ.get('AWARD_OFFER_EMAIL_COOLOFF_HOURS', '24'))
except (TypeError, ValueError):
    AWARD_OFFER_EMAIL_COOLOFF_HOURS = 24
AWARD_EMAIL_APP_IDS = os.environ.get('AWARD_EMAIL_APP_IDS', '')

# F7: when a reviewer is assigned, also email the STUDENT an advance notice (who will
# contact them + the interviewer's name/phone/email). OFF by default — switch on only after
# reviewers have given non-objection to sharing their contact. Per-reviewer opt-out lives on
# ReviewerProfile.share_phone_with_students (default shared).
STUDENT_ASSIGNMENT_EMAIL_ENABLED = os.environ.get('STUDENT_ASSIGNMENT_EMAIL_ENABLED', '').lower() in ('1', 'true', 'yes')

# When a student confirms their profile (shortlisted → profile_complete), send the richer
# "your application is in — here's what happens next" email (Check-2 review → doc requests →
# interview with 3 slots → minor needs a guardian). When ON it SUPERSEDES the basic
# submission-ack email at that step; when OFF the basic ack still sends. EN+BM.
PROFILE_COMPLETE_EMAIL_ENABLED = os.environ.get('PROFILE_COMPLETE_EMAIL_ENABLED', '').lower() in ('1', 'true', 'yes')

# Cool-off windows before a decision's comm goes out, giving time to reconsider/reverse.
# DECLINE: a post-shortlist admin decline is held silently this many days before it reveals
# (status → rejected) + the decline email sends. AWARD: a student-accepted award is held this
# many days before the 'funding confirmed' email + onboarding (the 'sponsored' flip). An admin
# can cancel/hold within the window and the student never sees it. **Default 0 = OFF (immediate),
# like the other comms flags — prod sets the env vars (DECLINE=7, AWARD=2) to switch the cool-off on.**
DECLINE_COOLOFF_DAYS = float(os.environ.get('DECLINE_COOLOFF_DAYS', '0'))
AWARD_COOLOFF_DAYS = float(os.environ.get('AWARD_COOLOFF_DAYS', '0'))

# Interview scheduling: the assigned reviewer proposes a few times, the student books
# one in-app, and we send confirmations + reminders. OFF by default — the whole surface
# (admin propose-card + student booking panel + endpoints) is dark until flipped on.
INTERVIEW_SCHEDULING_ENABLED = os.environ.get('INTERVIEW_SCHEDULING_ENABLED', '').lower() in ('1', 'true', 'yes')
# How many days a reviewer has to complete a review once an applicant is assigned. Shown as
# the "Please review by" date in the reviewer-assigned email. Soft target (no enforcement yet).
REVIEW_SLA_DAYS = int(os.environ.get('REVIEW_SLA_DAYS', '10'))
# Verdict-completion nudges (TD-131): the send_review_nudges cron nudges a reviewer whose
# verdict is approaching/overdue (assigned_at + REVIEW_SLA_DAYS) and escalates to super-admins
# REVIEW_ESCALATE_GRACE_DAYS after the due date. Dark by default — the cron is inert until on.
REVIEW_NUDGES_ENABLED = os.environ.get('REVIEW_NUDGES_ENABLED', '').lower() in ('1', 'true', 'yes')
REVIEW_NUDGE_SOON_DAYS = int(os.environ.get('REVIEW_NUDGE_SOON_DAYS', '2'))   # nudge this many days BEFORE due
REVIEW_ESCALATE_GRACE_DAYS = int(os.environ.get('REVIEW_ESCALATE_GRACE_DAYS', '4'))  # escalate this many days AFTER due (→ day 14)
# Auto-generate a Google Meet link (+ calendar event) on booking. Separate flag so the
# scheduling surface can go live BEFORE the Google Workspace organiser account is wired.
# When off (or creds missing / API error), booking still succeeds — the email simply has
# no link (or uses a manually-pasted one). Needs a Workspace service account w/ domain-wide
# delegation; see GOOGLE_MEET_SA_JSON + MEET_ORGANISER_EMAIL.
INTERVIEW_MEET_ENABLED = os.environ.get('INTERVIEW_MEET_ENABLED', '').lower() in ('1', 'true', 'yes')
# The Workspace mailbox that organises the interview calendar events (Meet links are
# created on its calendar). The service account impersonates it via domain-wide delegation.
MEET_ORGANISER_EMAIL = os.environ.get('MEET_ORGANISER_EMAIL', 'info@halatuju.xyz')
# Service-account credentials JSON (the whole key, as a string) for Calendar/Meet.
# Secret — set via Cloud Run env var, NEVER committed. Empty → Meet generation no-ops.
GOOGLE_MEET_SA_JSON = os.environ.get('GOOGLE_MEET_SA_JSON', '')
# Interview defaults.
INTERVIEW_DURATION_MIN = int(os.environ.get('INTERVIEW_DURATION_MIN', '30'))  # matches the "about 30 minutes" copy
# How close to the start a student may still self-reschedule / cancel (hours before).
INTERVIEW_RESCHEDULE_CUTOFF_HOURS = int(os.environ.get('INTERVIEW_RESCHEDULE_CUTOFF_HOURS', '12'))

# Action Centre Phase 2: a gentle Cikgu Gopal nudge when a student's TYPED answer is
# TOTALLY off-topic (one cheap, billable Gemini call per answer). Off by default (a
# billable-AI knob, like the doc-assist flags); AI-off/error always accepts the answer.
CHECK2_ANSWER_RELEVANCE_ENABLED = os.environ.get('CHECK2_ANSWER_RELEVANCE_ENABLED', '').lower() in ('1', 'true', 'yes')

# Supporting-document upload guardrails (cost + abuse). Env-overridable.
MAX_DOC_SIZE_BYTES = int(os.environ.get('MAX_DOC_SIZE_BYTES', str(8 * 1024 * 1024)))   # 8 MB/file
MAX_DOCS_PER_APPLICATION = int(os.environ.get('MAX_DOCS_PER_APPLICATION', '40'))
# Cap on 'other' (reviewer-requested extra) documents per application. Each lands in its
# own request-keyed slot, so without a cap a reviewer could request unbounded extras.
MAX_OTHER_DOCS = int(os.environ.get('MAX_OTHER_DOCS', '10'))
# Document-assist (Gemini field extraction on upload): hourly cap per application —
# beyond it the upload still succeeds + Vision/deterministic feedback still run, but
# the billable Gemini call is skipped (student sees a "we'll review manually" note).
DOC_ASSIST_RATE_LIMIT_PER_HOUR = int(os.environ.get('DOC_ASSIST_RATE_LIMIT_PER_HOUR', '15'))
# When True, only call Gemini if the free deterministic presence check is uncertain
# (saves cost). Default False = always extract (richer data for the admin).
DOC_ASSIST_ONLY_WHEN_UNCERTAIN = os.environ.get('DOC_ASSIST_ONLY_WHEN_UNCERTAIN', '') == '1'
# Document genuineness fingerprint (verification-assurance roadmap): a soft multimodal
# "does this look like a real photo of the official document?" check. One extra Gemini call
# per IC upload. Default OFF — dark until validated on prod, then flip via --update-env-vars.
DOC_GENUINENESS_CHECK_ENABLED = os.environ.get('DOC_GENUINENESS_CHECK_ENABLED', '') == '1'
# IC Gemini second opinion: when the cheap deterministic MyKad read is low-confidence
# (missing core field, or it disagrees with the typed profile), re-read the card image
# with Gemini. Already self-gated to shaky reads only; set to '0' to disable entirely
# if cost ever spikes. Default ON.
IC_GEMINI_FALLBACK_ENABLED = os.environ.get('IC_GEMINI_FALLBACK_ENABLED', '1') != '0'

# Conditional Bursary Award Agreement (the binding bursary CONTRACT a student + their
# parent/guardian surety sign in-session when they accept an award). OFF by default —
# the template wording is a DRAFT pending lawyer review, and turning it on adds new
# required signature fields to award acceptance. The donor is NEVER a party or named;
# the Foundation (signatory configured below) is the named counterparty.
BURSARY_AGREEMENT_ENABLED = os.environ.get('BURSARY_AGREEMENT_ENABLED', '').lower() in ('1', 'true', 'yes')
BURSARY_AGREEMENT_VERSION = '2026-v1'

# Guarantor (parent/guardian surety) phone-PIN verification — the same-session parent
# gate that runs before the in-session bursary signature (only when the agreement flag
# above is on). An SMS PIN is sent to the guardian's PRE-DECLARED, LOCKED phone (from
# profile.guardians, captured at apply); a successful check stamps the application. The
# signature requires that stamp to be FRESH — within this TTL — so a signature can't ride
# a days-old verification, and (because the phone is not editable at signing) a dishonest
# student can't self-verify in the parent's place.
GUARANTOR_PHONE_VERIFY_TTL_SECONDS = int(os.environ.get('GUARANTOR_PHONE_VERIFY_TTL_SECONDS', '1800'))

# Award acceptance / onboarding entry point. DEFAULT OFF: the "View my award" panel on
# /scholarship/application (→ the accept + onboarding flow) stays hidden until that flow is
# tested end-to-end. Awarded students are instead invited into it by a separate email later;
# until then they only see the bank-details task. Flip to 1 to expose the panel.
AWARD_ACCEPTANCE_ENABLED = os.environ.get('AWARD_ACCEPTANCE_ENABLED', '').lower() in ('1', 'true', 'yes')
# The Foundation's interim signatory (placeholder "Suresh" until the real officer is set
# via env var). The donor is never named — this is the FOUNDATION counterparty only.
FOUNDATION_SIGNATORY_NAME = os.environ.get('FOUNDATION_SIGNATORY_NAME', 'Suresh')
FOUNDATION_SIGNATORY_TITLE = os.environ.get(
    'FOUNDATION_SIGNATORY_TITLE', 'For and on behalf of the Foundation (interim signatory)')
FOUNDATION_SIGNATORY_NRIC = os.environ.get('FOUNDATION_SIGNATORY_NRIC', '')

# Logging configuration (structured JSON for Cloud Run)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
