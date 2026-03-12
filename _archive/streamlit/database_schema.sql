-- Database Schema for HalaTuju (Supabase / PostgreSQL)

-- Table: student_profiles
-- This table stores all user data, including authentication credentials (hashed PIN),
-- academic grades, and psychometric signals.

CREATE TABLE IF NOT EXISTS public.student_profiles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    
    -- Identity & Auth
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    pin_hash TEXT NOT NULL, -- Bcrypt hash of 6-digit PIN
    email TEXT, -- Optional
    
    -- Activity Tracking
    last_login TIMESTAMP WITH TIME ZONE,
    
    -- Academic Data
    -- Stores grades as JSON: {"math": "A", "bm": "A+", ...}
    grades JSONB DEFAULT '{}'::jsonb,
    
    -- Biographic & Health Flags
    gender TEXT, -- 'Male', 'Female' (or localized strings)
    colorblind TEXT, -- 'Ya'/'Tidak'
    disability TEXT, -- 'Ya'/'Tidak'
    
    -- Psychometric Data
    -- Stores quiz results: {"work_preference_signals": {...}, ...}
    student_signals JSONB DEFAULT '{}'::jsonb
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_student_profiles_phone ON public.student_profiles(phone);

-- RLS Policies (Row Level Security) - Optional Template
-- ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Enable read for users based on phone" ON public.student_profiles FOR SELECT USING (true); 
-- (Note: Actual RLS implementation depends on your specific Supabase Auth setup. 
-- Since this app handles its own PIN auth, standard RLS based on auth.uid() might not apply directly 
-- unless integrated with Supabase Auth users).
