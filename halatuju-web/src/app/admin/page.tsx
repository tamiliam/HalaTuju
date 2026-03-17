'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { getPartnerDashboard, type DashboardData } from '@/lib/admin-api'
import { useEffect, useState } from 'react'
import QRCode from 'react-qr-code'

export default function AdminDashboard() {
  const { token } = useAdminAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!token) return
    getPartnerDashboard({ token })
      .then(setData)
      .catch(() => setError('Anda bukan admin organisasi rakan kongsi.'))
  }, [token])

  const referralUrl = data?.org_code
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}?ref=${data.org_code}`
    : null

  const handleCopy = async () => {
    if (!referralUrl) return
    await navigator.clipboard.writeText(referralUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

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

      {referralUrl && (
        <div className="bg-white rounded-lg p-6 shadow-sm border mb-8">
          <h2 className="font-semibold mb-1">Pautan Rujukan Pelajar</h2>
          <p className="text-sm text-gray-500 mb-4">
            Kongsi pautan ini kepada pelajar untuk mendaftar di bawah organisasi anda.
          </p>

          <div className="flex flex-col sm:flex-row gap-6">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-4">
                <input
                  type="text"
                  readOnly
                  value={referralUrl}
                  className="flex-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-lg text-sm text-gray-700 select-all"
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
                <button
                  onClick={handleCopy}
                  className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
                >
                  {copied ? 'Disalin!' : 'Salin'}
                </button>
              </div>

              <div className="flex gap-2">
                <a
                  href={`https://wa.me/?text=${encodeURIComponent(`Daftar di HalaTuju untuk semak kelayakan kursus anda: ${referralUrl}`)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                  </svg>
                  WhatsApp
                </a>
              </div>
            </div>

            <div className="flex flex-col items-center gap-2">
              <div className="bg-white p-3 border rounded-lg">
                <QRCode value={referralUrl} size={120} />
              </div>
              <p className="text-xs text-gray-400">Imbas untuk mendaftar</p>
            </div>
          </div>
        </div>
      )}

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
