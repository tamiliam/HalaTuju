'use client'

/**
 * The language switcher — and, since the 2026-09-21 audit, the one place that knows a language
 * can take a moment to arrive.
 *
 * ⚠ **THE BOX SHOWS THE CHOICE; THE PROVIDER OWNS THE WORDS.** H17 made `locale` and its
 * catalogue one piece of state that changes in one commit, which is what rules out a render where
 * the switcher says Tamil and the heading is English. Correct, and this control was written as
 * `value={locale}` — so on a slow link choosing Tamil *visibly snapped back to English* for the
 * whole download, with nothing on screen to say anything was happening. It read as broken, and it
 * invited the second click that raced two chunks against each other.
 *
 * The fix is not to loosen the committed state. It is that **the pending choice is this control's
 * own UI state**: the box shows it at once, `aria-busy` says the control is working, and the
 * WORDS follow when the catalogue lands. `pending` is only "busy" while it differs from the
 * committed locale, so a language already in memory — English, or anything visited this tab —
 * commits in the same event and never flickers a spinner.
 *
 * ⚠ **AND A FAILURE IS SAID OUT LOUD.** A tab held open across a deploy asks for a chunk hash
 * that no longer exists. `setLocale` now rejects rather than committing a half-move, so the box
 * returns to the language actually on screen, nothing is persisted, and the reader is told — in
 * the language they are reading — through the house toast. There is no "a new version is
 * available, reload" mechanism in this codebase to hang it off, so the message says to reload.
 */

import { useRef, useState } from 'react'

import { useToast } from '@/components/Toast'
import { useT, LOCALE_LABELS, type Locale } from '@/lib/i18n'

export default function LanguageSelector() {
  const { locale, setLocale, t } = useT()
  const { showToast } = useToast()
  const [pending, setPending] = useState<Locale | null>(null)
  // The reader's LATEST pick, read from the settled callbacks. A ref rather than state because it
  // is only ever compared, never rendered: an answer for a choice already replaced must not put
  // the control back or raise a message about a language nobody is waiting for.
  const latest = useRef<Locale | null>(null)

  const choose = (next: Locale) => {
    latest.current = next
    setPending(next)
    setLocale(next).then(
      () => { if (latest.current === next) setPending(null) },
      () => {
        if (latest.current !== next) return
        setPending(null)
        showToast(t('common.languageLoadFailed'), 'error')
      },
    )
  }

  // Busy only while the choice has NOT yet reached the words. A synchronous commit (English, or a
  // language already in memory) leaves these equal in the very first render after the change.
  const busy = pending !== null && pending !== locale

  return (
    <span className="inline-flex items-center gap-1.5">
      <select
        value={pending ?? locale}
        onChange={(e) => choose(e.target.value as Locale)}
        aria-busy={busy}
        className="text-sm border border-ground-200 rounded-lg px-2 py-1.5 bg-ground-0 text-ground-600 focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none cursor-pointer"
        aria-label="Language"
      >
        {Object.entries(LOCALE_LABELS).map(([key, label]) => (
          <option key={key} value={key}>{label}</option>
        ))}
      </select>
      {/* The house spinner, at the size of the control beside it. `aria-hidden` because
          `aria-busy` on the select already carries the meaning — two announcements of one fact
          is one too many. */}
      {busy && (
        <span
          aria-hidden
          className="inline-block animate-spin rounded-full h-3.5 w-3.5 border-2 border-brand-shape border-t-transparent"
        />
      )}
    </span>
  )
}
