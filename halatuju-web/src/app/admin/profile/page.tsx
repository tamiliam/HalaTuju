'use client'

import '@/lib/messagesScholarship'   // TD-416: the university picker's scholarship.* words (their own slice)
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getAdminMe, getAdminProfile, updateAdminMe, updateAdminProfile, getReviewerProfile, updateReviewerProfile,
  getSourceProfile, updateSourceProfile,
  type AdminMe, type AdminMeCard, type ReviewerProfile, type SourceProfile,
} from '@/lib/admin-api'
import { blankReviewer, missingReviewerFields, reviewerProfileComplete } from '@/lib/reviewerProfile'
import { cardsFor, profileContext, reviewsCases, type ProfileCardId } from '@/lib/profileCards'
import { refusalKey } from '@/lib/sourceConsole'
import { useT } from '@/lib/i18n'
import { lazySource } from '@/components/source/LazySource'
import type { CardProps, MeCard, ProfileDraft, ProfileState, SourceForm } from '@/components/adminProfile/shared'
import type { ComponentType } from 'react'

// ⚠ THE CARDS ARE LAZY, IN ONE CHUNK (common profile S1, 2026-10-31): `adminProfile/cards`, one
// LITERAL specifier, so the bundler emits ONE chunk however many loaders name it (`lazySource`, the
// house pattern — see its docstring). The route used to import the university list and its picker
// statically for everybody; now they are off its first load. ⚠ NOT ONE CHUNK PER CARD, and not a
// second chunk for the heavy card: each chunk is an entry in the webpack runtime EVERY route
// downloads — eight put the median 0.127 kB under its line, two still cost 0.04 kB (see `cards.tsx`).
const loadCards = () => import('@/components/adminProfile/cards')
const CARDS: Record<ProfileCardId, ComponentType<CardProps>> = {
  you: lazySource(() => loadCards().then((m) => m.YouCard)),
  contact: lazySource(() => loadCards().then((m) => m.ContactCard)),
  access: lazySource(() => loadCards().then((m) => m.AccessCard)),
  qualifications: lazySource(() => loadCards().then((m) => m.QualificationsCard)),
  address: lazySource(() => loadCards().then((m) => m.AddressCard)),
  takingPart: lazySource(() => loadCards().then((m) => m.TakingPartCard)),
  organisation: lazySource(() => loadCards().then((m) => m.OrganisationCard)),
  signin: lazySource(() => loadCards().then((m) => m.SignInCard)),
}

const sourceFormOf = (d: SourceProfile): SourceForm => ({
  source_name: d.source.name, contact_person: d.source.contact_person,
  contact_email: d.source.contact_email, phone: d.source.phone,
})

const CARD_KEYS = ['job_title', 'about', 'phone', 'share_phone_with_team', 'share_phone_with_students'] as const
const cardOf = (m: AdminMe): MeCard => ({
  job_title: m.job_title ?? '', about: m.about ?? '', phone: m.phone ?? '',
  share_phone_with_team: !!m.share_phone_with_team, share_phone_with_students: m.share_phone_with_students ?? true,
})
/** The reviewer profile as the onboarding rule reads it: its phone is the card's (`admin/me/`). */
const withPhone = (r: ReviewerProfile | null, phone: string): ReviewerProfile =>
  ({ ...(r ?? blankReviewer()), phone })

/** An `admin/me/` refusal, in the reader's words (`views_admin/me.py`). */
const ME_REFUSALS = ['name_required', 'name_too_long', 'phone_required', 'phone_too_long',
  'job_title_too_long', 'about_too_long', 'not_editable']

/**
 * THE PROFILE PAGE — ONE shell for every admin-platform person, a source user included (common
 * profile S1, owner ruling 2026-10-31; roadmap docs/plans/2026-10-31-common-profile-roadmap.md).
 *
 * It renders exactly `cardsFor(...)` (`lib/profileCards.ts`, the ONE list with ONE rule per card)
 * and owns the data and the ONE Save, which writes every changed part to its own endpoint:
 *   the name and the person's card (job title, About, phone, who sees the phone) — `admin/me/`
 *   PATCH, for every role (common profile S2); a partner's organisation contact — `admin/profile/`
 *   PUT; a source's organisation — `admin/source/profile/` PATCH; the reviewer cards (qualifications,
 *   languages, address, pause) — `admin/reviewer-profile/` PATCH, WITHOUT the phone, which is the
 *   card's. The photo and a password change are their own actions (`admin/me/photo/`,
 *   `admin/me/password/`), not part of Save.
 *
 * ⚠ A SOURCE USER IS REFUSED EVERY STAFF ENDPOINT (deny by default), so its page calls only
 * `admin/me/` GET/PATCH, `admin/me/photo/`, `admin/me/password/` and `admin/source/profile/`
 * GET/PATCH — `components/source/noStaffCalls.test.tsx` holds it to that.
 *
 * ⚠ THE FIRST-SIGN-IN HOLD STAYS REVIEWER-ROLE ONLY. A Reviewer whose compulsory fields are missing
 * is held here (the layout guard) and sent on to Applications by the save that completes them; a
 * holder of `review` in any other role sees a reminder, never a block.
 */
export default function AdminProfilePage() {
  const { token, role, session, refreshRole, setPhotoUrl: setHeaderPhoto } = useAdminAuth()
  const router = useRouter()
  const { t, locale } = useT()
  const ctx = profileContext(role)
  const cards = cardsFor(ctx)
  const isSource = ctx.role === 'source_partner'
  const isPartner = ctx.role === 'partner'
  const reviews = reviewsCases(ctx)
  const isReviewerRole = ctx.role === 'reviewer'

  const [me, setMe] = useState<AdminMe | null>(null)
  const [photoUrl, setPhotoUrl] = useState<string | null>(null)
  const [orgName, setOrgName] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [draft, setDraft] = useState<ProfileDraft | null>(null)
  // The last SAVED copy, kept beside the working one so "is there anything to save?" has something
  // to compare against (request #6), and refreshed on every save.
  const [saved, setSaved] = useState<ProfileDraft | null>(null)
  const [failed, setFailed] = useState(false)
  const [invalid, setInvalid] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  // A refusal takes the focus (source review L10): it sits beside Save, and a keyboard or
  // screen-reader user must land on it rather than wonder why nothing happened.
  const messageRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (message && !message.ok) messageRef.current?.focus() }, [message])

  // Own account (Your access, Sign-in) — fetched with the drafts below, and refetched ONLY when the
  // reader changes language (the gift names), never touching the drafts.
  const localeRef = useRef(locale)
  localeRef.current = locale
  const meLocale = useRef<string | null>(null)
  useEffect(() => {
    if (!token || meLocale.current === null || meLocale.current === locale) return
    meLocale.current = locale
    getAdminMe(locale, { token }).then(setMe).catch(() => {})
  }, [token, locale])

  // Waits for the role: which endpoints may be called depends on it (a source user's would refuse).
  const known = !!role
  useEffect(() => {
    if (!token || !known) return
    let live = true
    const lang = localeRef.current
    Promise.all([
      getAdminMe(lang, { token }),
      isSource ? getSourceProfile({ token }) : Promise.resolve(null),
      isPartner ? getAdminProfile({ token }) : Promise.resolve(null),
      reviews ? getReviewerProfile({ token }).catch(() => null) : Promise.resolve(null),
    ]).then(([m, src, prof, rev]) => {
      if (!live) return
      const base: ProfileDraft = {
        name: m.name, card: cardOf(m),
        orgContact: prof?.org_contact_person || '', orgPhone: prof?.org_phone || '',
        reviewer: rev, source: src ? sourceFormOf(src) : null,
      }
      meLocale.current = lang
      setMe(m); setPhotoUrl(m.photo_url); setEmail(m.email)
      setOrgName(prof?.org_name ?? (src?.source.organisation || null))
      setDraft(base); setSaved(base)
    }).catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [token, known, isSource, isPartner, reviews])

  const set = useCallback((patch: Partial<ProfileDraft>) =>
    setDraft((prev) => (prev ? { ...prev, ...patch } : prev)), [])
  const setRev = useCallback((patch: Partial<ReviewerProfile>) =>
    setDraft((prev) => (prev ? { ...prev, reviewer: { ...(prev.reviewer ?? blankReviewer()), ...patch } } : prev)), [])
  const setCard = useCallback((patch: Partial<MeCard>) =>
    setDraft((prev) => (prev ? { ...prev, card: { ...prev.card, ...patch } } : prev)), [])
  const onPhoto = useCallback((url: string | null) => {
    setPhotoUrl(url)
    setHeaderPhoto?.(url)                 // the header's avatar follows at once
  }, [setHeaderPhoto])
  const report = useCallback((key: string, bad: boolean) =>
    setInvalid((prev) => (!!prev[key] === bad ? prev : { ...prev, [key]: bad })), [])

  if (!draft || !saved) {
    return <p className="mt-8 text-center text-ground-500">{t(failed ? 'admin.myProfile.loadError' : 'common.loading')}</p>
  }

  // Request #6, applied across the console: a Save that would write nothing stays inactive.
  // ⚠ The dangerous direction is the OPPOSITE of the reported one — a button wrongly disabled
  // strands real work with no way to keep it — so every field this page can write is compared,
  // the reviewer cards and a source's organisation included, and the baseline is refreshed on save.
  const nameDirty = draft.name !== saved.name
  const cardChanges: AdminMeCard = {}
  for (const k of CARD_KEYS) {
    if (k === 'share_phone_with_students' && !reviews) continue
    if (draft.card[k] !== saved.card[k]) (cardChanges as Record<string, unknown>)[k] = draft.card[k]
  }
  const cardDirty = Object.keys(cardChanges).length > 0
  const orgDirty = isPartner && (draft.orgContact !== saved.orgContact || draft.orgPhone !== saved.orgPhone)
  const revDirty = reviews && JSON.stringify(draft.reviewer) !== JSON.stringify(saved.reviewer)
  const srcDirty = isSource && JSON.stringify(draft.source) !== JSON.stringify(saved.source)
  const dirty = nameDirty || cardDirty || orgDirty || revDirty || srcDirty
  const blocked = Object.values(invalid).some(Boolean)

  // Onboarding: a Reviewer whose backend flag is false is held here until the compulsory fields are
  // filled. `missing` is a live client mirror (updates as they type) that drives the banner.
  const gated = isReviewerRole && role?.reviewer_profile_complete === false
  const missing = reviews ? missingReviewerFields(draft.name, withPhone(draft.reviewer, draft.card.phone)) : []
  const remind = reviews && !isReviewerRole && missing.length > 0
  const MISSING_LABEL: Record<string, string> = {
    name: t('admin.name'),
    highest_qualification: t('admin.reviewer.highestQualification'),
    university: t('admin.reviewer.university'),
    graduation_year: t('admin.reviewer.graduationYear'),
    field_of_study: t('admin.reviewer.fieldOfStudy'),
    languages: t('admin.reviewer.onboarding.languages'),
    phone: t('admin.reviewer.phone'),
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !dirty || blocked) return
    setSaving(true); setMessage(null)
    // Which endpoint refused, so the message is that endpoint's words.
    let step: 'me' | 'source' | 'other' = 'me'
    try {
      let next: ProfileDraft = draft
      if (nameDirty || cardDirty) {
        const m = await updateAdminMe({ ...(nameDirty ? { name: draft.name.trim() } : {}), ...cardChanges }, { token })
        setMe(m)
        next = { ...next, name: m.name, card: cardOf(m) }
      }
      step = 'source'
      if (isSource && srcDirty && draft.source) {
        const s = draft.source
        // The organisation only: the source's own name goes through `admin/me/` since S2.
        const d = await updateSourceProfile({
          source: { name: s.source_name.trim(), contact_person: s.contact_person.trim(),
                    contact_email: s.contact_email.trim(), phone: s.phone.trim() },
        }, { token })
        next = { ...next, source: sourceFormOf(d) }
      }
      step = 'other'
      if (orgDirty && orgName) {
        await updateAdminProfile({ org_contact_person: draft.orgContact, org_phone: draft.orgPhone }, { token })
      }
      if (revDirty && draft.reviewer) {
        // ⚠ Without the phone and "share with students": they are the card's, saved above.
        const { phone: _p, share_phone_with_students: _s, ...rest } = draft.reviewer
        void _p; void _s
        await updateReviewerProfile(rest, { token })
      }
      setDraft(next); setSaved(next)
      setMessage({ ok: true, text: t('admin.profileUpdated') })
      // Onboarding: this save completed a held Reviewer's profile — refresh the role flag and send
      // them on to their workspace (the layout guard releases once the flag flips).
      if (gated && reviewerProfileComplete(next.name, withPhone(next.reviewer, next.card.phone))) {
        await refreshRole()
        router.push('/admin/scholarship')
        return
      }
      // The header shows the person's name (and a source's "<source> · Source").
      if (nameDirty || (isSource && next.source?.source_name !== saved.source?.source_name)) void refreshRole()
    } catch (err) {
      const code = (err as { code?: string })?.code ?? ''
      setMessage({ ok: false, text: step === 'me' && ME_REFUSALS.includes(code) ? t(`admin.myProfile.error.${code}`)
        : step === 'source' ? t(refusalKey('profile', code))
          : (err instanceof Error && err.message) || t('admin.profileUpdateFailed') })
    }
    setSaving(false)
  }

  const meta = (session?.user?.app_metadata ?? {}) as { providers?: string[]; provider?: string }
  const providers = meta.providers ?? (meta.provider ? [meta.provider] : [])
  const state: ProfileState = {
    t, token, me, role: ctx.role, isSuper: ctx.isSuper, permissions: ctx.permissions ?? [], email,
    draft, saved, set, setRev, setCard, report, orgName, providers, reviews, photoUrl, onPhoto,
  }

  return (
    <form onSubmit={save} className="space-y-6" data-testid="admin-profile">
      <h1 className="text-2xl font-bold text-ground-900">{t('admin.profile')}</h1>

      {gated && (
        <div className={`rounded-lg p-4 border ${missing.length ? 'bg-caution-50 border-caution-200' : 'bg-positive-50 border-positive-200'}`}>
          <p className={`text-sm font-medium ${missing.length ? 'text-caution-900' : 'text-positive-800'}`}>
            {missing.length ? t('admin.reviewer.onboarding.title') : t('admin.reviewer.onboarding.allSet')}
          </p>
          {missing.length > 0 && (
            <>
              <p className="text-sm text-caution-800 mt-1">{t('admin.reviewer.onboarding.intro')}</p>
              <ul className="mt-1 list-disc ml-5 text-sm text-caution-800">
                {missing.map((f) => <li key={f}>{MISSING_LABEL[f]}</li>)}
              </ul>
            </>
          )}
        </div>
      )}

      {/* Anyone else holding `review`: a reminder, never a block (owner ruling 2026-10-31). */}
      {remind && (
        <div className="rounded-lg p-4 border bg-info-50 border-info-200" data-testid="reviewer-reminder">
          <p className="text-sm font-medium text-info-900">{t('admin.myProfile.reminderTitle')}</p>
          <p className="text-sm text-info-800 mt-1">{t('admin.myProfile.reminderIntro')}</p>
          <ul className="mt-1 list-disc ml-5 text-sm text-info-800">
            {missing.map((f) => <li key={f}>{MISSING_LABEL[f]}</li>)}
          </ul>
        </div>
      )}

      {cards.map((id) => {
        const Card = CARDS[id]
        return <Card key={id} state={state} />
      })}

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving || !draft.name.trim() || !dirty || blocked}
          title={dirty ? undefined : t('common.nothingToSave')}
          className="w-full sm:w-auto px-8 bg-brand-fill text-brand-fill-ink py-3 rounded-lg font-medium hover:bg-brand-fill-hover transition-colors disabled:opacity-50">
          {saving ? t('admin.saving') : t('common.save')}
        </button>
        {message && (
          <p ref={messageRef} tabIndex={-1} role={message.ok ? 'status' : 'alert'}
            className={`text-sm outline-none ${message.ok ? 'text-positive-700' : 'text-critical-600'}`}>{message.text}</p>
        )}
      </div>
    </form>
  )
}
