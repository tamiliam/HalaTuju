/**
 * What `npm run mobile-check` measures, and where — the matrix and the settings in one place.
 *
 * Read by the Playwright config and the spec. Nothing here touches a browser.
 *
 *   MOBILE_BASE         the site to measure. Default http://localhost:3100, where the config starts
 *                       `next dev` with the design sandbox switched on. A remote base (for example
 *                       https://halatuju.xyz) measures the public pages only — the sandbox does not
 *                       exist in a production build.
 *   MOBILE_PUBLIC_BASE  optional: measure the PUBLIC pages from here instead — the "measure the live
 *                       site" mode (https://halatuju.xyz), for checking a deploy AFTER it lands. It
 *                       measures production, not this branch, so it can never stand in for the
 *                       default run before a push.
 *
 * ⚠ THE DEFAULT RUN MEASURES THIS BRANCH, WITH LIVE DATA. Locally the app calls its API at
 * `APP_API` (`.env.local`, normally localhost:8000), which is usually not running — and the live API
 * refuses a localhost origin (no CORS header). So the spec PROXIES: each GET/HEAD the page sends to
 * `APP_API/api/…` is fetched from `LIVE_API` by Playwright's own request client (not bound by CORS)
 * and handed back with an `access-control-allow-origin` for the page; preflights are answered too.
 * Writes are still aborted before they leave. The page is this branch's code over production's
 * read-only data — the same data the live site shows. If a proxied call fails, the spec refuses to
 * record the cell rather than measure a page drawn without its data.
 *   MOBILE_UPDATE=1     rewrite the baseline after the run (`npm run mobile-check -- --update`).
 *   MOBILE_ALLOW_WORSE=1  let that rewrite RAISE numbers. See run.mjs for why it exists.
 */
import * as fs from 'fs'
import * as path from 'path'
import { MOBILE_CLASS } from '../src/lib/mobileClass'

export const WEB_ROOT = path.resolve(__dirname, '..')
export const OUTPUT_DIR = path.join(__dirname, 'output')
export const RESULTS_DIR = path.join(OUTPUT_DIR, 'results')
export const SHOTS_DIR = path.join(OUTPUT_DIR, 'screenshots')
export const BASELINE_PATH = path.join(__dirname, 'baseline.json')

export const BASE = (process.env.MOBILE_BASE || 'http://localhost:3100').replace(/\/$/, '')
export const PUBLIC_BASE = (process.env.MOBILE_PUBLIC_BASE || BASE).replace(/\/$/, '')

export function isLocal(base: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(base)
}

/** The sandbox only exists on a local dev server started with NEXT_PUBLIC_SANDBOX=1. */
export const SANDBOX_ON = isLocal(BASE)

/** `NEXT_PUBLIC_API_URL` from an env file, or undefined. */
function envFileApi(file: string): string | undefined {
  const full = path.join(WEB_ROOT, file)
  if (!fs.existsSync(full)) return undefined
  const m = fs.readFileSync(full, 'utf8').match(/^NEXT_PUBLIC_API_URL=(.+)$/m)
  return m ? m[1].trim().replace(/\/$/, '') : undefined
}

/**
 * The API the LOCAL app calls: what `next dev` reads — the process env first, then `.env.local`,
 * then next.config.js's own default.
 */
export const APP_API = (process.env.NEXT_PUBLIC_API_URL || envFileApi('.env.local')
  || 'http://localhost:8000').replace(/\/$/, '')

/**
 * The live API: `.env.production`'s NEXT_PUBLIC_API_URL, which must equal the Dockerfile's
 * `ARG API_URL` default (what Cloud Build actually bakes in). Read, never typed here; if the two
 * disagree, the check stops rather than pick one.
 */
export function liveApi(): string {
  const env = envFileApi('.env.production')
  const docker = (fs.readFileSync(path.join(WEB_ROOT, 'Dockerfile'), 'utf8')
    .match(/^ARG API_URL=(\S+)$/m) ?? [])[1]?.replace(/\/$/, '')
  if (!env || !docker || env !== docker) {
    throw new Error(`mobile-check: cannot settle the live API — .env.production says ${env ?? 'nothing'}, `
      + `the Dockerfile's ARG API_URL says ${docker ?? 'nothing'}. They must exist and agree.`)
  }
  return env
}

/** Proxy the local app's API calls to the live API (see the header): only when pages are local. */
export const PROXY_API = isLocal(PUBLIC_BASE)

/**
 * 360 is the narrowest phone in the standard (small Android); 390 is today's iPhone. 375 and 430
 * are in the standard too; two widths keep a full run short, and 360 is the harder of the four.
 */
export const WIDTHS = [360, 390] as const
export const LOCALES = ['en', 'ms', 'ta'] as const
export type Locale = (typeof LOCALES)[number]

/** What `<html lang>` reads once each catalogue is committed (`src/components/HtmlLang.tsx`). */
export const EXPECTED_LANG: Record<Locale, string> = { en: 'en', ms: 'ms-MY', ta: 'ta' }

/** The localStorage key the app reads its language from (`src/lib/storage.ts` KEY_LOCALE). */
export const LOCALE_KEY = 'halatuju_locale'

export interface Target {
  /** The baseline key's first part: a route from mobileClass.ts, or `sandbox:<slug>`. */
  id: string
  url: string
  kind: 'public' | 'sandbox'
}

/** Every route with a `visit` URL in mobileClass.ts — the pages a stranger can open. */
export function publicTargets(): Target[] {
  return Object.entries(MOBILE_CLASS)
    .filter(([, e]) => e.visit)
    .map(([route, e]) => ({ id: route, url: `${PUBLIC_BASE}${e.visit}`, kind: 'public' as const }))
}

/**
 * The sandbox slugs, read from `src/sandbox/surfaces.tsx` itself so the list is never copied by
 * hand. That module mounts real React screens and cannot be imported into Node, so its source is
 * read instead: every `slug: '…'` at the indentation of a SURFACES entry. Two cross-checks keep
 * the reading honest — one `render:` per slug in the array, and (in the spec) the sandbox index
 * page linking exactly these slugs.
 */
export function sandboxSlugs(): string[] {
  const src = fs.readFileSync(path.join(WEB_ROOT, 'src', 'sandbox', 'surfaces.tsx'), 'utf8')
    .replace(/\r\n?/g, '\n')
  const start = src.indexOf('export const SURFACES')
  const end = src.indexOf('\n]\n', start)
  if (start === -1 || end === -1) throw new Error('mobile-check: SURFACES array not found in surfaces.tsx')
  const block = src.slice(start, end)
  const slugs = Array.from(block.matchAll(/^ {4}slug: '([^']+)'/gm), (m) => m[1])
  const renders = (block.match(/^ {4}render: /gm) ?? []).length
  if (slugs.length < 15 || slugs.length !== renders) {
    throw new Error(`mobile-check: read ${slugs.length} slugs and ${renders} renders from SURFACES; `
      + 'the reader no longer matches how surfaces.tsx is written — fix sandboxSlugs()')
  }
  return slugs
}

export function sandboxTargets(): Target[] {
  if (!SANDBOX_ON) return []
  return sandboxSlugs().map((slug) => ({ id: `sandbox:${slug}`, url: `${BASE}/sandbox/${slug}`, kind: 'sandbox' as const }))
}

export const cellKey = (id: string, width: number, locale: Locale) => `${id} @${width} ${locale}`

/** A cell key as a file name: no slashes, brackets or spaces; the home page reads as `home`. */
export const fileSafe = (key: string) => key.replace(/^\/ /, 'home ')
  .replace(/[^\w@.-]+/g, '_').replace(/^_+|_+$/g, '')

/** The three numbers the ratchet holds, per cell. */
export interface Numbers {
  overflow: number
  smallInputs: number
  smallTargets: number
}

export interface Baseline {
  _how_this_works?: string
  measured?: Record<string, string>
  cells: Record<string, Numbers>
}

export function readBaseline(): Baseline {
  if (!fs.existsSync(BASELINE_PATH)) return { cells: {} }
  return JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8')) as Baseline
}

/**
 * Overflow is a pixel count that can wobble by a pixel or two with font rendering, so growth
 * inside this slack is not "worse". Appearing where the baseline had none always is.
 */
export const OVERFLOW_SLACK_PX = 8

/** Why a cell is worse than its baseline, or [] if it is not. A cell with no baseline is held
 *  to zero sideways scroll and zero small fields; its tap targets are recorded, not judged. */
export function worseThan(now: Numbers, base: Numbers | undefined): string[] {
  const out: string[] = []
  if (!base) {
    if (now.overflow > 0) out.push(`new cell scrolls sideways by ${now.overflow}px (must be 0)`)
    if (now.smallInputs > 0) out.push(`new cell has ${now.smallInputs} text field(s) under 16px (must be 0)`)
    return out
  }
  if (base.overflow === 0 && now.overflow > 0) out.push(`now scrolls sideways by ${now.overflow}px (baseline 0)`)
  if (base.overflow > 0 && now.overflow > base.overflow + OVERFLOW_SLACK_PX) {
    out.push(`sideways scroll grew ${base.overflow}px → ${now.overflow}px`)
  }
  if (now.smallInputs > base.smallInputs) out.push(`small text fields ${base.smallInputs} → ${now.smallInputs}`)
  if (now.smallTargets > base.smallTargets) out.push(`small tap targets ${base.smallTargets} → ${now.smallTargets}`)
  return out
}
