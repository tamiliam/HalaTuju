-- Security item 5 (leftover): stop anonymous enumeration of the public field-images bucket.
--
-- The `field-images` Storage bucket is public=true (category/pathway illustrations,
-- meant to be readable). But the single `storage.objects` policy "Public read field
-- images" granted SELECT to everyone, which ALSO permits the list API to enumerate
-- every object (all 55 filenames). The frontend never lists the bucket — it reads
-- each image by a known /storage/v1/object/public/field-images/<path> URL, which a
-- public bucket serves WITHOUT any RLS policy. So dropping this SELECT policy blocks
-- enumeration while leaving image display untouched.
--
-- Applied via Supabase MCP (migration: field_images_revoke_anon_list) on 2026-06-12.
-- Verified: public object read still 200; anon list now returns []. No new advisor warnings.
--
-- Rollback (re-open listing) if ever needed:
--   CREATE POLICY "Public read field images" ON storage.objects
--     FOR SELECT USING (bucket_id = 'field-images');

DROP POLICY IF EXISTS "Public read field images" ON storage.objects;
