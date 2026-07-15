import type { ManualChapter } from './types'

/** Org admin chapter — running the programme. Every power traces to role-matrix.md. */
export const roleOrgAdmin: ManualChapter = {
  slug: 'role-org-admin',
  title: 'Organisation admin',
  group: 'role',
  role: 'org_admin',
  blurb: 'Run your programme: your team, your cases, sponsors and the Administration panel.',
  sections: [
    {
      anchor: 'org-admin-overview',
      title: 'Running your programme',
      body: (
        <>As the <strong>organisation admin</strong> you run your programme end-to-end within your own
        organisation. You see every application, you manage your team, you can act on and QC cases, and you vet
        sponsors. Everything you do is scoped to <strong>your organisation only</strong> — you never see or touch
        another organisation&rsquo;s data.</>
      ),
    },
    {
      anchor: 'org-admin-team',
      title: 'Your team',
      body: (
        <>Open <strong>Administration</strong> → <strong>Invite reviewers &amp; admins</strong> to build your
        team. You can invite three programme roles into your organisation:
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li><strong>Reviewer</strong> — works the applicants you assign them.</li>
            <li><strong>View-only admin</strong> — sees everything in your organisation, read-only.</li>
            <li><strong>QC</strong> — the second pair of eyes (and an overflow reviewer).</li>
          </ul>
          <span className="mt-2 block">You can <strong>Resend</strong> a sign-in invite or <strong>Revoke</strong>
          (and later restore) access from the staff table. One safeguard: you can&rsquo;t revoke the
          <strong> last</strong> organisation admin — the Revoke option simply isn&rsquo;t offered on the sole
          admin, so your organisation is never left without one.</span></>
      ),
      img: '/manual/org-admin-team.png',
      alt: 'The Administration staff table with invite and revoke controls (placeholder)',
    },
    {
      anchor: 'org-admin-assigning',
      title: 'Assigning applicants',
      body: (
        <>On <strong>B40 Applications</strong> you get an <strong>Assigned</strong> column with an inline control
        to give a case to one of <em>your</em> reviewers (and the same control sits on each applicant&rsquo;s
        page). You can only assign your own organisation&rsquo;s active reviewers. A case can only change hands
        while a review is live (Awaiting review / Interviewing) — the control is disabled otherwise.</>
      ),
      img: '/manual/org-admin-assign.png',
      alt: 'The Assigned column and inline reviewer control (placeholder)',
    },
    {
      anchor: 'org-admin-acting',
      title: 'Acting on cases, and QC',
      noConflictBanner: true,
      body: (
        <>You can act on <strong>any</strong> case in your organisation — the three action boxes (outstanding
        checks, interview stage, recommendation) work for you like a reviewer&rsquo;s, and you can QC too. The
        <strong> no-conflict rule</strong> applies to you exactly as it does to a QC: you can never QC a case whose
        verdict you recorded, and never QC a case you reviewed — it must go to someone else. That&rsquo;s
        two-person control, and it protects the integrity of every award.</>
      ),
    },
    {
      anchor: 'org-admin-sponsors',
      title: 'Vetting sponsors',
      body: (
        <>On <strong>Sponsors</strong> you review the organisations and people who want to fund students. You can
        <strong> Approve</strong>, <strong>Reject</strong> or <strong>Suspend</strong> a sponsor account — approval
        lets them into the funding flow; suspend pauses an approved sponsor. (This vetting used to sit with
        reviewers; it now belongs to you.)</>
      ),
      img: '/manual/org-admin-sponsors.png',
      alt: 'The Sponsors vetting list with approve/reject/suspend (placeholder)',
    },
    {
      anchor: 'org-admin-administration',
      title: 'The Administration panel',
      body: (
        <>The <strong>Administration</strong> page is your control room. Its <strong>Organisation</strong> section
        holds your staff management and a <strong>Billing &amp; usage</strong> card (marked <em>coming soon</em> —
        it will show your programme&rsquo;s costs and usage once metering is switched on). The platform-only tools
        (adding organisations, referral partners) don&rsquo;t appear for you — those stay with the HalaTuju
        platform team.</>
      ),
      img: '/manual/org-admin-administration.png',
      alt: 'The Administration panel organisation section (placeholder)',
    },
    {
      anchor: 'org-admin-what-stays-platform',
      title: 'What stays with the platform',
      body: (
        <>So expectations are clear, a few powers are deliberately kept with the HalaTuju platform team (not any
        organisation role):
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li><strong>Reopening a recorded decision</strong> (and cancelling a reopen).</li>
            <li><strong>Setting the award amount</strong> — a reviewer recommends; the amount is fixed by
            pathway. (A dedicated Finance role will take money powers when payouts go live.)</li>
            <li><strong>Countersigning the bursary agreement.</strong></li>
            <li><strong>Appointing another organisation admin, or adding an organisation</strong> — ask the
            platform team and they&rsquo;ll set it up.</li>
          </ul></>
      ),
    },
  ],
}
