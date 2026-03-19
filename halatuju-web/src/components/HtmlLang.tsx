'use client'

import { useEffect } from 'react'
import { useT } from '@/lib/i18n'

export function HtmlLang() {
  const { locale } = useT()

  useEffect(() => {
    document.documentElement.lang = locale === 'ms' ? 'ms-MY' : locale === 'ta' ? 'ta' : 'en'
  }, [locale])

  return null
}
