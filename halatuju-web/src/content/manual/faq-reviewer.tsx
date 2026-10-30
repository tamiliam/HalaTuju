/** The reviewer FAQ — moved out of `faq.tsx` whole (2026-10-30) when that file passed the 600-line
 *  standard. Moves only: every Q&A below is the line it was. */
import type { QA } from './types'

export const REVIEWER_FAQ: QA[] = [
    {
      q: <>I land on an <strong>Overview</strong> now instead of the list. What is it?</>,
      a: <>It is your own work, gathered on one page: the cases currently with you, <strong>the date each
        verdict is due</strong>, and how many are due soon or already overdue. It is the first entry under your
        gift in the menu, and you can go straight to <strong>Applications</strong> from there as before &mdash;
        nothing was taken away. The due dates are the same ones the reminder emails quote. You will not find
        money or the programme&rsquo;s overall figures on it; those belong to the people who run the gift.</>,
    },
    {
      q: <>An STPM student&rsquo;s Academic card now shows <strong>SPM prerequisites</strong>. What are they?</>,
      a: <>The SPM grades an STPM student enters alongside her STPM results, because many degree courses also
        set SPM requirements. Since 2 October 2026 they are saved to her profile instead of only to her
        browser, so they appear on the card once she has entered or re-saved them. They are what she typed;
        check them against her SPM slip as you would her other grades. A student who has not entered any
        shows none.</>,
    },
    {
      q: <>What is a <strong>Matriculation, Asasi or Diploma</strong> student on the Academic card?</>,
      a: <>Since 26 October 2026 a student may enter Matriculation, Asasi (Foundation) or Diploma results
        instead of STPM. They count as <strong>STPM-equivalent</strong>: the gift&rsquo;s minimum CGPA is
        tested on her overall CGPA, and her merit is that CGPA ÷ 4 × 100, as for an STPM student. The card
        shows the qualification with her overall CGPA (for example <strong>Matriculation · CGPA 3.47</strong>),
        the CGPA as printed on her results, her co-curriculum score (Matriculation and Asasi: the overall CGPA
        is 90% CGPA and 10% co-curriculum; a Diploma&rsquo;s overall CGPA is its CGPA as it is), her MUET band
        and the SPM grades she entered. Only a diploma from a <strong>public</strong> institution counts; a
        private-college diploma does not qualify. Her results document is the separate
        <strong> STPM / Matriculation / Asasi / Diploma results</strong> upload (see the next question).</>,
    },
    {
      q: <>Which <strong>results</strong> must a student upload, and what does the Academic card check?</>,
      a: <>It follows the course she has chosen. Bound for a <strong>university degree</strong> with STPM,
        Matriculation, Asasi or Diploma results, she uploads those results (<strong>required</strong>); her SPM
        slip is <strong>optional</strong> and never stops her submitting. A student with only SPM results who
        chose a degree must upload higher results too (a degree needs them), as well as her SPM slip. On a <strong>post-SPM pathway</strong>
        (Matriculation, Form 6, Polytechnic, ILKBS, PISMP and so on) only the <strong>SPM results slip</strong> is
        required. With no course chosen yet, it follows the results she holds. An application keeps the
        requirement it was submitted under &mdash; but one submitted before the higher-results upload existed (26 October 2026) by a degree-bound student holding STPM, Matriculation, Asasi or Diploma results, with none uploaded, shows that slot as <strong>Missing</strong>, its Academic card is at most <strong>Probable</strong> (&ldquo;STPM results not on file&rdquo;), and the system asks her for them (raised while the case is Completed, instead of the semester-result request); nothing sends it back to her. The Academic card checks the higher results&rsquo; name, which
        results they are and the CGPA (and, for STPM, the subject grades) against what she entered; an SPM slip
        is compared only if one is on file. STPM results (slip or certificate) are checked for genuineness like an SPM slip: a screenshot of the online results-checker page is flagged, and her Documents page asks her to re-upload the real document (after she submits, request it yourself); a printout of the MPM results web page (PDF, scan or photo) or a certified copy is fine. On the cockpit, an STPM student&rsquo;s grades carry <strong>one tick</strong> after the subjects when every grade matches her STPM results (as SPM grades do), and her CGPA (worked out from her grades: Pengajian Am + her best three others) a tick when it matches; a small <strong>&ne;</strong> marker sits beside a grade or the CGPA that differs &mdash; hover over it for the document&rsquo;s grade or PNGK; no tick means no results read yet, or a subject not on the document, and <strong>not calculated</strong> beside the CGPA means fewer than Pengajian Am + three grades were entered, so the figure shown is the one she typed. A marker is a prompt to read the document yourself; it does not change the verdict on its own. After she submits, the system also asks her (in her Action Centre, while the case is Completed) to <strong>add her remaining STPM subjects</strong> when she entered fewer than Pengajian Am + three, and to <strong>confirm her co-curriculum score</strong> when the one on file could not be worked out cleanly; each opens her STPM results page and closes by itself once she saves there. An STPM CGPA counts as matching the document only within 0.01 (since 28 October 2026); Matriculation, Asasi and Diploma keep 0.05, as their prints may round to one decimal.
        A Matriculation academic transcript and a polytechnic Diploma academic transcript are checked too (since 29 October 2026): a clear one counts as genuine, and anything the check is unsure of stays <strong>not checked</strong> &mdash; it is never called fake. By the owner&rsquo;s ruling, only the <strong>final</strong> result counts: for Matriculation and a Diploma, the final academic transcript (a <strong>provisional</strong> transcript that prints its completion status and final CGPA counts as final). A <strong>semester result slip</strong> (a final &ldquo;Lulus dan Tamat&rdquo; slip included), a screenshot of the <strong>polytechnic student portal</strong>, or a transcript that shows the programme still in progress does not count: the card reads as if the final results are not yet on file &mdash; Academic is at most <strong>Probable</strong>, the card says the final transcript is still owed, her Documents page asks her for her final academic transcript, and once she has submitted the system asks her for it too (when her programme asks for higher results). Only what the page itself shows decides this: a transcript whose status line is missing from the page or cannot be read stays <strong>not checked</strong> and nobody is asked to upload it again. A <strong>Matriculation offer letter</strong> uploaded here is not a results document and is flagged as such. Asasi and other Diploma results (UiTM, private colleges) are <strong>not checked</strong> yet &mdash; read the document yourself. When the document looks like a different kind of results, or an SPM slip, the card
        says so and the student was shown a note; none of these stops her application. Since 27 October 2026 a higher result uploaded as her
        <strong> SPM slip</strong> is recognised too: the card says it is a higher result, not an SPM slip, nothing is compared with her SPM
        grades and she is never told to change them; where her page shows the higher-results card she is offered a one-tap move into it.</>,
    },
    {
      q: <>The Academic card says the student <strong>only has SPM results</strong>, or <strong>moved</strong> a slip between the results cards. What happened?</>,
      a: <>Before submitting, she either chose &ldquo;Continue with SPM results only&rdquo; &mdash; the STPM,
        Matriculation, Asasi or Diploma results she had entered were removed, her SPM results were kept, and
        she is now assessed on SPM &mdash; or moved an SPM slip she had put in the higher-results card into the
        SPM slot. The note gives the date (and, for the first, which results went and their CGPA). She may
        have been shortlisted on the results she removed: the shortlist was <strong>not</strong> run again, so
        judge the change yourself and ask at interview if it is unclear. Once an application is submitted
        these actions are closed &mdash; request any document you need instead. A higher result moved OUT of the SPM card (by her, or by the HalaTuju team on 26 October 2026) is noted the same way, naming the card it came from (the SPM card or the semester result).</>,
    },
    {
      q: <>Why did STPM students move up the list when I sort by <strong>merit</strong>?</>,
      a: <>The merit score is now <strong>out of 100 for every student</strong>. An SPM student&rsquo;s is
        worked out from her SPM grades and co-curriculum, exactly as before. An STPM student&rsquo;s used to be
        her CGPA as it stands (for example 3.70), so every STPM student sorted below every SPM student; it is
        now her overall CGPA ÷ 4 × 100 (3.70 shows as 92.5), the same conversion the course guide uses. Her
        CGPA itself has not changed: it now has its own <strong>CGPA</strong> line on the Academic card. A dash means there are no
        results to score yet &mdash; it is not a zero, and it always sorts last.</>,
    },
    {
      q: <>Where do I see what the student told us about their <strong>family</strong>?</>,
      a: <>In <strong>Family &amp; finances</strong>, under <strong>About your family</strong>: each family member
        the student listed, their occupation, who earns, any monthly income they declared, and why and since
        when someone is not working. These are the student&rsquo;s own answers, not checked facts. The
        <strong> Parent contact</strong> line above them is only the person we call &mdash; it is not the whole
        family. The small tick beside that name appears only when the name matches a parent&rsquo;s or
        guardian&rsquo;s IC the student uploaded; no tick means it does not match, or no such IC has been read.</>,
    },
    {
      q: <>What does the small blue <strong>tick</strong> beside a value mean?</>,
      a: <>That the value is backed by a document she uploaded. The <strong>school</strong> is ticked from her
        school-leaving certificate; her <strong>SPM grades</strong> from her SPM results slip (one tick after the
        subjects); her <strong>programme</strong>, <strong>institution</strong> and <strong>reporting date</strong> from
        her own offer letter &mdash; including when we filled them in from that letter for her. No tick means
        no such document has been read yet, or it shows something different; it is never a sign of a problem on
        its own. The school is always shown in capitals, as the documents print it. When she named no
        institution, the card shows the one on her offer letter.</>,
    },
    {
      q: <>What is the <strong>place-of-birth</strong> line beside the NRIC?</>,
      a: <>The state the student was born in, read from the place-of-birth code in her IC number (the two
        digits in the middle). A gift can accept only students born in certain states; one born elsewhere,
        born outside Malaysia, with &ldquo;place of birth unknown&rdquo; (code 82), or whose IC number cannot be
        read does not pass that rule. The line is checked again every time the case opens: if the IC
        number was changed after she applied and no longer meets the rule, it turns red, and QC can
        accept the case only with a recorded reason. Where you are in doubt, request her birth
        certificate.</>,
    },
    {
      q: <>Why do I only see some applicants?</>,
      a: <>You see <strong>only the applicants assigned to you</strong>, so you can focus on your own. That&rsquo;s
        normal.</>,
    },
    {
      q: <>Why does my profile ask for my languages?</>,
      a: <>So we can assign you students you can speak with comfortably. Set your fluency in English, Bahasa Melayu
        and Tamil on your <strong>Profile</strong> — we match you to applicants whose preferred language you
        share.</>,
    },
    {
      q: <>Will my phone number be shared with students?</>,
      a: <>Your number may be shared with the students assigned to you, so they know to expect your call. It&rsquo;s
        on by default — you can <strong>opt out anytime</strong> on your Profile. Your <strong>home address is
        never shown to anyone</strong>, including the programme lead.</>,
    },
    {
      q: <>I need a break. How do I stop being given new students?</>,
      a: <>On <strong>My profile</strong>, in the <strong>Taking part</strong> card, tick <strong>Pause new
        cases</strong>. Nobody new will be assigned to you until you untick it. You don&rsquo;t need permission
        and nobody is judging — this is unpaid work and life happens.</>,
    },
    {
      q: <>If I pause, do I lose my account or the students I already have?</>,
      a: <>No. Pausing is <strong>not</strong> leaving: you keep your account, you can still sign in, and
        <strong> any interview already yours stays yours</strong> — please finish those, or tell the programme
        lead if you can&rsquo;t. Only <em>new</em> assignments stop.</>,
    },
    {
      q: <>Can somebody pause me without asking?</>,
      a: <>Your organisation admin can, and it is meant kindly — usually when someone has gone quiet and cases are
        waiting. It takes nothing away from you, and the same switch brings you back whenever you want.</>,
    },
    {
      q: <>What is the &ldquo;Student profile (draft)&rdquo;?</>,
      a: <>A short summary written automatically from the student&rsquo;s own application. A helpful starting point
        — always check it against the uploaded documents before relying on it.</>,
    },
    {
      q: <>How do I judge the Income (B40) check? It&rsquo;s the hardest one.</>,
      a: <>Two routes. <strong>STR route:</strong> the proof is an <em>approved</em> MySTR record — a
        <strong> SALINAN application-record is not proof</strong>; if the status isn&rsquo;t clearly
        &ldquo;Lulus&rdquo;, ask for the MySTR Semakan Status / Dashboard, or the approval letter.
        <strong> Salary route:</strong> payslips / EPF, judged per head against the B40 line. When it&rsquo;s
        genuinely borderline, that&rsquo;s what the interview is for — don&rsquo;t force a verdict on weak
        evidence.</>,
    },
    {
      q: <>How do I ask the student a question?</>,
      a: <>Use <strong>Raise a query</strong> or <strong>Request a document</strong>. They get an email; their
        reply shows in the <strong>Outstanding</strong> box. While the student is still completing their
        documents, a note takes the place of both: what they still owe is listed under <strong>Blockers</strong>,
        and they are already being asked for it.</>,
    },
    {
      q: <>What does &ldquo;Save verdict &amp; generate final profile&rdquo; do?</>,
      a: <>It records your decision and creates the final, polished profile — and sends the case on for
        <strong> QC</strong>. The student becomes visible to sponsors only once QC accepts it.</>,
    },
    {
      q: <>What&rsquo;s the difference between rating Pass/Fail and approving?</>,
      a: <>The <strong>Pass/Fail</strong> on each fact says whether the <em>AI read that fact correctly</em>.
        <strong> Approve / Decline</strong> is your actual recommendation. They&rsquo;re separate: you can Pass all
        four facts and still <strong>Decline</strong> — for instance, income verified but above the B40 line.</>,
    },
    {
      q: <>Can I undo a decision after I Save?</>,
      a: <>Not as a reviewer — <strong>Save is final from your side</strong>. If something needs changing, contact
        the HalaTuju team (<strong>help@halatuju.xyz</strong>); a super-admin can reopen the case. Check the facts
        before you save.</>,
    },
    {
      q: <>What&rsquo;s the recommended amount for?</>,
      a: <>It&rsquo;s your suggestion of how much assistance would help, set on the slider. It guides the
        sponsor.</>,
    },
    {
      q: <>The offer letter doesn&rsquo;t match the stated pathway — what do I do?</>,
      a: <>Note it and ask in the interview (or raise a query). They may have updated their plan; you can also ask
        them to upload the latest offer letter, which replaces the old one.</>,
    },
    {
      q: <>The student has completed a semester or two — should I ask for more?</>,
      a: <>If they have their results (CGPA), you may ask them to upload the latest result. If it&rsquo;s
        satisfactory (above 3.0), you may consider recommending them for support.</>,
    },
    {
      q: <>How do the suggested interview questions work?</>,
      a: <>In the <strong>Interview Stage</strong>, tap <strong>Suggest interview questions</strong> — the system
        proposes a few from this student&rsquo;s record; tap <strong>Generate more</strong> for others. A prompt,
        not a script: ask your own too, and jot <strong>one line</strong> per point before you submit. Every
        point needs an answer — <strong>Resolved</strong>, a short note (even &ldquo;See conclusion&rdquo;), or
        <strong> Delete</strong> — or the submit is refused and Approve and Decline stay greyed out.</>,
    },
    {
      q: <>Why is there always a &ldquo;Motivation &amp; grit&rdquo; point on the agenda?</>,
      a: <>Motivation is deliberately a human judgement — the system never scores it — so it&rsquo;s always on the
        agenda, and flagged for extra attention when the statement of intent is thin.</>,
    },
    {
      q: <>How do I schedule the interview?</>,
      a: <>On the applicant&rsquo;s page, use <strong>Interview scheduling</strong> to propose two or three times.
        The student picks one and a <strong>Google Meet</strong> link is created automatically — you both get a
        confirmation, plus reminders the day before and an hour before.</>,
    },
    {
      q: <>What if the student needs a different time, or doesn&rsquo;t book?</>,
      a: <>They can <strong>reschedule or cancel</strong> up to a few hours before, and you&rsquo;ll see the
        change. If they cancel, just propose fresh times.</>,
    },
]
