-- Audit A1.7 (TD-467 / SEC-18): give the private b40-documents bucket a type list and a size cap.
--
-- *** NOT APPLIED. *** This is the owner's live step. It was written in Sprint A1.7 and left for the
-- owner to run (Supabase SQL editor, or the MCP apply_migration), then read back with the SELECT at
-- the bottom. Nothing in this file has touched the live project.
--
-- WHY. The bucket has no limits of its own: a signed upload URL accepts any type and any size, and
-- the server only learns what was sent when the browser reports it at the record step. The record
-- step refuses a wrong type or an oversize file (unsupported_format / file_too_large), but the bytes
-- are already in the bucket by then. With these limits, Storage refuses them at the PUT.
--
-- LIVE READ-BACK, 2026-11-06 (read-only, project pbrrlyoyyiftckqvzvvo):
--   b40-documents: public = false, allowed_mime_types = NULL, file_size_limit = NULL.
--   Objects stored, by type (count, largest):
--     application/pdf           1694   42.9 MB  (p99 5.6 MB)
--     image/jpeg                1460    7.4 MB
--     image/png                  213   17.6 MB  (110 document keys + 103 request screenshots, <= 0.9 MB)
--     image/webp                   3   41 KB    (staff photos, written by the server)
--     application/octet-stream     2    0.5 MB
--   Every object over 8 MB (one 42.9 MB PDF, three 17.6 MB PNGs) and both octet-stream objects have
--   NO document row: the record step refused them and they were left behind as orphans.
--   Recorded rows: applicant_documents pdf 1701 (max 7.7 MB), jpeg 1466 (max 7.4 MB), png 105
--   (max 5.5 MB); org_request_attachments png 103 (max 0.8 MB). No HEIC row is left (converted).
--
-- WHAT IS ALLOWED, and why each type is on the list:
--   application/pdf, image/jpeg, image/png  - what students and staff actually upload.
--   image/heic, image/heif                  - iPhone photos, accepted then converted to JPEG.
--   image/gif, image/bmp, image/tiff        - accepted by the document door today (views.py
--                                             _ALLOWED_UPLOAD_EXTENSIONS); kept so nothing that
--                                             works now starts failing.
--   image/webp                              - accepted by both doors, and the server writes staff
--                                             photos as webp (the bucket limits apply to the
--                                             server's own uploads too).
--   image/jpg, image/avif,                  - the record step accepts any image/*; some Android apps send
--   image/heic-sequence, image/heif-sequence  the non-standard image/jpg, and phones can produce AVIF or HEIC
--                                             sequences. SVG is deliberately NOT allowed (script risk).
--   The server also writes pdf (bursary agreement, letters, split results) and jpeg (HEIC
--   conversion) into this bucket; both are on the list.
--
-- SIZE: 26214400 bytes = 25 MB, the highest cap an organisation can set (org_config_registry
-- max_doc_size_mb, max 25; default 8). Each organisation's own cap is still enforced at the record
-- step. Development-module files are capped lower (10 MB) in code. The project ceiling is 50 MB.
--
-- OWNER DECISION BEFORE APPLYING - application/octet-stream:
--   Some browsers send no type for a .heic file (seen on Windows and some Android Chrome); the web
--   client then PUTs it as application/octet-stream, and the record step accepts it by its file
--   name. Two such PUTs happened in October 2026 (neither was recorded). As written below,
--   octet-stream is NOT allowed, so such a file fails at the PUT and the student sees "upload
--   failed". To keep those uploads working, add 'application/octet-stream' to the list (it lets an
--   untyped file of any content through, up to the size cap).
--
-- ACCEPTANCE after applying: run the SELECT below and see the list and 26214400; then on a phone,
-- upload one photo and one PDF as a student, and one screenshot on a request.
--
-- Rollback (remove the limits again):
--   UPDATE storage.buckets SET allowed_mime_types = NULL, file_size_limit = NULL
--    WHERE id = 'b40-documents';

UPDATE storage.buckets
   SET allowed_mime_types = ARRAY[
         'application/pdf',
         'image/jpeg',
         'image/png',
         'image/webp',
         'image/heic',
         'image/heif',
         'image/gif',
         'image/bmp',
         'image/tiff',
         'image/jpg',
         'image/avif',
         'image/heic-sequence',
         'image/heif-sequence'
       ],
       file_size_limit = 26214400
 WHERE id = 'b40-documents';

-- Verify:
SELECT id, public, allowed_mime_types, file_size_limit
  FROM storage.buckets
 WHERE id = 'b40-documents';
