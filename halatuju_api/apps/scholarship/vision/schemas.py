"""The Gemini field schemas and per-document extraction hints (moved verbatim from
``vision.py``, audit sprint A3.1)."""

from ..higher_results import HINT as _HIGHER_HINT, SCHEMA as _HIGHER_SCHEMA
from ..offer_reader import OFFER_SCHEMA


# ── Document-assist: Gemini field extraction over messy supporting docs ────────
# Gemini PICKS the fields from arbitrary layouts (better than token-presence on
# the raw text); the deterministic matchers then DECIDE the verdict (so the
# student-facing verdict can never be a Gemini hallucination). Runs automatically
# on upload (see DocumentListCreateView), soft + never blocking.

GEMINI_EXTRACT_DOC_TYPES = frozenset({
    'salary_slip', 'epf', 'water_bill', 'electricity_bill', 'results_slip', 'offer_letter',
    'str', 'guardianship_letter', 'birth_certificate', 'bank_statement',
    # V1: the declared-informal-income supporting doc must be READ, not merely present.
    'income_support_doc',
    # V4: promoted academic-completeness docs — read the CGPA / school so the officer sees it.
    'school_leaving_cert', 'semester_result', 'higher_results',   # + third route S3b
})

_STR = {'type': 'string'}
# #5: which of the three real STR artifacts this is (closed set — no open-ended "other"),
# so the extractor reads each layout's fields from the right place + the officer sees the source.
_STR_SOURCE = {'type': 'string', 'enum': ['letter', 'semakan_status', 'dashboard', 'unknown']}


def _doc_schema(props: dict) -> dict:
    """An object schema with the given string fields + a shared warnings array."""
    out = dict(props)
    out['warnings'] = {'type': 'array', 'items': {'type': 'string'}}
    return {'type': 'object', 'properties': out}


_FIELD_SCHEMAS = {
    # Income Check-1: read the earner's NRIC too, so a member-tagged slip can be
    # cross-checked against that member's IC (name + IC number), not the student.
    # Income Check-1 (STR): the recipient (name + NRIC) is the household earner, plus the
    # CURRENCY facts — status (Lulus/diluluskan/…) + the STR year — since a stale STR no
    # longer proves B40. Covers both the MOF letter and the MySTR portal screenshot.
    'str': _doc_schema({'recipient_name': _STR, 'recipient_nric': _STR, 'status': _STR,
                        'year': _STR, 'amount': _STR, 'source_type': _STR_SOURCE}),
    'salary_slip': _doc_schema({'name': _STR, 'nric': _STR, 'employer': _STR, 'currency': _STR,
                                'gross_income': _STR, 'net_income': _STR,
                                'gross_income_ytd': _STR, 'period': _STR}),
    'epf': _doc_schema({'name': _STR, 'nric': _STR, 'employer': _STR, 'employer_number': _STR,
                        'latest_balance': _STR, 'last_contribution': _STR,
                        'monthly_contribution': _STR, 'months_counted': _STR,
                        'employer_contribution_total': _STR, 'employee_contribution_total': _STR,
                        'contribution_status': _STR, 'statement_date': _STR, 'address': _STR,
                        'year': _STR}),
    # Income Check-1: utility bills carry the home address + the MONTHLY charge + any
    # UNPAID balance (a high outstanding amount is a soft hardship signal). Extraction-v2
    # (2026-07-10): bill_date (Tarikh Bil — a POINT-IN-TIME date, the preferred currency anchor
    # over the Tempoh Bil range; see income_engine._bill_as_of) + account_no (No. Akaun — the stable
    # premises join-key). Electricity also reads usage_kwh (Kegunaan/kWj — the high-usage-vs-income
    # signal) + tariff (Tarif A domestik confirms a home vs a commercial/landlord account).
    'water_bill': _doc_schema({'name': _STR, 'address': _STR, 'amount': _STR,
                               'unpaid_balance': _STR, 'billing_period': _STR,
                               'bill_date': _STR, 'account_no': _STR,
                               'usage_m3': _STR, 'tariff': _STR}),
    'electricity_bill': _doc_schema({'name': _STR, 'address': _STR, 'amount': _STR,
                                     'unpaid_balance': _STR, 'billing_period': _STR,
                                     'bill_date': _STR, 'account_no': _STR,
                                     'usage_kwh': _STR, 'tariff': _STR}),
    # S2: read the GRADE against each subject (not just the subject list) so the
    # academic engine can verify the typed grades against the slip.
    # Check-1 fix: also read the Malay BAND phrase per subject (Cemerlang Tertinggi /
    # Cemerlang Tinggi / …) — a SECOND, redundant encoding of the grade printed on the
    # slip. The academic engine cross-checks letter↔band to catch row-transposition
    # misreads (e.g. Matematik A vs Sains A+ swapped) and degrades to 'check' on conflict.
    'results_slip': _doc_schema({'candidate_name': _STR, 'exam': _STR,
                                 'results': {'type': 'array', 'items': {'type': 'object',
                                             'properties': {'subject': _STR, 'grade': _STR,
                                                            'band': _STR}}}}),
    # Pathway Check-1: the offer letter's facts. Its schema, prompt, inputs (up to 3 pages + the PDF
    # text layer) and version live in offer_reader.py (offer exact-read S4, 2026-11-01), where
    # extract_document_fields sends every offer read.
    'offer_letter': OFFER_SCHEMA,
    # Income Check-1: the Birth Certificate links the income earner (mother) to the
    # student. Read the child + both parents' names AND their NRICs (the strong match).
    # `bc_child_dob` exists ONLY to validate `bc_child_nric` (see `nric_dob_agrees`) — the
    # child row is the one that ties the certificate to THIS student, so a misread number
    # would newly BLOCK a student where a blank never did.
    'birth_certificate': _doc_schema({'bc_child_name': _STR, 'bc_child_nric': _STR,
                                      'bc_child_dob': _STR,
                                      'bc_mother_name': _STR, 'bc_mother_nric': _STR,
                                      'bc_father_name': _STR, 'bc_father_nric': _STR}),
    # Income Check-1: a guardianship order / authorisation letter ties the legal guardian
    # to the student (the ward). Read the guardian + ward names + the guardian's NRIC.
    'guardianship_letter': _doc_schema({'guardian_name': _STR, 'guardian_nric': _STR,
                                        'ward_name': _STR, 'doc_kind': _STR}),
    # Post-award bursary payout: the student's bank statement / passbook. Read the bank
    # name, the account number, and the account-holder name as printed — the holder MUST
    # be the student (checked deterministically, never by the AI).
    'bank_statement': _doc_schema({'bank_name': _STR, 'account_number': _STR,
                                   'account_holder': _STR}),
    # V1 — the declared-informal-income supporting doc (Phase 2A D1: employer/wage letter,
    # bank statements showing income, OR a community/penghulu letter). Read WHO it is for
    # (the earner, not the student), the amount + period it evidences, and WHAT kind of
    # letter it is. A blank/wrong image reads no fields → student_verdict 'wrong_doc' →
    # does NOT clear the declared-income gap (see income_engine.has_income_support_doc).
    'income_support_doc': _doc_schema({'name': _STR, 'nric': _STR, 'amount': _STR,
                                       'period': _STR, 'issuer': _STR, 'kind': _STR}),
    # V4 — a school-leaving certificate (Sijil Berhenti Sekolah): the student's name + NRIC, the
    # school, the conduct rating (kelakuan), and the co-curricular / leadership roles + remarks
    # (activities) — the owner-specified set (2026-07-15). The name is matched against the student
    # (officer chip); NRIC + kelakuan + activities give the officer the cert's identity, conduct, and
    # leadership read.
    'school_leaving_cert': _doc_schema({'name': _STR, 'nric': _STR, 'school': _STR, 'kelakuan': _STR,
                                        'activities': _STR}),
    # V4 — a current-semester result slip for a continuing student: institution, programme, the
    # semester label, and the CGPA (the officer's current-performance read).
    'semester_result': _doc_schema({'name': _STR, 'nric': _STR, 'institution': _STR,
                                    'programme': _STR, 'semester': _STR, 'cgpa': _STR}),
    'higher_results': _HIGHER_SCHEMA,     # third route S3b: STPM / Matric / Asasi / Diploma results
}

# Which extracted field holds the person's name (for the deterministic verdict).
_NAME_FIELD = {
    'salary_slip': 'name', 'epf': 'name', 'water_bill': 'name', 'electricity_bill': 'name',
    'results_slip': 'candidate_name', 'offer_letter': 'candidate_name', 'str': 'recipient_name',
    'bank_statement': 'account_holder',
    # V4 — a school-leaving cert names the STUDENT (matched against them). A semester_result has
    # no student-name field (institution/programme/cgpa) → no name-match, the read is the signal.
    'school_leaving_cert': 'name', 'higher_results': 'candidate_name',
}

# Optional per-doc-type instruction appended to the extraction prompt.
_DOC_HINTS = {
    # The slip is a TABLE; each row prints the grade TWICE (a letter + a Malay band).
    # Ask for both, ALIGNED to the same row — the academic engine cross-checks them to
    # catch a row-transposition misread. (The deterministic `_split_band` still strips
    # any band words that leak into the subject name.)
    'higher_results': _HIGHER_HINT,
    'school_leaving_cert': (' This is a Malaysian school-leaving certificate (Sijil Berhenti '
                            'Sekolah). Read: "name" = the student (Nama Murid); "nric" = the '
                            'student\'s No. Kad Pengenalan (12 digits); "school" = the issuing '
                            'school; "kelakuan" = the conduct rating exactly as printed (e.g. '
                            'TERPUJI / BAIK / SEDERHANA); "activities" = the co-curricular / '
                            'leadership roles (the Kurikulum/Sukan/Badan Khas "Jawatan" entries, '
                            'e.g. "Naib Bendahari Persatuan Bahasa Tamil") plus the Catatan remark, '
                            'joined with "; " — or empty if none.'),
    'results_slip': (' This is an SPM results slip — a TABLE with one row per subject '
                     '(code · subject name · LETTER grade · Malay BAND phrase). For EACH '
                     'subject row return {subject, grade, band}: "subject" = the subject '
                     'NAME only (drop the leading code); "band" = the Malay band phrase on '
                     'THAT SAME row; "grade" = the grade the BAND means, using this EXACT '
                     'mapping (the band is the source of truth — the printed +/- letter is '
                     'small and easy to misread): Cemerlang Tertinggi=A+, Cemerlang '
                     'Tinggi=A, Cemerlang=A-, Kepujian Tertinggi=B+, Kepujian Tinggi=B, '
                     'Kepujian Atas=C+, Kepujian=C, Lulus Atas=D, Lulus=E, Gagal=G, Tidak '
                     'Hadir=TH. The printed letter MUST agree with the band — if they '
                     'differ, trust the BAND. Read strictly row by row: the grade and band '
                     'belong to the subject printed on the SAME line; NEVER carry a grade or '
                     'band up or down to a different subject, even if the slip is faint or '
                     'watermarked. Ignore the "Ujian Lisan" line and any watermark text.'),
    'str': (' This is meant to be a Malaysian STR (Sumbangan Tunai Rahmah) proof. It should be ONE '
            'of three recognised kinds — set "source_type" to: "letter" (an official Kementerian '
            'Kewangan STR APPROVAL letter — KEMENTERIAN KEWANGAN letterhead, a "No. Rujukan" + '
            'date, stating the STR application was approved/"diluluskan"); "semakan_status" (the '
            'MySTR "Semakan Status" check page — its distinctive markers are "Maklumat Pemohon" + '
            '"Status Permohonan Semasa" + a "Fasa Bayaran" phase table; desktop OR mobile); '
            '"dashboard" (the MySTR mobile-app HOME — its distinctive markers are the side/nav menu '
            '(Dashboard / Jadual Perkhidmatan / Kaunter / Soalan Lazim (FAQ) / Panduan Pengguna / '
            'Borang), a profile card with the name + IC in brackets, a "Status Permohonan STR" card, '
            'and a "Status Kelayakan SARA" card — and it does NOT have a "Fasa Bayaran" table); '
            'else "unknown". CRITICAL: SARA (Sumbangan Asas Rahmah) is a DIFFERENT programme from '
            'STR. A document that only concerns SARA and does NOT show STR approval — e.g. a '
            'Perdana Menteri greeting/congratulation letter saying the person is "terpilih untuk '
            '(terus) menerima bantuan SARA" — is NOT valid STR proof: set "source_type"="unknown" '
            'and leave "status" EMPTY (do NOT infer "approved"/"Lulus" from SARA-recipient '
            'wording). (The "Semakan Status" page\'s own "Sumbangan Asas Rahmah" section is fine — '
            'that whole page IS an STR artifact.) "recipient_name" = the recipient\'s full name '
            '("Nama Penerima" on the letter, "Nama" on the portal, or the dashboard profile-card '
            'name); "recipient_nric" = their IC / MyKad ("No Pengenalan" / "No. MyKad" / the '
            'number in brackets — keep ALL 12 digits even without dashes); "status" = the STR '
            'approval status: the VALUE shown beneath or beside the label "Status Permohonan STR" / '
            '"Status Permohonan Semasa" — i.e. "Lulus" / "diluluskan" (approved), "Ditolak" / '
            '"Tidak Layak" (rejected), "Dalam proses" (pending). CRITICAL: the status is that VALUE, '
            'NEVER the label — do NOT return the programme word "STR" itself as the status (on the '
            'dashboard the card reads "Status Permohonan STR" then "Lulus" on the next line → status '
            'is "Lulus"). "year" = the STR cycle year, taken ONLY from the letter date or a '
            '"Maklumat Pembayaran" / "Tarikh Kredit" payment date (e.g. "20/01/2026" → "2026"); '
            'NEVER read a year from page chrome such as the nav/menu (e.g. a "Soalan Lazim (FAQ) '
            '2026" menu item is NOT the STR year); if no such date is shown, leave it EMPTY. '
            '"amount" = the total STR in RM ("jumlah … STR … RM1,200" / "Jumlah Bayaran Keseluruhan '
            'STR"). Leave a field empty if it is not present.'),
    'electricity_bill': (' This is a Malaysian electricity bill — usually TNB (Tenaga Nasional, header '
                         '"Bil Elektrik Anda"; SESB in Sabah / SESCO in Sarawak). "name" = the '
                         'account-holder name; "address" = the premises address. "account_no" = the '
                         'account number, labelled "No. Akaun" (keep the digits). "amount" = ONLY '
                         'the CURRENT month\'s charge ("Caj Semasa" / "Caj Penggunaan Bulan Semasa") '
                         '— do NOT use "Jumlah Perlu Dibayar", which is the TOTAL including arrears. '
                         '"unpaid_balance" = the arrears ("Baki Terdahulu" / "Tunggakan", RM). '
                         '"bill_date" = the BILL DATE labelled "Tarikh Bil" — a single point-in-time '
                         'date (e.g. "18.03.2026"); this is DISTINCT from the billing period. '
                         '"billing_period" = the consumption period labelled "Tempoh Bil" (a range, '
                         'e.g. "17.02.2026 - 16.03.2026"). "usage_kwh" = the consumption in kWh/kWj '
                         '("Kegunaan"). "tariff" = the tariff / premise class ("Tarif", e.g. "Domestik '
                         'Am" for a home). Leave a field empty if it is not present.'),
    'water_bill': (' This is a Malaysian water utility bill (state-run — e.g. Air Selangor, SAJ/'
                   'Ranhill, PBAPP, SADA, SAINS, LAP/Air Perak, PAIP, SAMB). "name" = the account '
                   'holder\'s name ("Nama"); "address" = the supply/billing address; "amount" = ONLY '
                   'the CURRENT month\'s charge ("Caj Air Semasa" / "Jumlah Caj Air Semasa" / '
                   '"Jumlah Bil Semasa") — do NOT use "Jumlah Bil Perlu Dibayar", which is the TOTAL '
                   'including arrears; "unpaid_balance" = the arrears carried forward ("Tunggakan" / '
                   '"Baki Tertunggak", RM) — empty if none; "billing_period" = the bill month/period '
                   '("Tempoh Bil"); "bill_date" = the point-in-time bill/issue date ("Tarikh Bil") if '
                   'printed; "account_no" = the account number ("No. Akaun"); "usage_m3" = the water '
                   'consumed in cubic metres ("Penggunaan"/"Kegunaan", unit m³ / meter padu); '
                   '"tariff" = the tariff/premise class ("Tarif", e.g. domestik) if shown. '
                   'IMPORTANT — dating the bill: some operators (e.g. Lembaga Air Perak / LAP) print '
                   'NO "Tarikh Bil" or "Tempoh Bil". If neither is present, set "bill_date" to the '
                   'LATEST / most recent METER-READING date — the newest "Tarikh" beside the meter '
                   'reading ("No. Meter" / "Bacaan Meter" / "Bacaan", the row with the current usage) '
                   '— because that is when this bill was issued. Do NOT use "Bil Akhir" / "Bayaran '
                   'Akhir" for the date (those are the PREVIOUS bill and the LAST payment, not this '
                   'bill). Leave any field empty if it is not present.'),
    'salary_slip': (' This is a Malaysian salary slip / payslip — OR a government benefit / pension '
                    'payment statement (e.g. a PERKESO/SOCSO "Penyata Bayaran Faedah" survivor\'s '
                    'pension "Pencen Penakat"), which counts as household income too. "name" = the '
                    'EMPLOYEE\'s / recipient\'s full name; "nric" = their Malaysian IC number — look '
                    'for a label ("No. K/P" / "No. KP" / "K/P" / "IC No" / "No. Kad Pengenalan" / '
                    '"MyKad"), OR any 12-digit number shaped like a MyKad (YYMMDD-PB-#### — six '
                    'digits, then two, then four) sitting in the employee-details block even if it '
                    'is UNLABELLED; keep the 12 digits. Do NOT use the employee / staff / payroll '
                    'number (usually shorter and often prefixed with a letter, e.g. "F01677") as the '
                    'IC. "employer" = the company (leave empty for a benefit/pension statement); '
                    '"currency" = the pay currency. Set "SGD" if this is a SINGAPORE payslip — '
                    'tell-tale signs: an "S$" sign on the amounts, CPF (Central Provident Fund) or '
                    'SDL (Skills Development Levy) lines, an employer ending "Pte Ltd" / "Private '
                    'Limited", a Singapore address, or a Singapore work-pass / FIN number. Otherwise '
                    '"MYR" (a Malaysian slip shows RM, with EPF/KWSP and SOCSO/PERKESO); '
                    '"gross_income" = the GROSS monthly pay = the TOTAL earnings for the month = '
                    'basic salary PLUS all allowances and overtime (the "Total Payment" / "Jumlah '
                    'Pendapatan" / gross-earnings total). Do NOT use the "Basic Salary" line alone '
                    'when a higher total-earnings figure is shown — a job with overtime/allowances '
                    'earns more than its basic. For a benefit/pension statement, '
                    'the regular MONTHLY benefit amount (e.g. "Amaun Bayaran" RM687.50); "net_income" '
                    '= the net/take-home pay; "gross_income_ytd" = the YEAR-TO-DATE / cumulative '
                    'gross total — labelled "Year To Date" / "YTD" / "Jumlah Terkumpul" / '
                    '"Pendapatan Terkumpul" / "Terkumpul" / "Sehingga Kini" / "Cumulative"; OR, when '
                    'the earnings are laid out in TWO number columns (the current month vs a '
                    'cumulative / "Terkumpul" column), it is the CUMULATIVE column total — read BOTH '
                    'columns, do not stop at the first. It captures variable overtime a single month '
                    'misses; leave empty only if the slip truly shows one month with no cumulative '
                    'figure. "period" = the pay month/year (e.g. "March 2026"). '
                    'IMPORTANT for money fields: on a HAND-WRITTEN voucher the amount is often '
                    'ruled into TWO columns — ringgit (RM) and sen (cents) — separated by a '
                    'vertical line. Read that line as a DECIMAL POINT: "326 | 00" is RM326.00, '
                    '"4856 | 75" is RM4856.75. NEVER concatenate the two columns into one whole '
                    'number (RM326.00 must not become 32600). Also: the take-home pay (net) can '
                    'never exceed the gross — if your reading makes net > gross, you have likely '
                    'mis-read a column; re-read. '
                    'Leave a field empty if it is not present.'),
    'epf': (' This is a Malaysian EPF/KWSP statement ("PENYATA AHLI"). "name" = the member\'s '
            'full name; "nric" = "No. Kad Pengenalan" (keep the 12 digits). "employer_number" = '
            '"No. Majikan" EXACTLY as printed, INCLUDING when it is all zeros ("000000000" — that '
            'means no active employer / unemployed, so KEEP it, do NOT blank it); "employer" = the '
            'employer NAME if one is shown (often absent). "latest_balance" = the TOTAL savings '
            '"JUMLAH SIMPANAN" (RM); "year" = the statement year; "statement_date" = "Tarikh '
            'Penyata". The contribution table ("Caruman") shows, per month, an EMPLOYER share '
            '("Caruman Majikan") and a MEMBER share ("Caruman Ahli" / "Caruman Pekerja"). SUM each '
            'column over the months shown: "employer_contribution_total" = Σ Caruman Majikan (RM), '
            '"employee_contribution_total" = Σ Caruman Ahli (RM), and "months_counted" = how many '
            'months you summed. "monthly_contribution" = the most recent single month\'s total '
            'contribution from "CARUMAN SEMASA" (NOT the balance) — leave EMPTY if "Tiada Transaksi". '
            '"contribution_status" = "has" if there is at least one real monthly contribution; '
            '"zero" ONLY if it clearly shows NONE ("Tiada Transaksi" / all zero) — a real signal of '
            'no formal salary; "unknown" if the contributions section is unreadable/absent (do NOT '
            'guess "zero" when you simply cannot read it). "address" = the member\'s correspondence '
            'address if printed. Leave any field empty if it is not present.'),
    'birth_certificate': (' This is a Malaysian birth certificate (Sijil Kelahiran, JPN). It has '
                          'three labelled sections IN ORDER: "KANAK-KANAK / CHILD", then "BAPA / '
                          'FATHER", then "IBU / MOTHER". Read each name from WITHIN its section, '
                          'anchored on the SECTION HEADER — NOT on the field label: the name field '
                          'is labelled "Nama" on some certificates and "Nama Penuh" on others, so '
                          'accept EITHER. Return: "bc_child_name" = the name in the KANAK-KANAK / '
                          'CHILD block (the lines between the "KANAK-KANAK" header and the "BAPA" '
                          'header); "bc_child_nric" = the child IC if shown; "bc_father_name" + '
                          '"bc_father_nric" = the "Nama"/"Nama Penuh" and "No. Kad Pengenalan" in the '
                          'BAPA / FATHER block; "bc_mother_name" + "bc_mother_nric" = the "Nama"/'
                          '"Nama Penuh" and "No. Kad Pengenalan" in the IBU / MOTHER block (keep all '
                          '12 NRIC digits). IGNORE the "PEMBERITAHU / INFORMANT" block at the bottom '
                          'entirely — its "Nama" is the informant (often a grandparent), NOT the '
                          'child or a parent. Use names EXACTLY as printed (keep bin/binti/a/l/a/p). '
                          'Leave a field empty if absent. THE CHILD\'S IC: on a modern certificate a '
                          '12-digit number is printed in the TOP-RIGHT block beside the barcode, '
                          'often UNLABELLED (e.g. "080117-10-2004") — that is the child\'s IC number. '
                          'Return it as "bc_child_nric" with all 12 digits. Do NOT confuse it with '
                          'the certificate/register number, which carries LETTERS (e.g. "BZ21723"); '
                          'if the number you see has any letter in it, leave "bc_child_nric" empty. '
                          'Also return "bc_child_dob" = the child\'s date of birth ("Tarikh Lahir") '
                          'EXACTLY as printed (e.g. "17 JANUARI 2008"). On an older certificate that '
                          'shows no child IC at all, leave "bc_child_nric" empty and do NOT add any '
                          'warning about a missing/unlabelled child IC.'),
    'guardianship_letter': (' This is EITHER a Malaysian court-issued guardianship order OR a '
                            'written authorisation letter from a parent placing the applicant '
                            '(the "ward") under someone\'s care. Return: "guardian_name" = the '
                            'guardian\'s full name; "guardian_nric" = the guardian\'s IC number '
                            'if shown (12 digits); "ward_name" = the child/ward the letter is '
                            'about (the applicant); "doc_kind" = "court_order" if it is a court '
                            'guardianship order, else "authorisation_letter". Leave a field '
                            'empty if it is not present or not legible.'),
    'income_support_doc': (' This is a SUPPORTING document for a household member\'s informal '
                           'or self-declared income — an employer/wage letter, a bank statement '
                           'showing income, or a community/village-head (penghulu/JKKK) letter. '
                           'Return: "name" = the person the document is about (a working household '
                           'member, NOT necessarily the applicant); "nric" = their IC number if '
                           'shown; "amount" = any monthly income / salary / payment figure stated '
                           '(as printed, e.g. "RM1,200"); "period" = the month/period it covers if '
                           'shown; "issuer" = who issued it (employer / bank / penghulu / JKKK); '
                           '"kind" = one of "employer_letter", "bank_statement", "community_letter", '
                           'else "other". Leave a field empty if it is not present or not legible.'),
    'semester_result': (' This is a post-SPM SEMESTER result — an STPM MPM slip ("Keputusan '
                        'Peperiksaan Semester"), a Matriculation/Politeknik/university semester '
                        'result slip, or a student-portal results screenshot. Return: "name" = the '
                        'STUDENT\'s full name ("Nama") as printed; "nric" = the student\'s IC number '
                        '("No. Kad Pengenalan", keep all 12 digits); "institution" = the '
                        'college/university/board; "programme" = the course/programme; "semester" = '
                        'the semester shown; "cgpa" = the CUMULATIVE grade point ONLY — labelled '
                        '"PNGK" / "HPNM" / "CGPA" / "Himpunan PNGK" / "Kumulatif" (the running '
                        'average across semesters). If the slip shows ONLY a single semester\'s '
                        'grades with NO cumulative figure (e.g. an STPM Semester 1 slip), LEAVE '
                        '"cgpa" EMPTY and add NO warning about it — a semester-only slip has no CGPA. '
                        'Do NOT use a single-semester GPA ("PNM" / "GPA Semester") as the cgpa.'),
}
