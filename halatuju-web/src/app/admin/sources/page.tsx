'use client'

import '@/lib/messagesScholarship'   // TD-416: this page's scholarship.* words (their own slice)
import Link from 'next/link'
import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getSources, updateSource, type SourceItem } from '@/lib/admin-api'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import PanelTabs from '@/components/admin/PanelTabs'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { formatPhone, isValidPhone } from '@/lib/scholarship'
import PartnerEmailsCard from '@/components/sources/PartnerEmailsCard'
import { SignInBadge, Toggle } from '@/components/sources/shared'

// Sources (referral organisations) registry — a card in Administration → ORGANISATION
// (super/org_admin/admin). List + inline edit.
//
// ⚠ NO ADD HERE SINCE SOURCE SIGN-IN S2 (2026-10-30): a source is created by INVITING ITS PERSON
// (Invitations → Source; the old POST answers 410 `use_source_invitation`), so the button is a link
// there — for super and org_admin only, who are the roles that may invite (owner: Admin does not).
// ⚠ EDIT LOCKS ONCE THE SOURCE HAS SIGNED IN (owner ruling 2026-10-30): its name and contact
// details are then its own (its console's Profile) and a change is refused 409 `managed_by_source`.
// The Active toggle stays the organisation's. Reuses PartnerOrganisation.phone /
// contact_person / contact_email (NOT a separate contact_phone column). The active-in-apply
// toggle decides which sources a gift's Configuration may OFFER; each gift then switches its own
// on (2026-10-08), and this page shows "On N of M gifts". Referral attribution is unaffected.
// The "Students" count = bursary APPLICATIONS attributed to the source by referral chip, among
// its own organisation's applications (backend _source_application_counts). Since sources Sprint
// B (2026-10-18) every row is a source OWNED by the caller's organisation — the house org is not a
// source, so it is not listed and carries no residual.
//
// TWO PANELS, one badge each (owner ruling, 2026-07-26): Organisations is the default and the
// registry is the thing you land on; Partner emails is a deliberate second click. They were
// stacked until then, which put a five-row switchboard between the admin and the table they
// came for. Only one panel is mounted at a time — the emails card fetches on first reveal.

const inputCls = 'w-full px-3 py-2 border border-ground-300 rounded-lg focus:ring-2 focus:ring-info-500 focus:border-info-500'
const inputBad = 'w-full px-3 py-2 border border-critical-400 rounded-lg focus:ring-2 focus:ring-critical-500 focus:border-critical-500'
// Phone is optional; when present it must be a valid Malaysian number. Display + input both
// run through the platform's shared formatPhone/isValidPhone (same helpers the apply form uses).
const phoneInvalid = (v: string) => v.trim() !== '' && !isValidPhone(v)

type EditForm = { name: string; contact_person: string; contact_email: string; phone: string }

/** The two panels. `orgs` is the default — the registry is what the page is for. */
const PANELS = ['orgs', 'emails', 'terms'] as const
type Panel = (typeof PANELS)[number]
// Owner, 2026-08-04: Reviewers, Sponsors and Sources all wear the same three tabs, and one with
// nothing behind it is shown DISABLED rather than hidden — so the surfaces look alike and a
// not-yet-built panel reads as coming rather than as absent.
const TERMS_READY = false   // no source-partner terms document exists yet
const panelLabel: Record<Panel, string> = {
  orgs: 'admin.sources.tabOrganisations',
  emails: 'admin.sources.tabEmails',
  terms: 'admin.sources.tabTerms',
}

export default function SourcesPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()

  const r = effectiveRole(role)
  // Sources management: super + admin + org_admin (owner 2026-07-19). Matches the backend gate.
  const canManage = canAccess('/admin/sources', r)
  // Inviting (and so adding) a source: super + org_admin only (source sign-in S2).
  const canInvite = r === 'super' || r === 'org_admin'

  const [sources, setSources] = useState<SourceItem[]>([])
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<EditForm>({ name: '', contact_person: '', contact_email: '', phone: '' })
  const [panel, setPanel] = useState<Panel>('orgs')

  const load = () => { if (token) getSources({ token }).then((d) => setSources(d.sources)).catch(() => setMessage({ type: 'error', text: t('admin.sources.loadError') })) }
  useEffect(() => { load() }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (role && !canManage) {
    return <p className="text-critical-600">{t('admin.sources.superRequired')}</p>
  }

  const errText = (err: unknown) => {
    const code = (err as { code?: string })?.code
    // The source signed in between this page loading and the Save: its details are its own now.
    if (code === 'managed_by_source') return t('admin.sources.managedRefused')
    return err instanceof Error ? err.message : t('admin.actionFailed')
  }

  // ⚠ SWITCHING A SOURCE ON PUTS IT ON NO FORM (owner, 2026-10-08): each gift chooses its own
  // sources in its Configuration, so the page says where to go next rather than leaving the
  // admin to believe the form now lists it.
  const toggleActive = async (s: SourceItem) => {
    setBusy(s.id); setMessage(null)
    try {
      const updated = await updateSource(s.id, { show_in_apply: !s.show_in_apply }, { token: token! })
      setSources((rows) => rows.map((r) => (r.id === s.id ? { ...r, show_in_apply: updated.show_in_apply } : r)))
      if (updated.show_in_apply && !s.show_in_apply) {
        setMessage({ type: 'success', text: t('admin.sources.nowPerGift') })
      }
    } catch (err) { setMessage({ type: 'error', text: errText(err) }) }
    setBusy(null)
  }

  /** "On 2 of 2 gifts" / "On no gift form" — the count is the server's, over its ACTIVE gifts. */
  const giftLine = (s: SourceItem) => (s.gift_count > 0
    ? t('admin.sources.onGifts', { n: String(s.gift_count), m: String(s.gift_total) })
    : t('admin.sources.onNoGift'))

  // Has this row actually been edited? Compared field by field against the source the form was
  // opened from — the same four fields `updateSource` writes, so the two cannot disagree.
  const editDirty = (s: SourceItem) =>
    editForm.name !== s.name
    || editForm.contact_person !== s.contact_person
    || editForm.contact_email !== s.contact_email
    || editForm.phone !== s.phone

  const startEdit = (s: SourceItem) => {
    setEditingId(s.id)
    setEditForm({ name: s.name, contact_person: s.contact_person, contact_email: s.contact_email, phone: s.phone })
  }

  const saveEdit = async (id: number) => {
    if (phoneInvalid(editForm.phone)) { setMessage({ type: 'error', text: t('profile.invalidPhone') }); return }
    setBusy(id); setMessage(null)
    try {
      const updated = await updateSource(id, editForm, { token: token! })
      setSources((rows) => rows.map((r) => (r.id === id ? { ...r, ...updated } : r)))
      setEditingId(null)
      setMessage({ type: 'success', text: t('admin.sources.updated') })
    } catch (err) {
      setMessage({ type: 'error', text: errText(err) })
      // Refused because it has joined: re-read, so the row shows its lock instead of the form.
      if ((err as { code?: string })?.code === 'managed_by_source') { setEditingId(null); load() }
    }
    setBusy(null)
  }

  /** Edit is offered until somebody has signed in for the source; then the source keeps it. */
  const managed = (s: SourceItem) => s.sign_in === 'joined'

  return (
    <div className="font-plex">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ground-900">{t('admin.sources.title')}</h1>
          <p className="text-sm text-ground-500 mt-1">{t('admin.sources.subtitle')}</p>
        </div>
        {/* A source is added by inviting its person (source sign-in S2) — a link to the Source tab
            of Invitations, for the two roles that may invite. Only on the registry panel. */}
        {panel === 'orgs' && canInvite && (
          <Link href="/admin/organisation/staff?kind=source"
            className="shrink-0 px-4 bg-brand-fill text-brand-fill-ink py-2.5 rounded-lg font-medium hover:bg-brand-fill-hover">
            {t('admin.sources.invite')} →
          </Link>
        )}
      </div>

      <PanelTabs ariaLabelKey="admin.sources.tabsAria" active={panel} onSelect={setPanel}
        tabs={PANELS.map((key) => ({
          key, labelKey: panelLabel[key], disabled: key === 'terms' && !TERMS_READY,
        }))} />

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${
          message.type === 'success' ? 'bg-positive-50 border border-positive-200 text-positive-700'
          : 'bg-critical-50 border border-critical-200 text-critical-600'}`}>{message.text}</div>
      )}

      {/* The emails card is mounted only while its badge is selected, so each reveal re-reads the
          send log (last-sent lines must never be stale). It stays self-contained + fail-soft, so a
          partner-emails hiccup can never take the registry down with it. */}
      {panel === 'emails' && <PartnerEmailsCard token={token} t={t} />}

      {/* The registry is HIDDEN rather than unmounted: a half-finished inline edit survives a trip
          to the emails badge and back. The plain `hidden` attribute (not a Tailwind class) is
          deliberate — it takes the table out of the accessibility tree as well as the layout. */}
      <div hidden={panel !== 'orgs'} data-testid="sources-registry">
        {/* ── PHONE: one card per referring organisation (owner, 2026-09-08) ──────────────────
            The name and the ACTIVE switch lead: this list answers "which schools appear on the
            apply form", and that switch is the answer. The contact details follow as a quiet
            block, and the student count sits with them.

            ⚠ THE SWITCH IS LIVE, THE EDIT FORM IS NOT — the owner's payment-run ruling applied
            to its next case: *"Desktop is the preferred option. Phone is for quick checking."*
            Flipping a school on or off is a check-and-tap; retyping a contact person, an email
            and a phone number in six boxes is desk work. So the card says where to do it rather
            than opening a form nobody wants to fill in on a phone.

            ⚠ THE GIFT COUNT (2026-10-08) is the same line as the table's: each gift chooses its
            sources in its own Configuration, so this page only says how many have. */}
        <div className="space-y-2.5 md:hidden" data-testid="source-cards">
          {sources.map((s) => (
            <div key={s.id} className="rounded-xl border border-ground-200 bg-ground-0 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <span className="block text-sm font-semibold text-ground-900">{s.name}</span>
                  <span className="block text-[11px] text-ground-400">{s.code}</span>
                  <span className="block text-[11px] text-ground-400" data-testid={`gift-line-card-${s.code}`}>
                    {giftLine(s)}
                  </span>
                </div>
                <Toggle on={s.show_in_apply} disabled={busy === s.id}
                  onClick={() => toggleActive(s)} label={t('admin.sources.activeInApply')} />
              </div>

              <div className="mt-2 space-y-0.5 text-[11px] text-ground-600">
                <div>{s.contact_person || t('admin.sources.empty')}</div>
                <div className="truncate text-ground-500">{s.contact_email || t('admin.sources.empty')}</div>
                <div className="text-ground-500">{s.phone ? formatPhone(s.phone) : t('admin.sources.empty')}</div>
              </div>

              <div className="mt-2 flex items-center justify-between gap-3 border-t border-ground-100 pt-2">
                <span className="flex items-center gap-2">
                  <span className="inline-block min-w-[1.75rem] rounded-full bg-ground-100 px-2 py-0.5 text-center text-[11px] text-ground-600">
                    {s.student_count ?? 0}
                  </span>
                  <SignInBadge state={s.sign_in} t={t} />
                </span>
                <span className="text-[11px] text-ground-500">
                  {t(managed(s) ? 'admin.sources.managed' : 'admin.sources.editOnDesktop')}
                </span>
              </div>
            </div>
          ))}
        </div>

        <TableFrame className="hidden md:block" minWidth={940} label={t('admin.sources.title')}>
        <table className="w-full text-sm">
          <thead className="bg-ground-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colOrganisation')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colContactPerson')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colEmail')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colPhone')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colSignIn')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colActive')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colStudents')}</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {sources.map((s) => editingId === s.id ? (
              // Inline edit expands into a single full-width labelled panel (spanning all
              // columns) rather than cramming inputs into narrow cells — no truncated text,
              // no row-height misalignment. Mirrors the Add-a-source form layout.
              <tr key={s.id} className="bg-info-50/40">
                <td colSpan={8} className="px-4 py-5">
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <label className="block">
                      <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.name')}</span>
                      <input className={inputCls} value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                      <span className="block text-xs text-ground-400 mt-1">{s.code}</span>
                    </label>
                    <label className="block">
                      <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.contactPerson')}</span>
                      <input className={inputCls} value={editForm.contact_person} onChange={(e) => setEditForm({ ...editForm, contact_person: e.target.value })} />
                    </label>
                    <label className="block">
                      <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.email')}</span>
                      <input className={inputCls} type="email" value={editForm.contact_email} onChange={(e) => setEditForm({ ...editForm, contact_email: e.target.value })} />
                    </label>
                    <label className="block">
                      <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.phone')}</span>
                      <input className={phoneInvalid(editForm.phone) ? inputBad : inputCls} inputMode="tel"
                        value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: formatPhone(e.target.value) })} />
                      {phoneInvalid(editForm.phone) && <span className="block text-xs text-critical-600 mt-1">{t('profile.invalidPhone')}</span>}
                    </label>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-3 mt-4">
                    <div className="flex items-center gap-3">
                      <Toggle on={s.show_in_apply} disabled={busy === s.id} onClick={() => toggleActive(s)} label={t('admin.sources.activeInApply')} />
                      <span className="text-sm text-ground-700">{t('admin.sources.activeInApply')}</span>
                    </div>
                    <div className="flex items-center gap-3 ml-auto">
                      {/* Request #6: nothing edited, nothing to save. The row IS its own baseline —
                          `startEdit` copies the source into the form — so the comparison is direct.
                          The toggle beside it is an ACTION and stays live regardless. */}
                      <button disabled={busy === s.id || phoneInvalid(editForm.phone)
                                        || !editDirty(s)} onClick={() => saveEdit(s.id)}
                        title={editDirty(s) ? undefined : t('common.nothingToSave')}
                        className="px-5 bg-brand-fill text-brand-fill-ink py-2 rounded-lg text-sm font-medium hover:bg-brand-fill-hover disabled:opacity-50">
                        {busy === s.id ? t('admin.sources.saving') : t('admin.sources.save')}
                      </button>
                      <button onClick={() => setEditingId(null)} className="text-sm text-ground-500 hover:text-ground-700">{t('admin.sources.cancel')}</button>
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              <tr key={s.id}>
                <td className="px-4 py-3">
                  <span className="font-semibold text-ground-900">{s.name}</span>
                  <span className="block text-xs text-ground-400">{s.code}</span>
                  {/* How many gifts list it, under the name rather than as a column. */}
                  <span className="block text-xs text-ground-400" data-testid={`gift-line-row-${s.code}`}>
                    {giftLine(s)}
                  </span>
                </td>
                <td className="px-4 py-3 text-ground-600">{s.contact_person || t('admin.sources.empty')}</td>
                <td className="px-4 py-3 text-ground-500">{s.contact_email || t('admin.sources.empty')}</td>
                <td className="px-4 py-3 text-ground-500 whitespace-nowrap">{s.phone ? formatPhone(s.phone) : t('admin.sources.empty')}</td>
                <td className="px-4 py-3" data-testid={`sign-in-${s.code}`}><SignInBadge state={s.sign_in} t={t} /></td>
                <td className="px-4 py-3"><Toggle on={s.show_in_apply} disabled={busy === s.id} onClick={() => toggleActive(s)} label={t('admin.sources.activeInApply')} /></td>
                <td className="px-4 py-3">
                  <span className="inline-block min-w-[1.75rem] text-center px-2 py-0.5 text-xs rounded-full bg-ground-100 text-ground-600">{s.student_count ?? 0}</span>
                </td>
                <td className="px-4 py-3">
                  <div className="text-right">
                    {managed(s) ? (
                      <span className="text-xs text-ground-500">{t('admin.sources.managed')}</span>
                    ) : (
                      <button onClick={() => startEdit(s)} className="text-xs font-medium text-primary-600 hover:text-primary-800">{t('admin.sources.edit')}</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {sources.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-6 text-center text-ground-400">{t('admin.sources.noSources')}</td></tr>
            )}
          </tbody>
        </table>
        </TableFrame>
        <p className="mt-3 text-sm text-ground-500">{t('admin.sources.managedNote')}</p>
      </div>
    </div>
  )
}
