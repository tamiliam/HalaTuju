'use client'

import '@/lib/messagesScholarship'   // TD-416: the university picker's scholarship.* words (their own slice)
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getAdminMe, getAdminProfile, updateAdminProfile, getReviewerProfile, updateReviewerProfile,
  getSourceProfile, updateSourceProfile,
  type AdminMe, type ReviewerProfile, type SourceProfile,
} from '@/lib/admin-api'
import { blankReviewer, missingReviewerFields, reviewerProfileComplete } from '@/lib/reviewerProfile'
import { cardsFor, profileContext, reviewsCases, type ProfileCardId } from '@/lib/profileCards'
import { refusalKey } from '@/lib/sourceConsole'
import { useT } from '@/lib/i18n'
import { lazySource } from '@/components/source/LazySource'
import type { CardProps, ProfileDraft, ProfileState, SourceForm } from '@/components/adminProfile/shared'
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

/**
 * THE PROFILE PAGE — ONE shell for every admin-platform person, a source user included (common
 * profile S1, owner ruling 2026-10-31; roadmap docs/plans/2026-10-31-common-profile-roadmap.md).
 *
 * It renders exactly `cardsFor(...)` (`lib/profileCards.ts`, the ONE list with ONE rule per card)
 * and owns the data and the ONE Save, which writes every changed part to its own endpoint:
 *   the name — `admin/profile/` PUT (staff) or `admin/source/profile/` PATCH (a source);
 *   a partner's organisation contact — `admin/profile/` PUT; a source's organisation —
 *   `admin/source/profile/` PATCH; the reviewer cards — `admin/reviewer-profile/` PATCH.
 *
 * ⚠ A SOURCE USER IS REFUSED EVERY STAFF ENDPOINT (deny by default), so its page calls only
 * `admin/me/` GET, `admin/source/profile/` GET/PATCH and `admin/me/password/` POST (a password
 * change) — `components/source/noStaffCalls.test.tsx` holds it to that.
 *
 * ⚠ THE FIRST-SIGN-IN HOLD STAYS REVIEWER-ROLE ONLY. A Reviewer whose compulsory fields are missing
 * is held here (the layout guard) and sent on to Applications by the save that completes them; a
 * holder of `review` in any other role sees a reminder, never a block.
 */
export default function AdminProfilePage() {
  const { token, role, session, refreshRole } = useAdminAuth()
  const router = useRouter()
  const { t, locale } = useT()
  const ctx = profileContext(role)
  const cards = cardsFor(ctx)
  const isSource = ctx.role === 'source_partner'
  const isPartner = ctx.role === 'partner'
  const reviews = reviewsCases(ctx)
  const isReviewerRole = ctx.role === 'reviewer'

  const [me, setMe] = useState<AdminMe | null>(null)
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

  // Own account (Your access, Sign-in) — refetched in the reader's language for the gift names,
  // never touching the drafts.
  useEffect(() => {
    if (!token) return
    getAdminMe(locale, { token }).then(setMe).catch(() => {})
  }, [token, locale])

  // Waits for the role: which endpoints may be called depends on it (a source user's would refuse).
  const known = !!role
  useEffect(() => {
    if (!token || !known) return
    let live = true
    const load = async (): Promise<[ProfileDraft, string, string | null]> => {
      if (isSource) {
        const d = await getSourceProfile({ token })
        return [{ name: d.user.name, orgContact: '', orgPhone: '', reviewer: null, source: sourceFormOf(d) },
                d.user.email, d.source.organisation || null]
      }
      const [p, rev] = await Promise.all([
        getAdminProfile({ token }),
        reviews ? getReviewerProfile({ token }).catch(() => null) : Promise.resolve(null),
      ])
      return [{ name: p.name, orgContact: p.org_contact_person || '', orgPhone: p.org_phone || '',
                reviewer: rev, source: null }, p.email, p.org_name]
    }
    load().then(([base, mail, org]) => {
      if (!live) return
      setDraft(base); setSaved(base); setEmail(mail); setOrgName(org)
    }).catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [token, known, isSource, reviews])

  const set = useCallback((patch: Partial<ProfileDraft>) =>
    setDraft((prev) => (prev ? { ...prev, ...patch } : prev)), [])
  const setRev = useCallback((patch: Partial<ReviewerProfile>) =>
    setDraft((prev) => (prev ? { ...prev, reviewer: { ...(prev.reviewer ?? blankReviewer()), ...patch } } : prev)), [])
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
  const orgDirty = isPartner && (draft.orgContact !== saved.orgContact || draft.orgPhone !== saved.orgPhone)
  const revDirty = reviews && JSON.stringify(draft.reviewer) !== JSON.stringify(saved.reviewer)
  const srcDirty = isSource && JSON.stringify(draft.source) !== JSON.stringify(saved.source)
  const dirty = nameDirty || orgDirty || revDirty || srcDirty
  const blocked = Object.values(invalid).some(Boolean)

  // Onboarding: a Reviewer whose backend flag is false is held here until the compulsory fields are
  // filled. `missing` is a live client mirror (updates as they type) that drives the banner.
  const gated = isReviewerRole && role?.reviewer_profile_complete === false
  const missing = reviews ? missingReviewerFields(draft.name, draft.reviewer) : []
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
    try {
      let next: ProfileDraft = draft
      if (isSource && draft.source) {
        const s = draft.source
        const d = await updateSourceProfile({
          ...(nameDirty ? { user: { name: draft.name.trim() } } : {}),
          source: { name: s.source_name.trim(), contact_person: s.contact_person.trim(),
                    contact_email: s.contact_email.trim(), phone: s.phone.trim() },
        }, { token })
        next = { ...draft, name: d.user.name, source: sourceFormOf(d) }
      } else {
        if (nameDirty || orgDirty) {
          const data: Record<string, string> = { name: draft.name }
          if (isPartner && orgName) {
            data.org_contact_person = draft.orgContact
            data.org_phone = draft.orgPhone
          }
          await updateAdminProfile(data, { token })
        }
        if (revDirty && draft.reviewer) await updateReviewerProfile(draft.reviewer, { token })
      }
      setDraft(next); setSaved(next)
      setMessage({ ok: true, text: t('admin.profileUpdated') })
      // Onboarding: this save completed a held Reviewer's profile — refresh the role flag and send
      // them on to their workspace (the layout guard releases once the flag flips).
      if (gated && reviewerProfileComplete(next.name, next.reviewer)) {
        await refreshRole()
        router.push('/admin/scholarship')
        return
      }
      // The header shows the person's name (and a source's "<source> · Source").
      if (nameDirty || (isSource && next.source?.source_name !== saved.source?.source_name)) void refreshRole()
    } catch (err) {
      setMessage({ ok: false, text: isSource
        ? t(refusalKey('profile', (err as { code?: string })?.code))
        : (err instanceof Error && err.message) || t('admin.profileUpdateFailed') })
    }
    setSaving(false)
  }

  const meta = (session?.user?.app_metadata ?? {}) as { providers?: string[]; provider?: string }
  const providers = meta.providers ?? (meta.provider ? [meta.provider] : [])
  const state: ProfileState = {
    t, token, me, role: ctx.role, isSuper: ctx.isSuper, permissions: ctx.permissions ?? [], email,
    draft, saved, set, setRev, report, orgName, providers,
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
