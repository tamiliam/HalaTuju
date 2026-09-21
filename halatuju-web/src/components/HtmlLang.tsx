'use client'

/**
 * `<html lang>` — and it follows THE WORDS ON SCREEN, never the language that was asked for.
 *
 * ⚠ It used to read `locale`, the reader's CHOICE. The two differ for as long as a catalogue
 * chunk takes to arrive — and for a returning Tamil or Malay reader that is every single visit,
 * because the server cannot read `localStorage`, so the HTML it sends is always English. The
 * result was `lang="ta"` over English text: a screen reader pronouncing English words with Tamil
 * phonetics, and a browser offering to translate a page that was already in the user's language.
 * `contentLocale` is the locale of the catalogue actually committed, so this attribute is now
 * true at every instant rather than true once the download finishes.
 */

import { useEffect } from 'react'
import { useT } from '@/lib/i18n'

export function HtmlLang() {
  const { contentLocale } = useT()

  useEffect(() => {
    document.documentElement.lang = contentLocale === 'ms' ? 'ms-MY' : contentLocale === 'ta' ? 'ta' : 'en'
  }, [contentLocale])

  return null
}
