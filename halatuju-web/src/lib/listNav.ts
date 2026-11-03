/**
 * Previous / Next through a LIST, from a detail page (Requests list R1, 2026-11-03).
 *
 * A list page writes what it is showing — the ordered ids of the page, the URL to come back to,
 * and the i18n key of the tab's name — under its own key; the detail page reads it and offers
 * "‹ Back to <tab>" and "‹ Previous · 2 of 7 · Next ›". The walk is the PAGE you came from
 * (D7): crossing to the next page would need a fetch from the detail page, and is a follow-up.
 *
 * ⚠ ONE HOME FOR THIS, SHARED. The Applications cockpit hand-rolls the same thing
 * (`halatuju_admin_scholarship_nav`, ids only, no position, no keys); it moves onto this hook after
 * Mobile M6b re-lays-out that header — see docs/technical-debt.md.
 *
 * ⚠ STORAGE IS INJECTED AND EVERY TOUCH IS GUARDED. `sessionStorage` is absent on the server,
 * throws in some private windows, and can hold anything a previous version wrote; a record that
 * does not parse to the expected shape is treated as no record, and a detail id that is not in
 * the record hides the nav altogether (a direct link, or a stale list) rather than guessing.
 */
import { useEffect, useState } from 'react'

/** The slice of `Storage` this module uses — so a test can pass a Map-backed fake. */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/** What a list leaves behind for its detail pages. */
export interface ListNavRecord {
  ids: number[]
  /** The list's own URL, path and query — so "Back" returns to the same tab, filter and page. */
  backHref: string
  /** The i18n key of the tab's name, for "Back to <tab>". */
  labelKey: string
}

/** Where one detail page sits in its list. `prevId` / `nextId` are null at the ends. */
export interface ListNavPosition {
  index: number
  total: number
  prevId: number | null
  nextId: number | null
  backHref: string
  labelKey: string
}

/** The Requests list's key. Each list has its own, so two lists never read each other's ids. */
export const REQUESTS_LIST_NAV = 'requests'

const PREFIX = 'halatuju_list_nav:'

/** The browser's sessionStorage, or null on the server / when it is unavailable. */
export function sessionStore(): StorageLike | null {
  try {
    return typeof window !== 'undefined' && window.sessionStorage ? window.sessionStorage : null
  } catch {
    return null
  }
}

export function writeListNav(
  key: string, record: ListNavRecord, store: StorageLike | null = sessionStore(),
): void {
  if (!store) return
  try {
    store.setItem(PREFIX + key, JSON.stringify(record))
  } catch { /* storage full or refused — the detail page simply shows no Previous / Next */ }
}

export function readListNav(
  key: string, store: StorageLike | null = sessionStore(),
): ListNavRecord | null {
  if (!store) return null
  try {
    const raw = store.getItem(PREFIX + key)
    if (!raw) return null
    const v = JSON.parse(raw) as Partial<ListNavRecord>
    const ok = Array.isArray(v.ids) && v.ids.every((n) => typeof n === 'number')
      && typeof v.backHref === 'string' && typeof v.labelKey === 'string'
    return ok ? { ids: v.ids as number[], backHref: v.backHref as string, labelKey: v.labelKey as string } : null
  } catch {
    return null
  }
}

/** Where `id` sits in `record`, or null when it is not there. */
export function positionIn(record: ListNavRecord | null, id: number): ListNavPosition | null {
  if (!record) return null
  const index = record.ids.indexOf(id)
  if (index < 0) return null
  return {
    index,
    total: record.ids.length,
    prevId: index > 0 ? record.ids[index - 1] : null,
    nextId: index < record.ids.length - 1 ? record.ids[index + 1] : null,
    backHref: record.backHref,
    labelKey: record.labelKey,
  }
}

/**
 * The detail page's position in the list it came from. Read AFTER mount (null on the server and
 * on the first client render), so server and client render the same thing.
 */
export function useListNav(
  key: string, id: number, store?: StorageLike | null,
): ListNavPosition | null {
  const [pos, setPos] = useState<ListNavPosition | null>(null)
  useEffect(() => {
    setPos(positionIn(readListNav(key, store === undefined ? sessionStore() : store), id))
  }, [key, id, store])
  return pos
}

/**
 * Whether ← / → should be LEFT ALONE: focus is in something a person types into or picks from,
 * a modifier is held (the browser's own Back / word-jump shortcuts), something already handled
 * the key, or a dialog is open over the page (the detail page's confirm sheets).
 */
export function arrowKeysIgnored(e: KeyboardEvent, doc: Document = document): boolean {
  if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return true
  const el = doc.activeElement
  // `closest('[contenteditable]…')` as well as `isContentEditable`: jsdom does not implement the
  // latter, and a test that cannot see the rule cannot hold it.
  if (el instanceof HTMLElement
      && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT'
          || el.isContentEditable
          || el.closest('[contenteditable]:not([contenteditable="false"])') !== null)) return true
  return doc.querySelector('[role="dialog"], [role="alertdialog"]') !== null
}
