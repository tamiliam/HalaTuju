'use client'

import { useState, useEffect, useCallback } from 'react'
import { useT } from '@/lib/i18n'
import { listReferees, addReferee, type Referee } from '@/lib/api'

export default function ScholarshipReferee({ token }: { token: string | null }) {
  const { t } = useT()
  const [referees, setReferees] = useState<Referee[]>([])
  const [form, setForm] = useState({ name: '', role: '', relationship: '', phone: '', email: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const r = await listReferees({ token })
      setReferees(r.referees)
    } catch { /* ignore */ }
  }, [token])

  useEffect(() => { refresh() }, [refresh])

  const set = (k: keyof typeof form, v: string) => setForm((p) => ({ ...p, [k]: v }))

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !form.name.trim()) return
    setSaving(true)
    setError(null)
    try {
      await addReferee(form, { token })
      setForm({ name: '', role: '', relationship: '', phone: '', email: '' })
      await refresh()
    } catch {
      setError(t('scholarship.referee.error'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3">
      {referees.length > 0 && (
        <ul className="space-y-1 text-sm text-gray-700">
          {referees.map((r) => (
            <li key={r.id}>• {r.name}{r.role ? ` (${r.role})` : ''}{r.phone ? ` — ${r.phone}` : ''}</li>
          ))}
        </ul>
      )}
      <form onSubmit={handleAdd} className="space-y-2">
        <input className="input" placeholder={t('scholarship.referee.name')} value={form.name} onChange={(e) => set('name', e.target.value)} />
        <div className="grid grid-cols-2 gap-2">
          <input className="input" placeholder={t('scholarship.referee.role')} value={form.role} onChange={(e) => set('role', e.target.value)} />
          <input className="input" placeholder={t('scholarship.referee.relationship')} value={form.relationship} onChange={(e) => set('relationship', e.target.value)} />
          <input className="input" placeholder={t('scholarship.referee.phone')} value={form.phone} onChange={(e) => set('phone', e.target.value)} />
          <input className="input" placeholder={t('scholarship.referee.email')} value={form.email} onChange={(e) => set('email', e.target.value)} />
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" disabled={saving || !form.name.trim()} className="btn-primary text-sm disabled:opacity-50">
          {saving ? t('scholarship.referee.adding') : t('scholarship.referee.add')}
        </button>
      </form>
    </div>
  )
}
