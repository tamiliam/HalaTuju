/**
 * @jest-environment jsdom
 *
 * TD-285 (owner's F1 ruling, 2026-09-29) — WHAT THE OFFICER SEES OF THE "WHOSE STR?" IC ASK.
 *
 * A cannot-judge STR no longer blocks submission (the lead's reading of the ruling, review
 * F-B/F-D); its missing IC is asked AFTER submission through Check 2, and the officer follows it in
 * Outstanding. Review F-F: nothing rendered the new codes on the officer's side. This mounts the
 * real cockpit and asserts the ask is listed as an UPLOAD task, under the student's own wording
 * (the harness's `t` echoes keys, so the key IS the wording's address), never as a raw officer
 * ticket.
 */
import { screen, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import type { AdminResolutionItem } from '@/lib/admin-api'

installCockpitConsoleGuard()

const ASK = (code: string): AdminResolutionItem => ({
  id: 931, fact: 'income', code, params: { household_member: 'mother' }, prompt: '',
  kind: 'doc', doc_type: 'parent_ic', status: 'open',
  source: 'check2' as AdminResolutionItem['source'], resolution_text: '',
  created_at: '2026-09-29T09:00:00.000Z', resolved_at: null,
})

describe("the officer's Outstanding list", () => {
  it.each([
    ['mother_ic_for_str_missing'],
    ['mother_ic_for_str_unreadable'],
  ])('lists %s as the upload the student was asked for', async (code) => {
    renderCockpit({ role: 'super', stage: 'profile_complete',
                    build: { resolution_items: [ASK(code)] } })
    const title = await screen.findByText(`scholarship.actionCentre.item.${code}.title`,
                                          { exact: false })
    const row = title.closest('li') as HTMLElement
    expect(row).toBeTruthy()
    expect(within(row).getByText('admin.scholarship.outstanding.uploadLabel', { exact: false }))
      .toBeTruthy()
    expect(screen.queryByText('admin.scholarship.outstanding.empty')).toBeNull()
  })
})
