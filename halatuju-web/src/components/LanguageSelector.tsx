'use client'

import { useT, LOCALE_LABELS, type Locale } from '@/lib/i18n'

export default function LanguageSelector() {
  const { locale, setLocale } = useT()

  return (
    <select
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
      className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-600 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none cursor-pointer"
      aria-label="Language"
    >
      {Object.entries(LOCALE_LABELS).map(([key, label]) => (
        <option key={key} value={key}>{label}</option>
      ))}
    </select>
  )
}
