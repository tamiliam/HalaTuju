import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let _adminSupabase: SupabaseClient | null = null

/**
 * Separate Supabase client for admin auth.
 * Uses a different storage key so admin and student sessions don't conflict.
 */
export function getAdminSupabase(): SupabaseClient {
  if (!_adminSupabase) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    if (!url || !key) {
      throw new Error('Supabase credentials not configured')
    }
    _adminSupabase = createClient(url, key, {
      auth: {
        storageKey: 'halatuju_admin_session',
      },
    })
  }
  return _adminSupabase
}

export async function adminSignInWithPassword(email: string, password: string) {
  const { data, error } = await getAdminSupabase().auth.signInWithPassword({
    email,
    password,
  })
  return { data, error }
}

export async function adminSignInWithGoogle() {
  const { data, error } = await getAdminSupabase().auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/admin/auth/callback`,
    },
  })
  return { data, error }
}

export async function adminResetPassword(email: string) {
  const { error } = await getAdminSupabase().auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/admin/login`,
  })
  return { error }
}

export async function adminSignOut() {
  const { error } = await getAdminSupabase().auth.signOut()
  return { error }
}

export async function getAdminSession() {
  const { data: { session }, error } = await getAdminSupabase().auth.getSession()
  return { session, error }
}
