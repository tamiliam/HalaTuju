'use client'

/**
 * The ORGANISATION the breadcrumb names — for the pages that narrow by it (TD-228, 2026-10-05).
 *
 * The shell holds the crumb's choice (`AppShell`'s `selectedOrg`); this hands the same value to the
 * page beneath, so the crumb and the list read ONE answer. `''` means nothing chosen, and a page
 * sends no `?org=` — the list is exactly what the caller's fence allows, as before.
 *
 * STILL DISPLAY, NOT A FENCE. The server re-resolves `?org=` inside the caller's own fence
 * (`_AdminBase._org_narrowing`): a super may name any organisation, anybody else only their own,
 * and any other code is a 404. Read today by Requests; Sponsors and Sources are TD-228's open half.
 * Never attach it to requests globally (TD-193's warning) — each list opts in, with a fence test.
 */
import { createContext, useContext } from 'react'

export interface OrgScope {
  /** The chosen organisation's code, or `''` when nothing has been chosen. */
  selected: string
  select: (code: string) => void
}

const OrgScopeContext = createContext<OrgScope>({ selected: '', select: () => {} })

export const OrgScopeProvider = OrgScopeContext.Provider

export function useOrgScope(): OrgScope {
  return useContext(OrgScopeContext)
}
