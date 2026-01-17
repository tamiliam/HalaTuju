-- 1. Enable pgcrypto for UUIDs (if not already)
create extension if not exists "pgcrypto";

-- 2. Update student_profiles table
-- checks if table exists, if so alters it, or creates it if fresh

create table if not exists student_profiles (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now())
);

-- Add/Ensure columns exist
alter table student_profiles 
  add column if not exists phone text unique,
  add column if not exists pin_hash text,
  add column if not exists full_name text,
  add column if not exists email text,
  add column if not exists grades jsonb,
  add column if not exists last_login timestamp with time zone;

-- 3. Add Index for fast lookup by phone
create index if not exists idx_student_phone on student_profiles(phone);
