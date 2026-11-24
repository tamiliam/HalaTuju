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

## 2b. The derived fingerprint key (LL5; an owner step, the value in words only, no script)

**Who runs this.** These are the OWNER's steps. No agent runs them. Nothing creates or grants a secret
without the owner's yes at that time. The key value is never printed, never pasted in a chat, and never
put in a file that git tracks.

**The order.** (1) Make the derived key value and pipe it straight into the create command below.
(2) Give the replay's service account read access to that one secret. (3) Once the job exists (step 4),
give it to the job as `REPLAY_FINGERPRINT_KEY`. No tool in this repository makes the value yet: step
(1) is described in words only, below.

> **Step 2b needs a helper to make the derived value. Not built. Owner decides.**

Make the derived key once: read the production SECRET_KEY, compute sha256(salt + SECRET_KEY) as hex,
write it straight into Secret Manager as the replay job's REPLAY_FINGERPRINT_KEY. Needs the Secret
Manager API and the owner's yes at that time, given for this step when it is run.

The wiring is now built (LL5 phase C1): the replay passes `REPLAY_FINGERPRINT_KEY` on to its `new`
child ONLY when it is started with `--human-lens`. Without that flag the key stays in the parent and no
child sees it. The secret's name is fixed: `halatuju-replay-fingerprint-key`. Create it with the value
coming in on standard input (`--data-file=-`) straight from the step that computes it, never typed,
shown or saved:

```
gcloud secrets create halatuju-replay-fingerprint-key --replication-policy=automatic --data-file=- --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

> **Never run this command on its own. It waits for typed input. If you type or paste the key, the key shows on the screen. The Enter key then adds a new line, and that stored value stops every run (exit 3). The value must come in through a pipe, from the helper. The helper is not built.**

Give the replay's service account read access to this one secret:

```
gcloud secrets add-iam-policy-binding halatuju-replay-fingerprint-key --member serviceAccount:halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

Once the job exists (step 4), mount it as the variable the replay reads:

```
gcloud run jobs update halatuju-replay --update-secrets REPLAY_FINGERPRINT_KEY=halatuju-replay-fingerprint-key:latest --region asia-southeast1 --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

The lens itself runs only with `--human-lens` and an absolute `--human-lens-exam-folder` outside any
git repository; `--human-lens-freeze` (off by default) is the only way to write an exam file. Do not
run the job with the lens until the home of the exam file is decided.

- **Never seen.** Neither `SECRET_KEY` nor the derived value may reach a terminal, a shell history or
  a file (not even a temporary one), and neither goes into the image.
- **The input.** The hash is over the salt followed by the exact characters of `SECRET_KEY`, with
  nothing added: no newline, no space. Tools that print or read a value often add a newline at the end;
  a newline in the input gives a different, wrong key. The salt is the fixed `_KEY_SALT` in
  `halatuju_api/apps/scholarship/verdict_context.py`.
- **The value stored** is the derived key, never `SECRET_KEY` itself: exactly 64 hex characters, with
  no new line at the end and no spaces. If the variable is set to anything else that is not empty (a
  newline or spaces alone included), the job does not start: the parent stops while it loads its
  settings, before any child starts, prints one fatal line (`ImproperlyConfigured`, the class name
  only) and exits with code 3. This happens with the lens off too, because the parent loads the
  variable on every run once the secret is mounted. Absent or empty, it runs key-free and every
  fingerprint mismatches; with the lens on, exam-1 gets no score and the job still exits 0. If an
  exam-1 file exists (or a freeze run has enough candidate cases), the block says "not run:
  key_blank". Otherwise it says "not run: exam_missing" or "the exam is not frozen yet". Read the
  block, not the exit code.
- **A second create fails.** Running the `gcloud secrets create` command above a second time fails
  with "already exists". To replace a wrong value, the owner adds a new version, with the value again
  coming in on standard input:

```
gcloud secrets versions add halatuju-replay-fingerprint-key --data-file=- --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

> **Never run this command on its own. It waits for typed input. If you type or paste the key, the key shows on the screen. The Enter key then adds a new line, and that stored value stops every run (exit 3). The value must come in through a pipe, from the helper. The helper is not built.**

- **A wrong but well-shaped key** (64 hex characters made from a wrong input) is not caught here. The
  replay's human lens (built in LL5) compares the key's 8-character key check with the `key_check`
  stored on the recorded verdicts and refuses to freeze or score exam-1 on a mismatch, so it is caught
  there (`candidate_key_check_not_current` or `candidate_key_checks_differ` before a freeze,
  `key_check_differs_from_exam` or `key_check_differs_from_cases` after it).
- **Who can read it.** The replay's service account is given access to this one secret, but project
  Owners, Editors and Secret Manager admins can read it too.
- **Never `SECRET_KEY` on the job.** The job must never be given `SECRET_KEY` (not as a variable, not
  as a secret). The replay refuses to start if its environment holds a `SECRET_KEY` that is not empty.

Delete the secret with the rest in step 6.

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
fix (the migrate step sets its own `lock_timeout`, so an `ALTER` fails fast) is TD-669.

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

Only when the lens switch (`--human-lens`) is on, the lens and coach-grade report comes after the JSON lines, between the lines `=== LL5 lens report start ===` and `=== LL5 lens report end ===`; exit code 4 means a lens or coach error, or a report that could not be shown. How to read the block:
`docs/replay-human-lens.md`.

`--counts-only` and `--human-lens` cannot be used together: that is an argument error (exit code 2)
and nothing runs. Run the counts without the lens. A relative `--human-lens-exam-folder` is an
argument error too (exit code 2).

## 5b. Where the exam file lives in production (OPEN: the owner decides)

The human lens keeps its frozen exams in two files, `exam-1.json` and `exam-old.json`, in one exam
folder. The folder must survive from one run to the next, or "frozen" means nothing. Where that folder
lives in production is not decided and not built. There are two options. This section gives the facts
of each. It does not choose.

**Facts that hold for both options.**

- The replay job's work folder is `/tmp/replay` (the default `--workdir` in `parent.py`). On the Cloud
  Run job it is in memory and is lost after each run.
- The job's printed output goes to Cloud Logging. The job does not write the markdown report. It does
  write files into its work folder: each child's record file (`old.jsonl`, `new.jsonl`,
  `new_again.jsonl`) and, with the lens on, the `new` child's two result files (`human_lens.json` and
  `coach_grade.json`). They are lost when the job ends, with the rest of that folder.
- The job's service account has no project role (step 2), so it has no Storage access.
- How the freeze writes its file: it writes the exam to a temp file in the same folder (Python's
  `tempfile.mkstemp`), then makes a HARD LINK from that temp file to the exam's name (`os.link`), then
  removes the temp file. A hard link never replaces a file that already exists. It is not an exclusive
  create of the final name. Before the link, the freeze also checks that the name does not exist.
- A mounted bucket (gcsfuse) has no hard links. So the freeze code as it is today cannot write there:
  it answers `folder_not_writable`.
- The folder must be a full path, outside every git repository, and on a filesystem with hard links.
- If an exam file is lost, a normal run does not make a new one. It reports `exam_missing` and the
  number of cases that could enter, and gives no score for that exam. Only a run with
  `--human-lens-freeze` writes a new exam file, and it may hold other cases than the lost one.
- An exam file that exists is never overwritten. When it exists, every run loads it and scores it, a
  freeze run too. The freeze itself also refuses a name that exists (`already_frozen`).

**Option A: the station.**

- What it is: the lens runs on the owner's station against production, read-only. The exam folder is
  a local folder outside every repository.
- What must be granted: the owner's yes to read production from the station.
- Where the file sits: in that local folder on the station.
- If the station or the folder is lost: the exam files are lost with it. The next normal run reports
  `exam_missing`. This tool makes no backup copy.
- What stops a second freeze from replacing the first: a run loads the existing file and does not
  freeze again. The freeze checks that the name does not exist, and the hard link refuses a name that
  exists (`already_frozen`).
- Also a fact: the learning-loop roadmap (Sprint LL5, "When it runs") says production data cannot be
  copied to a home machine. The exam files hold plain application ids and one decision time per id.
  The owner's yes would need to cover that.
- Also a fact: these owner steps describe the Cloud Run job only. Steps to run the replay on the
  station are not written.
- Also a fact: this option needs two more things on the station. (1) The derived key on that
  machine. Today the key is planned to live only in Secret Manager, for the Cloud Run job. (2) A
  read-only database login on that machine.
- Also a fact: this option needs an exam folder on a filesystem with hard links. This was not checked
  on the station.

**Option B: a bucket object.**

- What it is: each exam file is one object in a Cloud Storage bucket. It is written with a
  must-not-exist precondition, so a frozen exam can never be overwritten.
- What must be granted: the owner's yes to give the replay job's service account Storage access.
- Where the file sits: as an object in that bucket.
- If the object or the bucket is lost: the exam file is lost. The next normal run reports
  `exam_missing`. Step 6 ("remove everything") lists no bucket today.
- What stops a second freeze from replacing the first: the must-not-exist precondition refuses the
  write when the object exists.
- Also a fact: this option is not built. The freeze code today writes only to a local folder, by hard
  link. The lens runs inside the replay's network refusal, which lets only the database address
  through, so a Storage call from there would be refused today. Option B needs new code.

**One more fact.** A third home exists in principle: a network file share mounted into the job (a
Cloud Run NFS volume, on Filestore). Hard links work there, so the freeze code needs no change. It
costs money each month. It is not priced here.

Until the owner decides, the lens does not run on real data.

## 6. Afterwards: remove everything

```
gcloud run jobs delete halatuju-replay --region asia-southeast1 --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud secrets delete halatuju-replay-db-url --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud secrets delete halatuju-replay-fingerprint-key --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud iam service-accounts delete halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud artifacts docker images delete asia-southeast1-docker.pkg.dev/gen-lang-client-0871147736/cloud-run-source-deploy/halatuju-replay --delete-tags --quiet --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

Then run `halatuju_api/apps/scholarship/eval/replay/owner/replay_ro_drop.sql` in the Supabase SQL editor
and paste its CHECK answers (both empty) back to the lead.

## 7. R3 checklist (the lead, before the owner reads the report)

Added in the R2 review round. Each item is a known limit of the R2 harness; R3 either closes it or writes
it into the report as a limit.

- [ ] **Adapters on real record shapes.** Only 4 of the 29 adapters have run on an application, and that
  application came from the test factory (award.proposed_award_amount, award.course_start_unknown,
  funding.classify_pathway, verdict.build_verdict). The other **25** have never run against a real record. In
  the counts-only run (step 5), check that each of the 25 finds its cases. In the full run, check that each
  writes records with **0 dropped keys** and few C (could not run). An adapter with a C count close to its
  case count is broken, not the engine.
- [ ] **Course eligibility covers SPM requirements only.** `courses.check_eligibility` runs the SPM
  requirements table (`requirements_df`). The TVET and university requirement tables are not replayed.
  `courses.check_stpm_eligibility` covers STPM separately. A change in the TVET or university tables does not
  show up in this replay at all. Write that limit into the report.
- [ ] **No Bumiputera answer.** The course engine's Bumiputera flag is False on BOTH sides (owner ruling
  2026-10-28: course-guide only). A change to how Bumiputera-only courses are decided is therefore not
  tested. This is a coverage gap, not a pass.
- [ ] **Rulings narrowed in R2.** R-67 is listed, not encoded, until R3 rules on its exact shape. Every
  R-67 difference is B until then. R-DEG7's unknown-to-TVET branch matches only when the stored pathway
  code maps to that TVET category. A category reached from a programme name alone stays B.
