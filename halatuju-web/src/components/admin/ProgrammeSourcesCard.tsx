'use client'

// "Who referred you?" — which referral sources THIS gift's apply form lists (per-gift referral
// sources, Sprint 1, 2026-10-08). Design of record: the owner-approved mock-up, with the site's
// Toggle rather than tick boxes ("toggles not tick boxes"). It sits under the Questions card on
// Programme → Configuration and shares that tab's SaveBar: the switches only move a DRAFT, and
// Save / Discard / the pending count in the bar include them. Since Sprint 2 (same day) these
// switches ARE the student's "Who referred you?" list on this gift's apply form.
//
// ⚠ ONLY ACTIVE SOURCES ARE OFFERED — switched on in Sources and never a tenant; the server
// decides that list. A source newly switched on there joins NO gift, and a new gift starts with
// none on, so "nothing on" is a real, ordinary state and says so in words.
//
// THE FIXED CHOICES (request #44, 2026-10-25 — the owner reversed "not toggles" for two of them):
// Halatuju.xyz and Facebook / WhatsApp each get a switch here, in the SAME draft and SaveBar; Other
// is always on and says so. Every gift starts with both on. An older api that sends no
// `fixed_sources` gets the old read-only footer, so a web-first deploy shows nothing it cannot save.
//
// ⚠ NOT ACCESS CONTROL — a dropdown's contents. The endpoint is org-fenced; nothing here is.

import Link from 'next/link'
import { Toggle } from '@/components/sources/shared'
import type { ProgrammeConfigFixedSource, ProgrammeConfigSource } from '@/lib/admin-api'
import type { SourceDraft } from '@/lib/programmeConfig'
// The three choices every form carries, in the apply form's own words — the ONE web list.
import { FIXED_REFERRAL_CODES as ALWAYS_ON } from '@/lib/referralSources'

export default function ProgrammeSourcesCard({ sources, fixed, draft, onToggle, t }: {
  sources: ProgrammeConfigSource[]
  /** The three fixed choices as the server holds them for this gift; absent from an older api. */
  fixed?: ProgrammeConfigFixedSource[]
  draft: SourceDraft
  onToggle: (code: string) => void
  t: (k: string, vars?: Record<string, string>) => string
}) {
  const isOn = (s: ProgrammeConfigSource) => draft[s.code] ?? s.on
  const n = sources.filter(isOn).length
  const label = (code: string) => t(`scholarship.apply.org.${code}`)
  return (
    <section className="mt-6 rounded-2xl border border-ground-200 bg-ground-0 shadow-sm"
      aria-labelledby="section-sources" data-testid="sources-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ground-100 px-5 py-4">
        <div className="min-w-0">
          <h2 id="section-sources" className="text-lg font-semibold text-ground-900">
            {t('scholarship.apply.field.org')}
          </h2>
          <p className="text-sm text-ground-500">{t('admin.programme.config.sourcesHint')}</p>
        </div>
        <span className="whitespace-nowrap text-sm text-ground-500" data-testid="sources-count">
          {t('admin.programme.config.sourcesCount', { n: String(n), m: String(sources.length) })}
        </span>
      </div>

      {n === 0 && (
        <p className="border-b border-ground-100 px-5 py-3 text-sm text-ground-600" data-testid="sources-none">
          {t('admin.programme.config.sourcesNone')}
        </p>
      )}

      <ul className="divide-y divide-ground-100">
        {sources.map((s) => (
          <li key={s.code} className="flex items-center justify-between gap-4 px-5 py-3"
            data-testid={`source-${s.code}`}>
            <div className="min-w-0">
              <span className="block font-medium text-ground-900">{s.name}</span>
              <span className="block text-xs text-ground-400">{s.code}</span>
            </div>
            <Toggle on={isOn(s)} onClick={() => onToggle(s.code)} label={s.name} />
          </li>
        ))}
      </ul>

      {fixed && fixed.length > 0 && (
        <div className="border-t border-ground-100" data-testid="sources-fixed">
          <div className="px-5 pt-3">
            <h3 className="text-sm font-semibold text-ground-900">{t('admin.programme.config.sourcesFixedTitle')}</h3>
            <p className="text-xs text-ground-500">
              {t('admin.programme.config.sourcesFixedHint', { other: label('other') })}
            </p>
          </div>
          <ul className="divide-y divide-ground-100">
            {fixed.map((f) => (
              <li key={f.code} className="flex items-center justify-between gap-4 px-5 py-3"
                data-testid={`fixed-${f.code}`}>
                <span className="font-medium text-ground-900">{label(f.code)}</span>
                {f.switchable
                  ? <Toggle on={draft[f.code] ?? f.on} onClick={() => onToggle(f.code)} label={label(f.code)} />
                  : <span className="text-sm text-ground-500">{t('admin.programme.config.sourcesAlwaysOn')}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-1 rounded-b-2xl border-t border-ground-100 bg-ground-50 px-5 py-3 text-sm text-ground-600">
        {!fixed?.length && (
          <p data-testid="sources-always">
            {t('admin.programme.config.sourcesAlways')}{' '}
            <span className="font-medium text-ground-900">{ALWAYS_ON.map(label).join(' · ')}</span>
          </p>
        )}
        <Link href="/admin/sources" className="text-info-700 underline hover:no-underline">
          {t('admin.programme.config.sourcesLink')}
        </Link>
      </div>
    </section>
  )
}
