/**
 * @jest-environment jsdom
 *
 * AN APPLICATION THAT IS NOT THERE — the officer cockpit's unhappy path.
 *
 * ⚠ **IT IS MOUNTED THROUGH `renderCockpit`, NEVER BY IMPORTING `view.tsx`** — the harness's
 * `jest.mock` calls are hoisted into it, and a test that imported the page first would hand it
 * the real `admin-api`.
 *
 * The cockpit already drew `error` ahead of the loading line, so unlike `/admin/payments/[id]`
 * it did not spin. What it drew was a bare red `admin.scholarship.loadFailed`, which names the
 * wrong cause: the identical rejection is an application that is gone and one belonging to
 * another organisation, which the detail GET answers 404 for so that its existence is never
 * leaked. The shared state claims neither.
 */
import { screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

it('draws the not-found state and STOPS loading', async () => {
  renderCockpit({ role: 'admin', loadFails: true })
  await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
  expect(screen.queryByText('common.loading')).toBeNull()
  // The old sentence named a cause the rejection does not carry.
  expect(screen.queryByText('admin.scholarship.loadFailed')).toBeNull()
})

it('keeps loading until the application answers', async () => {
  // The happy path's FIRST paint, which must still read as waiting rather than as missing.
  const view = renderCockpit({ role: 'admin' })
  expect(screen.getByText('common.loading')).toBeTruthy()
  expect(screen.queryByTestId('record-not-found')).toBeNull()
  await view.findByText('Test Student 07')
})
