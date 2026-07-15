import type { ManualChapter } from './types'

/** Reviewer chapter — the existing reviewer guide, re-homed as a role chapter.
 *  Sponsor-vetting is deliberately absent: that power moved to the org admin. */
export const roleReviewer: ManualChapter = {
  slug: 'role-reviewer',
  title: 'Reviewer',
  group: 'role',
  role: 'reviewer',
  blurb: 'Check the facts on your assigned applicants and recommend a decision.',
  sections: [
    {
      anchor: 'reviewer-profile',
      title: 'Set up your profile',
      body: (
        <>Open your <strong>Profile</strong> and set your <strong>language fluency</strong> (English, Bahasa
        Melayu, Tamil) — we use it to assign you students you can speak with comfortably. While you&rsquo;re there,
        decide whether to <strong>share your phone number</strong> with your students (on by default; untick to opt
        out). It takes a minute and only needs doing once.</>
      ),
    },
    {
      anchor: 'reviewer-your-applicants',
      title: 'Your applicants',
      body: (
        <>On <strong>B40 Applications</strong> you&rsquo;ll see <strong>only the applicants assigned to you</strong>
        — not everyone&rsquo;s. Each row shows the name, source, qualification, merit score and status. Click a
        name to open the review screen — everything is on that one page.</>
      ),
      img: '/reviewer-guide/step1-list.png',
      alt: 'The B40 Applications list showing your assigned applicants',
    },
    {
      anchor: 'reviewer-working-a-case',
      title: 'Working a case',
      body: (
        <>Your review is the <strong>four checks</strong> (see Basics). Green tiles move past quickly; your real
        work is the amber and red ones. You have three tools, in order of effort: <strong>read the document
        yourself</strong>; <strong>raise a query or request a document</strong> (the student replies by email); or
        <strong> ask in the interview</strong>. Don&rsquo;t pass weak evidence through — it&rsquo;s fairer to ask
        for a clean upload.</>
      ),
      img: '/reviewer-guide/step2-overview.png',
      alt: 'The applicant review screen and details',
    },
    {
      anchor: 'reviewer-profile-card',
      title: 'The student profile',
      body: (
        <>The <strong>Student profile (draft)</strong> is a short summary written automatically from the
        student&rsquo;s own application — a helpful starting point, not the final word. It updates as the student
        answers questions, and is rewritten into the final version when you save your verdict. You can expand
        <em> the student&rsquo;s own words</em> underneath.</>
      ),
      img: '/reviewer-guide/step5-profile.png',
      alt: 'The Student profile (draft) card',
    },
    {
      anchor: 'reviewer-queries',
      title: 'Asking the student something',
      body: (
        <>If something&rsquo;s unclear, don&rsquo;t guess. <strong>Raise a query</strong> or <strong>request a
        document</strong> — the student gets an email and replies, and their answer appears in the
        <strong> Outstanding</strong> box. Best done before the interview so your conversation is focused.</>
      ),
      img: '/reviewer-guide/step6-outstanding.png',
      alt: 'The Outstanding box and the raise-a-query controls',
    },
    {
      anchor: 'reviewer-scheduling',
      title: 'Scheduling the interview',
      body: (
        <>On the applicant&rsquo;s page, use <strong>Interview scheduling</strong> to <strong>propose three
        times</strong> that suit you. The student picks one, and HalaTuju automatically creates a
        <strong> Google Meet</strong> link and sends both of you a confirmation, plus reminders the day before and
        an hour before. If the student reschedules or cancels, you&rsquo;ll see the change — just propose fresh
        times if needed. It&rsquo;s a short video call (about 30&ndash;45 minutes); parents are welcome to join.</>
      ),
    },
    {
      anchor: 'reviewer-interview-stage',
      title: 'The interview stage',
      body: (
        <>When you&rsquo;re ready to talk to the student, the <strong>Interview Stage</strong> gathers your agenda
        in one place: the pre-interview flags, any <strong>carried-over queries</strong> the student didn&rsquo;t
        answer, the points the verdict marks <strong>&ldquo;confirm at interview&rdquo;</strong>, and a standing
        <strong> Motivation &amp; grit</strong> section. Tap <strong>Suggest interview questions</strong> (or
        <strong> Generate more</strong>) and ask your own. After each point, jot <strong>one line</strong> on what
        you found, then <strong>Submit interview findings</strong>. If a point mentions income above the line,
        that&rsquo;s for your judgement — explore the family&rsquo;s real situation, don&rsquo;t quote a figure.</>
      ),
      img: '/reviewer-guide/step7-interview.png',
      alt: 'The Interview Stage with suggested questions',
    },
    {
      anchor: 'reviewer-decision',
      title: 'Your decision',
      body: (
        <>In the <strong>Decision</strong> card you rate the AI&rsquo;s verification (<strong>Pass</strong> or
        <strong> Fail</strong> per fact — this only says whether the AI <em>read</em> each fact correctly, and is
        separate from your recommendation), set a <strong>recommended assistance amount</strong>, write a short
        <strong> conclusion</strong>, select <strong>Approve</strong> or <strong>Decline</strong>, and click
        <strong> Save verdict &amp; generate final profile</strong>. You can Pass all four facts and still Decline
        (for example, income is verified but sits above the B40 line).
          <span className="mt-2 block rounded-lg border border-amber-200 bg-amber-50 p-3"><strong>Save is a
          one-way step from your side.</strong> It records the decision and sends the case on for QC; only a
          super-admin can reopen it afterwards. Check the facts before you save.</span></>
      ),
      img: '/reviewer-guide/step8-decision.png',
      alt: 'The Decision card with the four facts, amount slider and buttons',
      float: true,
    },
  ],
}
