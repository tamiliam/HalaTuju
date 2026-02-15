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
    _supabase = createClient(url, key)
  }
  return _supabase
}

// Auth helper functions
export async function signInWithPhone(phone: string) {
  const { data, error } = await getSupabase().auth.signInWithOtp({
    phone,
  })
  return { data, error }
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
