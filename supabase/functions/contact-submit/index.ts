// Supabase Edge Function: contact-submit
//
// The public contact form posts here instead of inserting straight into the
// `contact_submissions` table. This function verifies a Cloudflare Turnstile
// token server-side (so bots can't spam the form) and only then writes the row,
// using the service role. After this is live, anon INSERT on contact_submissions
// is revoked so this function is the ONLY write path (a bot can't bypass it by
// inserting directly with the public anon key).
//
// Env (Supabase auto-injects SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY; set the
// rest as function secrets):
//   TURNSTILE_SECRET_KEY  — Cloudflare Turnstile secret (verify the token)
//
// Deploy:  supabase functions deploy contact-submit --no-verify-jwt
//   (--no-verify-jwt: the contact form is public, no Supabase login required.)

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const ALLOWED_ORIGINS = new Set([
  'https://halatuju.xyz',
  'https://www.halatuju.xyz',
  'http://localhost:3000',
])
const ALLOWED_CATEGORIES = new Set(['general', 'bug', 'data_deletion', 'feedback'])
const MAX = { name: 200, contact: 200, message: 5000 }

function corsHeaders(origin: string | null): Record<string, string> {
  const allow = origin && ALLOWED_ORIGINS.has(origin) ? origin : 'https://halatuju.xyz'
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
    'Vary': 'Origin',
  }
}

function json(body: unknown, status: number, origin: string | null): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
  })
}

async function verifyTurnstile(token: string, ip: string | null): Promise<boolean> {
  const secret = Deno.env.get('TURNSTILE_SECRET_KEY')
  if (!secret) {
    console.error('contact-submit: TURNSTILE_SECRET_KEY not configured')
    return false
  }
  try {
    const res = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secret, response: token, ...(ip ? { remoteip: ip } : {}) }),
    })
    const data = await res.json()
    return data?.success === true
  } catch (e) {
    console.error('contact-submit: siteverify failed', e)
    return false
  }
}

Deno.serve(async (req) => {
  const origin = req.headers.get('Origin')

  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(origin) })
  }
  if (req.method !== 'POST') {
    return json({ error: 'method_not_allowed' }, 405, origin)
  }

  let payload: Record<string, unknown>
  try {
    payload = await req.json()
  } catch {
    return json({ error: 'invalid_json' }, 400, origin)
  }

  const token = typeof payload.token === 'string' ? payload.token : ''
  if (!token) return json({ error: 'captcha_required' }, 400, origin)

  // Cloud Run / Cloudflare set the real client IP in these headers.
  const ip =
    req.headers.get('CF-Connecting-IP') ||
    req.headers.get('X-Forwarded-For')?.split(',')[0]?.trim() ||
    null

  if (!(await verifyTurnstile(token, ip))) {
    return json({ error: 'captcha_failed' }, 403, origin)
  }

  // Validate + normalise the submission.
  const name = String(payload.name ?? '').trim()
  const contact = String(payload.contact ?? '').trim()
  const message = String(payload.message ?? '').trim()
  const category = String(payload.category ?? 'general')

  if (!name || !contact || !message) {
    return json({ error: 'missing_fields' }, 400, origin)
  }
  if (name.length > MAX.name || contact.length > MAX.contact || message.length > MAX.message) {
    return json({ error: 'too_long' }, 400, origin)
  }
  const cat = ALLOWED_CATEGORIES.has(category) ? category : 'general'

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )
  const { error } = await supabase
    .from('contact_submissions')
    .insert({ name, contact, category: cat, message })

  if (error) {
    console.error('contact-submit: insert failed', error)
    return json({ error: 'insert_failed' }, 500, origin)
  }
  return json({ ok: true }, 200, origin)
})
