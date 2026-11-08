/**
 * @jest-environment jsdom
 *
 * A2.1: the final profile is written in the BACKGROUND after the verdict is saved (the
 * `finalise-profiles` cron), so the card says so while it waits, and says so plainly if the
 * retries ran out. The draft stays on screen in both cases.
 */
import { render, screen } from '@testing-library/react'
import { GeneratedProfile } from './GeneratedProfile'
import { buildApplicationDetail, buildSponsorProfile } from '@/test/adminApplicationDetail'
import type { AdminSponsorProfile } from '@/lib/admin-api'

const t = (k: string) => k

const renderCard = (profile: AdminSponsorProfile) => render(
  <GeneratedProfile app={buildApplicationDetail('interviewing')} t={t as never} profile={profile}
    genLang="en" setGenLang={jest.fn()} busy="" error="" decisionReopened={false}
    showOwnWords={false} setShowOwnWords={jest.fn()} />)

const DRAFT = { final_markdown: '', current_markdown: 'A determined SPM leaver.' }

it('pending: the card says the final profile is being written, and keeps the draft', () => {
  renderCard(buildSponsorProfile({ ...DRAFT, finalise_state: 'pending' }))
  expect(screen.getByText('admin.scholarship.profileFinalising')).toBeTruthy()
  expect(screen.queryByText('admin.scholarship.profileFinaliseFailed')).toBeNull()
  expect(screen.getByText('A determined SPM leaver.')).toBeTruthy()
})

it('failed: the card says the retries ran out, and keeps the draft', () => {
  renderCard(buildSponsorProfile({ ...DRAFT, finalise_state: 'failed' }))
  expect(screen.getByText('admin.scholarship.profileFinaliseFailed')).toBeTruthy()
  expect(screen.queryByText('admin.scholarship.profileFinalising')).toBeNull()
  expect(screen.getByText('A determined SPM leaver.')).toBeTruthy()
})

it('drafting (A2.3b): no text yet, so the card says the first draft is on its way', () => {
  renderCard(buildSponsorProfile({ final_markdown: '', current_markdown: '', finalise_state: 'drafting' }))
  expect(screen.getByText('admin.scholarship.profileDrafting')).toBeTruthy()
  expect(screen.queryByText('admin.scholarship.profilePending')).toBeNull()
})

it('drafting with a draft already there (Generate pressed meanwhile): the draft, no note', () => {
  renderCard(buildSponsorProfile({ ...DRAFT, finalise_state: 'drafting' }))
  expect(screen.queryByText('admin.scholarship.profileDrafting')).toBeNull()
  expect(screen.getByText('A determined SPM leaver.')).toBeTruthy()
})

it('nothing queued (or an older API that sends no state): no note at all', () => {
  for (const state of ['', undefined] as const) {
    const { unmount } = renderCard(buildSponsorProfile({ ...DRAFT, finalise_state: state }))
    expect(screen.queryByText('admin.scholarship.profileFinalising')).toBeNull()
    expect(screen.queryByText('admin.scholarship.profileFinaliseFailed')).toBeNull()
    unmount()
  }
})
