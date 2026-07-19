'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getSources, createSource, updateSource, type SourceItem,
} from '@/lib/admin-api'
import { useT } from '@/lib/i18n'

// Sources (referral organisations) registry — a card in Administration → ORGANISATION
// (super/org_admin only). List + inline edit + add. Reuses PartnerOrganisation.phone /
// contact_person / contact_email (NOT a separate contact_phone column). The active-in-apply
// toggle governs the future apply-form source list; referral attribution is unaffected.

const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
const slugify = (v: string) => v.toLowerCase().replace(/[^a-z0-9-]/g, '')

function Toggle({ on, onClick, disabled, label }: {
  on: boolean; onClick: () => void; disabled?: boolean; label: string
}) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label}
      onClick={disabled ? undefined : onClick} disabled={disabled}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
        on ? 'bg-blue-600' : 'bg-gray-300'}`}>
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
        on ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
  )
}

type EditForm = { name: string; contact_person: string; contact_email: string; phone: string }

export default function SourcesPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()

  const isSuper = !!(role?.is_super_admin || role?.role === 'super')
  // Sources management: super + admin + org_admin (owner 2026-07-19). Matches the backend gate.
  const canManage = isSuper || role?.role === 'org_admin' || role?.role === 'admin'

  const [sources, setSources] = useState<SourceItem[]>([])
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState<number | 'new' | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<EditForm>({ name: '', contact_person: '', contact_email: '', phone: '' })
  const [adding, setAdding] = useState(false)
  const [addForm, setAddForm] = useState({ code: '', name: '', contact_person: '', contact_email: '', phone: '', show_in_apply: false })

  const load = () => { if (token) getSources({ token }).then((d) => setSources(d.sources)).catch(() => setMessage({ type: 'error', text: t('admin.sources.loadError') })) }
  useEffect(() => { load() }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (role && !canManage) {
    return <p className="text-red-600">{t('admin.sources.superRequired')}</p>
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

  const startEdit = (s: SourceItem) => {
    setEditingId(s.id)
    setEditForm({ name: s.name, contact_person: s.contact_person, contact_email: s.contact_email, phone: s.phone })
  }

  const saveEdit = async (id: number) => {
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
    e.preventDefault(); setBusy('new'); setMessage(null)
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
    <div className="max-w-5xl">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('admin.sources.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('admin.sources.subtitle')}</p>
        </div>
        <button type="button" onClick={() => setAdding((v) => !v)}
          className="shrink-0 px-4 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700">
          + {t('admin.sources.add')}
        </button>
      </div>

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${
          message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700'
          : 'bg-red-50 border border-red-200 text-red-600'}`}>{message.text}</div>
      )}

      {adding && (
        <form onSubmit={submitAdd} className="bg-white rounded-xl border shadow-sm p-6 space-y-4 mb-6">
          <h2 className="font-semibold text-gray-900">{t('admin.sources.addTitle')}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="block text-sm text-gray-600 mb-1">{t('admin.sources.code')}</span>
              <input className={inputCls} value={addForm.code}
                onChange={(e) => setAddForm({ ...addForm, code: slugify(e.target.value) })} required />
              <span className="block text-xs text-gray-400 mt-1">{t('admin.sources.codeHelp')}</span>
            </label>
            <label className="block">
              <span className="block text-sm text-gray-600 mb-1">{t('admin.sources.name')}</span>
              <input className={inputCls} value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} required />
            </label>
            <label className="block">
              <span className="block text-sm text-gray-600 mb-1">{t('admin.sources.contactPerson')}</span>
              <input className={inputCls} value={addForm.contact_person} onChange={(e) => setAddForm({ ...addForm, contact_person: e.target.value })} />
            </label>
            <label className="block">
              <span className="block text-sm text-gray-600 mb-1">{t('admin.sources.email')}</span>
              <input className={inputCls} type="email" value={addForm.contact_email} onChange={(e) => setAddForm({ ...addForm, contact_email: e.target.value })} />
            </label>
            <label className="block">
              <span className="block text-sm text-gray-600 mb-1">{t('admin.sources.phone')}</span>
              <input className={inputCls} value={addForm.phone} onChange={(e) => setAddForm({ ...addForm, phone: e.target.value })} />
            </label>
            <div className="flex items-center gap-3 pt-6">
              <Toggle on={addForm.show_in_apply} onClick={() => setAddForm({ ...addForm, show_in_apply: !addForm.show_in_apply })} label={t('admin.sources.activeInApply')} />
              <span className="text-sm text-gray-700">{t('admin.sources.activeInApply')}</span>
            </div>
          </div>
          <p className="text-xs text-gray-400">{t('admin.sources.activeHelp')}</p>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={busy === 'new'} className="px-6 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">
              {busy === 'new' ? t('admin.sources.saving') : t('admin.sources.create')}
            </button>
            <button type="button" onClick={() => setAdding(false)} className="text-sm text-gray-500 hover:text-gray-700">{t('admin.sources.cancel')}</button>
          </div>
        </form>
      )}

      <div className="bg-white rounded-xl shadow-sm border overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.sources.colOrganisation')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.sources.colContactPerson')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.sources.colEmail')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.sources.colPhone')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.sources.colActive')}</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.sources.colStudents')}</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {sources.map((s) => editingId === s.id ? (
              <tr key={s.id} className="bg-blue-50/40">
                <td className="px-4 py-3">
                  <input className={inputCls} value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                  <span className="block text-xs text-gray-400 mt-1">{s.code}</span>
                </td>
                <td className="px-4 py-3"><input className={inputCls} value={editForm.contact_person} onChange={(e) => setEditForm({ ...editForm, contact_person: e.target.value })} /></td>
                <td className="px-4 py-3"><input className={inputCls} type="email" value={editForm.contact_email} onChange={(e) => setEditForm({ ...editForm, contact_email: e.target.value })} /></td>
                <td className="px-4 py-3"><input className={inputCls} value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} /></td>
                <td className="px-4 py-3"><Toggle on={s.show_in_apply} disabled={busy === s.id} onClick={() => toggleActive(s)} label={t('admin.sources.activeInApply')} /></td>
                <td className="px-4 py-3 text-gray-500">{s.student_count ?? 0}</td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <button disabled={busy === s.id} onClick={() => saveEdit(s.id)} className="text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50">
                    {busy === s.id ? t('admin.sources.saving') : t('admin.sources.save')}
                  </button>
                  <button onClick={() => setEditingId(null)} className="ml-3 text-xs text-gray-500 hover:text-gray-700">{t('admin.sources.cancel')}</button>
                </td>
              </tr>
            ) : (
              <tr key={s.id}>
                <td className="px-4 py-3">
                  <span className="font-semibold text-gray-900">{s.name}</span>
                  <span className="block text-xs text-gray-400">{s.code}</span>
                </td>
                <td className="px-4 py-3 text-gray-600">{s.contact_person || t('admin.sources.empty')}</td>
                <td className="px-4 py-3 text-gray-500">{s.contact_email || t('admin.sources.empty')}</td>
                <td className="px-4 py-3 text-gray-500">{s.phone || t('admin.sources.empty')}</td>
                <td className="px-4 py-3"><Toggle on={s.show_in_apply} disabled={busy === s.id} onClick={() => toggleActive(s)} label={t('admin.sources.activeInApply')} /></td>
                <td className="px-4 py-3">
                  <span className="inline-block min-w-[1.75rem] text-center px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">{s.student_count ?? 0}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => startEdit(s)} className="text-xs font-medium text-blue-600 hover:text-blue-800">{t('admin.sources.edit')}</button>
                </td>
              </tr>
            ))}
            {sources.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400">{t('admin.sources.noSources')}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
