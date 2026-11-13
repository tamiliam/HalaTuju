# A5 replay: the owner's steps (written in R1, run in R3)

Written by the lead in sprint R1. **Nothing here has been run.** Each step needs a fresh yes from the
owner at the time (design section 6). Every `gcloud` command carries `--account` and `--project`; none
changes the gcloud config; none uses `--set-env-vars`.

Names used below (change them in one place if you prefer others):

| What | Name |
|------|------|
| GCP project | `gen-lang-client-0871147736` (account `tamiliam@gmail.com`), region `asia-southeast1` |
| Secret | `halatuju-replay-db-url` |
| Service account | `halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com` (no project role at all) |
| Image | `asia-southeast1-docker.pkg.dev/gen-lang-client-0871147736/cloud-run-source-deploy/halatuju-replay:r1` |
| Job | `halatuju-replay` |

If `cloud-run-source-deploy` is not the Artifact Registry repository the api's source deploys use, list
them first and use that one:
`gcloud artifacts repositories list --location asia-southeast1 --account tamiliam@gmail.com --project gen-lang-client-0871147736`

## 1. The read-only role (Supabase SQL editor)

Run the PRE-CHECK at the top of `halatuju_api/apps/scholarship/eval/replay/owner/replay_ro_create.sql`
first (Postgres version, and whether `postgres` has BYPASSRLS; if not, use the per-table read policy
fallback in the same file). Then run the rest with a real password and the expiry date (run date plus 7
days) in place of the two placeholders, and paste the CHECK answers back to the lead, including the
CREATE-on-public answer and the list of SECURITY DEFINER functions `replay_ro` can run. The connection string is the
**session pooler, port 5432** (never 6543), user `replay_ro.<project ref>`:

`postgresql://replay_ro.<project ref>:<password>@<session pooler host>:5432/postgres`

## 2. The secret and the service account

Write the connection string to a temporary file (one line, no newline at the end), then:

```
gcloud secrets create halatuju-replay-db-url --replication-policy=automatic --data-file=<temp file> --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

Delete the temporary file. Then a service account that can read that ONE secret and nothing else (no
project role, so it cannot reach Storage, Vision or Gemini even if asked):

```
gcloud iam service-accounts create halatuju-replay --display-name "A5 replay (read only)" --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud secrets add-iam-policy-binding halatuju-replay-db-url --member serviceAccount:halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

## 3. Build the image (Cloud Build, by hand; no trigger)

From the HalaTuju repo root, in Git Bash, with `<LIVE_MAIN_SHA>` the commit of the live api revision.
The context folder (here `../replay-ctx`) must be outside the repo and empty.

```
mkdir -p ../replay-ctx/old ../replay-ctx/new ../replay-ctx/harness
git archive -o ../replay-ctx/old.tar v3.1.0 halatuju_api
git archive -o ../replay-ctx/new.tar <LIVE_MAIN_SHA> halatuju_api
cd ../replay-ctx
tar -xf old.tar -C old
tar -xf new.tar -C new
rm old.tar new.tar
git -C ../HalaTuju rev-parse v3.1.0^{commit} > old/COMMIT
git -C ../HalaTuju rev-parse <LIVE_MAIN_SHA> > new/COMMIT
cp -r new/halatuju_api/apps/scholarship/eval/replay harness/replay
rm -rf harness/replay/owner
cp new/halatuju_api/apps/scholarship/eval/replay/owner/Dockerfile.replay Dockerfile
gcloud builds submit . --tag asia-southeast1-docker.pkg.dev/gen-lang-client-0871147736/cloud-run-source-deploy/halatuju-replay:r1 --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

The harness is taken from the live main tree, so the A5 harness must be merged before the build. The
build fails on its own if any engine path does not resolve in either tree.

## 4. Create the job (no execution yet)

```
gcloud run jobs create halatuju-replay --image asia-southeast1-docker.pkg.dev/gen-lang-client-0871147736/cloud-run-source-deploy/halatuju-replay:r1 --region asia-southeast1 --service-account halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --set-secrets REPLAY_DATABASE_URL=halatuju-replay-db-url:latest --tasks 1 --max-retries 0 --task-timeout 3h --cpu 2 --memory 4Gi --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

No environment variables are set: the image carries only `TZ`, `DJANGO_SETTINGS_MODULE` and `PYTHONPATH`.
If anything has to change later, use `--update-secrets` / `--update-env-vars`, never the `--set-` forms.

## 5. Run it: counts first, then the replay

> **HARD RULE: no deploy, no migration, no ALTER while the replay job runs.** This covers the api, the
> web and any Supabase change (a schema change from the dashboard or the MCP too). Run the job in a
> quiet window (late evening, no deploy planned, no other job touching the database). If a deploy
> cannot wait, **stop the job first** with the command below (the execution name is in the
> output of the run command, or `gcloud run jobs executions list`), and deploy only once it shows as
> cancelled.

```
gcloud run jobs executions cancel <EXECUTION> --region asia-southeast1 --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

**No deploy and no migration while the job runs**, because each child holds ONE read transaction for
the whole run (up to 3 hours). An `ALTER` on a table the job has read waits for that transaction to
end, and every live query on the table then queues behind the waiting `ALTER`: the site stalls. The
job's own timeouts do not prevent this: `SET LOCAL lock_timeout` (5s) only stops the JOB waiting on a
lock, and `SET LOCAL idle_in_transaction_session_timeout` (12 minutes for the parent, 2 minutes for each
child) only ends a transaction left idle. The parent reads no table while it waits for the children to
join, counts the cases only after they have joined, then ends its transaction at once. The deploy-side
fix (the migrate step sets its own `lock_timeout`, so an `ALTER` fails fast) is TD-620.

The `^@^` prefix tells gcloud to split the arguments on `@`, because the months contain a comma.
`<INSTANT>` is the snapshot time with a timezone, for example `2026-11-20T18:00:00+08:00`.

```
gcloud run jobs execute halatuju-replay --region asia-southeast1 --wait --args "^@^--instant=<INSTANT>@--months=2026-11,2026-12@--counts-only" --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

Read the counts with the lead. Then, on a fresh yes, the full run (once; once more only if R3 needs it):

```
gcloud run jobs execute halatuju-replay --region asia-southeast1 --wait --args "^@^--instant=<INSTANT>@--months=2026-11,2026-12" --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

The output is in Cloud Logging under the job; it holds only codes, amounts, hashes and case ids.

## 6. Afterwards: remove everything

```
gcloud run jobs delete halatuju-replay --region asia-southeast1 --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud secrets delete halatuju-replay-db-url --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud iam service-accounts delete halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud artifacts docker images delete asia-southeast1-docker.pkg.dev/gen-lang-client-0871147736/cloud-run-source-deploy/halatuju-replay --delete-tags --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

Then run `halatuju_api/apps/scholarship/eval/replay/owner/replay_ro_drop.sql` in the Supabase SQL editor
and paste its CHECK answers (both empty) back to the lead.
