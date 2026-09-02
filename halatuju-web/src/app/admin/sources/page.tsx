'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getSources, createSource, updateSource, type SourceItem,
} from '@/lib/admin-api'
import { useT } from '@/lib/i18n'
import PanelTabs from '@/components/admin/PanelTabs'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { formatPhone, isValidPhone } from '@/lib/scholarship'
import PartnerEmailsCard from '@/components/sources/PartnerEmailsCard'
import { Toggle } from '@/components/sources/shared'

// Sources (referral organisations) registry — a card in Administration → ORGANISATION
// (super/org_admin only). List + inline edit + add. Reuses PartnerOrganisation.phone /
// contact_person / contact_email (NOT a separate contact_phone column). The active-in-apply
// toggle governs the future apply-form source list; referral attribution is unaffected.
// The "Students" count = bursary APPLICATIONS attributed to the org by referral chip
// (backend _source_application_counts); the house org "BrightPath" gets the residual.
//
// TWO PANELS, one badge each (owner ruling, 2026-07-26): Organisations is the default and the
// registry is the thing you land on; Partner emails is a deliberate second click. They were
// stacked until then, which put a five-row switchboard between the admin and the table they
// came for. Only one panel is mounted at a time — the emails card fetches on first reveal.

const inputCls = 'w-full px-3 py-2 border border-ground-300 rounded-lg focus:ring-2 focus:ring-info-500 focus:border-info-500'
const inputBad = 'w-full px-3 py-2 border border-critical-400 rounded-lg focus:ring-2 focus:ring-critical-500 focus:border-critical-500'
const slugify = (v: string) => v.toLowerCase().replace(/[^a-z0-9-]/g, '')
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

  const isSuper = effectiveRole(role) === 'super'
  // Sources management: super + admin + org_admin (owner 2026-07-19). Matches the backend gate.
  const canManage = canAccess('/admin/sources', effectiveRole(role))

  const [sources, setSources] = useState<SourceItem[]>([])
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState<number | 'new' | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<EditForm>({ name: '', contact_person: '', contact_email: '', phone: '' })
  const [adding, setAdding] = useState(false)
  const [panel, setPanel] = useState<Panel>('orgs')
  const [addForm, setAddForm] = useState({ code: '', name: '', contact_person: '', contact_email: '', phone: '', show_in_apply: false })

  const load = () => { if (token) getSources({ token }).then((d) => setSources(d.sources)).catch(() => setMessage({ type: 'error', text: t('admin.sources.loadError') })) }
  useEffect(() => { load() }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (role && !canManage) {
    return <p className="text-critical-600">{t('admin.sources.superRequired')}</p>
  }

  const errText = (err: unknown) => {
    const code = (err as { code?: string })?.code
    if (code === 'code_taken') return t('admin.sources.codeTaken')
    if (code === 'code_and_name_required') return t('admin.sources.codeAndNameRequired')
    return err instanceof Error ? err.message : t('admin.actionFailed')
  }

  const toggleActive = async (s: SourceItem) => {
    setBusy(s.id); setMessage(null)
    try {
      const updated = await updateSource(s.id, { show_in_apply: !s.show_in_apply }, { token: token! })
      setSources((rows) => rows.map((r) => (r.id === s.id ? { ...r, show_in_apply: updated.show_in_apply } : r)))
    } catch (err) { setMessage({ type: 'error', text: errText(err) }) }
    setBusy(null)
  }

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
    } catch (err) { setMessage({ type: 'error', text: errText(err) }) }
    setBusy(null)
  }

  const submitAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (phoneInvalid(addForm.phone)) { setMessage({ type: 'error', text: t('profile.invalidPhone') }); return }
    setBusy('new'); setMessage(null)
    try {
      await createSource(addForm, { token: token! })
      setAdding(false)
      setAddForm({ code: '', name: '', contact_person: '', contact_email: '', phone: '', show_in_apply: false })
      setMessage({ type: 'success', text: t('admin.sources.created') })
      load()
    } catch (err) { setMessage({ type: 'error', text: errText(err) }) }
    setBusy(null)
  }

  return (
    <div className="max-w-5xl font-plex">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ground-900">{t('admin.sources.title')}</h1>
          <p className="text-sm text-ground-500 mt-1">{t('admin.sources.subtitle')}</p>
        </div>
        {/* Adding belongs to the registry — on the emails panel the button would do nothing visible. */}
        {panel === 'orgs' && (
          <button type="button" onClick={() => setAdding((v) => !v)}
            className="shrink-0 px-4 bg-brand-fill text-brand-fill-ink py-2.5 rounded-lg font-medium hover:bg-brand-fill-hover">
            + {t('admin.sources.add')}
          </button>
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

      {panel === 'orgs' && adding && (
        <form onSubmit={submitAdd} className="bg-ground-0 rounded-xl border shadow-sm p-6 space-y-4 mb-6">
          <h2 className="font-semibold text-ground-900">{t('admin.sources.addTitle')}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.code')}</span>
              <input className={inputCls} value={addForm.code}
                onChange={(e) => setAddForm({ ...addForm, code: slugify(e.target.value) })} required />
              <span className="block text-xs text-ground-400 mt-1">{t('admin.sources.codeHelp')}</span>
            </label>
            <label className="block">
              <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.name')}</span>
              <input className={inputCls} value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} required />
            </label>
            <label className="block">
              <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.contactPerson')}</span>
              <input className={inputCls} value={addForm.contact_person} onChange={(e) => setAddForm({ ...addForm, contact_person: e.target.value })} />
            </label>
            <label className="block">
              <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.email')}</span>
              <input className={inputCls} type="email" value={addForm.contact_email} onChange={(e) => setAddForm({ ...addForm, contact_email: e.target.value })} />
            </label>
            <label className="block">
              <span className="block text-sm text-ground-600 mb-1">{t('admin.sources.phone')}</span>
              <input className={phoneInvalid(addForm.phone) ? inputBad : inputCls} inputMode="tel"
                value={addForm.phone} onChange={(e) => setAddForm({ ...addForm, phone: formatPhone(e.target.value) })} />
              {phoneInvalid(addForm.phone) && <span className="block text-xs text-critical-500 mt-1">{t('profile.invalidPhone')}</span>}
            </label>
            <div className="flex items-center gap-3 pt-6">
              <Toggle on={addForm.show_in_apply} onClick={() => setAddForm({ ...addForm, show_in_apply: !addForm.show_in_apply })} label={t('admin.sources.activeInApply')} />
              <span className="text-sm text-ground-700">{t('admin.sources.activeInApply')}</span>
            </div>
          </div>
          <p className="text-xs text-ground-400">{t('admin.sources.activeHelp')}</p>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={busy === 'new'} className="px-6 bg-brand-fill text-brand-fill-ink py-2.5 rounded-lg font-medium hover:bg-brand-fill-hover disabled:opacity-50">
              {busy === 'new' ? t('admin.sources.saving') : t('admin.sources.create')}
            </button>
            <button type="button" onClick={() => setAdding(false)} className="text-sm text-ground-500 hover:text-ground-700">{t('admin.sources.cancel')}</button>
          </div>
        </form>
      )}

      {/* The emails card is mounted only while its badge is selected, so each reveal re-reads the
          send log (last-sent lines must never be stale). It stays self-contained + fail-soft, so a
          partner-emails hiccup can never take the registry down with it. */}
      {panel === 'emails' && <PartnerEmailsCard token={token} t={t} />}

      {/* The registry is HIDDEN rather than unmounted: a half-finished inline edit survives a trip
          to the emails badge and back. The plain `hidden` attribute (not a Tailwind class) is
          deliberate — it takes the table out of the accessibility tree as well as the layout. */}
      <div hidden={panel !== 'orgs'} className="bg-ground-0 rounded-xl shadow-sm border overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="bg-ground-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colOrganisation')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colContactPerson')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colEmail')}</th>
              <th className="text-left px-4 py-3 font-medium text-ground-600">{t('admin.sources.colPhone')}</th>
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
                <td colSpan={7} className="px-4 py-5">
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
                      {phoneInvalid(editForm.phone) && <span className="block text-xs text-critical-500 mt-1">{t('profile.invalidPhone')}</span>}
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
                </td>
                <td className="px-4 py-3 text-ground-600">{s.contact_person || t('admin.sources.empty')}</td>
                <td className="px-4 py-3 text-ground-500">{s.contact_email || t('admin.sources.empty')}</td>
                <td className="px-4 py-3 text-ground-500 whitespace-nowrap">{s.phone ? formatPhone(s.phone) : t('admin.sources.empty')}</td>
                <td className="px-4 py-3"><Toggle on={s.show_in_apply} disabled={busy === s.id} onClick={() => toggleActive(s)} label={t('admin.sources.activeInApply')} /></td>
                <td className="px-4 py-3">
                  <span className="inline-block min-w-[1.75rem] text-center px-2 py-0.5 text-xs rounded-full bg-ground-100 text-ground-600">{s.student_count ?? 0}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => startEdit(s)} className="text-xs font-medium text-info-600 hover:text-info-800">{t('admin.sources.edit')}</button>
                </td>
              </tr>
            ))}
            {sources.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-ground-400">{t('admin.sources.noSources')}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
