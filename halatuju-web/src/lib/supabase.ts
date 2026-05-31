import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let _supabase: SupabaseClient | null = null

// Lazy-initialised browser client (avoids build-time env var errors)
export function getSupabase(): SupabaseClient {
  if (!_supabase) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    if (!url || !key) {
      throw new Error('Supabase credentials not configured')
    }
    // flowType: 'pkce' — OAuth returns a `?code=` that can only be exchanged with
    // the code-verifier stored under THIS client's storage key. The default
    // ('implicit') returns the session in the URL hash, which any mounted client
    // (this student client is mounted globally, incl. on /admin/* + /sponsor/*
    // callbacks) would happily read — leaking the admin/sponsor Google session into
    // the student session. PKCE closes that bleed.
    _supabase = createClient(url, key, { auth: { flowType: 'pkce' } })
  }
  return _supabase
}

// Auth helper functions
export async function signInWithPhone(_phone: string) {
  // Phone/OTP login is not yet implemented
  return {
    data: null,
    error: { message: 'Phone login is coming soon. Please use Google sign-in for now.' },
  }
}

export async function verifyOTP(phone: string, token: string) {
  const { data, error } = await getSupabase().auth.verifyOtp({
    phone,
    token,
    type: 'sms',
  })
  return { data, error }
}

export async function signInWithGoogle() {
  const { data, error } = await getSupabase().auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  })
  return { data, error }
}

export async function signOut() {
  const { error } = await getSupabase().auth.signOut()
  return { error }
}

export async function getSession() {
  const { data: { session }, error } = await getSupabase().auth.getSession()
  return { session, error }
}

export async function getUser() {
  const { data: { user }, error } = await getSupabase().auth.getUser()
  return { user, error }
}

export async function signInAnonymously() {
  const { data, error } = await getSupabase().auth.signInAnonymously()
  return { data, error }
}

export async function linkIdentity(provider: 'google') {
  const { data, error } = await getSupabase().auth.linkIdentity({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  })
  return { data, error }
}
