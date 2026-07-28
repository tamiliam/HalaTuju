import type { ManualChapter } from './types'

/** Org admin chapter — running the programme. Every power traces to role-matrix.md. */
export const roleOrgAdmin: ManualChapter = {
  slug: 'role-org-admin',
  title: 'Organisation admin',
  group: 'role',
  role: 'org_admin',
  blurb: 'Run your programme: your team, your cases, your sponsors and your money.',
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
        <>Open <strong>Staff</strong> from the menu to build your
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
      alt: 'The Staff table with invite and revoke controls (placeholder)',
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
      anchor: 'org-admin-sponsor-record',
      title: 'A sponsor’s record and their wallet',
      body: (
        <>Click a sponsor&rsquo;s name to open their whole record: what they have <strong>given</strong>, what is
        already <strong>committed</strong> to students, what is still <strong>available</strong> — one set of
        figures per gift, because a wallet belongs to a gift and the money is not interchangeable between them.
        Below that sit the credits behind those figures, the students they are funding (by the anonymous code the
        sponsor sees, so you and they mean the same person), and the people they have invited.
        <br /><br />
        <strong>Wallet credits are the money coming in.</strong> A sponsor transfers to us off the platform, and a
        <strong> general admin</strong> records it against the gift with the bank transfer reference and signs as
        recorder. <strong>You countersign</strong> — and only then is that money spendable on a student. Every
        signature must be a different person and each typed name must match that account&rsquo;s name exactly. If
        your organisation has a <strong>finance admin</strong> there is a middle step, and until they have checked
        it you will see &ldquo;waiting for the finance check&rdquo; instead of a countersign button — the same
        chain as a payment run.
        <br /><br />
        You cannot record a credit yourself, deliberately: the person who opens a chain cannot also close it. An
        unconfirmed credit can be <strong>voided</strong> if it was mis-keyed; a confirmed one never can, and is
        corrected by a balancing entry instead.</>
      ),
    },
    {
      anchor: 'org-admin-sponsor-emails',
      title: 'What sponsors hear from us',
      body: (
        <>Open <strong>Sponsors</strong> and switch to the <strong>Emails</strong> badge. Nine
        emails sit there — a welcome when someone registers, the outcome of your vetting decision
        either way, a confirmation when a gift is recorded, the alerts about students waiting, and
        the invitation a sponsor sends to a friend. Each one has its own switch and its own
        wording, and you can edit both.
        <br /><br />
        This exists because until now a sponsor was <em>approved and never told</em>. The decision
        flipped a field on our side and nothing reached them.
        <br /><br />
        <strong>Two things have to be true before anything sends:</strong> the feature must be
        turned on for the whole programme, and that particular email must be switched on. Until
        the first is done the panel says so plainly at the top — your switches still save, but
        nothing goes out. Three of the nine are <em>already</em> reaching sponsors through the
        older system; those are marked <strong>Sending today</strong>, so an unlit switch never
        means an email is silent when it isn&rsquo;t.
        <br /><br />
        <strong>Two things the editor will refuse to save.</strong> A detail we cannot fill in for
        that email (the chips under the box are the ones that work — anything else would print as
        <code>{'{'}like_this{'}'}</code> in someone&rsquo;s inbox, and the same list is what stops
        a template ever naming a student). And three kinds of wording: any claim about
        <strong> tax relief</strong> — we hold no approval for that and it is the one line that
        could cost a donor money — anything calling someone &ldquo;your student&rdquo;, because a
        sponsor funds a student rather than acquiring one, and pressure wording, because these are
        account emails and not marketing.</>
      ),
    },
    {
      anchor: 'org-admin-administration',
      title: 'Your organisation in the menu',
      body: (
        <>The menu — the strip of icons on the left, which opens when you point at it — groups everything
        by what it belongs to. Your organisation&rsquo;s group holds
        <strong> Overview</strong>, <strong>Staff</strong>, <strong>Sponsors</strong>, <strong>Payments</strong>,
        <strong> Contracts</strong>, <strong>Sources</strong> and <strong>Billing &amp; usage</strong> (marked
        <em> soon</em> until metering is switched on). Below it sits your programme&rsquo;s own group, with the
        applications. Platform-only tools — adding organisations or referral partners — never appear for you;
        those stay with the HalaTuju platform team.</>
      ),
      img: '/manual/org-admin-administration.png',
      alt: 'The organisation group in the menu (placeholder)',
    },
    {
      anchor: 'org-admin-payments',
      title: 'Payment runs',
      body: (
        <>Each month a payment run is built in <strong>Payments</strong>. It lists the students
        who qualify for that month, with the amount each is due, and greys out the rest with the reason (no
        eWallet confirmed yet, already paid this month, no balance left, and so on). Somebody prepares and signs
        it, then <strong>you countersign</strong>. Only at your countersignature is the payment instruction
        emailed to Vircle with the file attached — nothing moves before that.</>
      ),
      img: '/manual/org-admin-payments.png',
      alt: 'A payment run awaiting countersignature (placeholder)',
    },
    {
      anchor: 'org-admin-payments-signing',
      title: 'Who signs, and what breaks a signature',
      body: (
        <>Every signature on a run must belong to a <strong>different person</strong>, and each typed name must
        match that account&rsquo;s name exactly. If your organisation has a <strong>finance admin</strong>, there
        is a middle step: the run must be <em>checked</em> by finance before you can countersign, and until then
        you&rsquo;ll see &ldquo;waiting for the finance check&rdquo;. You can appoint one yourself from
        <strong> Staff</strong>, inviting them as <strong>Finance</strong>; the moment their account is active the step applies, including
        to a run already sitting in front of you. If you have no finance admin, the chain is just the two
        signatures. <strong>Editing a run after any signature returns it to draft and clears every signature
        collected so far</strong> — deliberately, so nobody signs one list and a different one goes out.</>
      ),
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
            pathway. (The <strong>Finance</strong> role, which you can appoint yourself, checks payment runs —
            it does not set award amounts.)</li>
            <li><strong>Countersigning the bursary agreement.</strong></li>
            <li><strong>Appointing another organisation admin, or adding an organisation</strong> — ask the
            platform team and they&rsquo;ll set it up.</li>
          </ul></>
      ),
    },
  ],
}
