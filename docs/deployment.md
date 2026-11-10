Moved word for word from halatuju_api/CLAUDE.md on 2026-11-03. CLAUDE.md keeps the short rules; this is the full text.

## Deployment

| Component | Platform | Region | Service |
|-----------|----------|--------|---------|
| Backend | Cloud Run | asia-southeast1 | halatuju-api |
| Frontend | Cloud Run | asia-southeast1 | halatuju-web |
| Database | Supabase | Singapore | pbrrlyoyyiftckqvzvvo |

### What the api image installs and carries (H1, 2026-09-18)

- The Dockerfile installs **`requirements.lock`** — exact `==` pins, a freeze of what pip actually
  installed in the production image build of 2026-09-18. Two builds of one commit now install the
  same code. Refresh it deliberately, never as a side effect: the recipe is in the file's header.
- **`requirements.txt` stays** as the statement of intent — the allowed ranges and the reason each
  package is here. A new package goes in `requirements.txt` first, then into the lock.
- **`.dockerignore`** keeps the tests, the eval corpus, prose and local state out of the image.
  The Cloud Build trigger runs `docker build`, so `.dockerignore` is the file that counts —
  `.gcloudignore` does nothing here.

### GCP Project

`gen-lang-client-0871147736` (account: `tamiliam@gmail.com`)

### How a change reaches production

1. **A push to `main` IS a deploy request, and for HalaTuju it needs the owner's yes** (`push = deploy`).
   Two Cloud Build triggers run committed configs — `halatuju_api/cloudbuild.yaml` (files
   `halatuju_api/**`, ignoring `docs/**` and this file) and `halatuju-web/cloudbuild.yaml`
   (`halatuju-web/**`, ignoring `docs/**`). Root `docs/**` and `CHANGELOG.md` deploy nothing.
2. **The tests are the gate.** Each build runs its suite in parallel with `docker build`; Push and
   Deploy wait for both, so a red suite ships nothing. api: `manage.py check`,
   `makemigrations --check`, `pytest -n auto`; web: `npm run gates` then `npm run bundle-budget -- --gate`.
   Run the gate's OWN command lines locally first (see Testing). Never deploy more than twice for one feature.
3. **MIGRATE-FIRST. Triggers never run `migrate`.** Apply the migration to production BY HAND before
   the push (Supabase MCP or psql): render the Postgres DDL with the postgresql schema editor (local
   `sqlmigrate` renders SQLite) — the DDL and the ledger row are in each migration's docstring — then
   `INSERT INTO django_migrations (app, name, applied) …` in the SAME transaction. A choices-only
   migration needs only the ledger row. ⚠ After an `UPDATE` that touches a `DEFERRABLE INITIALLY
   DEFERRED` foreign key, run **`SET CONSTRAINTS ALL IMMEDIATE;` before `CREATE INDEX`** in the same
   transaction, or Postgres refuses the index (0163, 2026-10-03). The old image must stay safe
   between migrate and deploy: additive and nullable first, `NOT NULL` in a later migration (0163 → 0164).
   A NOT NULL column the old image never names takes a DATABASE default (`db_default`, courses 0088).
   **Catalogue rows a new gate hides go in AFTER the deploy that carries the gate.** Bumi D1 order:
   apply the 0088 SQL → push (api + web) → CONFIRM the new api AND web revisions both serve 100% →
   `ingest_spm_courses --file data/spm/spm_new_courses_D1.json --institution-id UNIV-012` (dry run),
   then `--apply`. The eligibility frame loads at start-up, so the rows show from the next revision.
   ROLLBACK: delete the 84 D1 rows from `saved_courses`, `admission_outcomes`, `course_tags`,
   `course_requirements`, `course_institutions`, then `courses` (Postgres has no cascade — Django's
   CASCADE is Python-side — so a student's saved UiTM course would abort a bare `courses` delete; the
   exact DELETE is in the 0088 docstring) BEFORE rolling back to a pre-0088 image.
   **Bumi D2 order (no migration):** read-only SQL first (below) → push (api + web) → CONFIRM the new api
   AND web revisions both serve 100% (the D2 rows use the `any_of` engine and the Bumi matric tracks need
   the D2 `pathways.py`; an old image reads an `any_of` group as a unit nobody can meet, so it would hide
   those 5 ATAU rows from everyone, and would give the matric rows no merit) → `ingest_spm_courses
   --file data/spm/spm_new_courses_D2.json --create-institutions` (dry run: expect `CREATE INSTITUTION MARA-BPT` and 66 CREATE, 0 UPDATE, 0 flagged) → the same with `--apply` →
   a re-revision so the frame reloads. The rows carry their own parents (no `--institution-id`). Read-only
   SQL before `--apply`: none of the 66 ids already in `courses`; `MARA-BPT` not in `institutions`; the
   seven UNIV ids exist (MARA-BPT's type IPTA and state "WP Kuala Lumpur" were checked against prod in
   review round 1). BEFORE ANY ROLLBACK, read-only: who chose a D2 course (a JSON choice, not a foreign key,
   so a delete leaves it pointing at nothing): `SELECT id, status FROM scholarship_applications WHERE
   chosen_programme->>'course_id' IN (D2) OR EXISTS (SELECT 1 FROM jsonb_array_elements(top_choices) e
   WHERE e->>'course_id' IN (D2))` and `SELECT count(*) FROM api_student_profiles WHERE
   chosen_programme->>'course_id' IN (D2)`; if either is non-zero, decide with the owner first.
   ROLLBACK, one transaction, D2 = the 66 ids of `data/spm/spm_new_courses_D2.json`
   (also the list in `docs/plans/2026-10-28-bumi-and-islamic-coverage-roadmap.md`, Sprint D2):
   `DELETE FROM saved_courses / admission_outcomes / course_tags / courses_career_occupations /
   course_requirements / course_institutions WHERE course_id IN (D2)`, then `DELETE FROM courses WHERE
   course_id IN (D2)`, then `DELETE FROM institutions WHERE institution_id = 'MARA-BPT'` (only after its
   course links are gone), then a re-revision. The D2 code may stay deployed (it shows only rows that exist).
   **Bumi F1 order (no migration; UP_TVET public, non-MARA):** read-only SQL first (below) → push (api +
   web) → CONFIRM the new api AND web revisions both serve 100% (an old api has no `mara` / `tvet_other`
   pathway, so the ILKA-* rows would show as plain "tvet"; an old web has no chips for them) →
   `ingest_tvet_courses --file data/tvet/tvet_new_courses_F1.json --create-institutions` (dry run: expect 4
   `CREATE INSTITUTION` (IKBN-022, ILKA-001..003), 35 `CREATE TVET-…`, 0 UPDATE, 33 `LINK` lines, "116 already
   held", 90 flagged, no "marked new but already exists", and no "Refusing") → the same with `--apply` (it refuses any `courses[]` id that already
   exists or is not `TVET-…`; a reviewed RE-run of the same file needs `--allow-update`) → a re-revision so the frame reloads. A held
   course (IJTM-* / IKBN-*) only GAINS campus links; its row and rule are never written. Read-only SQL before
   `--apply`: none of the 35 ids in `courses`; none of IKBN-022 / ILKA-001..003 in `institutions`; every
   IJTM-001..034 / IKBN-001..021 present; `SELECT count(*) FROM course_institutions WHERE (course_id,
   institution_id) IN (F1LINKS)` = 0 (F1LINKS = the 33 `held_links` with `already_linked: false`; a
   new link prod already holds makes `--apply` refuse, so this list is exactly what F1 added — review
   2026-10-29 found 22 prod pairs whose hyperlink carries June's id_kursus, now marked held). BEFORE ANY
   ROLLBACK, read-only: `SELECT id, status FROM scholarship_applications WHERE chosen_programme->>'course_id'
   IN (F1) OR EXISTS (SELECT 1 FROM jsonb_array_elements(top_choices) e WHERE e->>'course_id' IN (F1))` and
   `SELECT count(*) FROM api_student_profiles WHERE chosen_programme->>'course_id' IN (F1)`; non-zero → the
   owner decides first. ROLLBACK, one transaction, F1 = the 35 `courses[].course_id` of the file:
   `DELETE FROM saved_courses / admission_outcomes / course_tags / courses_career_occupations /
   course_requirements / course_institutions WHERE course_id IN (F1)`, then `DELETE FROM course_institutions
   WHERE (course_id, institution_id) IN (F1LINKS)`, then `DELETE FROM courses WHERE course_id IN (F1)`, then
   `DELETE FROM institutions WHERE institution_id IN ('IKBN-022','ILKA-001','ILKA-002','ILKA-003')` (only
   after their links are gone), then a re-revision. The F1 code may stay deployed. F2 (MARA) = the same
   command on a file built with `--families mara` (`MARA-NNN` institutions, category MARA).
   **Bumi F2 order (no migration; UP_TVET public MARA):** read-only SQL first → push (api + web) → CONFIRM
   the new api AND web revisions both serve 100% (the F2 parser and fixtures ship with the api; the rows
   themselves only need F1's `mara` pathway, already live) → `ingest_tvet_courses --file
   data/tvet/tvet_new_courses_F2.json --create-institutions` (dry run: expect 233 `CREATE INSTITUTION
   MARA-001..233` lines, 181 `CREATE TVET-…`, 0 UPDATE, 0 `LINK`, the line "181 new courses (606 campus
   offerings); 0 new campus links to held courses (0 already held); 59 flagged rows NOT ingested.", and
   no "Refusing") → the same with `--apply` ("Applied 181 courses, 0 held-course links; created 233
   institutions.") → a re-revision so the eligibility frame reloads. A reviewed RE-run of the same file needs
   `--allow-update`. Read-only SQL before `--apply`: `python manage.py ingest_tvet_courses --file
   data/tvet/tvet_new_courses_F2.json --sql` prints two SELECTs (the 181 course ids in `courses`; the 233
   `MARA-NNN` ids in `institutions`), each must return 0 rows; any row → stop (the file's picture is not
   prod's). Smoke after the re-revision: a Bumi citizen's search on `source_type=mara` returns 181 rows, a
   non-Bumi one 4 (the GIATMARA pages silent on Bumiputera), a foreigner who says Bumi the same 4 at most.
   ROLLBACK: `python manage.py ingest_tvet_courses --file data/tvet/tvet_new_courses_F2.json --rollback-sql`
   prints, first, the read-only checks to run BEFORE any rollback (who chose an F2 course:
   `scholarship_applications` chosen_programme / top_choices, `api_student_profiles` chosen_programme and
   `saved_courses`;
   `admission_outcomes` / `stpm_courses` rows naming a MARA-NNN institution; non-zero → the owner decides
   first), then the rollback in ONE transaction: `DELETE FROM saved_courses / admission_outcomes /
   course_tags / courses_career_occupations / course_requirements / course_institutions WHERE course_id IN
   (F2)`, then `DELETE FROM courses WHERE course_id IN (F2)`, then `DELETE FROM institutions WHERE
   institution_id IN (MARA-001..MARA-233)` (only after their links are gone; MARA-BPT is never touched),
   `COMMIT`, then a re-revision. F2 = the 181 `courses[].course_id` of the file. The F2 code may stay deployed.
   Both SQL flags refuse a file whose ids are not `TVET-<digits>` / `MARA-NNN` (or F1's IKBN- / ILKA- / IJTM-
   shapes and held IJTM- / IKBN- course ids) or hold a quote, so nothing hand-edited reaches the console.
   **Bumi F1b order (no migration; held TVET flags + remarks):** read-only SQL first → push (api) → CONFIRM
   the new api revision serves 100% → `fix_held_tvet_flags --file data/tvet/held_flag_fix_F1b.json` (dry run,
   through the `release-decisions` job, item 12's form: `--args=manage.py,fix_held_tvet_flags,--file,data/tvet/held_flag_fix_F1b.json`
   (the file ships in the image); expect "208 field change(s) on 63 course(s); 63 courses checked", no
   "Refusing") → the same with `,--apply` ("Applied 208 field change(s) on 63 course(s). Now re-revision
   halatuju-api so the eligibility frame reloads.") → a re-revision so the eligibility frame reloads. It writes
   ONLY `req_malaysian` / `no_colorblind` / `no_disability` / `remarks` of the 63 listed courses, in one
   transaction, and refuses the whole run if any listed course is missing, is not IJTM- / IKBN-, or any of its
   four fields differs from the file's `old` (compare-and-set; every mismatch printed). Read-only SQL before
   the push: `python manage.py fix_held_tvet_flags --file data/tvet/held_flag_fix_F1b.json --sql` prints ONE
   SELECT over `course_requirements` that returns only the listed rows whose three flags or remarks differ
   from the file's `old` (or are missing): it must return 0 rows; any row → stop, the file's picture is not
   prod's (rebuild or ask the owner; never edit `old` by hand to match). ROLLBACK: `--reverse --apply` (new →
   old, the same compare-and-set; `--sql --reverse` is its read-only check), then a re-revision. The
   `not_applied` differences in the file wait for the owner; nothing applies them.
4. **Reconcile the ledger before the push.** Compare every migration file with production's
   `SELECT app, name FROM django_migrations ORDER BY name` (read-only): a gap in the middle is the
   signal (0135 sat applied-but-unrecorded for a day in July). Release list: `docs/releases/v3.0.0-migrations.md`.
   Two sessions racing for one number: the second renumbers on rebase, and the ledger row is handed
   to the owner only once the number is settled.
5. **Eligibility, money and identity work gets an adversarial review BEFORE the push**, by an agent
   that did not build it (owner rule 2026-09-21; three user-reachable defects slipped past green gates).
6. **A push is a REQUEST.** Match your SHA in `gcloud builds list`, read the status, then check
   `status.latestReadyRevisionName` (never `status.traffic[0]` — this service carries a tagged revision
   at index zero). Only then say "live".
7. **Hotfix bypass:** run the trigger by hand with `_SKIP_TESTS=1` (command in each `cloudbuild.yaml`
   header); write the skip into the retro. **Rollback:** shift Cloud Run traffic to the previous
   revision (no build), or re-import the pre-H2 trigger exports in `docs/infra/`.
8. **Every gcloud command carries `--account tamiliam@gmail.com --project gen-lang-client-0871147736`**,
   and env changes use **`--update-env-vars`, never `--set-env-vars`** (it wipes the rest). Read a live
   value from `gcloud run services describe halatuju-api`, never from a settings default (the `VIRCLE_*`
   folder defaults are stale on purpose). The `release-decisions` Cloud Run Job follows the api image on
   every deploy (`SyncReleaseJob`) but NOT its env: mirror an env change onto the job by hand.
9. Scheduled work runs as **Cloud Scheduler → `POST /api/v1/internal/cron/<job>/`** with
   `X-Cron-Secret` (`CronRunView.JOBS`) set to the job FAMILY's key (`cron_auth.JOB_FAMILY`, A1.9a; a
   new job must be given a family or `test_cron_auth.py` fails); a POST needs a body (`-d '{}'`) or the load balancer answers 411.
   Read-service health (2026-10-24): `vision-outage` (daily 02:00 UTC, Vision OCR + Gemini reads, 24 h
   window), `read-outage-start` (`halatuju-read-outage-start`, hourly at :05 MYT, `--hourly` start-edge:
   mails once when an outage begins, ≥2 failures from ≥2 applications), `reprocess-ic-vision`
   (`halatuju-reprocess-ic-vision`, hourly: never-read docs + reads our outage deferred).
   **Time budget (A2.2, TD-518):** the sweep stops cleanly after `REPROCESS_TIME_BUDGET_SECONDS` (default 80) with
   at most `REPROCESS_BATCH_LIMIT` (100) documents a run; the next hour carries on (the cron output shows
   `STOPPED-AT-TIME-BUDGET`). Both are env-tunable on the service; nothing needs setting for the default.
   **G6 queues (A2.1, A2.3), MIGRATE-FIRST:** migrations `scholarship` `0209_sponsorprofile_finalise_queue` and
   `0210_read_and_notify_queues` are applied by hand BEFORE the API push. Three Scheduler jobs exist BEFORE the API
   push: `finalise-profiles` (every 5 min, `paid` secret family), `read-documents` (every 15 min, `paid`) and
   `assign-emails` (every 15 min, `email` family). `scholarship/urls.py` is at 599 of 600 lines: add no routes there.
   **Own timeout (SP-14):** met by the time budget; a separate Cloud Run Job was NOT adopted (it would bypass
   `cron_health.run_job`, so the System health light would read it as missed). Optional later, not done.
   **System health light (2026-10-28):** every cron run's outcome is recorded (`cron_health.run_job`,
   the body of `CronRunView`) and every email send's (`EMAIL_BACKEND` is now
   `apps.scholarship.mail_backend.RecordingSMTPBackend`, the SMTP backend plus one bookkeeping line) in
   `system_health_status` (scholarship `0180`, MIGRATE-FIRST); super admins read it at
   `GET /api/v1/admin/scholarship/system-health/` (60 s cache). ⚠ **Adding, pausing or re-timing a
   Scheduler job means editing `cron_health.EXPECTED_CADENCE` in the same change**, or the light reads
   it as missed (or never watches it). Supabase Auth's own mail (invites, resets) is not seen.
10. **When more than one agent is in the checkout:** declare the files you own in
   `AGENT-TERRITORY.log` (gitignored); stage explicit paths, never `git add -A`; build in a
   `git worktree` and push from it with `git push origin HEAD:main` — never check out `main` there.
   ⚠ A `node_modules` JUNCTION in a worktree must be removed with `[IO.Directory]::Delete('<path>')`
   BEFORE `git worktree remove`: a recursive delete walks into the real `node_modules` (happened 2026-10-05).
11. **A live re-read through a Cloud Run JOB must carry the service's read flags.** The jobs
   (`release-decisions` and the rest) carry only core env, not the `halatuju-api` service's
   `DOC_GENUINENESS_CHECK_ENABLED` / `BILLING_USAGE_ENABLED`; with the genuineness flag off the re-read
   silently rewrites `vision_fields` WITHOUT `authenticity` — it wipes the stored score (corpus C4,
   2026-10-26; TD-407). Run it as `gcloud run jobs execute <job> --task-timeout=3600s
   --update-env-vars=DOC_GENUINENESS_CHECK_ENABLED=1,BILLING_USAGE_ENABLED=true` (plus `--account` /
   `--project`), and check a sample of re-read rows for an `authenticity` block before calling it done.
   A batch over a few dozen documents also outlasts the job's default 10-minute task timeout.
   ⚠ The flag is on only for the exact value `1` (`true` leaves it off). **Since TD-407 (2026-10-27) the
   code guards it too:** a re-read that scores nothing keeps the stored score (WARNING `TD-407: kept the
   stored genuineness score`), and the hand-run `reextract_documents` / `reextract_offers` refuse to
   start without the flag unless `--allow-without-genuineness`. The HOURLY `reprocess_unread_ic` (cron
   endpoint, which swallows errors as a 200) only WARNS — log + stdout — and runs, so the self-heal never
   stops quietly; billing off only warns everywhere. The operational rule above still stands — without
   the flag a re-read keeps old scores but scores nothing new.
12. **A one-off team command runs through the `release-decisions` job with an args override** (its
   container command is `python`; its stored args are `manage.py,send_pending_decision_emails`). A value
   holding commas (JSON) needs gcloud's alternate delimiter `^@^`. Example — `split_combined_results`
   (2026-10-28; splits a combined results PDF into parts filed in the right results card, or moves a
   whole results document; PREVIEW unless `--apply`; plan from `--plan <file|inline JSON>` or the
   `SPLIT_RESULTS_PLAN` env var; the gitignored plan file never reaches the image, so pass it inline):
   `gcloud run jobs execute release-decisions --region asia-southeast1 --wait --account tamiliam@gmail.com
   --project gen-lang-client-0871147736 --args="^@^manage.py@split_combined_results@--plan@<compact JSON>"`
   (add `@--apply` to perform), or `--update-env-vars="^@^SPLIT_RESULTS_PLAN=<compact JSON>"
   --args=manage.py,split_combined_results[,--apply]`. It reads nothing with Gemini/Vision, so it needs
   none of item 11's read flags: the new/moved documents are left unread and the LIVE service's hourly
   self-heal reads them with the service's own flags. It needs `SUPABASE_URL` /
   `SUPABASE_SERVICE_ROLE_KEY` (on the job). Read the execution's log for the preview before `--apply`.

**Where documents go:** a new retrospective in `docs/retrospectives/`, release notes in
`docs/releases/`, sprint and incident history in `docs/sprint-history.md`, a domain rule in
`docs/domain-rules.md` — this file keeps current state only.

### Environment variables (Cloud Run `halatuju-api`)

Defaults live in `halatuju/settings/base.py` and `production.py`; each has a comment saying why.
**Secrets are named here, never written down.** Flags are OFF unless set to `1`/`true`.

| Variable | What it means |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `halatuju.settings.production` |
| `SECRET_KEY` | Django secret (production refuses the dev fallback) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | The database (production uses these, not `DATABASE_URL`; either one marks "real database") |
| `DATABASE_URL` | Alternative to the `DB_*` set (Supabase Session Pooler URI) |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | Comma lists; `CORS_ALLOWED_ORIGINS='*'` is refused |
| `SUPABASE_URL` | Supabase project URL — the ES256 JWKS check needs it |
| `SUPABASE_JWT_SECRET` | HS256 secret for legacy anon/service JWTs |
| `SUPABASE_SERVICE_ROLE_KEY` | Creates staff Supabase accounts (invite/resend); without it onboarding 500s |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | AI: Gemini primary, OpenAI the report fallback. ⚠ The Gemini key must belong to the HalaTuju GCP project (billing PREPAID since 2026-10-24 — credit running out is an outage, 402); set it on `halatuju-api` AND the `release-decisions` job. Until 2026-10-24 the live key sat in a project outside the owner's billing view |
| `GOOGLE_CLOUD_VISION_API_KEY` | Cloud Vision OCR (also usable by the eval tools) |
| `CONTRACT_QUIZ_MODEL`, `APPLY_COPY_DRAFT_MODEL`, `REQUESTS_TRIAGE_MODEL` | The model each job tries first. Contract quiz / sponsor terms / Word import and request triage default to `gemini-3.8-flash` and then fall back down the Flash cascade (`gemini.generate_with_fallback`, within a 115 s deadline: 100 s for the first model, a later one only with 15 s left; owner 2026-11-10, Gemini Phase 1). Apply-page copy (`gemini-2.5-flash`) makes one call, no fallback. ⚠ An env var set on the service still overrides the default: one pinned to `gemini-2.5-pro` (404 for our key) costs a failed call before the fallback answers |
| `GOOGLE_DWD_SERVICE_ACCOUNT` | The Workspace delegation account's EMAIL (`halatuju-meet@…`), **keyless** (TD-125): the runtime SA signs as it through the IAM Credentials API. Not a secret. Empty → Meet/Drive/Sheets do nothing |
| `MEET_ORGANISER_EMAIL` | The Workspace mailbox Meet, Drive and Sheets act as |
| `GOOGLE_MEET_SA_JSON` | **GONE** (TD-329, 2026-10-04): removed from Cloud Run, the key deleted in GCP, the code path deleted; setting it does nothing |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `DEFAULT_FROM_EMAIL` | Brevo SMTP. ⚠ Rotating the Brevo key also means Supabase Auth's own SMTP setting |
| `FRONTEND_URL` | Links in emails (`https://halatuju.xyz`) |
| `ADMIN_NOTIFY_EMAIL`, `FOUNDATION_NOTIFY_EMAIL`, `COURSE_REFRESH_REMINDER_EMAIL` | Who internal notices go to |
| `CRON_SECRET` | Guards `/api/v1/internal/cron/`: the OLD shared key, still accepted for every job while set (SEC-05 / TD-546). Retire it with `--remove-env-vars CRON_SECRET` once every Scheduler job sends its family key and the INFO line `opened by the shared CRON_SECRET` has stopped |
| `CRON_SECRET_MONEY`, `CRON_SECRET_PAID`, `CRON_SECRET_EMAIL`, `CRON_SECRET_MAINTENANCE` | A1.9a: one key per job family (`apps/scholarship/cron_auth.py` lists which job is in which). A job opens with its own family's key only; an unset key opens nothing. Four DIFFERENT random values; set with `--update-env-vars` and put each in its Scheduler jobs' `X-Cron-Secret` header |

> **Client IP warning (A1.9a).** The caller's address is the RIGHTMOST `X-Forwarded-For` hop (`halatuju/throttling.py`), which assumes the browser calls the API `run.app` URL directly. If a proxy or load balancer is ever put in front, every user will share one IP and the throttles (and the admin-login lock) must be changed first. IPv6 throttle keys use the /64 network; signing records keep the full address.

| `SENTRY_DSN` | Error tracking (no PII sent; the `X-Search-Term` header is scrubbed, `halatuju/sentry_scrub.py`) |
| `DOCUMENT_BACKUP_BUCKET` | GCS bucket `backup_documents` mirrors the private document bucket into |
| `SGD_TO_MYR_RATE` | S$ → RM for Singapore payslips (in-review cases only) |
| `MAX_DOC_SIZE_BYTES`, `MAX_DOCS_PER_APPLICATION`, `MAX_OTHER_DOCS`, `DOC_STAGE_MAX_ATTEMPTS` | Upload limits and the re-upload circuit-breaker |
| `DOC_ASSIST_RATE_LIMIT_PER_HOUR`, `DOC_ASSIST_ONLY_WHEN_UNCERTAIN`, `IC_GEMINI_FALLBACK_ENABLED` (default ON), `DOC_GENUINENESS_CHECK_ENABLED` | Paid AI reads on upload |
| `CHECK2_STUDENT_QUERIES_ENABLED`, `CHECK2_AUTO_GENERATE`, `CHECK2_ANSWER_RELEVANCE_ENABLED`, `VERDICT_CASE_SUMMARY_ENABLED` | Check-2 switches (the last three are paid) |
| `SPONSOR_POOL_ENABLED` | The anonymised sponsor pool (live) |
| `THIRD_ROUTE_OPEN` | Matriculation / Asasi / Diploma results accepted by the profile writer (third results route). S2b (the student form) needs it `1` — set it with `--update-env-vars` BEFORE that push. While off, third-route values 400 `third_route_closed` (an SPM / STPM `completed_qualifications` list still passes, S2b) |
| `SPONSOR_MOCK_DONATIONS_ENABLED` | **NEVER in production** (TD-258) — mints money; refuses to arm against a real database |
| `SPONSOR_COMMS_ENABLED`, `SPONSOR_TERMS_ENABLED`, `PARTNER_COMMS_ENABLED`, `PARTNER_NOTIFY_MAX_PER_RUN` | Platform halves of two-gate comms (each template has its own switch) |
| `SPONSOR_SEEN_THROTTLE_HOURS`, `ADMIN_SEEN_THROTTLE_HOURS`, `POOL_FUNDED_GRACE_HOURS` | Last-seen stamps; how long a funded card lingers |
| `DECLINE_COOLOFF_DAYS`, `DECLINE_QC_COOLOFF_HOURS`, `AWARD_COOLOFF_DAYS`, `AWARD_OFFER_EMAIL_COOLOFF_HOURS` | Embargo windows before a decision's email |
| `AWARD_ACCEPTANCE_ENABLED`, `BANK_DETAILS_CAPTURE_ENABLED` (deprecated) | Post-award student screens |
| `BURSARY_AGREEMENT_ENABLED` | In-app signing. ⛔ **TD-347 must be fixed first** |
| `GUARANTOR_PHONE_VERIFY_TTL_SECONDS`, `SIGN_ACCEPT_DEADLINE_DAYS`, `BURSARY_SIGN_REMINDER_DAYS`, `CONTRACTS_DRIVE_FOLDER` | Signing chain |
| `VIRCLE_SETUP_ENABLED`, `VIRCLE_ID_PREFIX`, `VIRCLE_ID_BAND_MIN` / `_MAX` | The eWallet task and the typed-id guard |
| `VIRCLE_AIRTABLE_PUSH_URL` / `VIRCLE_AIRTABLE_SECRET` | Vircle webhooks (secrets; blank = dark) |
| `VIRCLE_PAYMENTS_EMAIL`, `VIRCLE_PAYMENTS_FOLDER`, `VIRCLE_DRIVE_FOLDER`, `VIRCLE_SHEET_NAME`, `VIRCLE_SHEET_ID`, `VIRCLE_GUIDE_FOLDER`, `VIRCLE_GUIDE_FILENAME`, `VIRCLE_GUIDE_CACHE_SECONDS`, `VIRCLE_SPENDING_FOLDER`, `VIRCLE_SPENDING_SUMMARY_FOLDER`, `SPENDING_REPORT_QUIET_DAYS` | Payments, the relay sheet, the guide, spending reports (read live values, not defaults) |
| `INTERVIEW_SCHEDULING_ENABLED`, `INTERVIEW_MEET_ENABLED`, `INTERVIEW_DURATION_MIN`, `INTERVIEW_RESCHEDULE_CUTOFF_HOURS` | Interviews |
| `REVIEW_SLA_DAYS`, `REVIEW_NUDGES_ENABLED`, `REVIEW_NUDGE_SOON_DAYS`, `REVIEW_ESCALATE_GRACE_DAYS` | Reviewer deadlines and nudges |
| `STUDENT_ASSIGNMENT_EMAIL_ENABLED`, `PROFILE_COMPLETE_EMAIL_ENABLED` | Student notices |
| `WHATSAPP_ENABLED`, `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` (secret), `TWILIO_WHATSAPP_FROM`, `TWILIO_WHATSAPP_*_CONTENT_SID[_EN/_BM]` | WhatsApp reminders |
| `TWILIO_VERIFY_SERVICE_SID`, `PHONE_VERIFY_ENABLED` (paused), `PHONE_VERIFY_CHANNEL` | Student phone verification |
| `PARTNER_TEMP_PASSWORD_TTL_DAYS` | Staff temporary passwords |
| `REQUESTS_ENABLED`, `REQUESTS_QUOTE_MARGIN_PCT`, `BILLING_USAGE_ENABLED` | Requests space; the usage screen (the meter always runs) |
| `PARTNER_EMAIL_RESET_KINDS` | Set, run the seed job, UNSET. Several kinds need `--update-env-vars "^@^PARTNER_EMAIL_RESET_KINDS=a,b"` |
| `PROFILE_REFRESH_APP_IDS`, `AWARD_EMAIL_APP_IDS`, `VIRCLE_EMAIL_APP_IDS`, `SIGN_INVITE_APP_IDS`, `SEED_SPONSOR_ID` / `SEED_AWARD_APP_IDS`, `PATHWAY_REPAIR_APP_IDS`, `INCOME_DOC_TAG_APPLY`, `REQUIREMENTS_SNAPSHOT_APPLY`, `BACKFILL_VERDICT_VERSION_APPLY`, `BACKFILL_CONFIRMED_PROFILES_APPLY`, `REEXTRACT_DOC_TYPE`, `REEXTRACT_PASS` | One-shot scopes for argless cron jobs — set, run, unset |

Local-only (never on Cloud Run): `UPDATE_EMAIL_GOLDEN` (⛔ never set — see Live rules),
`HALATUJU_API_URL` / `HALATUJU_ADMIN_TOKEN` (`record_request_analysis`).
**Web (`halatuju-web`, build-time):** `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY` (public), `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (public),
`NEXT_PUBLIC_APP_VERSION` (from `COMMIT_SHA`, TD-076), `NEXT_PUBLIC_ORG_CODE` (unset in production),
`NEXT_PUBLIC_SANDBOX`, `NEXT_PUBLIC_THEME_SWITCH`.

## Live flag values (read from the running services, 2026-11-05)

Read with `gcloud run services describe` (JSON) on the running services, never from settings defaults. Services: `halatuju-api` revision `halatuju-api-01256-9kt`, `halatuju-web` revision `halatuju-web-01085-zz5`, region asia-southeast1. Re-read before relying on a value; a deploy that sets an env var changes it.

**Secret safety:** values are recorded only for switches and non-secret settings. Any key, token, password, DSN, address, id or other value that is or may be sensitive is listed by NAME only, as "(secret, not recorded)". No variable on either service is a Secret Manager reference; all are plain environment values.

**Flag parsing:** the code reads most flags with `.lower() in ('1','true','yes')`. Two are stricter: `DOC_GENUINENESS_CHECK_ENABLED` is ON only for the exact value `1`, and `IC_GEMINI_FALLBACK_ENABLED` is OFF only for `0`.

### Switches set on the api service

| Variable | Live value | State |
|---|---|---|
| `SPONSOR_POOL_ENABLED` | `true` | ON |
| `CHECK2_STUDENT_QUERIES_ENABLED` | `true` | ON |
| `DOC_GENUINENESS_CHECK_ENABLED` | `1` | ON |
| `CHECK2_AUTO_GENERATE` | `1` | ON |
| `INTERVIEW_MEET_ENABLED` | `1` | ON |
| `INTERVIEW_SCHEDULING_ENABLED` | `1` | ON |
| `STUDENT_ASSIGNMENT_EMAIL_ENABLED` | `1` | ON |
| `REVIEW_NUDGES_ENABLED` | `1` | ON |
| `WHATSAPP_ENABLED` | `1` | ON |
| `CHECK2_ANSWER_RELEVANCE_ENABLED` | `1` | ON |
| `PROFILE_COMPLETE_EMAIL_ENABLED` | `1` | ON |
| `VERDICT_CASE_SUMMARY_ENABLED` | `0` | OFF |
| `VIRCLE_SETUP_ENABLED` | `1` | ON |
| `REQUESTS_ENABLED` | `1` | ON |
| `PARTNER_COMMS_ENABLED` | `1` | ON |
| `SPONSOR_COMMS_ENABLED` | `1` | ON |
| `BILLING_USAGE_ENABLED` | `true` | ON |
| `THIRD_ROUTE_OPEN` | `1` | ON |
| `MAINTENANCE_REMINDERS_ENABLED` | `true` | ON |

### Switches NOT set on the api service (the code default applies)

| Variable | Code default | State in production |
|---|---|---|
| `AWARD_ACCEPTANCE_ENABLED` | off | OFF |
| `BANK_DETAILS_CAPTURE_ENABLED` | off | OFF |
| `BURSARY_AGREEMENT_ENABLED` | off | OFF |
| `PHONE_VERIFY_ENABLED` | off | OFF |
| `SPONSOR_TERMS_ENABLED` | off | OFF |
| `SPONSOR_MOCK_DONATIONS_ENABLED` | off, and refused on any managed database (never set in production) | OFF |
| `IC_GEMINI_FALLBACK_ENABLED` | on (off only when set to `0`) | ON |

### Non-secret settings on the api service

| Variable | Live value |
|---|---|
| `DECLINE_COOLOFF_DAYS` | `7` |
| `AWARD_COOLOFF_DAYS` | `2` |
| `MERIT_DATA_VERSION` | `2026-03-13` |
| `DATA_RELOAD_TRIGGER` | `sprint8-1771373867` |
| `PISMP_DATA_RELOAD` | `2026-06-23-asasi-tvet` |
| `DJANGO_SETTINGS_MODULE` | `halatuju.settings.production` |
| Container limits | cpu `1000m`, memory `2Gi` |
| Autoscaling | max instances `3`, no minimum set, startup CPU boost `true` |

### Secret or sensitive variables on the api service (name only)

| Variable | Value |
|---|---|
| `DB_HOST` | (secret, not recorded) |
| `DB_PORT` | (secret, not recorded) |
| `DB_USER` | (secret, not recorded) |
| `DB_PASSWORD` | (secret, not recorded) |
| `DB_NAME` | (secret, not recorded) |
| `ALLOWED_HOSTS` | (secret, not recorded) |
| `CORS_ALLOWED_ORIGINS` | (secret, not recorded) |
| `SECRET_KEY` | (secret, not recorded) |
| `SUPABASE_JWT_SECRET` | (secret, not recorded) |
| `GEMINI_API_KEY` | (secret, not recorded) |
| `SUPABASE_URL` | (secret, not recorded) |
| `SUPABASE_SERVICE_ROLE_KEY` | (secret, not recorded) |
| `EMAIL_HOST_USER` | (secret, not recorded) |
| `EMAIL_HOST_PASSWORD` | (secret, not recorded) |
| `FRONTEND_URL` | (secret, not recorded) |
| `OPENAI_API_KEY` | (secret, not recorded) |
| `EMAIL_HOST` | (secret, not recorded) |
| `ADMIN_NOTIFY_EMAIL` | (secret, not recorded) |
| `CRON_SECRET` | (secret, not recorded) |
| `DOCUMENT_BACKUP_BUCKET` | (secret, not recorded) |
| `COURSE_REFRESH_REMINDER_EMAIL` | (secret, not recorded) |
| `MEET_ORGANISER_EMAIL` | (secret, not recorded) |
| `DEFAULT_FROM_EMAIL` | (secret, not recorded) |
| `TWILIO_WHATSAPP_FROM` | (secret, not recorded) |
| `TWILIO_WHATSAPP_REMINDER_CONTENT_SID` | (secret, not recorded) |
| `TWILIO_ACCOUNT_SID` | (secret, not recorded) |
| `TWILIO_AUTH_TOKEN` | (secret, not recorded) |
| `TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_EN` | (secret, not recorded) |
| `TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_BM` | (secret, not recorded) |
| `TWILIO_WHATSAPP_REMINDER_CONTENT_SID_EN` | (secret, not recorded) |
| `TWILIO_WHATSAPP_REMINDER_CONTENT_SID_BM` | (secret, not recorded) |
| `TWILIO_VERIFY_SERVICE_SID` | (secret, not recorded) |
| `AWARD_EMAIL_APP_IDS` | (secret, not recorded) |
| `VIRCLE_EMAIL_APP_IDS` | (secret, not recorded) |
| `VIRCLE_SHEET_ID` | (secret, not recorded) |
| `VIRCLE_DRIVE_FOLDER` | (secret, not recorded) |
| `VIRCLE_PAYMENTS_FOLDER` | (secret, not recorded) |
| `VIRCLE_GUIDE_FOLDER` | (secret, not recorded) |
| `VIRCLE_AIRTABLE_PUSH_URL` | (secret, not recorded) |
| `VIRCLE_AIRTABLE_SECRET` | (secret, not recorded) |
| `VIRCLE_SPENDING_FOLDER` | (secret, not recorded) |
| `VIRCLE_SPENDING_SUMMARY_FOLDER` | (secret, not recorded) |
| `GOOGLE_DWD_SERVICE_ACCOUNT` | (secret, not recorded) |

### halatuju-web

The web service carries only the three build-time public settings below; they are not switches.

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | (secret, not recorded) |
| `NEXT_PUBLIC_SUPABASE_URL` | (secret, not recorded) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | (secret, not recorded) |
