/**
 * An AUTH-ONLY Supabase client — TD-300 (2026-09-28).
 *
 * The web app uses exactly one part of Supabase: `.auth`. Every call site is `getX().auth.…`
 * (typecheck proves it: `AuthOnlyClient` has no `.from`, `.storage`, `.channel` or `.functions`).
 * But `createClient` from `@supabase/supabase-js` eagerly constructs ALL of Supabase in its
 * constructor — a Realtime client, a PostgREST client, a Storage client (with `iceberg-js`) and
 * the `buffer` polyfill two of them need — so none of it can tree-shake, and 73 of 87 routes
 * paid for it at first load: the Supabase chunk was 51.3 kB gzipped, and only the auth half is
 * ever called. This module builds the auth client the way `createClient` does and nothing else.
 *
 * ⚠ IT MIRRORS `SupabaseClient._initSupabaseAuthClient` (supabase-js 2.95.3) FIELD FOR FIELD —
 * the same URL, the same headers in the same order, the same DEFAULT storage key
 * (`sb-<project ref>-auth-token`, which is where every signed-in STUDENT's session already lives:
 * a different key would sign every student out), and the same option object including the keys
 * supabase-js passes as `undefined` (GoTrueClient merges with `Object.assign`, so an explicit
 * `undefined` and an absent key are not the same thing). `supabaseAuthClient.test.ts` pins every
 * one of those against the real `createClient`, and pins `SUPABASE_JS_VERSION` against the
 * installed package, so a Supabase upgrade that changes any of it turns jest red — it does not
 * silently drift.
 * drift-test: halatuju-web/src/lib/__tests__/supabaseAuthClient.test.ts
 *
 * The one thing left out on purpose: supabase-js also subscribes to its own auth client to hand
 * the access token to Realtime. That subscriber only ever touches Realtime, which this app never
 * opens, so dropping it changes nothing a user or the API can see.
 *
 * ⚠ DO NOT IMPORT A VALUE FROM `@supabase/supabase-js` ANYWHERE IN src/. One `createClient`
 * brings the whole 51 kB chunk back to every route; the same test file refuses it (`import type`
 * is free and stays allowed).
 */
import { AuthClient } from '@supabase/auth-js'

/** The supabase-js release whose `createClient` this mirrors; it goes into `X-Client-Info`
 *  exactly as supabase-js sends it.
 *  drift-test: halatuju-web/src/lib/__tests__/supabaseAuthClient.test.ts */
export const SUPABASE_JS_VERSION = '2.95.3'

/** supabase-js computes this once, at module load, from the same four checks. */
function jsEnv(): string {
  if (typeof (globalThis as { Deno?: unknown }).Deno !== 'undefined') return 'deno'
  if (typeof document !== 'undefined') return 'web'
  if (typeof navigator !== 'undefined' && navigator.product === 'ReactNative') return 'react-native'
  return 'node'
}
const JS_ENV = jsEnv()

/** The only options this app passes to `createClient` — see the three `get…Supabase()`. */
export interface AuthOnlyOptions {
  storageKey?: string
  flowType: 'pkce'
}

/** The shape every caller relies on: a Supabase client that has only `.auth`. */
export interface AuthOnlyClient {
  auth: InstanceType<typeof AuthClient>
}

/** `createClient(url, key, { auth: options })`, minus everything that is not `.auth`. */
export function createAuthOnlyClient(
  supabaseUrl: string,
  supabaseKey: string,
  options: AuthOnlyOptions,
): AuthOnlyClient {
  // validateSupabaseUrl + ensureTrailingSlash, same messages.
  const trimmed = supabaseUrl?.trim()
  if (!trimmed) throw new Error('supabaseUrl is required.')
  if (!trimmed.match(/^https?:\/\//i)) {
    throw new Error('Invalid supabaseUrl: Must be a valid HTTP or HTTPS URL.')
  }
  let baseUrl: URL
  try {
    baseUrl = new URL(trimmed.endsWith('/') ? trimmed : trimmed + '/')
  } catch {
    throw Error('Invalid supabaseUrl: Provided URL is malformed.')
  }
  if (!supabaseKey) throw new Error('supabaseKey is required.')

  // DEFAULT_AUTH_OPTIONS + the default storage key, overlaid by ours. (supabase-js's default
  // flowType is 'implicit'; every client here passes 'pkce', so the type requires it.)
  const settings = {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    storageKey: `sb-${baseUrl.hostname.split('.')[0]}-auth-token`,
    ...options,
  }
  const headers = { 'X-Client-Info': `supabase-js-${JS_ENV}/${SUPABASE_JS_VERSION}` }
  const auth = new AuthClient({
    url: new URL('auth/v1', baseUrl).href,
    headers: { Authorization: `Bearer ${supabaseKey}`, apikey: `${supabaseKey}`, ...headers },
    storageKey: settings.storageKey,
    autoRefreshToken: settings.autoRefreshToken,
    persistSession: settings.persistSession,
    detectSessionInUrl: settings.detectSessionInUrl,
    storage: undefined,
    userStorage: undefined,
    flowType: settings.flowType,
    lock: undefined,
    debug: undefined,
    throwOnError: undefined,
    fetch: undefined,
    hasCustomAuthorizationHeader: false,
  })
  return { auth }
}
