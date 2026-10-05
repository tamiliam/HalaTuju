-- RESTORE SCRIPT — the eight student-write RLS policies removed on 2026-10-05.
--
-- Captured from production pg_policies immediately BEFORE they were dropped, so this recreates
-- them exactly. Run it ONLY if removing them turns out to break something.
--
-- Why they were removed: they let a signed-in student write their OWN row directly through
-- PostgREST, bypassing every rule Django enforces (the parent-phone signing freeze, NRIC
-- verification, income/benefit flags, verification flags). Found by the request #26 adversarial
-- review. The web app makes zero direct table calls and the only edge function writes
-- contact_submissions, so nothing legitimate used them. Owner approved removal 2026-10-05.

BEGIN;
CREATE POLICY "Users can delete own outcomes" ON public.admission_outcomes AS PERMISSIVE FOR DELETE TO public USING (((( SELECT auth.uid() AS uid))::text = (student_id)::text));
CREATE POLICY "Users can insert own outcomes" ON public.admission_outcomes AS PERMISSIVE FOR INSERT TO public WITH CHECK (((( SELECT auth.uid() AS uid))::text = (student_id)::text));
CREATE POLICY "Users can update own outcomes" ON public.admission_outcomes AS PERMISSIVE FOR UPDATE TO public USING (((( SELECT auth.uid() AS uid))::text = (student_id)::text));
CREATE POLICY "Users can insert own api profile" ON public.api_student_profiles AS PERMISSIVE FOR INSERT TO public WITH CHECK (((( SELECT auth.uid() AS uid))::text = (supabase_user_id)::text));
CREATE POLICY "Users can update own api profile" ON public.api_student_profiles AS PERMISSIVE FOR UPDATE TO public USING (((( SELECT auth.uid() AS uid))::text = (supabase_user_id)::text));
CREATE POLICY "Users can insert own reports" ON public.generated_reports AS PERMISSIVE FOR INSERT TO public WITH CHECK (((( SELECT auth.uid() AS uid))::text = (student_id)::text));
CREATE POLICY "Users can delete own saved courses" ON public.saved_courses AS PERMISSIVE FOR DELETE TO public USING (((( SELECT auth.uid() AS uid))::text = (student_id)::text));
CREATE POLICY "Users can insert own saved courses" ON public.saved_courses AS PERMISSIVE FOR INSERT TO public WITH CHECK (((( SELECT auth.uid() AS uid))::text = (student_id)::text));
COMMIT;
