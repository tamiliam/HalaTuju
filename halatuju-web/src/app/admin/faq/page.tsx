// Reviewer FAQ — administrative + reviewing questions. Static English for now (BM/Tamil to follow).
// Reached only after sign-in (gated by the admin layout). Collapsible accordion via native
// <details> (no client JS needed).

type QA = { q: React.ReactNode; a: React.ReactNode }

const ADMIN: QA[] = [
  {
    q: <>Is this paid? Do reviewers get any compensation?</>,
    a: <>No — reviewing is <strong>voluntary</strong>, and there&rsquo;s no payment. Thank you for giving your
      time to these students.</>,
  },
  {
    q: <>How do I sign in next time?</>,
    a: <>Go to <strong>halatuju.xyz/admin/login</strong> and enter your email and password, or sign in with
      Google.</>,
  },
  {
    q: <>How do I change or reset my password?</>,
    a: <>On the sign-in page, click <strong>Forgot password</strong>, enter your email, and follow the link we
      send to set a new one.</>,
  },
  {
    q: <>Does my email have to be Gmail?</>,
    a: <>No — any email address works.</>,
  },
  {
    q: <>Is the information I see confidential?</>,
    a: <>Yes. Treat everything about an applicant as <strong>private</strong> — only discuss it with the
      HalaTuju team. Please don&rsquo;t download, share or keep applicant details.</>,
  },
  {
    q: <>Why does my profile ask for my languages?</>,
    a: <>So we can assign you students you can speak with comfortably. Set your fluency in English,
      Bahasa Melayu and Tamil on your <strong>Profile</strong> — we use it to match you to applicants
      whose preferred language you share.</>,
  },
  {
    q: <>Will my phone number be shared with students?</>,
    a: <>Your number may be shared with the students assigned to you, so they know to expect your
      call. It&rsquo;s on by default — you can <strong>opt out anytime</strong> on your Profile
      (untick &ldquo;Share my phone number…&rdquo;) and we&rsquo;ll leave it out.</>,
  },
  {
    q: <>I&rsquo;m stuck, or something looks wrong with my account — whom do I contact?</>,
    a: <>Email the HalaTuju team at <strong>help@halatuju.xyz</strong> and we&rsquo;ll help.</>,
  },
]

const REVIEWING: QA[] = [
  {
    q: <>Why do I only see some applicants?</>,
    a: <>You see <strong>only the applicants assigned to you</strong>, so you can focus on your own. That&rsquo;s
      normal.</>,
  },
  {
    q: <>What do the application statuses mean?</>,
    a: <>In order: <strong>Shortlisted</strong> — passed the first checks and invited to complete their
      application; <strong>Awaiting review</strong> — the student has confirmed their details and documents;
      the case is now with us and not yet reviewed; <strong>Interviewing</strong> — interview times proposed or
      booked; <strong>Interviewed</strong> — the interview is done and you&rsquo;ve submitted your findings;
      <strong> Accepted</strong> / <strong>Rejected</strong> — your decision is recorded. Most of your work is on
      the <em>Awaiting review</em> and <em>Interviewing</em> ones.</>,
  },
  {
    q: <>What is the &ldquo;Student profile (draft)&rdquo;?</>,
    a: <>A short summary written automatically from the student&rsquo;s own application. It&rsquo;s a helpful
      starting point — always check it against the uploaded documents before relying on it.</>,
  },
  {
    q: <>Should I just trust the AI?</>,
    a: <>No — the AI gives a <em>suggestion</em> for each of the four facts and a draft profile.
      <strong> You decide.</strong> Your Pass/Fail rating, based on the documents and your interview, also helps
      improve the AI over time.</>,
  },
  {
    q: <>What do the four checks mean?</>,
    a: <>Identity (is this really them), Academic record (do the grades match the slip), Pathway (is their study
      plan or offer in order), and Income (are they genuinely B40 / in need).</>,
  },
  {
    q: <>How do I judge the Income (B40) check? It&rsquo;s the hardest one.</>,
    a: <>There are two routes. <strong>STR route:</strong> the family receives Sumbangan Tunai Rahmah — the proof
      is an <em>approved</em> MySTR record. A <strong>SALINAN application-record is not proof of approval</strong>;
      if the status isn&rsquo;t clearly &ldquo;Lulus&rdquo;, ask for the MySTR Semakan Status / Dashboard showing
      approval, or the approval letter. <strong>Salary route:</strong> payslips / EPF show household income, judged
      per head against the B40 line. When it&rsquo;s genuinely borderline or you can&rsquo;t tell, that&rsquo;s
      what the interview is for — don&rsquo;t force a verdict on weak evidence.</>,
  },
  {
    q: <>How do I ask the student a question?</>,
    a: <>Use <strong>Raise a query</strong> or <strong>Request a document</strong>. They get an email; their
      reply shows in the <strong>Outstanding</strong> box.</>,
  },
  {
    q: <>What does &ldquo;Save verdict &amp; generate final profile&rdquo; do?</>,
    a: <>It records your decision and creates the final, polished profile a sponsor will see.</>,
  },
  {
    q: <>What&rsquo;s the difference between rating Pass/Fail and approving?</>,
    a: <>The <strong>Pass/Fail</strong> on each fact says whether the <em>AI read that fact correctly</em> — it
      helps us measure and improve the AI. <strong>Approve / Decline</strong> is your actual recommendation on the
      student. They&rsquo;re separate: you can Pass all four facts and still <strong>Decline</strong> — for
      instance, the income is verified but sits above the B40 line.</>,
  },
  {
    q: <>Can I undo a decision after I Save?</>,
    a: <>Not as a reviewer — <strong>Save is final from your side</strong> (it emails the student and sends the
      profile to sponsors). If something genuinely needs changing, contact the HalaTuju team
      (<strong>help@halatuju.xyz</strong>); a super-admin can reopen the case. So check the facts before you
      save.</>,
  },
  {
    q: <>What&rsquo;s the recommended amount for?</>,
    a: <>It&rsquo;s your suggestion of how much assistance would help, set on the slider. It guides the
      sponsor.</>,
  },
  {
    q: <>The student&rsquo;s offer letter doesn&rsquo;t match their stated pathway — what do I do?</>,
    a: <>Note it and ask them in the interview (or raise a query). They may have updated their plan; the
      conversation settles it. You can also ask them to upload the latest offer letter, which replaces the
      old one.</>,
  },
  {
    q: <>The student is already in college and has completed a semester or two — should I ask for more?</>,
    a: <>If they have completed one or more semesters and have their results (CGPA), you may ask them to upload
      their latest result. If it is satisfactory (above 3.0), you may consider recommending them for support.</>,
  },
  {
    q: <>How do the suggested interview questions work?</>,
    a: <>In the <strong>Interview Stage</strong>, tap <strong>Suggest interview questions</strong> and the system
      proposes a few, drawn from this student&rsquo;s record and anything still unverified — tap
      <strong> Generate more</strong> for additional ones. They&rsquo;re a prompt, not a script: ask your own
      questions too, and after each point jot <strong>one line</strong> on what you found before you submit.</>,
  },
  {
    q: <>What&rsquo;s on the interview agenda, and why is there always a &ldquo;Motivation &amp; grit&rdquo; point?</>,
    a: <>The agenda pulls together everything the earlier checks raised so none of it slips through:
      the pre-interview flags, any <strong>queries the student didn&rsquo;t answer</strong> (ask them in the
      conversation), the points the verdict marked <strong>&ldquo;confirm at interview&rdquo;</strong> (an
      uncertain grade, an identity that couldn&rsquo;t be auto-checked, or income that needs a fuller picture),
      and a standing <strong>Motivation &amp; grit</strong> point. Motivation is deliberately a human judgement —
      the system never scores it — so it&rsquo;s always on the agenda, and it&rsquo;s flagged for extra attention
      when the student&rsquo;s written statement of intent is thin. If a point notes income reading above the line,
      treat it as <strong>your</strong> cue to explore the family&rsquo;s real circumstances — please don&rsquo;t
      quote the figure back to the student.</>,
  },
  {
    q: <>How do I schedule the interview?</>,
    a: <>On the applicant&rsquo;s page, use <strong>Interview scheduling</strong> to propose two or three times.
      The student picks one, and a <strong>Google Meet</strong> link is created automatically — you and the
      student both get a confirmation, plus reminders the day before and an hour before. The booked time and
      Meet link appear on the applicant&rsquo;s page once they&rsquo;ve chosen.</>,
  },
  {
    q: <>What if the student needs a different time, or doesn&rsquo;t book?</>,
    a: <>They can <strong>reschedule or cancel themselves</strong> up to a few hours before, and you&rsquo;ll see
      the updated time. If they cancel, just propose fresh times. If they haven&rsquo;t booked yet, the times you
      proposed are simply waiting for them to choose.</>,
  },
  {
    q: <>Do I need to create the Google Meet link myself?</>,
    a: <>No — it&rsquo;s generated automatically when the student books, and shared with both of you. Parents are
      welcome to join the video call from home; it usually takes about 30&ndash;45 minutes.</>,
  },
]

function Item({ item }: { item: QA }) {
  return (
    <details className="group rounded-xl border border-gray-200 bg-white transition-colors open:border-blue-200 open:bg-blue-50/30 hover:border-gray-300">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 font-medium text-gray-900 [&::-webkit-details-marker]:hidden">
        <span>{item.q}</span>
        <svg
          className="h-5 w-5 shrink-0 text-gray-400 transition-transform duration-200 group-open:rotate-180 group-open:text-blue-500"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
        </svg>
      </summary>
      <div className="px-4 pb-4 text-sm leading-relaxed text-gray-600">{item.a}</div>
    </details>
  )
}

function Section({
  title, items, icon, tint,
}: { title: string; items: QA[]; icon: React.ReactNode; tint: string }) {
  return (
    <section className="mt-8">
      <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${tint}`}>{icon}</span>
        {title}
        <span className="text-sm font-normal text-gray-400">· {items.length}</span>
      </h2>
      <div className="mt-3 space-y-2.5">
        {items.map((item, i) => <Item key={i} item={item} />)}
      </div>
    </section>
  )
}

export default function ReviewerFaqPage() {
  return (
    <div className="max-w-2xl">
      {/* Friendly header */}
      <div className="flex items-start gap-4 rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
        </span>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Frequently asked questions</h1>
          <p className="mt-1 text-sm text-gray-600">
            Quick answers for reviewers. Tap a question to expand it — and see the <strong>Guide</strong> for a
            step-by-step walkthrough.
          </p>
        </div>
      </div>

      <Section
        title="Administrative" items={ADMIN} tint="bg-amber-100 text-amber-700"
        icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 0 1 1.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 0 1-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 0 1-.12-1.45l.527-.737c.25-.35.272-.806.108-1.204-.165-.397-.506-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.108-1.204l-.526-.738a1.125 1.125 0 0 1 .12-1.45l.773-.773a1.125 1.125 0 0 1 1.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894Z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
        </svg>}
      />
      <Section
        title="Reviewing" items={REVIEWING} tint="bg-blue-100 text-blue-700"
        icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>}
      />
    </div>
  )
}
