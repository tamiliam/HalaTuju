/* eslint-disable @next/next/no-img-element */
// Reviewer Guide — a short, friendly walkthrough of the B40 review process.
// Static English content for now (BM/Tamil to follow); images live in /public/reviewer-guide.
// Reviewers reach this only after signing in (gated by the admin layout), so it does not cover
// signing in — it opens with a welcome + a picture of the programme.

// `float`: only for an oddly tall (portrait) screenshot — it floats right and the
// text wraps so it doesn't dominate. Every other (landscape) image shows at natural
// size, stacked above its text.
const STEPS: { n?: number; title: string; body: React.ReactNode; img?: string; alt?: string; float?: boolean }[] = [
  {
    title: 'Before you start: set up your profile',
    body: (
      <>Open your <strong>Profile</strong> and set your <strong>language fluency</strong> (English, Bahasa Melayu,
      Tamil) — we use it to assign you students you can speak with comfortably. While you&rsquo;re there, decide
      whether to <strong>share your phone number</strong> with your students (on by default, so they know to expect
      your call; untick it to opt out). It takes a minute and only needs doing once.</>
    ),
  },
  {
    n: 1,
    title: 'Your applicants',
    body: (
      <>On <strong>B40 Applications</strong> you&rsquo;ll see <strong>only the applicants assigned to you</strong> —
      not everyone&rsquo;s. Each row shows the name, source, qualification, merit score and status.</>
    ),
    img: '/reviewer-guide/step1-list.png',
    alt: 'The B40 Applications list showing your assigned applicants',
  },
  {
    n: 2,
    title: 'Opening an applicant',
    body: (
      <>Click a name to open their review screen. Everything is on this one page: their details, the four
      checks, the documents, the interview, and your decision.</>
    ),
    img: '/reviewer-guide/step2-overview.png',
    alt: 'The applicant review screen and details',
  },
  {
    n: 3,
    title: 'The four checks',
    body: (
      <>Your review comes down to <strong>four facts</strong>: <strong>Identity</strong>,
      <strong> Academic record</strong>, <strong>Pathway</strong> (their study plan or offer), and
      <strong> Income (B40 need)</strong>. The &ldquo;Verification verdict&rdquo; shows what the system is
      confident about and what still needs your eye. Each tile is colour-coded:
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li><strong className="text-green-700">Green — Certain.</strong> The documents back it up.</li>
          <li><strong className="text-blue-700">Blue — Probable.</strong> Likely fine, but worth a glance.</li>
          <li><strong className="text-amber-700">Amber — Unsure.</strong> Needs your judgement.</li>
          <li><strong className="text-red-700">Red — Can&rsquo;t verify.</strong> The evidence is missing or
          unreadable — act on it (see the next step).</li>
        </ul></>
    ),
    img: '/reviewer-guide/step3-checks.png',
    alt: 'The Verification verdict showing the four checks',
  },
  {
    title: 'When a check isn’t green',
    body: (
      <>Green tiles you can move past quickly — your real work is the <strong>amber</strong> and <strong>red</strong>
      ones. You have three tools, in order of effort:
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li><strong>Read the document yourself</strong> (next step) — the system&rsquo;s reading is a starting
          point, not the last word.</li>
          <li><strong>Raise a query or request a document</strong> if something is missing or doesn&rsquo;t add
          up — the student replies by email.</li>
          <li><strong>Ask in the interview</strong> — best for anything that needs a conversation.</li>
        </ul>
        <span className="mt-2 block">A few common ones: a <strong>red Pathway</strong> usually means no offer
        letter yet — request it. An <strong>amber Income</strong> often means the STR proof isn&rsquo;t clearly
        approved (a SALINAN application-record is <em>not</em> proof) — ask for the MySTR &ldquo;Lulus&rdquo;
        status, or accept the salary route. An <strong>amber Academic</strong> means re-read the results slip
        against the grades. <strong>Don&rsquo;t pass weak evidence through</strong> — it&rsquo;s fairer to ask for
        a clean upload.</span></>
    ),
  },
  {
    n: 4,
    title: 'The documents behind each check',
    body: (
      <>The documents the student uploaded sit under those same four facts, each with the system&rsquo;s reading
      and a status. Click to view a document, or &ldquo;Re-run&rdquo; to read it again.</>
    ),
    img: '/reviewer-guide/step4-documents.png',
    alt: 'A student document opened for viewing',
  },
  {
    n: 5,
    title: 'The student profile',
    body: (
      <>The <strong>Student profile (draft)</strong> is a short summary written automatically from the
      student&rsquo;s own application — a helpful starting point, not the final word. It updates itself as the
      student answers questions, and is rewritten into the final version when you save your verdict. You can
      also expand <em>the student&rsquo;s own words</em> underneath.</>
    ),
    img: '/reviewer-guide/step5-profile.png',
    alt: 'The Student profile (draft) card',
  },
  {
    n: 6,
    title: 'Asking the student something',
    body: (
      <>If something&rsquo;s unclear, don&rsquo;t guess. <strong>Raise a query</strong> or
      <strong> request a document</strong> — the student gets an email and replies, and their answer appears in
      the <strong>Outstanding</strong> box. Best done before the interview so your conversation is focused.</>
    ),
    img: '/reviewer-guide/step6-outstanding.png',
    alt: 'The Outstanding box and the raise-a-query controls',
  },
  {
    title: 'Scheduling the interview',
    body: (
      <>On the applicant&rsquo;s page, use <strong>Interview scheduling</strong> to <strong>propose three
      times</strong> that suit you. The student picks one from their side, and HalaTuju automatically creates a
      <strong> Google Meet</strong> link and sends both of you a confirmation, plus reminders the day before and
      an hour before. You&rsquo;ll see the booked time and the Meet link once they&rsquo;ve chosen. If the student
      reschedules or cancels, you&rsquo;ll see the change — just propose fresh times if needed. It&rsquo;s a short
      video call (about 30&ndash;45 minutes); parents are welcome to join from home.
        <div className="mt-4 space-y-4">
          <figure className="m-0">
            <img src="/reviewer-guide/scheduling-1-propose.png" alt="Choosing interview times to propose on the calendar"
              className="block h-auto max-w-full rounded-lg border border-gray-200 shadow-sm" loading="lazy" />
            <figcaption className="mt-1 text-xs text-gray-500"><strong>1. Propose</strong> — pick a day, tick
            three times that suit you, then <em>Propose times</em>.</figcaption>
          </figure>
          <figure className="m-0">
            <img src="/reviewer-guide/scheduling-2-proposed.png" alt="The proposed times, waiting for the student to pick one"
              className="block h-auto max-w-full rounded-lg border border-gray-200 shadow-sm" loading="lazy" />
            <figcaption className="mt-1 text-xs text-gray-500"><strong>2. Waiting</strong> — your times sit here until
            the student picks one. Use <em>Propose alternative times</em> if you need to change them.</figcaption>
          </figure>
          <figure className="m-0">
            <img src="/reviewer-guide/scheduling-3-booked.png" alt="The booked interview time with a Join the video call button"
              className="block h-auto max-w-full rounded-lg border border-gray-200 shadow-sm" loading="lazy" />
            <figcaption className="mt-1 text-xs text-gray-500"><strong>3. Booked</strong> — once they choose, you see
            the time and a <em>Join the video call</em> button. <em>Reschedule</em> moves it to a new time.</figcaption>
          </figure>
        </div></>
    ),
  },
  {
    n: 7,
    title: 'The interview stage',
    body: (
      <>When you&rsquo;re ready to talk to the student, the <strong>Interview Stage</strong> gathers your agenda
      in one place so nothing from the earlier checks is lost: the pre-interview flags, any
      <strong> carried-over queries</strong> the student didn&rsquo;t answer (ask them in the conversation), the
      points the verdict marks <strong>&ldquo;confirm at interview&rdquo;</strong> (an uncertain grade, an
      identity that couldn&rsquo;t be auto-checked, or income that needs a fuller picture), and a standing
      <strong> Motivation &amp; grit</strong> section — always worth exploring, and flagged for extra attention when
      the statement of intent is thin. You can also tap <strong>Suggest interview questions</strong> (or
      <strong> Generate more</strong>) and ask your own. After each point, jot <strong>one line</strong> on what you
      found, then <strong>Submit interview findings</strong>. One note: if a point mentions income reading above the
      line, that&rsquo;s for your judgement — explore the family&rsquo;s real situation, don&rsquo;t quote a figure at
      the student.</>
    ),
    img: '/reviewer-guide/step7-interview.png',
    alt: 'The Interview Stage with suggested questions',
  },
  {
    n: 8,
    title: 'Your decision',
    body: (
      <>In the <strong>Decision</strong> card you:
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>rate the AI&rsquo;s verification — if you think it got a fact right, give it a <strong>Pass</strong>,
          otherwise a <strong>Fail</strong>, for each of the four facts;</li>
          <li>set a <strong>recommended assistance amount</strong> on the slider (an estimated need is shown to
          guide you);</li>
          <li>write a short <strong>conclusion</strong>;</li>
          <li>select <strong>Approve</strong> or <strong>Decline</strong>; and finally</li>
          <li>click <strong>Save verdict &amp; generate final profile</strong>.</li>
        </ul>
        <span className="mt-2 block"><strong>Pass/Fail is not your decision.</strong> It only says whether the AI
        <em> read each fact correctly</em> — it&rsquo;s separate from Approve/Decline. You can Pass all four facts
        and still <strong>Decline</strong> (for example, the income is verified but sits above the B40 line).</span>
        <span className="mt-2 block rounded-lg border border-amber-200 bg-amber-50 p-3"><strong>Save is a one-way
        step.</strong> It records the decision, emails the student, and sends the final profile to sponsors — and a
        reviewer can&rsquo;t undo it afterwards (only a super-admin can reopen a case). Check the facts before you
        save.</span></>
    ),
    img: '/reviewer-guide/step8-decision.png',
    alt: 'The Decision card with the four facts, amount slider and buttons',
    float: true,   // portrait screenshot — float right + wrap so it doesn't dominate
  },
]

export default function ReviewerGuidePage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900">Your part in the B40 programme</h1>

      <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-5 text-sm leading-relaxed text-gray-700">
        <p className="text-base font-semibold text-gray-900">Congratulations — and thank you for joining us as a reviewer.</p>
        <p className="mt-2">
          You&rsquo;re helping the <strong>B40 assistance programme</strong>, which supports students from
          lower-income families to continue into further study. Here&rsquo;s where your part fits:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Students <strong>apply online</strong> at halatuju.xyz.</li>
          <li>The system checks eligibility and <strong>shortlists</strong> those who qualify — a B40 background,
          a solid academic record, and a clear study pathway.</li>
          <li>Shortlisted students are then <strong>guided to complete</strong> their application: uploading
          documents, confirming family and income details, and answering any follow-up questions.</li>
          <li>When an application is ready, it comes to <strong>you</strong> — to check the key facts, talk to the
          student if needed, and recommend a decision.</li>
        </ul>
        <p className="mt-2">This guide shows you how. It takes about 5 minutes.</p>
      </div>

      <div className="mt-8 space-y-10">
        {STEPS.map((s, i) => (
          <section key={s.title}>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                {i + 1}
              </span>
              {s.title}
            </h2>
            {/* Default: image at natural size, stacked above the text. Only a `float`
                step (a tall portrait screenshot) floats right + wraps so it doesn't
                dominate. overflow-hidden contains the float. */}
            <div className="mt-2 overflow-hidden">
              {s.img && (
                <img
                  src={s.img}
                  alt={s.alt}
                  className={
                    'mb-3 block h-auto max-w-full rounded-lg border border-gray-200 shadow-sm'
                    + (s.float ? ' sm:float-right sm:ml-6 sm:mb-2 sm:max-w-[340px]' : '')
                  }
                  loading="lazy"
                />
              )}
              <div className="text-sm leading-relaxed text-gray-700">{s.body}</div>
            </div>
          </section>
        ))}
      </div>

      <div className="mt-10 rounded-2xl border border-gray-200 bg-white p-5 text-sm leading-relaxed text-gray-700">
        <strong>Thank you.</strong> Take your time, check the facts, and use a query or the interview whenever
        you&rsquo;re unsure. Your care makes a real difference to these students.
      </div>
    </div>
  )
}
