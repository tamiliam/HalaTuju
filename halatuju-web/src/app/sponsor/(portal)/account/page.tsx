'use client'

import { useEffect, useMemo, useState } from 'react'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { createSponsorReferral, getSponsorStandingGift, putSponsorStandingGift } from '@/lib/api'
import { poolFacets } from '@/lib/sponsorFilter'
import SponsorNotifyPrefs from '@/components/SponsorNotifyPrefs'

/**
 * My Account — profile, email cadence, and "invite a friend". R4 adds the giving
 * statement (two ledgers) here; R5 adds the trust/assurance surfaces.
 */
export default function AccountPage() {
  const { t } = useT()
  const { account } = useSponsorAuth()
  const { referrals, refreshReferrals, statement, gradMessages, pool } = useSponsorPortal()

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteName, setInviteName] = useState('')
  const [inviteNote, setInviteNote] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [inviteSent, setInviteSent] = useState(false)
  const { token } = useSponsorAuth()

  // AutoSponsor (R6) — standing-gift config, fetched + saved on this page.
  const facets = useMemo(() => poolFacets(pool || []), [pool])
  const [sgActive, setSgActive] = useState(false)
  const [sgField, setSgField] = useState('')
  const [sgState, setSgState] = useState('')
  const [sgMax, setSgMax] = useState('')
  const [sgConfigured, setSgConfigured] = useState(false)
  const [sgLast, setSgLast] = useState<string | null>(null)
  const [sgSaving, setSgSaving] = useState(false)
  const [sgSaved, setSgSaved] = useState(false)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    getSponsorStandingGift({ token }).then((g) => {
      if (cancelled) return
      setSgConfigured(g.configured); setSgActive(!!g.active)
      setSgField(g.field_pref || ''); setSgState(g.state_pref || '')
      setSgMax(g.max_amount || ''); setSgLast(g.last_allocated_at || null)
    }).catch(() => { /* 404 while flag off — leave defaults */ })
    return () => { cancelled = true }
  }, [token])

  const saveStandingGift = async () => {
    if (!token || sgSaving) return
    setSgSaving(true); setSgSaved(false)
    try {
      const g = await putSponsorStandingGift(
        { field_pref: sgField, state_pref: sgState, max_amount: sgMax.trim() || null, active: sgActive },
        { token },
      )
      setSgConfigured(g.configured); setSgLast(g.last_allocated_at || null); setSgSaved(true)
    } catch { /* keep the form on failure */ } finally { setSgSaving(false) }
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  const sendInvite = async () => {
    if (!token || !inviteEmail.trim() || inviting) return
    setInviting(true); setInviteError(''); setInviteSent(false)
    try {
      await createSponsorReferral(
        { invitee_email: inviteEmail.trim(), invitee_name: inviteName.trim(), note: inviteNote.trim() },
        { token },
      )
      setInviteEmail(''); setInviteName(''); setInviteNote(''); setInviteSent(true)
      await refreshReferrals()
    } catch (e) {
      const code = (e as Error & { code?: string }).code
      setInviteError(code === 'bad_email'
        ? t('sponsorPortal.referrals.errorEmail') : t('sponsorPortal.referrals.errorGeneric'))
    } finally { setInviting(false) }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{t('sponsorPortal.account.title')}</h1>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Profile */}
        <div className="rounded-2xl border bg-white p-5">
          <h2 className="font-semibold text-gray-900 mb-3">{t('sponsorPortal.account.detailsTitle')}</h2>
          <dl className="text-sm space-y-2">
            <div className="flex justify-between gap-3"><dt className="text-gray-500">{t('sponsorAuth.fullName')}</dt><dd className="font-medium text-gray-900 text-right">{account?.name || '—'}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-gray-500">{t('sponsorPortal.account.email')}</dt><dd className="font-medium text-gray-900 text-right break-all">{account?.email || '—'}</dd></div>
            {account?.phone && <div className="flex justify-between gap-3"><dt className="text-gray-500">{t('sponsorAuth.phone')}</dt><dd className="font-medium text-gray-900 text-right">{account.phone}</dd></div>}
          </dl>
          <div className="mt-4">
            <span className="inline-block px-2 py-1 text-xs font-semibold rounded-full bg-green-50 text-green-700">
              ✓ {t('sponsorPortal.myStudents.approvedPill')}
            </span>
          </div>
        </div>

        {/* Notifications */}
        <div className="rounded-2xl border bg-white p-5">
          <SponsorNotifyPrefs />
        </div>
      </div>

      {/* AutoSponsor — standing gift (R6) */}
      <section className="rounded-2xl border bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-gray-900">🔁 {t('sponsorPortal.autoSponsor.title')}</h2>
          <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
            <input type="checkbox" checked={sgActive}
              onChange={(e) => { setSgActive(e.target.checked); setSgSaved(false) }} className="h-4 w-4" />
            {t('sponsorPortal.autoSponsor.enable')}
          </label>
        </div>
        <p className="text-sm text-gray-600 mt-1 max-w-2xl">{t('sponsorPortal.autoSponsor.intro')}</p>
        <div className="mt-4 grid sm:grid-cols-3 gap-3">
          <label className="text-sm block">
            <span className="text-gray-500">{t('sponsorPortal.autoSponsor.field')}</span>
            <select value={sgField} onChange={(e) => { setSgField(e.target.value); setSgSaved(false) }} className={inputCls}>
              <option value="">{t('sponsorPortal.autoSponsor.any')}</option>
              {facets.fields.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label className="text-sm block">
            <span className="text-gray-500">{t('sponsorPortal.autoSponsor.state')}</span>
            <select value={sgState} onChange={(e) => { setSgState(e.target.value); setSgSaved(false) }} className={inputCls}>
              <option value="">{t('sponsorPortal.autoSponsor.any')}</option>
              {facets.states.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="text-sm block">
            <span className="text-gray-500">{t('sponsorPortal.autoSponsor.maxAmount')}</span>
            <input type="number" min="0" value={sgMax} onChange={(e) => { setSgMax(e.target.value); setSgSaved(false) }}
              placeholder={t('sponsorPortal.autoSponsor.noCap')} className={inputCls} />
          </label>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button onClick={saveStandingGift} disabled={sgSaving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {sgSaving ? t('sponsorPortal.autoSponsor.saving') : t('sponsorPortal.autoSponsor.save')}
          </button>
          {sgSaved && <span className="text-sm text-green-600">{t('sponsorPortal.autoSponsor.saved')}</span>}
        </div>
        <p className="text-[11px] text-gray-400 mt-3">{t('sponsorPortal.autoSponsor.note')}</p>
        {sgConfigured && sgLast && (
          <p className="text-[11px] text-gray-400 mt-1">
            {t('sponsorPortal.autoSponsor.lastAllocated').replace('{date}', new Date(sgLast).toLocaleDateString())}
          </p>
        )}
      </section>

      {/* Messages from students you supported — anonymous, linked to ref only */}
      {gradMessages.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-gray-900">{t('sponsorPortal.graduationMessages.title')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.graduationMessages.subtitle')}</p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {gradMessages.map((m, i) => (
              <div key={i} className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
                <p className="text-sm text-gray-800">💬 “{m.text}”</p>
                <p className="text-xs text-gray-500 mt-3">{t('sponsorPortal.graduationMessages.attribution')} · {m.ref}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Invite a friend + your invitations */}
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="rounded-2xl border bg-white p-5">
          <h2 className="text-lg font-bold text-gray-900">{t('sponsorPortal.referrals.title')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.referrals.subtitle')}</p>
          <div className="mt-3 space-y-3">
            <input value={inviteEmail} onChange={(e) => { setInviteEmail(e.target.value); setInviteSent(false) }}
              type="email" placeholder={t('sponsorPortal.referrals.emailPh')} className={inputCls} />
            <input value={inviteName} onChange={(e) => setInviteName(e.target.value)}
              placeholder={t('sponsorPortal.referrals.namePh')} className={inputCls} />
            <textarea value={inviteNote} onChange={(e) => setInviteNote(e.target.value)} rows={3} maxLength={500}
              placeholder={t('sponsorPortal.referrals.notePh')} className={inputCls} />
            {inviteError && <p className="text-sm text-red-600">{inviteError}</p>}
            {inviteSent && <p className="text-sm text-green-600">{t('sponsorPortal.referrals.sent')}</p>}
            <button onClick={sendInvite} disabled={inviting || !inviteEmail.trim()}
              className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
              {inviting ? t('sponsorPortal.referrals.sending') : t('sponsorPortal.referrals.send')}
            </button>
            <p className="text-xs text-gray-400">{t('sponsorPortal.referrals.privacy')}</p>
          </div>
        </div>
        <div className="rounded-2xl border bg-white p-5">
          <h2 className="text-lg font-bold text-gray-900">{t('sponsorPortal.referrals.listTitle')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.referrals.listSubtitle')}</p>
          {referrals.length > 0 ? (
            <ul className="mt-3 divide-y divide-gray-100">
              {referrals.map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-gray-700 truncate pr-2">{r.invitee_name || r.invitee_email || '—'}</span>
                  <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    r.status === 'joined' ? 'bg-green-100 text-green-700'
                      : r.status === 'expired' ? 'bg-amber-50 text-amber-600' : 'bg-gray-100 text-gray-600'}`}>
                    {t(`sponsorPortal.referrals.status.${r.status}`)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-gray-400">{t('sponsorPortal.referrals.empty')}</p>
          )}
        </div>
      </div>

      {/* Giving statement — two ledgers (donations in vs gifts out) */}
      {statement && (statement.donations.length > 0 || statement.gifts.length > 0) && (
        <section>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">{t('sponsorPortal.statement.title')}</h2>
            <button onClick={() => window.print()} className="px-3 py-1.5 text-sm font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl">
              {t('sponsorPortal.statement.print')}
            </button>
          </div>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.statement.intro')} <span className="text-gray-400">{t('sponsorPortal.statement.taxNote')}</span></p>
          <div className="mt-3 grid md:grid-cols-2 gap-4">
            <div className="rounded-2xl border bg-white p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-900">⬇ {t('sponsorPortal.statement.donations')}</h3>
                <span className="text-xs text-gray-400">RM {statement.total_in}</span>
              </div>
              {statement.donations.length > 0 ? (
                <ul className="text-sm divide-y divide-gray-100">
                  {statement.donations.map((d, i) => (
                    <li key={i} className="py-2 flex justify-between gap-2">
                      <span>{new Date(d.at).toLocaleDateString()}{d.reference ? <span className="text-gray-400"> · {d.reference}</span> : null}</span>
                      <b>RM {d.amount}</b>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-gray-400">—</p>}
              <p className="text-[11px] text-gray-400 mt-2">{t('sponsorPortal.statement.donationsNote')}</p>
            </div>
            <div className="rounded-2xl border bg-white p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-900">⬆ {t('sponsorPortal.statement.gifts')}</h3>
                <span className="text-xs text-gray-400">RM {statement.total_out}</span>
              </div>
              {statement.gifts.length > 0 ? (
                <ul className="text-sm divide-y divide-gray-100">
                  {statement.gifts.map((g, i) => (
                    <li key={i} className="py-2 flex justify-between gap-2">
                      <span>{new Date(g.at).toLocaleDateString()} <span className="text-gray-400">· {g.ref}</span></span>
                      <b>RM {g.amount}</b>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-gray-400">—</p>}
              <p className="text-[11px] text-gray-400 mt-2">{t('sponsorPortal.statement.giftsNote')}</p>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
