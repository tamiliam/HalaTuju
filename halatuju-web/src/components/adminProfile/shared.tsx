'use client'

import type { ReactNode } from 'react'
import type { AdminMe, ReviewerProfile } from '@/lib/admin-api'
import { formatMyMobile } from '@/lib/sponsorAuth'

/**
 * The common Profile page's shared pieces (common profile S1, 2026-10-31). The page
 * (`app/admin/profile/page.tsx`) owns the data and the ONE Save; each card under this folder is a
 * view of `ProfileState`, loaded as its own chunk, and writes only through `set` / `setRev`.
 *
 * ⚠ A SOURCE USER RENDERS THESE CARDS TOO. No card may call a staff endpoint: the page makes every
 * call, and `components/source/noStaffCalls.test.tsx` holds the source's page to its allowlist.
 */

/** A source's organisation fields — the editable half of `admin/source/profile/`. */
export interface SourceForm {
  source_name: string
  contact_person: string
  contact_email: string
  phone: string
}

/** The person's own card — what `PATCH admin/me/` writes (common profile S2). */
export interface MeCard {
  job_title: string
  about: string
  phone: string
  share_phone_with_team: boolean
  share_phone_with_students: boolean
}

/** Everything the page can save, as one value: compared with the last saved copy for "dirty".
 *  ⚠ The phone and "share with students" live in `card` ONLY (`admin/me/`), never in `reviewer`:
 *  one field, one writer. The reviewer save leaves both out. */
export interface ProfileDraft {
  name: string
  card: MeCard
  orgContact: string
  orgPhone: string
  reviewer: ReviewerProfile | null
  source: SourceForm | null
  /** A mentor's own area of mentoring (`admin/me/` `mentoring_area`, S7a); '' for everybody else. */
  mentoringArea: string
}

export type T = (k: string, vars?: Record<string, string>) => string

export interface ProfileState {
  t: T
  /** The admin session's token — for the one card that calls our API itself (Sign-in). */
  token: string | null
  me: AdminMe | null
  /** The effective role (`super` for a legacy super flag). */
  role: string | undefined
  isSuper: boolean
  permissions: readonly string[]
  email: string
  draft: ProfileDraft
  saved: ProfileDraft
  set: (patch: Partial<ProfileDraft>) => void
  setRev: (patch: Partial<ReviewerProfile>) => void
  setCard: (patch: Partial<MeCard>) => void
  /** Holds the `review` permission and is not a super (the reviewer cards' rule). */
  reviews: boolean
  /** A `review` holder or a mentor (S7a): the qualification / address cards and "share my phone
   *  with students" (`lib/profileCards.ts` `worksWithStudents`). */
  withStudents: boolean
  /** The photo now on the profile (a signed URL), and how a card changes it — straight away,
   *  not through Save (`admin/me/photo/`). */
  photoUrl: string | null
  onPhoto: (url: string | null) => void
  /** A card says one of its fields would be refused (Save sleeps while any is). */
  report: (key: string, bad: boolean) => void
  /** A referral partner's organisation name (from `admin/profile/`), or the source's organisation. */
  orgName: string | null
  /** The sign-in methods on the admin Supabase session (`app_metadata.providers`). */
  providers: readonly string[]
}

export type CardProps = { state: ProfileState }

export const CARD = 'bg-ground-0 rounded-xl p-6 shadow-sm border space-y-4'
export const inputCls = 'w-full px-3 py-2 border border-ground-300 rounded-lg focus:ring-2 focus:ring-info-500 focus:border-info-500'
export const labelCls = 'block text-sm text-ground-600 mb-1'
export const readOnlyCls = `${inputCls} bg-ground-50 text-ground-500`

/** The compulsory-field marker. */
export const Req = () => <span className="text-critical-600" aria-hidden> *</span>

export function CardFrame({ title, subtitle, icon, children, testId }: {
  title: string; subtitle?: string; icon?: string; children: ReactNode; testId: string
}) {
  return (
    <section className={CARD} data-testid={`profile-card-${testId}`} aria-label={title}>
      <h2 className="font-semibold flex items-center gap-2">
        {icon && <span aria-hidden>{icon}</span>}{title}
      </h2>
      {subtitle && <p className="text-sm text-ground-500 -mt-2 italic">{subtitle}</p>}
      {children}
    </section>
  )
}

/** Malaysian phone input: a fixed +60 prefix + a masked local part (12-345 6789). */
export function PhoneField({ id, value, onChange, required }: {
  id: string; value: string; onChange: (v: string) => void; required?: boolean
}) {
  return (
    <div className="flex items-stretch">
      <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-ground-300 bg-ground-50 text-sm text-ground-500">+60</span>
      <input
        id={id} type="tel" inputMode="numeric" autoComplete="tel-national" required={required}
        value={formatMyMobile(value)}
        onChange={(e) => onChange(formatMyMobile(e.target.value))}
        placeholder="12-345 6789"
        className="w-full px-3 py-2 border border-ground-300 rounded-r-lg focus:ring-2 focus:ring-info-500 focus:border-info-500"
      />
    </div>
  )
}
