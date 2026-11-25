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
| Exam bucket (LL6) | `halatuju-replay-exams-0871147736`, region `asia-southeast1` (made in step 4b; it does not exist until the owner makes it) |

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
project role, so it cannot reach Vision or Gemini even if asked; in LL6 it gets rights on ONE Storage
bucket only, in step 4b, and nothing else in Storage):

```
gcloud iam service-accounts create halatuju-replay --display-name "A5 replay (read only)" --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud secrets add-iam-policy-binding halatuju-replay-db-url --member serviceAccount:halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

## 2b. The derived fingerprint key (LL5 wiring; LL6: made by hand, once, with the recipe below)

**Who runs this.** These are the OWNER's steps. No agent runs them. Nothing creates or grants a secret
without the owner's yes at that time. The key value is never printed, never pasted in a chat, and never
put in a file that git tracks.

**What the key is.** sha256 of the fixed salt `halatuju.scholarship.verdict_context.evidence_fingerprint`
(`_KEY_SALT` in `halatuju_api/apps/scholarship/verdict_context.py`) followed by the exact characters
of the production `SECRET_KEY`, written as 64 hex characters. The secret's name is fixed:
`halatuju-replay-fingerprint-key`. The owner decided to make this key BY HAND. No helper tool makes it
and none will be built.

The wiring is built (LL5 phase C1): the replay passes `REPLAY_FINGERPRINT_KEY` on to its `new` child
ONLY when it is started with `--human-lens`. Without that flag the key stays in the parent and no child
sees it.

**The order.** (1) Make the key and store it with the recipe in 2b.1. (2) Give the replay's service
account read access to that one secret (2b.2). (3) Once the job exists (step 4), give it to the job as
`REPLAY_FINGERPRINT_KEY` (2b.3).

### 2b.1 The recipe (Git Bash only; one paste)

Where: Git Bash only. One paste, from the first `(` to the last `)`. Use it the first time. Use it again
whenever `SECRET_KEY` changes, but read "Once exam-1 is frozen" below first.

```
( set +x
K=$(gcloud run services describe halatuju-api --region asia-southeast1 --format="json[private]" --no-log-http --account tamiliam@gmail.com --project gen-lang-client-0871147736 | python -c 'import sys,json,hashlib,hmac
def stop(why): sys.exit("STOP: "+why+".")
try:
    s=json.loads(sys.stdin.buffer.read().decode("utf-8"))
    e=[v for c in s["spec"]["template"]["spec"]["containers"] for v in c.get("env") or [] if v.get("name")=="SECRET_KEY"]
except Exception:
    stop("could not read the service description (see any gcloud message above)")
if not e: stop("the service has no SECRET_KEY")
if any("value" not in v for v in e): stop("SECRET_KEY is kept as a secret reference, not a plain value")
ks={v["value"] for v in e}
k=ks.pop() if len(ks)==1 else ""
if not k or not k.isascii() or k.startswith("django-insecure"): stop("SECRET_KEY is not one plain production value")
d=hashlib.sha256(b"halatuju.scholarship.verdict_context.evidence_fingerprint"+k.encode("utf-8")).hexdigest()
sys.stderr.write("made:   key check "+hmac.new(bytes.fromhex(d),b"verdict_context key check",hashlib.sha256).hexdigest()[:8]+"\n")
sys.stdout.buffer.write(d.encode("ascii"))')
if [ "${#K}" -ne 64 ]; then echo "STOPPED. Nothing was stored."; exit 1; fi
gcloud secrets describe halatuju-replay-fingerprint-key --account tamiliam@gmail.com --project gen-lang-client-0871147736 >/dev/null 2>&1 || gcloud secrets create halatuju-replay-fingerprint-key --replication-policy=automatic --account tamiliam@gmail.com --project gen-lang-client-0871147736 || exit 1
printf %s "$K" | gcloud secrets versions add halatuju-replay-fingerprint-key --data-file=- --no-log-http --account tamiliam@gmail.com --project gen-lang-client-0871147736 || { echo "NOT STORED: see the gcloud error above."; exit 1; }
gcloud secrets versions access latest --secret halatuju-replay-fingerprint-key --no-log-http --account tamiliam@gmail.com --project gen-lang-client-0871147736 | python -c 'import sys,re,hmac,hashlib
b=sys.stdin.buffer.read()
ok=re.fullmatch(rb"[0-9a-fA-F]{64}",b)
print("stored: key check "+hmac.new(bytes.fromhex(b.decode("ascii")),b"verdict_context key check",hashlib.sha256).hexdigest()[:8]+"   OK 64 hex" if ok else "BAD: the stored value is not 64 hex characters ("+str(len(b))+" bytes)")' )
```

The recipe in the design plan writes `<ACCT>` where the account and project flags go. Here they are
already filled in (`--account tamiliam@gmail.com --project gen-lang-client-0871147736`, five places).
Change nothing else in the block.

A good screen (the first time; later runs have no "Created secret" line and a higher version number):

```
made:   key check 1a2b3c4d
Created secret [halatuju-replay-fingerprint-key].
Created version [1] of the secret [halatuju-replay-fingerprint-key].
stored: key check 1a2b3c4d   OK 64 hex
```

The two key-check codes must be the same. They are not secret. (`1a2b3c4d` above is only an example.)

If the screen shows something else:

- `STOP: ...` then `STOPPED. Nothing was stored.` = nothing changed. Send the STOP line to the agent.
- "secret reference" = a different recipe is needed. Ask for it.
- `NOT STORED` = nothing new saved. Fix the gcloud error (often "log in again") and paste the same block
  again.
- `BAD: ...` = paste the same block again (it adds a new version; the job reads the newest). Then, if
  wanted, disable the bad version (`<N>` is its number):
  `gcloud secrets versions disable <N> --secret halatuju-replay-fingerprint-key --account tamiliam@gmail.com --project gen-lang-client-0871147736`.
  Never edit a version.
- "Python was not found" or the Microsoft Store opens = change both `python -c` to `py -3 -c`.

> **Never run a gcloud command from this block on its own. Never run
> `gcloud run services describe halatuju-api` without `--format="json[private]"` and the pipe.**

Why the block is shaped this way (fixes found by the adversarial read of the first draft):

- **gcloud's own log files.** A plain `--format json` describe also writes the whole service
  description, with every plain environment value (`SECRET_KEY` too), into gcloud's log folder
  (`%APPDATA%\gcloud\logs`, kept 30 days). `--format="json[private]"` (with the quotes) prevents that.
- **HTTP logging.** If gcloud's HTTP logging is on, request and response bodies go to the screen and the
  log. `--no-log-http` is on each call that carries `SECRET_KEY` or the key.
- **No empty secret.** The value is stored only when it is exactly 64 characters. The secret is created
  (only if it does not exist yet) with no value, and the value is added as a version only after that
  check. The block never sends an empty value.
- **The value stays in memory.** It lives only in the shell variable `K` inside the brackets: not
  exported, not in the shell history, passed on by `printf` (a shell builtin), and gone at the closing
  `)`. `exit` inside the brackets ends only the bracket shell, not the Git Bash window.
- **Which `SECRET_KEY`.** The block reads the service's template. The "made" key check matches the
  live service only if the serving revision uses the template's `SECRET_KEY`.

**Once exam-1 is frozen.** The job reads the newest version (`:latest`, in 2b.3). If `SECRET_KEY` is
rotated after exam-1 is frozen, running the recipe again makes a new version under the new key, and the
lens then refuses exam-1 (`key_check_differs_from_exam`). Keeping exam-1 scoreable needs the job to keep
reading the OLD version. A new exam under a new key is not designed. Ask the release lead before any
`SECRET_KEY` rotation once exam-1 is frozen.

### 2b.2 Read access for the replay's service account

Give the replay's service account read access to this one secret:

```
gcloud secrets add-iam-policy-binding halatuju-replay-fingerprint-key --member serviceAccount:halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

### 2b.3 Give it to the job

Once the job exists (step 4), mount it as the variable the replay reads:

```
gcloud run jobs update halatuju-replay --update-secrets REPLAY_FINGERPRINT_KEY=halatuju-replay-fingerprint-key:latest --region asia-southeast1 --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

The lens itself runs only with `--human-lens` and ONE exam home: in production, the bucket
(`--human-lens-exam-bucket`, steps 4b and 5). `--human-lens-freeze` (off by default) is the only way to
freeze an exam. The proof-first run (step 4c) is the first lens run on real data. It has no freeze, so
it freezes and uploads nothing. It needs the bucket (step 4b), an image that holds LL6 (step 4c, first
box) and the owner's yes, and is never on a release slot (11:00, 16:00, 21:00 MYT) or an R3 run day. No
other lens run, and no freeze run, happens until step 4c has passed and the owner says yes again.

### 2b.4 Facts to keep in mind

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
- **A second run of the recipe.** The recipe creates the secret only when it does not exist yet. Every
  later run adds a new version, and the job reads the newest (`:latest`). There is no separate
  "replace" command: to replace a wrong value, paste the same recipe block again.
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

## 4b. The exam bucket and its access (LL6)

The owner chose a bucket as the exam home (step 5b). These are the OWNER's steps; no agent runs them.
The bucket does not exist until the owner makes it here.

What it is: ONE private bucket, `halatuju-replay-exams-0871147736`, region `asia-southeast1`, storage
class Standard, uniform bucket-level access, public access prevention enforced, and a default
event-based hold ON (every new object is held: it cannot be deleted or replaced until the hold is
released by hand). Soft delete stays on (a deleted object is kept 7 days). No locked retention policy.

```
gcloud storage buckets create gs://halatuju-replay-exams-0871147736 --location asia-southeast1 --default-storage-class STANDARD --uniform-bucket-level-access --public-access-prevention --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud storage buckets update gs://halatuju-replay-exams-0871147736 --default-event-based-hold --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

**If the name is already taken.** Bucket names are shared by everyone on Google Cloud. If the create
command reports a conflict (the name is not available), STOP: run nothing more here and ask the release
lead. Never run the job against a bucket that this step 4b did not make.

The replay's service account `halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com` gets
two roles ON THIS ONE BUCKET ONLY:

```
gcloud storage buckets add-iam-policy-binding gs://halatuju-replay-exams-0871147736 --member serviceAccount:halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --role roles/storage.objectCreator --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud storage buckets add-iam-policy-binding gs://halatuju-replay-exams-0871147736 --member serviceAccount:halatuju-replay@gen-lang-client-0871147736.iam.gserviceaccount.com --role roles/storage.objectViewer --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

- `roles/storage.objectCreator` lets the job add a NEW object. It cannot delete or replace one.
- `roles/storage.objectViewer` lets the job read an object and list the bucket. The list is needed: when
  an exam object is not found, the fetch makes one list call to tell "no exam yet" (the bucket answers)
  from "no such bucket" (it does not). Without the list right, every fetch on an empty bucket fails
  (exit 3).
- **The job must run as this dedicated replay service account** (step 4, `--service-account`), with
  these bucket-level roles only and NO project-level role. A wrong bucket name is harmless only under
  that condition. The code does not know the right name; it relies on the account's rights. Because the
  account has rights on this ONE bucket only, any other bucket name answers "no access" (or "not found"
  when no such bucket exists). The fetch then fails and the run stops (exit 3) before any replay child
  starts, so nothing is read from or written to that bucket. (A bucket that lets everyone read it would
  not refuse. Never type any bucket name but the one made here.)
- The bucket name is given to the job as a command-line argument (step 5), never as an environment
  variable. No environment variable and no secret is added to the job for the bucket.
- The bucket will hold application ids and decision times (the exam files). It stays private. It is
  removed in step 6.

## 4c. The proof-first run (before any real exam exists)

Nothing in LL6 has run against real Cloud Storage. Before any real exam exists, one sitting proves the
plumbing on the real, EMPTY bucket. Any object written for the proof is a DUMMY that holds no student
data.

This run is the first lens run on real data: it reads real cases. It has no freeze, so it freezes
nothing and uploads nothing.

- [ ] **FIRST: the job's image holds LL6.** An image built before LL6 does not know the bucket flag.
      (1) The release lead says LL6 is landed on main and live. (2) Build the image AGAIN from that
      commit: repeat step 3 with `<LIVE_MAIN_SHA>` = the live commit that holds LL6, the tag `r2` in
      place of `r1`, and a new, empty context folder (`../replay-ctx-r2` in place of every
      `../replay-ctx` in the block). (3) Point the job at the new image. Step 4 has only a create
      command, so use this line. It is not in the design plan: **check before use** (it uses the job,
      region and image path of steps 3 and 4, so if step 3 used another repository, use that one here
      too; it changes the image only):

      ```
      gcloud run jobs update halatuju-replay --image asia-southeast1-docker.pkg.dev/gen-lang-client-0871147736/cloud-run-source-deploy/halatuju-replay:r2 --region asia-southeast1 --account tamiliam@gmail.com --project gen-lang-client-0871147736
      ```

      How to recognise an image older than LL6: a lens run with the bucket flag stops at once with exit
      code 2 and an `unrecognized arguments:` line (that older image repeats what was typed, the bucket
      name included). Stop, do not retry, tell the release lead. (On an image that holds LL6, a typing
      slip in a flag gives `bad arguments (details withheld)`, exit code 2, instead: stop and tell the
      release lead too.)
- [ ] The owner's direct yes for this run, at the time.
- [ ] A time agreed with the release lead. Never on a release slot (11:00, 16:00 or 21:00 MYT). The
      hard rule of step 5 holds (no deploy, no migration while the job runs).
- [ ] Not on an R3 run day.
- [ ] The bucket is made (step 4b) and empty.
- [ ] A dummy object is never named `exam-1.json` or `exam-old.json`. A dummy under one of those names
      would be fetched by the next lens run, refused by the lens as an exam, and never replaced by the
      job; only the owner could remove it (release its hold, then delete).
- [ ] After the proof, the owner releases the hold on each dummy object and deletes it, so the bucket
      is empty again.

What the proof must show. Each item is something `exam_store.py` relies on; each is to be proven in this
run, not assumed:

1. **The token.** From the job, `metadata.google.internal` resolves and port 80 answers. A GET of the
   token path with the header `Metadata-Flavor: Google` returns a token. The code also requires the
   answer to carry the header `Metadata-Flavor: Google`.
2. **Storage is reachable.** `storage.googleapis.com:443` is reachable from the job with no VPC setting.
   The code resolves the name once, to one IPv4 address, connects to that address, and checks the
   certificate against the name `storage.googleapis.com` with the image's own CA bundle. The CA bundle in
   the slim image must verify it. (If it does not, the image needs `ca-certificates`: a
   `Dockerfile.replay` change, which goes to the release lead as a diff first.)
3. **The answers the fetch reads.** A missing object answers 404 to an account with objectViewer (the
   code reads only a 404 as "maybe no exam yet", and a 403 as a failure). A missing BUCKET answers 404
   to both the object GET and the list GET (the code needs the list GET to give anything but 200 there,
   so that a missing bucket fails, never reads as "no exam yet"). A bucket the account has no right on
   answers 403 (a failure).
4. **The empty list.** The list GET on the empty bucket (filtered to the one exam name) answers 200 with
   a JSON object (expected: an empty one, `{}`). The code accepts any JSON object here.
5. **The "never replace" lock.** An upload with `ifGenerationMatch=0` onto an existing dummy object is
   refused. Record WHICH status comes back. The code reads only 412 as "it exists" (it then compares the
   stored md5: the same = kept, another = `frozen_elsewhere`). Any other refusal, 403 for example, reads
   as a failed upload (`not_kept`, exit 4): still safe (nothing is replaced), but a lost race would then
   show `not_kept`, not `frozen_elsewhere`. Tell the release lead which status it was.
6. **The upload reply.** The upload reply carries `md5Hash` and `size`. `size` and `generation` are
   strings of digits; `md5Hash` is base64 (22 characters and `==`). The code reads `md5Hash` and `size`
   from the reply, or, when the reply lacks them, from one metadata GET; the fetch needs `generation` in
   that form.
7. **The hold.** The default event-based hold lands on an object the job's account uploads, with no extra
   permission. The code does not check this itself: it is the bucket's own lock.

How the run shows it, and what it cannot show:

- A lens run WITHOUT `--human-lens-freeze` on the empty bucket (the "lens run" command in step 5) covers
  items 1, 2, the missing-object half of 3, and 4, together. It passes when the job exits 0, both exams
  say "not run: exam_missing", and there is no `fatal` line. Nothing is frozen or uploaded on such a run.
  It is still a live run of the lens on production data.
- If any of those items fails, the job shows only exit 3 and a `fatal` line naming `ExamFetchFailed`.
  The job never prints an HTTP status, a token, the bucket name or a message, so it cannot say WHICH
  item failed.
- The missing-bucket and no-rights halves of item 3, and items 5, 6 and 7, cannot be seen in the job's
  fixed output, and no tool in this repository uploads a dummy object as the job's account (the store
  child uploads only an exam the lens itself froze and proved). The by-hand checks below cover part of
  them, with the limits written there. Nobody runs any other command against the bucket without the
  release lead's agreement and the owner's yes.
- Not in the seven, also not yet proven: the job's `/tmp` must allow hard links. Both the fetch (when an
  exam object exists) and the freeze write their file by hard link. A failure shows as exit 3 on a fetch,
  or as `folder_not_writable` on a freeze.

**By-hand checks with a dummy object.** These few commands look at the bucket itself, for what the job's
output cannot show. They upload ONE tiny dummy file that holds a fixed sentence and no data of any person.

- **Who types them.** The owner. The release lead may type them instead only if the owner says so in the
  yes for step 4c.
- **When.** AFTER the job run above has passed, so that run meets a truly empty bucket (the box above).
  The dummy, `ll6-proof/dummy-4c.txt`, can never be read as an exam: the job asks only for the objects
  `exam-1.json` and `exam-old.json`, and its one list call is filtered to names that begin with that one
  exam name (`list_path` in `exam_store.py`), so a name that begins `ll6-proof/` is never in its answer.
- **Shell.** Git Bash, as in step 3. Git Bash can rewrite an argument that looks like a path before
  gcloud sees it. A check on the station on 2026-11-25 (the same `gs://`, `--format=` and
  `--if-generation-match=0` arguments, handed to a Windows program) showed them arrive unchanged. If an
  error still names a strange path (for example one under `C:/Program Files/Git`), stop.
- **Flags.** Every gcloud line carries `--account`, `--project` and `--no-log-http` (no request or reply
  is written out, even if HTTP logging was left on). The flag and field names were checked against the
  installed gcloud on 2026-11-25. These commands have never been run, and the exact wording of each refusal
  is not known in advance: **check before use**.
- **STOP rule.** If any command gives a result other than the PASS written for it: stop, change nothing, run
  nothing more, and tell the release lead. Never delete the dummy to "retry".

1. Make the dummy file in a new, empty folder outside the repo (`mkdir` fails if the folder already
   exists: then stop and ask the release lead). PASS: no error.

   ```
   mkdir ~/ll6-proof-4c
   cd ~/ll6-proof-4c
   printf 'LL6 step 4c dummy object. No personal data.\n' > dummy-4c.txt
   ```

2. Upload it, create-only (this form can never replace anything). PASS: no `ERROR` line. It proves only
   that the owner's account can add a new object.

   ```
   gcloud storage cp dummy-4c.txt gs://halatuju-replay-exams-0871147736/ll6-proof/dummy-4c.txt --if-generation-match=0 --no-log-http --account tamiliam@gmail.com --project gen-lang-client-0871147736
   ```

3. Read its hold (only the name and the hold and retention fields, never a full dump). PASS: the answer
   holds `"event_based_hold": true`. Record the whole short answer. It proves item 7 for the bucket: the
   default hold lands on a new object. If that line is missing or `false`, stop: never run commands 4 and 5
   against an object without a hold.

   ```
   gcloud storage objects describe gs://halatuju-replay-exams-0871147736/ll6-proof/dummy-4c.txt --format="json(name,event_based_hold,temporary_hold,retention_expiration)" --no-log-http --account tamiliam@gmail.com --project gen-lang-client-0871147736
   ```

4. Try to replace it, create-only (the form the job uses). PASS: an `ERROR` line that names status 412,
   or a precondition that did not hold. Record that line exactly. It proves item 5 for the bucket: the
   create-only upload onto an existing object is refused with 412, the one answer the code reads as "it
   exists", even while the object is held. If the refusal names the hold or another status instead, stop
   and tell the release lead which.

   ```
   gcloud storage cp dummy-4c.txt gs://halatuju-replay-exams-0871147736/ll6-proof/dummy-4c.txt --if-generation-match=0 --no-log-http --account tamiliam@gmail.com --project gen-lang-client-0871147736
   ```

5. Try to replace it plainly (no create-only guard). PASS: an `ERROR` line that says the object is under
   a hold. Record that line exactly. It proves the hold itself: even the owner's account, which made the
   bucket, cannot replace a held object. This is a second, different refusal from command 4: command 4 is
   the create-only guard the code relies on (412); command 5 is the bucket's own lock behind it.

   ```
   gcloud storage cp dummy-4c.txt gs://halatuju-replay-exams-0871147736/ll6-proof/dummy-4c.txt --no-log-http --account tamiliam@gmail.com --project gen-lang-client-0871147736
   ```

Afterwards, leave the dummy in place. Removing it is the owner's own later step (the last box of the list
above): release its hold, then delete it, with the two one-object lines of step 6 and
`ll6-proof/dummy-4c.txt` in place of `exam-1.json`. The local folder `~/ll6-proof-4c` holds only the
dummy file and may be deleted.

What still stays unproven after the job run and these checks:

- **Items 5 and 7 for the JOB's account.** Commands 2 to 5 run as the owner's account (or the lead's use
  of it), so they prove the bucket's settings, not the rights of the job's service account. Whether the
  job's account gets 412 on an existing object is never seen in a normal run: only a lost race (two
  freeze runs at once) meets it. Any refusal but 412 reads as `not_kept` (exit 4): nothing is replaced.
  Whether the hold lands on an object the job's account uploads is not seen until a freeze run has kept
  an exam, and then only by reading that object's hold (command 3 with the exam's name in place of the
  dummy's: **check before use**).
- **Item 6, the upload reply.** These commands show no reply. It is first seen at the first freeze run. A
  reply in another shape gives `not_kept` (exit 4), or exit 3 on a later fetch; nothing is replaced.
- **The missing-bucket and no-rights halves of item 3.** The owner's account made this bucket and has
  rights on it, so these commands cannot show a missing bucket or a refused right. Both stop the run
  (exit 3) and never read as "no exam yet".
- For all three, the unit tests (`halatuju_api/apps/scholarship/tests/test_replay_exam_store.py`) check
  how the code reads these answers, with made-up replies. They do not show what Cloud Storage really
  sends.
- The `/tmp` hard links (above) are not touched by these checks.

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

**The lens runs (LL6: the exam home is the bucket).** First, the job's image must hold LL6 (step 4c,
first box). If a lens run stops at once with exit code 2 and an `unrecognized arguments:` line, the
image is older than LL6: stop, do not retry, tell the release lead. The first lens run is the
proof-first run (step 4c), after step 4b. Every other lens run, and every freeze run, comes only after
step 4c has passed, each on a fresh yes from the owner. The bucket name goes in as a job ARGUMENT,
`--human-lens-exam-bucket=<the bucket name>`, never as an environment variable. Type every flag name in
full (see `docs/replay-human-lens.md`, "Argument errors").

A lens run that only SCORES (no freeze; this is the normal lens run, and the run of step 4c):

```
gcloud run jobs execute halatuju-replay --region asia-southeast1 --wait --args "^@^--instant=<INSTANT>@--months=2026-11,2026-12@--human-lens@--human-lens-exam-bucket=halatuju-replay-exams-0871147736" --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

A FREEZE run (the same, plus `@--human-lens-freeze`):

```
gcloud run jobs execute halatuju-replay --region asia-southeast1 --wait --args "^@^--instant=<INSTANT>@--months=2026-11,2026-12@--human-lens@--human-lens-exam-bucket=halatuju-replay-exams-0871147736@--human-lens-freeze" --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

- **Freezing is an explicit choice, once per exam.** Only a run with `--human-lens-freeze` can freeze an
  exam and keep it in the bucket. A run without it never uploads anything.
- **What a freeze run does.** It first fetches both exams from the bucket into a private temp folder.
  An exam that is already in the bucket is loaded by the lens (scored, or refused if it is corrupt),
  never frozen again and never uploaded. An exam that is not in the bucket may be frozen in this run
  (if there are enough candidate cases); it is then kept in the bucket with a create-only upload
  (`ifGenerationMatch=0`), which asks Cloud Storage to refuse it when the object already exists.
- **Read the "exam home" line** after the lens block end line: "frozen and kept in the bucket" is the
  good answer. "NOT kept in the bucket. BLOCKING." exits 4: run a freeze run again. "was frozen by
  another run first" exits 0: the next run sits that exam. The full table is in
  `docs/replay-human-lens.md`.
- **If the fetch fails** (no token, no rights, no such bucket, a network error, a timeout, a stored
  object over 16 MiB, or a download whose size or md5 differs from what the bucket reports), the job
  exits 3 before any replay child starts. It never treats a failed fetch as "no exam yet", so it never
  freezes a second exam over a missing first one.
- Once an exam is kept, every later lens run, freeze or not, fetches and scores that same exam.

## 5b. Where the exam file lives in production (DECIDED: a bucket)

The human lens keeps its frozen exams in two files, `exam-1.json` and `exam-old.json`. They must
survive from one run to the next, or "frozen" means nothing. The job's work folder (`/tmp/replay`, the
default `--workdir`) is in memory on Cloud Run and is lost after each run, so it cannot be the home.

**The owner chose option B: a Cloud Storage bucket** (LL6). The station option and a mounted file share
were not chosen. The bucket and its access are step 4b. How it works (code in
`halatuju_api/apps/scholarship/eval/replay/exam_home.py` and `exam_store.py`):

- Each exam is one object in the bucket, `exam-1.json` and `exam-old.json`. The objects hold the plain
  application ids and one decision time per id, nothing else about a case.
- **At the start** of a run with `--human-lens-exam-bucket`, the replay makes a private temp folder
  inside its work folder and fetches both exams into it. Each exam is either fetched (the file is
  there) or "absent" (the bucket answered and holds no such object). Any other answer stops the run
  with exit 3 before any replay child starts.
- **The lens** then reads its exams from that temp folder, exactly as it reads an exam folder.
- **At the end**, and ONLY on a run with `--human-lens-freeze`, an exam that was absent at the start and
  was frozen in this run is kept in the bucket with one create-only upload (`ifGenerationMatch=0`).
  An exam that was fetched is never uploaded.
- **The temp folder is removed** at the end of every run.
- **The Cloud Storage work** is done by a separate small child process (`python -m replay.exam_store`),
  the only part that talks to Cloud Storage (the replay itself still talks to the database), started
  with only PATH, PYTHONPATH and LANG in its environment: no database url, no fingerprint key, no salt.
  It may reach only the metadata server (for the access token) and Cloud Storage.
- **What stops a second freeze from replacing the first:** a run that finds the exam in the bucket loads
  it and does not freeze it again; the upload is create-only; the service account has no right to delete
  or replace an object (objectCreator); and the bucket's default event-based hold holds every new object.
- **If an exam object is lost**, a normal run reports `exam_missing` and gives no score for that exam. Only
  a run with `--human-lens-freeze` makes a new one, and it may hold other cases than the lost one.

The proof-first run (step 4c) is the first lens run on real data. It has no freeze, so it freezes and
uploads nothing. It needs the bucket (step 4b) and the owner's yes, and is never on a release slot
(11:00, 16:00, 21:00 MYT) or an R3 run day. No other lens run, and no freeze run, happens until step 4c
has passed and the owner says yes again.

## 6. Afterwards: remove everything

**Retiring one exam (only when the owner decides an exam must go).** The job can never delete or
replace an exam, and the default hold keeps each object. So the owner RELEASES THE HOLD BY HAND first,
then deletes the object. These two lines are not in the design plan: **check before use** (they follow
the forms of the checked bucket-wide lines below, for one object):

```
gcloud storage objects update gs://halatuju-replay-exams-0871147736/exam-1.json --no-event-based-hold --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud storage rm gs://halatuju-replay-exams-0871147736/exam-1.json --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

(`exam-old.json` the same way.) After that, a normal lens run reports `exam_missing` for that exam, and
only a freeze run makes a new one, which may hold other cases. Soft delete keeps a copy of the deleted
object for 7 days.

**Removing the bucket.** First, the owner RELEASES THE HOLD BY HAND on every object; then deletes the
objects and the bucket (`rm --recursive` on the bucket also deletes the bucket itself). Soft delete keeps
a copy of each deleted object for 7 days (billed until it expires); a bucket restored from soft delete
comes back empty.

```
gcloud storage objects update "gs://halatuju-replay-exams-0871147736/*" --no-event-based-hold --account tamiliam@gmail.com --project gen-lang-client-0871147736
gcloud storage rm --recursive gs://halatuju-replay-exams-0871147736 --account tamiliam@gmail.com --project gen-lang-client-0871147736
```

Then the rest:

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
