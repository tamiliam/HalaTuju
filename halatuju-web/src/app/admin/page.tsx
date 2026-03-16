'use client'

import { useAuth } from '@/lib/auth-context'
import { getPartnerDashboard, type DashboardData } from '@/lib/admin-api'
import { useEffect, useState } from 'react'

export default function AdminDashboard() {
  const { token } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    getPartnerDashboard({ token })
      .then(setData)
      .catch(() => setError('Anda bukan admin organisasi rakan kongsi.'))
  }, [token])

  if (error) {
    return (
      <div className="text-red-600 mt-8 text-center">{error}</div>
    )
  }

  if (!data) {
    return (
      <div className="mt-8 text-center text-gray-500">Loading...</div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">
        {data.org_name} &mdash; Dashboard
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <p className="text-sm text-gray-500">Jumlah Pelajar</p>
          <p className="text-3xl font-bold text-blue-600">
            {data.total_students}
          </p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <p className="text-sm text-gray-500">Selesai Onboarding</p>
          <p className="text-3xl font-bold text-green-600">
            {data.completed_onboarding}
          </p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <p className="text-sm text-gray-500">SPM / STPM</p>
          <p className="text-3xl font-bold">
            {data.by_exam_type.spm || 0} / {data.by_exam_type.stpm || 0}
          </p>
        </div>
      </div>

      {data.top_fields.length > 0 && (
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Bidang Popular</h2>
          <ul className="space-y-2">
            {data.top_fields.map((f) => (
              <li key={f.field} className="flex justify-between">
                <span>{f.field}</span>
                <span className="text-gray-500">{f.count} pelajar</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
