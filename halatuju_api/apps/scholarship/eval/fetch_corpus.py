"""Fetch the real applicant-document corpus from Supabase into the local eval set, so the
owner can prune to genuine documents (of varying quality) and then score them offline FOR FREE.

READ-ONLY. Pulls, per document: the file bytes (private Storage bucket), the STORED Vision
read (vision_nric/name/address/fields — already computed by production, so scoring needs no
Gemini), and the linked applicant's name/NRIC/income route (the expected match context).

Writes into the eval set (all gitignored — real PII):
  fixtures/<doc_type>/<key>.<ext>   the image/PDF, for the owner to eyeball + prune
  snapshots/<key>.json              the stored read = the scorer's Layer-A input
  context.json                      per-doc expected name/NRIC/route/earner (+ app id, prod status)
  _manifest.csv                     key,doc_type,app_id,applicant,prod_status (reference)

key = "<doc_type>__a<app_id>__d<doc_id>" (unique, traceable, type-prefixed).

Env (read-only creds): DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
Usage: python fetch_corpus.py --types ic,parent_ic,results_slip,... [--limit-per-type N]
"""
import argparse, csv, json, os, urllib.parse, urllib.request, urllib.error
from collections import Counter

BUCKET = "b40-documents"
EXT = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "application/pdf": "pdf",
       "image/heic": "heic", "image/heif": "heif", "image/webp": "webp"}
SNAP_COLS = ["vision_nric", "vision_name", "vision_address", "vision_error", "vision_fields"]


def rest(base, key, table, select, params=None):
    """Read rows from PostgREST (service key bypasses RLS). Returns a list of dicts."""
    q = {"select": select, "limit": "5000", **(params or {})}
    url = f"{base}/rest/v1/{table}?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def download(base, key, path):
    req = urllib.request.Request(
        f"{base}/storage/v1/object/authenticated/{BUCKET}/{path}",
        method="GET", headers={"Authorization": f"Bearer {key}", "apikey": key})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read()


def ext_for(content_type, storage_path, filename):
    e = EXT.get((content_type or "").lower().split(";")[0].strip())
    if e:
        return e
    for src in (storage_path, filename):
        base = os.path.splitext(str(src or ""))[1].lstrip(".").lower()
        if base:
            return base
    return "bin"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", required=True, help="comma-separated doc_types")
    ap.add_argument("--limit-per-type", type=int, default=0)
    ap.add_argument("--metadata-only", action="store_true",
                    help="Refresh context.json + applicants.json only; skip the image download "
                         "+ snapshot writes (they already exist). Use to enrich without re-downloading.")
    ap.add_argument("--eval-dir", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    types = [t.strip() for t in args.types.split(",") if t.strip()]

    sb_base = os.environ["SUPABASE_URL"].rstrip("/")
    sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    snap_dir = os.path.join(args.eval_dir, "snapshots")
    fix_dir = os.path.join(args.eval_dir, "fixtures")
    os.makedirs(snap_dir, exist_ok=True)

    # Pull rows via PostgREST over the API host (the direct DB host is IPv6-only / not
    # reachable locally). Three READ-ONLY GETs, joined in Python.
    types_in = "(" + ",".join(types) + ")"
    docs = rest(sb_base, sb_key, "applicant_documents",
        "id,doc_type,storage_path,content_type,original_filename,household_member,"
        "vision_nric,vision_name,vision_address,vision_error,vision_run_at,vision_fields,application_id",
        {"doc_type": f"in.{types_in}"})
    apps = {a["id"]: a for a in rest(sb_base, sb_key, "scholarship_applications", "*")}
    profs = {p["supabase_user_id"]: p for p in rest(sb_base, sb_key, "api_student_profiles", "*")}
    rows = []
    for d in docs:
        if not (d.get("storage_path") or "").strip():
            continue
        a = apps.get(d["application_id"], {})
        p = profs.get(a.get("profile_id"), {})
        rows.append({
            "doc_id": d["id"], "doc_type": d["doc_type"], "storage_path": d["storage_path"],
            "content_type": d.get("content_type"), "original_filename": d.get("original_filename"),
            "household_member": d.get("household_member"),
            "vision_nric": d.get("vision_nric"), "vision_name": d.get("vision_name"),
            "vision_address": d.get("vision_address"), "vision_error": d.get("vision_error"),
            "vision_run_at": d.get("vision_run_at"), "vision_fields": d.get("vision_fields"),
            "app_id": d["application_id"], "income_route": a.get("income_route"),
            "income_earner": a.get("income_earner"), "prod_status": a.get("status"),
            "profile_name": p.get("name"), "profile_nric": p.get("nric"),
        })
    rows.sort(key=lambda r: (r["doc_type"], r["app_id"], r["doc_id"]))

    context, applicants, manifest = {}, {}, []
    if os.path.exists(os.path.join(args.eval_dir, "context.json")):
        context = json.load(open(os.path.join(args.eval_dir, "context.json"), encoding="utf-8"))
    per_type, ok, fail = Counter(), 0, 0
    for r in rows:
        dt = r["doc_type"]
        if args.limit_per_type and per_type[dt] >= args.limit_per_type:
            continue
        key = f"{dt}__a{r['app_id']}__d{r['doc_id']}"
        # context + manifest + the per-applicant declared record are built ALWAYS (cheap, no download).
        context[key] = {
            "profile_name": r["profile_name"] or "", "profile_nric": r["profile_nric"] or "",
            "income_route": r["income_route"] or "", "income_earner": r["income_earner"] or "",
            "household_member": r["household_member"] or "",
            "_doc_type": dt, "_app_id": r["app_id"], "_prod_status": r["prod_status"],
        }
        manifest.append([key, dt, r["app_id"], (r["profile_name"] or "")[:40], r["prod_status"]])
        aid = r["app_id"]
        if aid not in applicants:
            a = apps.get(aid, {})
            applicants[aid] = {"application": a, "profile": profs.get(a.get("profile_id"), {})}
        if not args.metadata_only:
            try:
                data = download(sb_base, sb_key, r["storage_path"])
            except (urllib.error.URLError, TimeoutError) as e:
                fail += 1
                print(f"  download FAILED {key}: {e}")
                continue
            ext = ext_for(r["content_type"], r["storage_path"], r["original_filename"])
            type_dir = os.path.join(fix_dir, dt)
            os.makedirs(type_dir, exist_ok=True)
            with open(os.path.join(type_dir, f"{key}.{ext}"), "wb") as f:
                f.write(data)
            snap = {c: r[c] for c in SNAP_COLS}
            snap["vision_run_at"] = r["vision_run_at"]   # already an ISO string from the API
            with open(os.path.join(snap_dir, f"{key}.json"), "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, default=str)
        per_type[dt] += 1
        ok += 1
    for fn, obj in (("context.json", context), ("applicants.json", applicants)):
        with open(os.path.join(args.eval_dir, fn), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
    with open(os.path.join(args.eval_dir, "_manifest.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["key", "doc_type", "app_id", "applicant", "prod_status"]); w.writerows(manifest)
    verb = "Indexed" if args.metadata_only else "Downloaded"
    print(f"\n{verb} {ok} documents ({fail} failed).")
    for t in types:
        print(f"  {t:22s} {per_type[t]}")
    print(f"context.json: {len(context)} · applicants.json: {len(applicants)} · _manifest.csv written.")


if __name__ == "__main__":
    main()
