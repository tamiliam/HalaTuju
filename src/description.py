# description.py

# This file contains the "Human-Friendly" descriptions for all Polytechnic Courses.
# Jobs are now dynamically loaded from CSV files (course_masco_link.csv + masco_details.csv)

import os
import csv

def _load_jobs_from_csv():
    """
    Loads job data from CSV files and returns a mapping:
    {course_id: [{"title": "Job Title", "url": "https://..."}, ...]}
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')
    
    link_file = os.path.join(data_dir, 'course_masco_link.csv')
    details_file = os.path.join(data_dir, 'masco_details.csv')
    
    # 1. Load MASCO Details: {masco_code: {title, url}}
    masco_lookup = {}
    if os.path.exists(details_file):
        try:
            with open(details_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('masco_code', '').strip()
                    title = row.get('job_title', '').strip()
                    url = row.get('url', '').strip()
                    if code and title:
                        # Add text fragment to scroll to "Kod MASCO" on mobile
                        if url and not url.endswith('#:~:text=Kod%20MASCO'):
                            url += '#:~:text=Kod%20MASCO'
                        masco_lookup[code] = {"title": title, "url": url}
        except Exception as e:
            print(f"Warning: Could not load masco_details.csv: {e}")
    
    # 2. Load Course-MASCO Links: {course_id: [masco_codes]}
    course_masco = {}
    if os.path.exists(link_file):
        try:
            with open(link_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    course_id = row.get('course_id', '').strip()
                    masco_code = row.get('masco_code', '').strip()
                    if course_id and masco_code:
                        if course_id not in course_masco:
                            course_masco[course_id] = []
                        # Avoid duplicates
                        if masco_code not in course_masco[course_id]:
                            course_masco[course_id].append(masco_code)
        except Exception as e:
            print(f"Warning: Could not load course_masco_link.csv: {e}")
    
    # 3. Join: {course_id: [{title, url}, ...]}
    result = {}
    for course_id, masco_codes in course_masco.items():
        jobs = []
        seen_titles = set()  # Avoid duplicate job titles
        for code in masco_codes:
            if code in masco_lookup:
                job = masco_lookup[code]
                if job["title"] not in seen_titles:
                    jobs.append(job)
                    seen_titles.add(job["title"])
        result[course_id] = jobs
    
    return result

# Load jobs once at module import
_JOBS_DATA = _load_jobs_from_csv()

def get_jobs_for_course(course_id):
    """Returns list of job dicts [{title, url}, ...] for a course."""
    return _JOBS_DATA.get(course_id, [])

course_info = {
    # --- AGROTECHNOLOGY ---
    # Forced Update v2.2
    "POLY-DIP-001": {
        "headline": "🌱 Agroteknologi: Pertanian Moden & Pintar",
        "synopsis": "Lupakan imej petani tradisional dengan cangkul. Kursus ini melatih anda menjadi 'Agropreneur Moden'. Anda akan belajar teknologi Fertigasi (tanam gantung), Pertanian Pintar (IoT/Sensor), dan cara mengurus ladang komersial dari benih hingga pemasaran. Sesuai untuk anda yang suka aktiviti luar (outdoor) tetapi mahukan kerjaya berteknologi tinggi."
    },
    
    # --- BIOTECHNOLOGY ---
    "POLY-DIP-002": {
        "headline": "🧬 Bioteknologi: Sains Hayat Industri",
        "synopsis": "Anda akan bekerja di makmal untuk menghasilkan produk berasaskan biologi—seperti makanan, ubat-ubatan, atau benih tanaman hibrid. Anda akan menguasai teknik Kultur Tisu, Mikrobiologi, dan Fermentasi. Ini adalah bidang untuk mereka yang teliti, suka eksperimen sains, dan berminat dengan inovasi makmal."
    },

    # --- GEOMATICS ---
    "POLY-DIP-003": {
        "headline": "🌍 Geomatik: Peta, Satelit & Dron",
        "synopsis": "Dulu dikenali sebagai 'Ukur Tanah', kini ia menggunakan Satelit (GPS) dan Dron. Tugas anda adalah mengukur bumi untuk menghasilkan peta digital yang tepat bagi pembinaan bangunan, jalan raya, dan perancangan bandar. Kerjaya ini menggabungkan kerja luar (fieldwork) yang lasak dengan analisis komputer yang canggih."
    },

    # --- RETAIL MANAGEMENT ---
    "POLY-DIP-004": {
        "headline": "🛒 Pengurusan Runcit: Raja Pasaran",
        "synopsis": "Pernah tertanya bagaimana pasar raya besar (Giant/AEON) atau butik fesyen antarabangsa diuruskan? Kursus ini mengajar anda logistik, susun atur kedai (Visual Merchandising), dan strategi jualan. Anda juga akan menjalani latihan industri intensif (WBL) di kedai sebenar untuk merasai pengalaman menjadi pengurus."
    },

    # --- INSURANCE ---
    "POLY-DIP-005": {
        "headline": "🛡️ Insurans: Pengurusan Risiko Profesional",
        "synopsis": "Bukan sekadar menjadi ejen insurans. Ini adalah ilmu profesional tentang Pengurusan Risiko Kewangan. Anda akan belajar menilai kerugian, undang-undang kewangan, dan bagaimana syarikat gergasi melindungi aset bernilai jutaan ringgit. Kemahiran ini sangat diperlukan oleh bank dan syarikat korporat."
    },

    # --- ENVIRONMENTAL ENGINEERING ---
    "POLY-DIP-006": {
        "headline": "♻️ Kejuruteraan Alam Sekitar: Wira Bumi",
        "synopsis": "Anda adalah doktor kepada alam sekitar. Belajar cara merawat air sisa, mengurus sisa pepejal (sampah), dan memantau kualiti udara. Tugas anda memastikan pembangunan negara tidak memusnahkan bumi. Sesuai untuk mereka yang peka dengan isu hijau dan mahukan kerjaya teknikal yang memberi impak positif."
    },

    # --- CIVIL ENGINEERING ---
    "POLY-DIP-007": {
        "headline": "🏗️ Kejuruteraan Awam: Pembina Negara",
        "synopsis": "Dari jambatan gergasi ke bangunan pencakar langit, andalah yang merealisasikannya. Anda akan belajar melukis pelan struktur, menguji kekuatan konkrit, dan menyelia tapak pembinaan. Kerja ini mungkin panas dan berdebu, tetapi pulangannya lumayan dan hasilnya kekal berdiri megah."
    },

    # --- ELECTRICAL ENGINEERING ---
    "POLY-DIP-008": {
        "headline": "⚡ Kejuruteraan Elektrik: Kuasa Tinggi",
        "synopsis": "Fokus sepenuhnya kepada tenaga elektrik. Bagaimana ia dijana, dihantar melalui kabel grid kebangsaan, dan diagihkan ke rumah. Anda akan pakar dalam pendawaian (wiring), motor elektrik industri, dan keselamatan voltan tinggi. Graduan kursus ini adalah 'tulang belakang' kepada TNB dan kilang-kilang besar."
    },

    # --- ELECTRICAL & ELECTRONIC ENGINEERING ---
    "POLY-DIP-009": {
        "headline": "🤖 Elektrik & Elektronik: Kuasa & Robotik",
        "synopsis": "Kursus '2-dalam-1' yang paling versatil. Anda belajar asas kuasa (Elektrik) DAN sistem kawalan pintar (Elektronik). Bayangkan anda boleh membuat wiring rumah, dan pada masa sama memprogramkan robot kilang (PLC). Ini menjadikan anda sangat laku dalam pelbagai industri, dari pembinaan hingga pembuatan cip."
    },

    # --- ELECTRICAL & INSTRUMENTATION (PETROCHEM) ---
    "POLY-DIP-010": {
        "headline": "🛢️ Elektrik & Instrumentasi: Pakar Petrokimia",
        "synopsis": "Kursus elit yang direka khusus untuk industri Minyak & Gas (O&G). Selain elektrik, anda belajar tentang 'Instrumentasi'—sensor dan alat kawalan yang memantau paip minyak dan loji kimia. Anda akan belajar sistem DCS dan PLC yang digunakan di loji penapisan (refinery)."
    },

    # --- ELECTRICAL ENGINEERING (SPECIALIZATIONS) ---
    "POLY-DIP-011": {
        "headline": "⚡ Elektrik (Kecekapan Tenaga): Audit & Jimat",
        "synopsis": "Tenaga adalah wang. Dalam kursus ini, anda belajar bukan sahaja cara *guna* elektrik, tapi cara *urus* elektrik supaya tidak membazir. Anda akan diajar tentang 'Energy Audit', Tenaga Boleh Diperbaharui (Solar/Angin), dan sistem kuasa cekap tenaga. Graduan kursus ini sangat dicari oleh kilang-kilang yang mahu kurangkan bil elektrik mereka."
    },
    "POLY-DIP-012": {
        "headline": "🌱 Elektrik (Tenaga Hijau): Masa Depan Bumi",
        "synopsis": "Dunia sedang beralih dari minyak ke tenaga bersih. Anda akan menjadi pakar dalam Teknologi Hijau: Panel Solar, Turbin Angin, dan Kereta Elektrik (EV). Anda belajar memasang, menyelenggara, dan mengintegrasikan sistem ini ke dalam grid nasional. Ini adalah kerjaya masa depan yang kalis kemelesetan."
    },

    # --- ELECTRONIC ENGINEERING (SPECIALIZATIONS) ---
    "POLY-DIP-013": {
        "headline": "💡 Elektronik (Optoelektronik): Cahaya & Laser",
        "synopsis": "Pernah dengar tentang Fiber Optik atau LED? Itu adalah Optoelektronik—menggunakan cahaya untuk hantar data dan kuasa. Anda akan belajar tentang laser, penderia cahaya (sensors), dan pembuatan cip semikonduktor. Sesuai untuk anda yang berminat dengan teknologi di sebalik internet berkelajuan tinggi dan skrin canggih."
    },
    "POLY-DIP-014": {
        "headline": "🤖 Elektronik (Kawalan): Otak Robot",
        "synopsis": "Bagaimana lengan robot di kilang kereta bergerak dengan tepat? Itu adalah Sistem Kawalan. Anda belajar memprogramkan 'otak' mesin menggunakan PLC dan sensor. Anda akan menjadi pakar yang memastikan barisan pengeluaran kilang (production line) berjalan secara automatik tanpa henti."
    },
    "POLY-DIP-015": {
        "headline": "💻 Elektronik (Komputer): Hardware & Chips",
        "synopsis": "Jika Sains Komputer fokus pada Software, kursus ini fokus pada Hardware. Anda belajar bagaimana komputer *dibina* dari dalam—pemproses (processor), litar memori, dan sistem terbenam (embedded systems). Anda akan mahir membaiki, mereka bentuk, dan menyelenggara sistem komputer industri."
    },
    "POLY-DIP-016": {
        "headline": "📡 Elektronik (Komunikasi): Dunia Tanpa Wayar",
        "synopsis": "Dari 5G ke Satelit, andalah yang menghubungkan dunia. Kursus ini mengajar teknologi di sebalik telefon pintar, menara pemancar, dan rangkaian data. Anda akan belajar tentang frekuensi radio (RF), gentian optik, dan sistem rangkaian tanpa wayar. Kerjaya di syarikat Telco (Maxis/Celcom) menanti anda."
    },
    "POLY-DIP-017": {
        "headline": "🏥 Elektronik (Perubatan): Doktor Mesin",
        "synopsis": "Gabungan Kejuruteraan dan Perubatan. Hospital penuh dengan mesin canggih (MRI, X-Ray, Mesin Dialisis). Tugas anda adalah memastikan mesin ini berfungsi 100% tepat untuk menyelamatkan nyawa. Anda belajar anatomi manusia asas DAN litar elektronik canggih."
    },

    # --- CHEMICAL ENGINEERING ---
    "POLY-DIP-018": {
        "headline": "🧪 Kejuruteraan Kimia: Dari Makmal ke Kilang",
        "synopsis": "Bagaimana minyak mentah jadi petrol? Bagaimana bahan kimia jadi plastik? Anda belajar proses 'skala besar' industri kimia. Anda akan mengendalikan loji kimia, memantau tindak balas kimia dalam reaktor gergasi, dan memastikan sisa buangan selamat untuk alam sekitar. Kerjaya 'high demand' di Pengerang dan Gebeng."
    },

    # --- MECHANICAL ENGINEERING ---
    "POLY-DIP-019": {
        "headline": "⚙️ Kejuruteraan Mekanikal: Asas Kejuruteraan",
        "synopsis": "Kursus kejuruteraan yang paling luas dan fleksibel. Anda belajar tentang semua benda yang bergerak—mesin, enjin, sistem hidraulik, dan bahan. Anda akan mahir menggunakan perisian CAD untuk melukis komponen dan tangan anda akan cekap membaiki mesin. Graduan kursus ini boleh bekerja di mana-mana kilang di dunia."
    },
    "POLY-DIP-020": {
        "headline": "🦾 Mekanikal (Automasi): Revolusi Industri 4.0",
        "synopsis": "Kilang masa depan tidak perlukan ramai pekerja, ia perlukan robot. Kursus ini mengajar anda membina dan menyelenggara sistem robotik industri. Anda akan belajar tentang Pneumatik (kuasa udara), Hidraulik (kuasa cecair), dan integrasi robot dengan komputer. Anda adalah arkitek kepada kilang pintar."
    },

    # --- AUTOMOTIVE ENGINEERING ---
    "POLY-DIP-021": {
        "headline": "🏎️ Automotif: Pakar Enjin & Servis",
        "synopsis": "Kursus untuk 'Petrolhead' sejati. Anda bukan sekadar mekanik bawah pokok; anda adalah pakar diagnostik. Anda belajar tentang enjin pembakaran dalam, sistem elektronik kereta moden (ECU), dan pengurusan pusat servis. Sesuai jika anda bercita-cita membuka bengkel moden atau menjadi pengurus di pusat servis jenama terkemuka (Honda/Toyota)."
    },

    # --- MATERIALS ENGINEERING ---
    "POLY-DIP-022": {
        "headline": "🧪 Kejuruteraan Bahan: Sains di Sebalik Besi",
        "synopsis": "Kenapa kapal terbang dibuat daripada aluminium, bukan besi? Kenapa bumper kereta plastik tapi keras? Anda belajar 'resipi' bahan—logam, polimer (plastik), seramik, dan komposit. Anda akan bekerja di makmal untuk menguji kekuatan bahan dan memastikan produk kilang tidak mudah patah atau karat."
    },

    # --- POWER PLANT ENGINEERING ---
    "POLY-DIP-023": {
        "headline": "🏭 Loji Kuasa: Jantung Tenaga Negara",
        "synopsis": "Kerjaya 'Heavy Duty'. Anda belajar mengendalikan mesin gergasi yang menjana elektrik untuk satu negara—Turbin, Dandang (Boiler), dan Generator. Anda akan bekerja di stesen janakuasa (Power Plant) untuk memastikan lampu di rumah kita tidak terpadam. Kerja yang sangat kritikal dan bergaji tinggi."
    },

    # --- MANUFACTURING ENGINEERING ---
    "POLY-DIP-024": {
        "headline": "🏭 Pembuatan (Manufacturing): Nadi Kilang",
        "synopsis": "Bagaimana telefon pintar dibuat secara besar-besaran? Kursus ini mengajar anda proses pengeluaran kilang. Anda belajar menggunakan mesin CNC (pemotong berkomputer), robotik industri, dan kawalan kualiti. Anda adalah orang penting yang memastikan kilang beroperasi dengan efisien dan produk siap tepat pada masanya."
    },

    # --- PACKAGING ENGINEERING ---
    "POLY-DIP-025": {
        "headline": "📦 Pembungkusan Industri: Seni & Sains Kotak",
        "synopsis": "Jangan pandang rendah pada kotak. Pembungkusan melindungi produk bernilai jutaan ringgit. Anda belajar mereka bentuk bungkusan yang tahan lasak, menarik, dan mesra alam. Anda akan mahir tentang bahan (kertas/plastik), mesin pembungkusan automatik, dan reka bentuk grafik untuk kotak. Industri makanan dan logistik sangat memerlukan pakar ini."
    },

    # --- AIR-CONDITIONING & REFRIGERATION ---
    "POLY-DIP-026": {
        "headline": "❄️ Penyamanan Udara: Wira Penyejuk",
        "synopsis": "Di Malaysia yang panas, kemahiran ini ibarat emas. Anda belajar sistem HVAC komersial—aircond pusat beli-belah, bilik sejuk beku (cold storage), dan sistem pengudaraan bangunan. Bukan sekadar pasang aircond rumah, tapi merancang dan menyelenggara sistem penyejukan industri yang kompleks."
    },

    # --- AGRICULTURAL ENGINEERING ---
    "POLY-DIP-027": {
        "headline": "🚜 Mekanikal (Pertanian): Teknologi Ladang",
        "synopsis": "Gabungan kejuruteraan dan pertanian. Anda belajar membaiki dan mengendalikan jentera ladang besar (traktor, penuai), sistem pengairan automatik, dan struktur rumah hijau. Tugas anda adalah memastikan teknologi ladang berjalan lancar untuk meningkatkan hasil makanan negara."
    },

    # --- PETROCHEMICAL (MECHANICAL) ---
    "POLY-DIP-028": {
        "headline": "🛢️ Mekanikal (Petrokimia): Pakar Minyak & Gas",
        "synopsis": "Direka khusus untuk industri O&G (Minyak & Gas). Anda belajar menyelenggara paip, injap, dan tangki di loji petrokimia yang berisiko tinggi. Keselamatan adalah nombor satu. Graduan kursus ini biasanya bekerja di hab industri seperti Pengerang, Kerteh, atau Bintulu."
    },

    # --- PLASTICS ENGINEERING ---
    "POLY-DIP-029": {
        "headline": "🧸 Plastik Industri: Mencipta Bentuk",
        "synopsis": "Hampir semua barang di sekeliling kita ada plastik. Kursus ini mengajar anda cara mereka bentuk acuan (molds) dan menggunakan mesin suntikan plastik (injection molding) untuk menghasilkan produk—dari botol air hingga komponen kereta. Malaysia ada 1,300 kilang plastik yang memerlukan kepakaran anda."
    },

    # --- AUTOMOTIVE DESIGN ---
    "POLY-DIP-030": {
        "headline": "🎨 Reka Bentuk Automotif: Seni Kereta",
        "synopsis": "Berbeza dengan kursus 'baik pulih', kursus ini fokus kepada PENCIPTAAN. Anda belajar menggunakan perisian CAD/CAM untuk melukis komponen kereta, mereka bentuk bentuk badan kereta (body styling), dan ergonomik. Sesuai untuk anda yang kreatif dan mahu bekerja di kilang pemasangan kereta (Proton/Perodua)."
    },

    # --- PRODUCT DESIGN ---
    "POLY-DIP-031": {
        "headline": "🎨 Reka Bentuk Produk: Seni + Fungsi",
        "synopsis": "Lihat sekeliling anda—tetikus komputer, kerusi, botol air. Semuanya direka oleh seseorang. Kursus ini mengajar anda menggabungkan kreativiti (Seni) dengan kejuruteraan (Fungsi). Anda akan belajar melukis lakaran, membuat model 3D (CAD), dan menghasilkan prototaip produk yang sedia untuk dikilangkan. Kerjaya yang sangat kreatif!"
    },

    # --- MECHATRONICS ---
    "POLY-DIP-032": {
        "headline": "🤖 Mekatronik: Robotik & AI",
        "synopsis": "Gabungan Mekanikal + Elektronik + Komputer. Ini adalah asas kepada Robotik. Anda belajar membina sistem pintar yang bergerak sendiri—seperti lengan robot kilang, dron, atau sistem 'Smart Home'. Anda akan mahir dalam sensor, motor, dan programming (Coding)."
    },

    # --- AIRCRAFT MAINTENANCE ---
    "POLY-DIP-033": {
        "headline": "✈️ Penyenggaraan Pesawat: Kerjaya di Awan Biru",
        "synopsis": "Bercita-cita bekerja di lapangan terbang? Kursus elit ini melatih anda menjadi doktor kepada kapal terbang. Anda belajar membaiki enjin turbin, sistem hidraulik pesawat, dan instrumen kokpit. Lulusan kursus ini bersedia untuk mengambil lesen jurutera pesawat (License A) yang bergaji lumayan."
    },

    # --- MARINE ENGINEERING ---
    "POLY-DIP-034": {
        "headline": "🚢 Kejuruteraan Perkapalan: Penakluk Lautan",
        "synopsis": "Kerjaya untuk jiwa yang kental. Anda belajar mengendalikan enjin kapal gergasi. Kursus ini unik kerana anda akan menjalani 'Latihan Laut' (belayar) selama 6 bulan. Graduan layak dikecualikan peperiksaan tertentu untuk menjadi Jurutera Laut (Marine Engineer) bertauliah. Gaji dalam USD menanti anda di lautan antarabangsa."
    },

    # --- BUILDING SERVICES ---
    "POLY-DIP-035": {
        "headline": "🏢 Perkhidmatan Bangunan: Nadi Pencakar Langit",
        "synopsis": "Bangunan tinggi tidak boleh berfungsi tanpa anda. Siapa yang pastikan lif bergerak, aircond sejuk, dan lampu menyala? Kursus ini mengajar anda mengurus 'sistem hidup' bangunan—elektrik, paip, dan keselamatan kebakaran. Kerjaya yang sangat stabil di mana-mana bandar besar."
    },

    # --- PROCESS ENGINEERING (PETROCHEM) ---
    "POLY-DIP-036": {
        "headline": "🧪 Proses (Petrokimia): Kawalan Loji",
        "synopsis": "Fokus kepada 'Proses'—bagaimana menukar bahan mentah menjadi produk kimia. Anda belajar mengawal suhu, tekanan, dan aliran dalam paip loji petrokimia. Anda akan berlatih menggunakan simulasi loji sebenar. Sesuai untuk mereka yang mahu bekerja di hab industri minyak & gas."
    },

    # --- ENTREPRENEURSHIP ---
    "POLY-DIP-037": {
        "headline": "🚀 Keusahawanan: Bina Bisnes Sendiri",
        "synopsis": "Jangan cari kerja, cipta kerja. Kursus ini bukan sekadar teori; ia adalah 'Inkubator Bisnes'. Anda belajar mencari modal, pemasaran digital, dan undang-undang bisnes. Anda akan dibimbing untuk menubuhkan syarikat sebenar sebelum tamat belajar. Sesuai untuk anda yang berjiwa bos."
    },

    # --- FINANCE ---
    "POLY-DIP-038": {
        "headline": "💰 Kewangan (Finance): Pakar Duit",
        "synopsis": "Kuasai bahasa wang. Anda belajar menganalisis pasaran saham, mengurus bajet syarikat, dan merancang pelaburan. Ini adalah tiket masuk ke dunia korporat dan perbankan. Anda akan faham bagaimana duit bekerja untuk menghasilkan lebih banyak duit."
    },

    # --- ISLAMIC FINANCE ---
    "POLY-DIP-039": {
        "headline": "☪️ Kewangan Islam: Perbankan Patuh Syariah",
        "synopsis": "Malaysia adalah hab Kewangan Islam dunia. Kursus ini mengajar sistem perbankan tanpa riba, Takaful (insurans Islam), dan pengurusan harta (Zakat/Waqaf). Industri ini berkembang pesat dan sangat memerlukan tenaga kerja mahir yang faham hukum muamalat."
    },

    # --- RECREATIONAL TOURISM ---
    "POLY-DIP-040": {
        "headline": "rafting🚣 Pelancongan Rekreasi: Kerjaya Lasak",
        "synopsis": "Ubah hobi 'hiking' dan 'travel' menjadi kerjaya. Anda belajar mengurus taman tema, resort eko-pelancongan, dan aktiviti luar (outdoor). Anda akan diajar tentang keselamatan rekreasi, pemanduan pelancong alam semulajadi, dan pengurusan acara. Pejabat anda adalah hutan, sungai, dan pulau."
    },

    # --- MARKETING ---
    "POLY-DIP-041": {
        "headline": "📢 Pemasaran: Kuasai Seni Jualan",
        "synopsis": "Kenapa sesetengah jenama 'viral'? Itu adalah kuasa pemasaran. Anda belajar psikologi pembeli, strategi pengiklanan, dan pemasaran digital (TikTok/IG Ads). Bukan sekadar jurujual, anda dilatih menjadi pakar strategi jenama yang tahu cara membuat produk laku keras di pasaran."
    },

    # --- BUSINESS STUDIES ---
    "POLY-DIP-042": {
        "headline": "💼 Pengajian Perniagaan: 'Swiss Army Knife' Korporat",
        "synopsis": "Kursus paling fleksibel dalam dunia bisnes. Anda belajar sikit tentang semua—HR (Sumber Manusia), Kewangan, Operasi, dan Pentadbiran. Ini menjadikan anda pekerja serba boleh yang boleh masuk ke mana-mana industri. Asas yang kukuh jika anda mahu menjadi CEO atau Pengurus suatu hari nanti."
    },

    # --- EVENT MANAGEMENT ---
    "POLY-DIP-043": {
        "headline": "🎉 Pengurusan Acara: Cipta Kenangan",
        "synopsis": "Di sebalik konsert gempak, ekspo mega, dan perkahwinan mewah, ada 'Event Manager' yang sibuk. Anda belajar merancang bajet, mengurus logistik, dan menyelesaikan krisis masa nyata. Kerja ini pantas, tekanan tinggi, tetapi sangat menyeronokkan. Tiada hari yang membosankan!"
    },

    # --- HOTEL MANAGEMENT ---
    "POLY-DIP-044": {
        "headline": "🏨 Pengurusan Hotel: Layanan 5 Bintang",
        "synopsis": "Dunia hospitaliti bukan sekadar senyum. Anda belajar mengurus 'Front Office', operasi 'Housekeeping', dan perkhidmatan makanan (F&B). Keunikan kursus ini: Anda akan menjalani latihan industri (WBL) selama 10 bulan di hotel sebenar—belajar sambil bekerja dalam suasana profesional."
    },

    # --- LOGISTICS & SUPPLY CHAIN ---
    "POLY-DIP-045": {
        "headline": "📦 Logistik & Rantaian Bekalan: Nadi Ekonomi",
        "synopsis": "Bagaimana barang dari China sampai ke pintu rumah anda dalam 3 hari? Itu magis Logistik. Anda belajar mengurus gudang, penghantaran kargo (darat/laut/udara), dan inventori. Dalam era E-Commerce (Shopee/Lazada), pakar logistik adalah orang yang paling dicari oleh syarikat."
    },

    # --- TOURISM MANAGEMENT ---
    "POLY-DIP-046": {
        "headline": "✈️ Pengurusan Pelancongan: Duta Negara",
        "synopsis": "Bawa dunia melawat Malaysia. Anda belajar merangka pakej pelancongan, mengurus agensi travel, dan teknik pemandu pelancong. Anda akan mahir tentang destinasi, budaya, dan cara memberikan pengalaman terbaik kepada pelancong. Kerjaya ini membolehkan anda mengembara sambil bekerja."
    },

    # --- RETAIL MANAGEMENT ---
    "POLY-DIP-047": {
        "headline": "🛍️ Pengurusan Peruncitan: Bukan Sekadar Jaga Kaunter",
        "synopsis": "Industri runcit perlukan pengurus, bukan sekadar juruwang. Anda belajar strategi susun atur kedai, pembelian stok (buying), dan khidmat pelanggan visual. Dari kedai serbaneka hingga butik mewah, andalah yang memastikan kedai untung dan pelanggan gembira."
    },

    # --- RESORT MANAGEMENT ---
    "POLY-DIP-048": {
        "headline": "🏝️ Pengurusan Resort: Kerjaya di Syurga Percutian",
        "synopsis": "Beza dengan hotel bandar, resort adalah tentang 'pengalaman santai'. Anda belajar mengurus fasiliti rekreasi, spa, dan aktiviti tetamu di lokasi peranginan (pulau/tanah tinggi). Jika anda suka suasana kerja yang tenang dan cantik, ini kursus untuk anda."
    },

    # --- ACCOUNTING ---
    "POLY-DIP-049": {
        "headline": "📊 Perakaunan (Accounting): Bahasa Bisnes",
        "synopsis": "Setiap syarikat, dari gerai burger hingga Petronas, perlukan Akauntan. Anda belajar merekod duit masuk/keluar, mengira cukai, dan audit. Ini adalah laluan pantas untuk menjadi akauntan bertauliah (ACCA/CIMA) pada masa depan. Kerjaya yang sangat stabil dan dihormati."
    },

    # --- TOWN & REGIONAL PLANNING ---
    "POLY-DIP-050": {
        "headline": "🏙️ Perancang Bandar: Arkitek Bandaraya",
        "synopsis": "Siapa tentukan di mana sekolah, taman, dan kilang patut dibina? Itu tugas Perancang Bandar. Anda belajar melukis pelan guna tanah, undang-undang pembangunan, dan mereka bentuk bandar yang selesa didiami. Anda bekerja rapat dengan PBT (Majlis Perbandaran) untuk membentuk masa depan bandar kita."
    },

    # --- HALAL FOOD SERVICES ---
    "POLY-DIP-051": {
        "headline": "🍽️ Perkhidmatan Makanan Halal: Global Standard",
        "synopsis": "Pasaran Halal dunia bernilai trilion ringgit. Kursus ini bukan sekadar masak; ia tentang Sains Halal. Anda belajar audit Halal, pengurusan dapur patuh syariah, dan nutrisi. Graduan kursus ini sangat dicari oleh hotel 5 bintang dan syarikat makanan antarabangsa yang mahu menembusi pasaran Muslim."
    },

    # --- INTERNATIONAL BUSINESS ---
    "POLY-DIP-052": {
        "headline": "🌐 Perniagaan Antarabangsa: Bisnes Tanpa Sempadan",
        "synopsis": "Kenapa jual di kampung jika boleh jual satu dunia? Anda belajar selok-belok Import/Eksport, undang-undang perdagangan antarabangsa, dan logistik global. Anda akan faham bagaimana Amazon atau Alibaba beroperasi. Sesuai untuk anda yang mahu kerjaya 'jet-setting' dan berurusan dengan orang luar negara."
    },

    # --- FASHION DESIGN ---
    "POLY-DIP-053": {
        "headline": "👗 Reka Bentuk Fesyen: Dari Lakaran ke Runway",
        "synopsis": "Adakah anda 'Trendsetter'? Kursus ini mengajar anda mencipta pakaian dari A sampai Z—melukis ilustrasi, memotong pola (pattern making), dan menjahit. Anda akan belajar fesyen digital (CAD) dan strategi jenama. Kemuncak kursus adalah Pertunjukan Fesyen Akhir di mana koleksi anda diperagakan di pentas."
    },

    # --- GRAPHIC DESIGN ---
    "POLY-DIP-054": {
        "headline": "🎨 Reka Bentuk Grafik: Komunikasi Visual",
        "synopsis": "Di zaman Instagram dan TikTok, visual adalah raja. Anda belajar menggunakan Photoshop, Illustrator, dan InDesign untuk mencipta logo, poster, dan grafik media sosial. Anda dilatih berfikir secara kreatif untuk menyelesaikan masalah komunikasi jenama. Skill ini laku keras sebagai Freelancer!"
    },

    # --- INDUSTRIAL DESIGN ---
    "POLY-DIP-055": {
        "headline": "🛋️ Reka Bentuk Industri: Cipta Produk Masa Depan",
        "synopsis": "Gabungan Seni + Kejuruteraan. Anda belajar mereka bentuk perabot, gajet elektronik, atau peralatan dapur supaya nampak cantik DAN berfungsi dengan baik. Anda akan menggunakan printer 3D dan perisian modelling canggih. Anda adalah pencipta yang menjadikan hidup manusia lebih mudah dan bergaya."
    },

    # --- SECRETARIAL SCIENCE ---
    "POLY-DIP-056": {
        "headline": "u0025D8u0025A5 Sains Kesetiausahaan: Pengurusan Pejabat Profesional",
        "synopsis": "Setiausaha moden adalah 'Gatekeeper' kepada CEO. Anda belajar mengurus jadual bos, menulis surat rasmi korporat, dan menganjurkan mesyuarat protokol tinggi. Kursus ini melatih anda menjadi sangat teratur, cekap, dan berimej korporat. Anda adalah orang kanan yang paling dipercayai dalam ofis."
    },

    # --- ARCHITECTURE ---
    "POLY-DIP-057": {
        "headline": "🏛️ Seni Bina (Architecture): Arkitek Masa Depan",
        "synopsis": "Sebelum bangunan dibina, ia bermula dalam imaginasi anda. Anda belajar melukis pelan bangunan, membina model skala, dan menggunakan perisian BIM 3D. Anda menggabungkan seni (kecantikan) dengan sains (kekuatan struktur). Ini langkah pertama untuk menjadi Arkitek berdaftar."
    },

    # --- CULINARY ARTS ---
    "POLY-DIP-058": {
        "headline": "👨‍🍳 Seni Kulinari: Master Chef",
        "synopsis": "Dapur profesional bukan tempat main-main. Anda dilatih disiplin ketat ala tentera untuk menghasilkan hidangan bertaraf 5 bintang. Anda belajar masakan Barat, Asia, Pastri, dan pengurusan kos restoran. Latihan industri di hotel terkemuka akan menguji ketahanan mental dan fizikal anda."
    },

    # --- NAVAL ARCHITECTURE ---
    "POLY-DIP-059": {
        "headline": "⚓ Seni Bina Kapal: Reka Bentuk Marin",
        "synopsis": "Ini bukan Arkitek bangunan, ini Arkitek Kapal! Anda belajar mereka bentuk bentuk badan kapal (hull) supaya ia laju dan stabil di laut. Anda belajar tentang hidrodinamik dan kestabilan apungan. Graduan kursus ini bekerja di limbungan kapal (shipyard) untuk membina kapal perang, feri, atau kapal kargo."
    },

    # --- BUSINESS INFORMATION SYSTEMS ---
    "POLY-DIP-060": {
        "headline": "💻 Sistem Maklumat Perniagaan: IT + Bisnes",
        "synopsis": "Jambatan antara 'Orang IT' dan 'Orang Bisnes'. Anda faham coding (SQL/Database), tapi anda juga faham Akaun dan Marketing. Tugas anda adalah membina sistem komputer yang membantu syarikat buat duit. Contohnya: Membina sistem stok untuk kedai runcit atau aplikasi jualan."
    },

    # --- AQUACULTURE ---
    "POLY-DIP-061": {
        "headline": "🐟 Akuakultur: Jutawan Ikan",
        "synopsis": "Industri makanan masa depan bukan di laut, tapi di kolam. Anda belajar menternak ikan, udang, dan rumpai laut secara komersial. Dari pembenihan (breeding) hingga tuaian, anda diajar teknik moden untuk hasil maksimum. Ramai graduan kursus ini menjadi usahawan ternakan yang berjaya."
    },

    # --- WOOD-BASED TECHNOLOGY ---
    "POLY-DIP-062": {
        "headline": "🌲 Teknologi Kayu: Seni & Kejuruteraan",
        "synopsis": "Malaysia adalah pengeksport perabot utama dunia. Anda belajar sifat kayu, teknologi pemprosesan, dan pembuatan perabot moden. Anda akan menggunakan mesin canggih untuk menukar balak mentah menjadi produk bernilai tinggi. Kerjaya yang stabil dalam industri perkayuan negara."
    },

    # --- LANDSCAPE HORTICULTURE ---
    "POLY-DIP-063": {
        "headline": "🌳 Landskap: Senibina Alam",
        "synopsis": "Jadikan bandar kita 'Taman dalam Bandar'. Anda belajar mereka bentuk taman, memilih pokok yang sesuai, dan teknologi penyelenggaraan landskap. Anda menggabungkan ilmu botani (pokok) dengan seni reka bentuk. Projek anda boleh jadi taman perumahan, padang golf, atau resort."
    },

    # --- MARINE ELECTRICAL ---
    "POLY-DIP-064": {
        "headline": "⚡ Elektrik Marin: Kuasa di Lautan",
        "synopsis": "Kapal moden adalah 'bandar terapung' yang perlukan kuasa elektrik 24 jam. Anda belajar menyelenggara generator kapal, sistem radar, dan automasi marin. Graduan kursus ini layak menjadi Pegawai Elektro-Teknikal (ETO) di atas kapal dagang dengan gaji lumayan."
    },

    # --- MARINE CONSTRUCTION ---
    "POLY-DIP-065": {
        "headline": "🏗️ Pembinaan Marin: Membina Gergasi Laut",
        "synopsis": "Bagaimana besi berat boleh terapung? Anda belajar membina dan membaiki struktur kapal di limbungan (dry dock). Anda akan mahir dalam kimpalan marin, pemasangan paip kapal, dan struktur terapung. Kerjaya 'hands-on' yang mencabar di pelabuhan dan limbungan kapal."
    },

    # --- CHEMICAL TECHNOLOGY (FAT & OIL) ---
    "POLY-DIP-066": {
        "headline": "palmoil🌴 Teknologi Minyak & Lemak: Emas Sawit",
        "synopsis": "Malaysia adalah raja minyak sawit dunia. Kursus unik ini mengajar anda kimia di sebalik minyak masak, sabun, dan kosmetik. Anda akan bekerja di makmal atau kilang oleokimia untuk memastikan produk sawit kita berkualiti tinggi dan selamat digunakan."
    },

    # --- DIGITAL ANIMATION ---
    "POLY-DIP-067": {
        "headline": "🎬 Animasi Digital: Hidupkan Imaginasi",
        "synopsis": "Minat anime atau filem Pixar? Belajar buat sendiri! Anda akan diajar melukis watak, membina model 3D, dan teknik pergerakan (animation). Anda bakal menjadi sebahagian daripada industri kreatif yang menghasilkan siri TV, filem, dan iklan gempak."
    },

    # --- VIDEO PRODUCTION ---
    "POLY-DIP-068": {
        "headline": "🎥 Produksi Video: Di Sebalik Tabir",
        "synopsis": "Lampu, Kamera, Action! Anda belajar teknik penggambaran, penulisan skrip, dan suntingan video (editing). Anda akan hasilkan filem pendek, dokumentari, dan video muzik anda sendiri. Sesuai untuk anda yang mahu jadi Youtuber profesional atau krew filem."
    },

    # --- DIGITAL ART ---
    "POLY-DIP-069": {
        "headline": "🎨 Seni Digital: Multimedia Kreatif",
        "synopsis": "Kursus paling luas dalam bidang kreatif. Anda belajar ilustrasi digital, kesan visual (VFX), dan reka bentuk konsep (Concept Art). Kemahiran ini laku keras dalam industri game, filem, dan pengiklanan. Anda adalah seniman moden yang melukis menggunakan tablet, bukan berus."
    },

    # --- FOOD TECHNOLOGY ---
    "POLY-DIP-070": {
        "headline": "🍔 Teknologi Makanan: Sains Di Sebalik Makanan",
        "synopsis": "Bagaimana makanan dalam tin tahan lama? Bagaimana buat burger daging tanpa daging? Anda belajar sains pemprosesan, pengawetan, dan pembungkusan makanan. Anda memastikan makanan yang kita beli di pasar raya adalah selamat, sedap, dan berkualiti."
    },

    # --- HALAL FOOD TECHNOLOGY ---
    "POLY-DIP-071": {
        "headline": "🥗 Teknologi Makanan (Pengurusan Halal)",
        "synopsis": "Industri Halal bukan sekadar 'No Pork'. Ia tentang sains kebersihan, keselamatan, dan pematuhan syariah yang ketat. Anda belajar sains pemprosesan makanan DAN undang-undang Halal JAKIM. Graduan kursus ini mendapat Sijil Eksekutif Halal—lesen mahal yang membolehkan anda menjadi Auditor Halal bertauliah."
    },

    # --- IT: SOFTWARE & APPS ---
    "POLY-DIP-072": {
        "headline": "📱 IT (Software & App Development): Pembangun Aplikasi",
        "synopsis": "Anda ada idea untuk 'Grab' atau 'TikTok' seterusnya? Kursus ini mengajar anda membina perisian dari kosong. Anda belajar coding (Java, Python, C++), mereka bentuk antaramuka (UI/UX), dan membangunkan aplikasi Mobile (Android/iOS). Anda adalah arkitek dunia digital."
    },

    # --- IT: NETWORKING ---
    "POLY-DIP-073": {
        "headline": "🌐 IT (Networking System): Jurutera Internet",
        "synopsis": "Tanpa anda, Netflix takkan loading. Anda belajar membina dan menjaga infrastruktur internet. Anda akan 'configure' router, switch, dan server. Anda adalah wira di sebalik tabir yang memastikan Wi-Fi laju, server tak 'down', dan data mengalir lancar di seluruh dunia."
    },

    # --- IT: INFORMATION SECURITY ---
    "POLY-DIP-074": {
        "headline": "🔐 IT (Information Security): Cyber Warrior",
        "synopsis": "Dunia siber penuh dengan hacker dan scammer. Tugas anda adalah menghalang mereka. Anda belajar tentang 'Ethical Hacking', penyulitan data (Encryption), dan forensik digital. Anda adalah polis siber yang melindungi data sulit bank, kerajaan, dan syarikat besar."
    },

    # --- IT: GAME PROGRAMMING ---
    "POLY-DIP-075": {
        "headline": "🎮 IT (Game Programming): Cipta Dunia Maya",
        "synopsis": "Jangan hanya main game, buat game sendiri! Anda belajar enjin permainan (Unity/Unreal), logik AI untuk musuh dalam game, dan fizik permainan. Kursus ini menggabungkan matematik, seni, dan coding. Sesuai untuk gamers yang mahu menukar hobi menjadi kerjaya profesional."
    },

    # --- IT: WEB DEVELOPMENT ---
    "POLY-DIP-076": {
        "headline": "💻 IT (Web Development): Arkitek Web",
        "synopsis": "Laman web adalah wajah syarikat. Anda belajar membina website yang cantik, pantas, dan selamat. Anda akan menguasai HTML, CSS, JavaScript, dan pangkalan data. Dari laman E-Commerce (Shopee) hingga portal korporat, anda yang membinanya."
    },

    # --- IT: DATA MANAGEMENT ---
    "POLY-DIP-077": {
        "headline": "📊 IT (Data Management): Saintis Data",
        "synopsis": "Data adalah minyak baharu. Syarikat perlukan orang yang pandai membaca trend dari data lambak (Big Data). Anda belajar mengumpul, menyusun, dan memvisualisasikan data menjadi graf yang bermakna. Skill ini sangat penting untuk syarikat membuat keputusan bisnes."
    },

    # --- PRINT MEDIA TECHNOLOGY ---
    "POLY-DIP-078": {
        "headline": "🖨️ Teknologi Media Cetak: Lebih Dari Kertas",
        "synopsis": "Percetakan belum mati, ia berevolusi. Anda belajar teknologi percetakan digital, pembungkusan (packaging), dan penerbitan buku. Anda akan mahir mengendalikan mesin cetak industri dan perisian desktop publishing. Industri ini kritikal untuk pengiklanan dan pembungkusan produk."
    },

    # --- QUANTITY SURVEYING ---
    "POLY-DIP-079": {
        "headline": "📋 Ukur Bahan (QS): Akauntan Binaan",
        "synopsis": "Dalam pembinaan, setiap bata ada harganya. Tugas QS adalah mengira kos projek dari awal sampai siap. Anda memastikan projek tidak lari bajet, mengurus kontrak, dan membayar kontraktor. Kerjaya ini sangat profesional dan bergaji lumayan di firma pembinaan."
    },

    # --- BATIK FASHION DESIGN ---
    "POLY-DIP-080": {
        "headline": "👘 Reka Bentuk Fesyen Batik: Warisan Glamor",
        "synopsis": "Gabungan tradisi dan fesyen moden. Anda belajar teknik mencanting batik asli DAN reka bentuk fesyen kontemporari. Anda bukan sekadar melukis kain, anda mencipta busana 'Haute Couture' berasaskan warisan negara. Sesuai untuk mereka yang berjiwa seni halus."
    },

    # --- CRAFT DESIGN ---
    "POLY-DIP-081": {
        "headline": "🪑 Reka Bentuk Kraf: Perabot & Seni",
        "synopsis": "Gabungan seni tangan tradisional dengan teknologi moden (CNC Machining). Anda belajar mereka bentuk perabot, ukiran kayu, dan produk kraf komersial. Anda bukan sekadar tukang kayu, tetapi pereka yang menghasilkan produk bernilai tinggi untuk pasaran eksport dan hiasan dalaman."
    },

    # --- LOGISTICS (ADDITIONAL) ---
    "POLY-DIP-082": {
        "headline": "🚚 Pengurusan Logistik: Pakar Penghantaran",
        "synopsis": "Dalam dunia E-Dagang, barang perlu bergerak laju. Kursus ini melatih anda menguruskan pergerakan barang dari kilang ke pengguna. Anda belajar tentang gudang, pengangkutan antarabangsa, dan inventori. Kemahiran ini sangat penting untuk memastikan ekonomi negara berjalan lancar."
    },

    # --- CERTIFICATE LEVEL (SIJIL) ---
    "POLY-CET-001": {
        "headline": "👷 Sijil Kejuruteraan Awam: Langkah Mula Binaan",
        "synopsis": "Laluan pantas ke tapak binaan. Anda belajar asas penting: bancuhan konkrit, kerja paip, dan penyeliaan tapak. Sijil ini membolehkan anda terus bekerja sebagai penyelia junior, ATAU sambung belajar ke peringkat Diploma (hanya 2 tahun lagi) untuk kerjaya lebih tinggi."
    },
    "POLY-CET-002": {
        "headline": "⚡ Sijil Kejuruteraan Elektrik: Pakar Wiring",
        "synopsis": "Fokus 100% pada kemahiran tangan. Anda akan mahir membuat pendawaian (wiring) rumah dan pejabat, membaiki kerosakan litar, dan penyelenggaraan asas. Lulusan kursus ini sangat laku sebagai juruteknik mahir, atau boleh terus sambung Diploma untuk menjadi pakar yang lebih besar."
    },
    "POLY-CET-003": {
        "headline": "⚙️ Sijil Kejuruteraan Mekanikal: Mahir Mesin",
        "synopsis": "Anda suka kerja tangan? Kursus ini mengajar anda menggunakan mesin bengkel (welding, memesin) dan melukis pelan CAD asas. Ia adalah asas kukuh untuk menjadi juruteknik kilang yang cekap. Selepas tamat, anda boleh terus bekerja atau naik taraf ke Diploma Kejuruteraan Mekanikal."
    },

    # ==========================================
    # KOLEJ KOMUNITI - DIPLOMA COURSES
    # ==========================================

    # --- HAIR DESIGN ---
    "KKOM-DIP-001": {
        "headline": "✂️ Dandanan Rambut: Stylist Profesional",
        "synopsis": "Bukan sekadar potong rambut. Anda belajar kimia pewarna rambut, rawatan kulit kepala, dan pengurusan salun. Kemahiran ini 'kalis kemelesetan'—orang sentiasa perlu gunting rambut. Sesuai untuk anda yang kreatif, suka berfesyen, dan bercita-cita buka kedai sendiri.",
        "pathway": "Ijazah Sarjana Muda Seni Kreatif / Pengurusan Perniagaan"
    },

    # --- 3D ANIMATION ---
    "KKOM-DIP-002": {
        "headline": "🎬 Animasi 3D: Hidupkan Karakter",
        "synopsis": "Minat filem Pixar atau game 3D? Belajar cara buat karakter bergerak, ekspresi muka, dan kesan visual (VFX). Kursus ini fokus kepada skil teknikal menggunakan software canggih. Anda akan hasilkan portfolio 'showreel' anda sendiri untuk tunjuk pada majikan.",
        "pathway": "Ijazah Sarjana Muda Animasi / Multimedia Kreatif"
    },

    # --- ARCHITECTURAL TECHNOLOGY ---
    "KKOM-DIP-003": {
        "headline": "🏢 Teknologi Seni Bina: Pelukis Pelan Digital",
        "synopsis": "Anda bukan Arkitek, tapi andalah orang kanan Arkitek. Anda belajar menggunakan perisian BIM (Building Information Modelling) untuk melukis bangunan dalam 3D. Industri pembinaan sekarang Wajib guna BIM, jadi graduan kursus ini sangat laku keras.",
        "pathway": "Ijazah Sarjana Muda Sains Seni Bina / Ukur Bahan"
    },

    # --- CULINARY ARTS ---
    "KKOM-DIP-004": {
        "headline": "🍳 Seni Kulinari: Chef Muda",
        "synopsis": "Belajar masak sambil bekerja! Program ini unik kerana ada 'Work Based Learning'—anda akan bekerja di hotel sebenar selama 8 bulan. Anda belajar masakan Barat, Asia, dan pengurusan dapur. Ini jalan pantas untuk jadi Chef tanpa perlu bayar yuran kolej swasta yang mahal.",
        "pathway": "Ijazah Sarjana Muda Seni Kulinari / Pengurusan Hotel"
    },

    # --- ELECTRONICS (INSTRUMENTATION) ---
    "KKOM-DIP-005": {
        "headline": "🎛️ Elektronik (Instrumentasi): Pakar Sensor Kilang",
        "synopsis": "Kilang moden penuh dengan sensor dan robot. Siapa yang pastikan sensor tu tepat? Anda! Kursus ini mengajar anda membaiki, menentukur (calibrate), dan menyelenggara alat elektronik di kilang. Kerja ini sangat spesifik dan bergaji tinggi dalam sektor pembuatan.",
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektrik / Elektronik"
    },

    # --- GAMES ART ---
    "KKOM-DIP-006": {
        "headline": "🎮 Games Art: Reka Dunia Video Game",
        "synopsis": "Khas untuk 'Gamers'. Anda belajar mereka bentuk senjata, raksasa, kenderaan, dan latar belakang (environment) untuk video game. Anda akan guna 'Game Engine' sebenar. Jangan sekadar main game, jadilah orang yang menciptanya.",
        "pathway": "Ijazah Sarjana Muda Pembangunan Permainan / Multimedia"
    },

    # --- HOTEL MANAGEMENT ---
    "KKOM-DIP-007": {
        "headline": "🏨 Pengurusan Hotel: Kerjaya Hospitaliti",
        "synopsis": "Masuk terus ke industri perhotelan. Anda belajar mengurus tetamu di Front Office, menjaga kebersihan Housekeeping, dan menyelia restoran. Program ini ada latihan industri panjang (WBL), jadi anda tamat belajar dengan pengalaman kerja sebenar.",
        "pathway": "Ijazah Sarjana Muda Pengurusan Hotel / Pelancongan"
    },

    # --- MECHANICAL DESIGN ---
    "KKOM-DIP-008": {
        "headline": "📐 Reka Bentuk Mekanikal: Lukis Paip & Mesin",
        "synopsis": "Fokus kepada lukisan teknikal untuk industri Minyak & Gas serta Kilang. Anda belajar software CAD untuk melukis sistem paip (Piping) dan komponen mesin. Skill ini sangat penting untuk syarikat kejuruteraan yang membina loji atau mesin.",
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Mekanikal / Pembuatan"
    },

    # --- MOBILE TECHNOLOGY ---
    "KKOM-DIP-009": {
        "headline": "📱 Teknologi Mudah Alih: Doktor Telefon & Apps",
        "synopsis": "Telefon rosak? Skrin pecah? Anda akan jadi pakar membaiki (repair) telefon pintar dan tablet. Selain hardware, anda juga belajar asas buat Apps dan UI/UX design. Sangat sesuai kalau anda nak buka kedai repair phone sendiri satu hari nanti.",
        "pathway": "Ijazah Sarjana Muda Elektronik / Telekomunikasi"
    },

    # --- PATISSERIE ---
    "KKOM-DIP-010": {
        "headline": "🍰 Pastri: Seni Kek & Roti",
        "synopsis": "Khas untuk yang teliti dan berseni. Anda fokus sepenuhnya kepada pembuatan roti, kek, coklat, dan hiasan gula (sugar art). Anda akan berlatih di dapur industri dan hotel. Skill ini laku keras untuk kerja hotel atau jual kek dari rumah (Home Baker).",
        "pathway": "Ijazah Sarjana Muda Seni Kulinari / Pengurusan Perkhidmatan Makanan"
    },

    # --- RAIL SIGNALLING ---
    "KKOM-DIP-011": {
        "headline": "🚄 Teknologi Rel: Kerjaya di Landasan",
        "synopsis": "Industri kereta api negara (MRT, LRT, ECRL) sedang berkembang pesat. Siapa yang pastikan tren tidak berlanggar? Anda! Kursus ini mengajar sistem isyarat (signalling) dan komunikasi keretapi. Sangat spesifik dan sangat diperlukan oleh syarikat seperti RapidKL dan KTMB.",
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektrik / Pengangkutan"
    },

    # --- SOUND & LIGHTING ---
    "KKOM-DIP-012": {
        "headline": "lighting💡 Bunyi & Cahaya: Krew Konsert Profesional",
        "synopsis": "Impian bekerja di balik tabir konsert atau rancangan TV? Kursus ini mengajar anda 'setup' sistem bunyi (PA system) dan lampu pentas yang canggih. Anda akan belajar tentang akustik, pendawaian pentas, dan kesan khas. Suasana kerja yang seronok dan tidak membosankan.",
        "pathway": "Ijazah Sarjana Muda Penyiaran / Kejuruteraan Audio"
    },

    # --- TELECOMMUNICATION ---
    "KKOM-DIP-013": {
        "headline": "📡 Telekomunikasi: Wira 5G & Internet",
        "synopsis": "Dunia tak boleh hidup tanpa internet. Anda belajar cara memasang kabel Fiber Optik, menyelenggara menara telekomunikasi, dan sistem rangkaian tanpa wayar. Kerjaya ini menjanjikan masa depan cerah kerana teknologi 5G sedang meletup sekarang.",
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektronik / Komunikasi"
    },

    # --- COMMERCIAL VEHICLE ---
    "KKOM-DIP-014": {
        "headline": "🚛 Kenderaan Perdagangan: Doktor Lori & Bas",
        "synopsis": "Jangan jadi mekanik kereta biasa. Jadilah pakar kenderaan berat! Enjin diesel, sistem brek angin, dan hidraulik lori memerlukan kepakaran khas. Gaji mekanik kenderaan berat selalunya lebih lumayan kerana industri logistik sangat bergantung kepada anda.",
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Mekanikal / Automotif"
    },

    # --- SOLAR PHOTOVOLTAIC ---
    "KKOM-DIP-015": {
        "headline": "☀️ Teknologi Solar: Tenaga Hijau",
        "synopsis": "Jadilah sebahagian daripada revolusi tenaga hijau. Anda belajar cara memasang panel solar di bumbung rumah dan bangunan, serta membuat pendawaian sistem solar (PV). Malaysia panas sepanjang tahun, jadi industri ini memang lubuk duit bagi mereka yang mahir.",
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektrik / Tenaga Boleh Baharu"
    },

    # --- BEAUTY THERAPY ---
    "KKOM-DIP-016": {
        "headline": "💅 Terapi Kecantikan: Pakar Spa & Estetik",
        "synopsis": "Kecantikan adalah bisnes besar. Anda belajar teknik rawatan muka (facial), spa tangan/kaki, dan seni solekan (makeup). Kursus ini juga mengajar anda cara menguruskan kedai spa. Sangat sesuai jika anda bercita-cita membuka spa atau menjadi jurusolek profesional.",
        "pathway": "Ijazah Sarjana Muda Pengurusan Pelancongan / Kesejahteraan (Wellness)"
    },

    # ==========================================
    # KOLEJ KOMUNITI - CERTIFICATE (SIJIL)
    # ==========================================

    # --- CULINARY (CERT) ---
    "KKOM-CET-001": {
        "headline": "👨‍🍳 Sijil Kulinari: Langkah Mula Chef",
        "synopsis": "Kursus pantas untuk masuk ke dapur profesional. Belajar asas memotong, memasak lauk Barat & Asia, dan disiplin dapur. Tamat belajar boleh terus kerja hotel, atau sambung Diploma untuk gaji lebih besar.",
        "pathway": "Diploma Seni Kulinari / Pengurusan Hotel (Politeknik/KK)"
    },

    # --- F&B SERVICE (CERT) ---
    "KKOM-CET-002": {
        "headline": "☕ Sijil Servis Makanan & Minuman: Profesional F&B",
        "synopsis": "Menjadi pelayan (waiter) profesional bukan sekadar hantar makanan. Anda belajar seni hidangan 'Fine Dining', bancuhan air (Barista), dan layanan tetamu VIP. Hotel 5 bintang sentiasa mencari staf yang terlatih sebegini.",
        "pathway": "Diploma Pengurusan Hotel / Pelancongan (Politeknik/KK)"
    },

    # --- RECREATIONAL TOURISM (CERT) ---
    "KKOM-CET-003": {
        "headline": "rafting🚣 Sijil Pelancongan Rekreasi: Kerjaya Outdoor",
        "synopsis": "Suka aktiviti lasak? Kursus ini ajar anda jadi jurupandu (guide) untuk aktiviti seperti hiking, water rafting, dan kem rekreasi. Belajar teknik keselamatan (First Aid) dan cara melayan pelancong. Kerja sambil main!",
        "pathway": "Diploma Pelancongan Rekreasi / Pengurusan Acara (Politeknik/KK)"
    },

    # --- AGROTECHNOLOGY (CERT) ---
    "KKOM-CET-004": {
        "headline": "🌱 Sijil Agroteknologi: Asas Pertanian",
        "synopsis": "Belajar cara tanam pokok, buat baja, dan urus tapak semaian (nursery). Kursus ini 100% praktikal di ladang. Sesuai untuk anda yang suka berbudi pada tanah atau nak tolong usahakan tanah keluarga.",
        "pathway": "Diploma Agroteknologi / Hortikultur Landskap (Politeknik)"
    },
    
    # --- 2D ANIMATION (CERT) ---
    "KKOM-CET-005": {
        "headline": "🎬 Sijil Animasi 2D: Kartun & Grafik",
        "synopsis": "Minat melukis anime atau kartun? Kursus ini ajar anda asas animasi 2D—dari lukisan tangan hingga digital. Anda akan belajar buat watak (Character Design) dan Papan Cerita (Storyboard). Langkah pertama untuk kerja di studio animasi Malaysia yang sedang naik.",
        "pathway": "Diploma Rekabentuk Grafik / Animasi (WBL)"
    },

    # --- 3D ANIMATION (CERT) ---
    "KKOM-CET-006": {
        "headline": "🧊 Sijil Animasi 3D: Dunia Maya",
        "synopsis": "Belajar buat model 3D menggunakan komputer. Anda akan cipta watak, kenderaan, dan bangunan dalam bentuk 3D. Kursus ini fokus kepada teknikal—modelling, texturing, dan rendering. Sesuai untuk gamers yang nak tahu macam mana game dibuat.",
        "pathway": "Diploma Animasi 3D / Games Art (WBL)"
    },

    # --- HAIR DESIGN (CERT) ---
    "KKOM-CET-007": {
        "headline": "✂️ Sijil Dandanan Rambut: Gunting & Gaya",
        "synopsis": "Kemahiran gunting rambut adalah kemahiran seumur hidup. Anda belajar teknik gunting lelaki & wanita, mewarna, dan kerinting rambut. Kursus ini juga ajar cara buka kedai gunting rambut sendiri. Modal kecil, untung besar!",
        "pathway": "Diploma Dandanan Rambut (WBL) / Terapi Kecantikan"
    },

    # --- FASHION & APPAREL (CERT) ---
    "KKOM-CET-008": {
        "headline": "👗 Sijil Fesyen & Pakaian: Jahit Baju Sendiri",
        "synopsis": "Dari lakaran ke baju siap. Anda belajar memotong kain, menjahit baju kurung/kemeja, dan menghias pakaian. Tak perlu beli baju lagi, anda boleh buat sendiri atau ambil tempahan orang. Ramai graduan kursus ini berjaya buka butik atau bisnes jahitan dari rumah.",
        "pathway": "Diploma Reka Bentuk Fesyen"
    },

    # --- CULINARY (CERT) - Same title but different ID from previous batch? ---
    # Check if duplicate. Assuming specific ID:
    "KKOM-CET-009": {
        "headline": "🍳 Sijil Kulinari: Asas Masakan Hotel",
        "synopsis": "Masuk dapur dengan yakin. Anda belajar potong, masak, dan hias makanan ala hotel. Kursus ini merangkumi masakan panas (Hot Kitchen) dan keselamatan makanan. Sangat praktikal untuk anda yang nak kerja restoran atau hotel cepat.",
        "pathway": "Diploma Seni Kulinari / Pengurusan Hotel"
    },

    # --- LANDSCAPE (CERT) ---
    "KKOM-CET-010": {
        "headline": "🌳 Sijil Landskap: Taman & Bunga",
        "synopsis": "Suka pokok dan alam? Anda belajar cara tanam pokok hiasan, reka bentuk taman mini, dan penjagaan rumput turf. Kerja ini menenangkan dan sentiasa ada permintaan untuk rumah-rumah baru dan projek perbandaran.",
        "pathway": "Diploma Teknologi Hortikultur Landskap / Agroteknologi"
    },

    # --- CREATIVE ADVERTISING (CERT) ---
    "KKOM-CET-011": {
        "headline": "📢 Sijil Pengiklanan Multimedia: Design & Iklan",
        "synopsis": "Belajar buat poster iklan, bunting, dan grafik media sosial yang menarik. Anda akan guna software grafik (Photoshop/Illustrator) dan belajar asas fotografi. Skill ini sangat penting untuk semua jenis bisnes yang nak buat marketing.",
        "pathway": "Diploma Rekabentuk Grafik / Media Cetak"
    },

    # --- HOTEL OPERATIONS (CERT) ---
    "KKOM-CET-012": {
        "headline": "🛎️ Sijil Operasi Perhotelan: Servis Tetamu",
        "synopsis": "Kursus 'All-in-One' untuk kerja hotel. Anda belajar sikit tentang Front Office (Reception), Housekeeping (Kemas Bilik), dan F&B (Hidang Makanan). Ini menjadikan anda pekerja serba boleh yang disukai oleh pengurus hotel.",
        "pathway": "Diploma Pengurusan Hotel / Pelancongan"
    },

    # --- PASTRY (CERT) ---
    "KKOM-CET-013": {
        "headline": "🍰 Sijil Pastri: Roti & Kek",
        "synopsis": "Fokus kepada 'Baking'. Belajar buat roti, kek hari jadi, dan biskut raya. Anda akan diajar teknik menghias kek (icing) yang cantik. Ramai graduan kursus ini buat duit dengan menjual kek dari rumah secara online.",
        "pathway": "Diploma Pastri / Seni Kulinari"
    },

    # --- TRAVEL & TOURISM (CERT) ---
    "KKOM-CET-014": {
        "headline": "✈️ Sijil Pengembaraan Pelancongan: Kerja Travel",
        "synopsis": "Nak kerja sambil jalan-jalan? Kursus ini ajar anda jadi Pemandu Pelancong (Tour Guide) dan cara urus tiket/tempahan. Anda belajar bercakap dengan yakin depan orang ramai. Sesuai untuk personaliti yang ceria dan suka jumpa orang.",
        "pathway": "Diploma Pengurusan Pelancongan"
    },

    # --- EVENT MANAGEMENT (CERT) ---
    "KKOM-CET-015": {
        "headline": "🎉 Sijil Pengendalian Acara: Krew Majlis",
        "synopsis": "Suka suasana meriah? Belajar cara menguruskan majlis perkahwinan, acara sukan, dan katering. Anda akan diajar protokol, susun atur dewan, dan layanan tetamu. Kerjaya yang seronok dan membolehkan anda jumpa ramai orang baru setiap hari.",
        "pathway": "Diploma Pengurusan Acara / Pelancongan"
    },

    # --- BUSINESS OPERATIONS (CERT) ---
    "KKOM-CET-016": {
        "headline": "💼 Sijil Pengoperasian Perniagaan: Asas Bisnes",
        "synopsis": "Nak tahu cara jalankan bisnes? Kursus ini ajar anda asas perakaunan, pemasaran, dan pengurusan stok. Sesuai untuk anda yang nak jadi kerani akaun yang cekap ATAU nak buka bisnes sendiri dengan ilmu yang betul.",
        "pathway": "Diploma Pengajian Perniagaan / Pemasaran"
    },

    # --- BUILDING MAINTENANCE (CERT) ---
    "KKOM-CET-017": {
        "headline": "🛠️ Sijil Penyelenggaraan Bangunan: Handyman Profesional",
        "synopsis": "Bangunan rosak? Anda yang baiki! Belajar asas paip, elektrik, aircond, dan kimpalan. Anda akan jadi 'Handyman' serba boleh yang sangat diperlukan oleh pejabat, hotel, dan sekolah. Kerja stabil dan gaji lumayan.",
        "pathway": "Diploma Kejuruteraan Perkhidmatan Bangunan / Awam"
    },

    # --- CONSTRUCTION SUPERVISION (CERT) ---
    "KKOM-CET-018": {
        "headline": "👷 Sijil Penyeliaan Tapak Bina: Kapten Tapak",
        "synopsis": "Jadilah ketua di tapak binaan. Anda belajar membaca pelan bangunan, menyelia pekerja, dan memastikan keselamatan tapak. Sesuai untuk anda yang suka kerja luar (outdoor) dan berjiwa kepimpinan.",
        "pathway": "Diploma Kejuruteraan Awam / Seni Bina"
    },

    # --- LOGISTICS (CERT) ---
    "KKOM-CET-019": {
        "headline": "📦 Sijil Perkhidmatan Logistik: Urus Kargo",
        "synopsis": "Belajar cara barang bergerak di seluruh dunia. Anda akan diajar mengurus gudang, stok, dan penghantaran lori. Dalam zaman Shopee/Lazada ni, pakar logistik memang laku keras!",
        "pathway": "Diploma Pengurusan Logistik / Perniagaan"
    },

    # --- INTERIOR DESIGN (CERT) ---
    "KKOM-CET-020": {
        "headline": "🛋️ Sijil Rekabentuk Dalaman: Hias Rumah",
        "synopsis": "Minat menghias bilik? Belajar cara susun perabot, pilih warna, dan lukis pelan hiasan dalaman (ID). Anda akan guna komputer untuk buat design 3D. Boleh kerja dengan firma ID atau jadi perunding hiasan bebas.",
        "pathway": "Diploma Seni Bina / Rekabentuk Dalaman"
    },

    # --- FURNITURE MAKING (CERT) ---
    "KKOM-CET-021": {
        "headline": "🪑 Sijil Pembuatan Perabot: Tukang Kayu Moden",
        "synopsis": "Gabungan seni pertukangan dan mesin moden. Belajar buat kerusi, meja, dan kabinet dapur yang berkualiti tinggi. Anda juga belajar ukiran kayu. Skill ini sangat mahal harganya dan membolehkan anda buka bengkel perabot sendiri.",
        "pathway": "Diploma Teknologi Berasaskan Kayu / Reka Bentuk Kraf"
    },

    # --- CREATIVE VISUAL ART (CERT) ---
    "KKOM-CET-022": {
        "headline": "🎨 Sijil Seni Visual Kreatif: Produk Kraf",
        "synopsis": "Buat duit dengan seni. Belajar buat cenderamata, batik, dan seramik yang boleh dijual. Kursus ini fokus kepada keusahawanan seni—bukan sekadar buat cantik, tapi buat yang orang nak beli.",
        "pathway": "Diploma Reka Bentuk Kraf / Fesyen"
    },

    # --- AQUACULTURE (CERT) ---
    "KKOM-CET-023": {
        "headline": "🐟 Sijil Teknologi Akuakultur: Ternak Ikan",
        "synopsis": "Belajar menternak ikan air tawar dan udang. Anda akan diajar teknik pembenihan, penjagaan kolam, dan rawatan penyakit ikan. Industri makanan sentiasa hidup, jadi peluang untuk jadi usahawan ternakan sangat cerah.",
        "pathway": "Diploma Teknologi Akuakultur (Politeknik)"
    },

    # --- AUTOMOTIVE (CERT) ---
    "KKOM-CET-024": {
        "headline": "🚗 Sijil Teknologi Automotif: Mekanik Mahir",
        "synopsis": "Kursus wajib untuk 'kaki kereta'. Belajar servis enjin, sistem brek, dan aircond kereta. Anda akan jadi mekanik bertauliah yang boleh kerja di pusat servis Honda/Toyota atau buka bengkel sendiri.",
        "pathway": "Diploma Kejuruteraan Mekanikal (Automotif)"
    },

    # --- ELECTRICAL TECHNOLOGY (CERT) ---
    "KKOM-CET-025": {
        "headline": "⚡ Sijil Teknologi Elektrik: Asas Pendawaian",
        "synopsis": "Belajar buat wiring rumah dan kilang. Anda akan diajar pasang suis, soket, dan papan agihan (DB). Ini adalah langkah pertama untuk mendapatkan lesen kompetensi PW2/PW4 dari Suruhanjaya Tenaga. Kemahiran wajib ada untuk jadi kontraktor elektrik.",
        "pathway": "Diploma Kejuruteraan Elektrik / Elektronik"
    },

    # --- ELECTRICAL INSTALLATION (CERT) - Specific Specialization ---
    "KKOM-CET-026": {
        "headline": "🔌 Sijil Pemasangan Elektrik: Pendawaian Industri",
        "synopsis": "Fokus kepada pendawaian Tiga Fasa (3-Phase) yang digunakan di kilang dan bangunan besar. Anda belajar kawalan motor elektrik dan sistem kuasa industri. Gaji pendawai industri selalunya lebih tinggi daripada pendawai rumah biasa.",
        "pathway": "Diploma Kejuruteraan Elektrik (Kuasa/Industri)"
    },

    # --- INFORMATION TECHNOLOGY (CERT) ---
    "KKOM-CET-027": {
        "headline": "💻 Sijil Teknologi Maklumat: Juruteknik IT",
        "synopsis": "Jadilah orang yang semua orang cari bila komputer rosak. Anda belajar format PC, pasang network (LAN), dan asas database. Anda juga diajar asas coding dan keselamatan siber. Kerja stabil di mana-mana ofis atau sekolah.",
        "pathway": "Diploma Teknologi Maklumat / Rangkaian"
    },

    # --- BUILDING CONSTRUCTION (CERT) ---
    "KKOM-CET-028": {
        "headline": "🏗️ Sijil Teknologi Pembinaan: Bina Rumah",
        "synopsis": "Belajar cara bina bangunan dari A sampai Z. Anda akan buat kerja konkrit, ikat bata, dan pasang bumbung. Kursus ini sangat praktikal. Tamat belajar, anda boleh kerja dengan kontraktor besar atau ambil upah ubah suai rumah.",
        "pathway": "Diploma Kejuruteraan Awam / Seni Bina"
    },

    # --- MANUFACTURING TECHNOLOGY (CERT) ---
    "KKOM-CET-029": {
        "headline": "🏭 Sijil Teknologi Pembuatan: Operator Mesin",
        "synopsis": "Kilang perlukan orang yang pandai guna mesin. Anda belajar kendalikan mesin Lathe, Milling, dan CNC. Anda juga belajar baca pelan kejuruteraan. Graduan kursus ini sangat laku di kawasan perindustrian seperti Shah Alam, Penang, dan Johor.",
        "pathway": "Diploma Kejuruteraan Mekanikal (Pembuatan)"
    },

    # --- FOOD PROCESSING (CERT) ---
    "KKOM-CET-030": {
        "headline": "🥫 Sijil Pemprosesan Makanan: Kilang Makanan",
        "synopsis": "Belajar cara buat makanan tahan lama (canning, packaging) dan produk sejuk beku. Anda juga belajar tentang kawalan kualiti (QC) dan persijilan Halal. Sesuai untuk anda yang nak kerja di kilang makanan atau buat produk jenama sendiri (IKS).",
        "pathway": "Diploma Teknologi Makanan / Halal"
    },

    # --- AIR-CONDITIONING (CERT) ---
    "KKOM-CET-031": {
        "headline": "❄️ Sijil Penyejukan & Penyamanan Udara: Pakar Aircond",
        "synopsis": "Di Malaysia yang panas, tukang aircond tak pernah putus kerja. Anda belajar pasang, servis, dan repair aircond rumah serta sistem chiller bangunan. Modal untuk mula bisnes sendiri sangat rendah, tapi pulangannya lumayan.",
        "pathway": "Diploma Kejuruteraan Mekanikal (Penyamanan Udara)"
    },

    # --- 4WD MAINTENANCE (CERT) ---
    "KKOM-CET-032": {
        "headline": "🚙 Sijil Penyelenggaraan 4WD: Mekanik Offroad",
        "synopsis": "Bukan kereta biasa, ini kereta pacuan 4 roda (4x4). Anda belajar sistem transmisi 4WD, suspensi lasak, dan enjin diesel turbo. Peminat offroad sanggup bayar mahal untuk mekanik yang faham kereta mereka. Jadilah pakar dalam niche ini.",
        "pathway": "Diploma Kejuruteraan Mekanikal (Automotif)"
    },

    # --- INDUSTRIAL MAINTENANCE (CERT) ---
    "KKOM-CET-033": {
        "headline": "⚙️ Sijil Penyenggaraan Industri: Doktor Kilang",
        "synopsis": "Mesin kilang tak boleh rosak lama-lama. Anda belajar sistem hidraulik, pneumatik (angin), dan kimpalan asas untuk membaiki mesin. Anda adalah 'doktor' yang memastikan kilang terus beroperasi 24 jam.",
        "pathway": "Diploma Kejuruteraan Mekanikal / Mekatronik"
    },

    # --- SUPERBIKE MAINTENANCE (CERT) ---
    "KKOM-CET-034": {
        "headline": "🏍️ Sijil Motosikal Berkuasa Tinggi: Mekanik Superbike",
        "synopsis": "Minat motor besar? Belajar servis enjin superbike, setting suspensi, dan sistem suntikan bahan api (fuel injection). Mekanik kapcai biasa tak reti buat ni. Ini adalah kemahiran premium untuk kedai motor eksklusif.",
        "pathway": "Diploma Kejuruteraan Mekanikal"
    },

    # --- MOBILE DEVICE TECHNOLOGY (CERT) ---
    "KKOM-CET-035": {
        "headline": "📱 Sijil Teknologi Peranti Mudah Alih: Doktor Telefon",
        "synopsis": "Telefon rosak, skrin pecah, bateri kong? Itu masalah semua orang. Kursus ini ajar anda membaiki (repair) telefon pintar dan tablet. Anda juga belajar asas buat Apps Android. Ini adalah kemahiran 'kalis zaman'—selagi orang guna telefon, anda ada kerja!",
        "pathway": "Diploma Mobile Technology / Kejuruteraan Elektronik"
    },

    # --- ARCHITECTURE TECHNOLOGY (CERT) ---
    "KKOM-CET-036": {
        "headline": "🏛️ Sijil Teknologi Senibina: Pelukis Pelan",
        "synopsis": "Minat tengok bangunan cantik? Belajar cara melukis pelan rumah dan bangunan menggunakan komputer (CAD & BIM). Anda juga akan belajar buat model bangunan 3D. Skill ini sangat diperlukan oleh arkitek dan pemaju perumahan.",
        "pathway": "Diploma Seni Bina / Kejuruteraan Awam"
    },

    # --- TELECOMMUNICATION (CERT) ---
    "KKOM-CET-037": {
        "headline": "📡 Sijil Teknologi Telekomunikasi: Wira Internet",
        "synopsis": "Pastikan Malaysia kekal 'online'. Anda belajar cara pasang kabel Fiber Optik, menyelenggara rangkaian internet, dan sistem telekomunikasi. Tanpa juruteknik ini, tiada WiFi dan tiada 5G. Kerja teknikal yang mencabar tapi gajinya berbaloi.",
        "pathway": "Diploma Teknologi Telekomunikasi / Kejuruteraan Elektronik"
    },

    # --- BEAUTY & SPA THERAPY (CERT) ---
    "KKOM-CET-038": {
        "headline": "💅 Sijil Terapi Kecantikan & Spa: Bisnes Cantik",
        "synopsis": "Ubah minat bersolek jadi kerjaya profesional. Belajar teknik rawatan muka (facial), urutan spa, dan solekan pengantin (MUA). Industri kecantikan adalah industri bernilai jutaan ringgit. Ramai graduan kursus ini berjaya buka spa sendiri atau jadi MUA terkenal.",
        "pathway": "Diploma Terapi Kecantikan / Pengurusan Perniagaan"
    },

    # ==========================================
    # IKBN - COURSES
    # ==========================================

    # --- ELEKTRIK (CHARGEMAN) ---
    "IKBN-DIP-001": {
        "headline": "⚡ Kuasa Elektrik: Nadi Industri",
        "synopsis": "Bayangkan satu kilang bergelap tanpa anda. Kursus ini melatih anda menjadi 'Chargeman' (Penjaga Jentera)—orang paling penting yang memastikan elektrik berjalan lancar. Lesen A1 yang anda dapat di sini adalah 'pasport emas' untuk gaji lumayan dalam sektor tenaga."
    },

    # --- HVAC (AIRCOND) ---
    "IKBN-DIP-002": {
        "headline": "❄️ Pakar Penyejukan: Kerjaya Sentiasa 'Cool'",
        "synopsis": "Di Malaysia yang panas, pakar aircond tidak akan pernah hilang kerja. Anda bukan sekadar servis aircond rumah; anda belajar merekabentuk sistem penyejukan gergasi untuk pasar raya dan kilang. Kerjaya teknikal yang sangat stabil dan sentiasa diperlukan."
    },

    # --- FESYEN ---
    "IKBN-DIP-003": {
        "headline": "👗 Rekaan Fesyen: Dari Lakaran ke 'Runway'",
        "synopsis": "Tukarkan idea kreatif anda menjadi jenama sebenar. Anda belajar segalanya: melakar fesyen, membuat pola, hingga menjahit busana 'Haute Couture'. Jangan sekadar menjahit baju orang, belajar cipta 'trend' dan buka butik jenama anda sendiri."
    },

    # --- REKABENTUK INDUSTRI ---
    "IKBN-DIP-006": {
        "headline": "🎨 Rekabentuk Produk: Cipta Gajet Masa Depan",
        "synopsis": "Lihat barang di sekeliling anda—tetikus, botol, kerusi—semuanya bermula dari lakaran pereka. Anda belajar menggunakan perisian canggih (CAD) dan '3D Printer' untuk mencipta produk baharu. Sesuai untuk anda yang berjiwa seni tapi minat teknologi."
    },

    # --- MAKANAN (KILANG) ---
    "IKBN-DIP-007": {
        "headline": "🏭 Teknologi Makanan: Chef Industri",
        "synopsis": "Masak di dapur itu biasa, tapi bagaimana menguruskan pengeluaran 1,000 tin saderi sejam? Ini adalah sains pengeluaran makanan skala besar. Anda belajar tentang keselamatan makanan (Halal/HACCP), pembungkusan, dan kualiti. Anda adalah 'gatekeeper' makanan negara."
    },

    # --- JENTERA BERAT ---
    "IKBN-CET-001": {
        "headline": "🚜 Jentera Berat: Kendalikan 'Gergasi Besi'",
        "synopsis": "Kerjaya untuk yang berjiwa kental. Anda akan pakar membaiki dan menyelenggara raksasa pembinaan seperti Jentolak (Bulldozer) dan Jengkaut (Excavator). Kemahiran hidraulik dan diesel yang anda belajar di sini sangat bernilai di tapak perlombongan dan pembinaan."
    },

    # --- KENDERAAN PERDAGANGAN ---
    "IKBN-CET-002": {
        "headline": "🚛 Logistik & Pengangkutan: Nadi Ekonomi",
        "synopsis": "Lori dan bas adalah darah yang menggerakkan ekonomi negara. Anda belajar servis enjin diesel gergasi, sistem brek angin, dan transmisi lori. Bidang ini menjanjikan kerja tetap di syarikat logistik besar atau syarikat pengangkutan awam."
    },

    # --- AUTOMOTIF (KERETA) ---
    "IKBN-CET-003": {
        "headline": "🛠️ Automotif: Doktor Kereta",
        "synopsis": "Langkah pertama untuk buka bengkel sendiri. Anda akan bedah siasat enjin, gearbox, dan sistem kereta sehingga anda boleh selesaikan apa saja masalah kenderaan. Kursus 'hands-on' sepenuhnya untuk menjadikan anda pomen yang disegani."
    },

    # --- EV (ELEKTRIK) ---
    "IKBN-CET-004": {
        "headline": "⚡🚗 Kereta Elektrik (EV): Mekanik Masa Depan",
        "synopsis": "Dunia sedang beralih ke arah elektrik (EV). Jadilah orang pertama yang mahir membaiki kereta hibrid dan elektrik sepenuhnya. Anda belajar tentang bateri voltan tinggi dan sistem motor elektrik. Kemahiran 'high-tech' yang sangat laku di masa depan."
    },

    # --- CAT KERETA ---
    "IKBN-CET-005": {
        "headline": "✨ 'Body & Paint': Seni Cantikkan Kereta",
        "synopsis": "Kereta calar? Warna kusam? Andalah penyelamatnya. Belajar seni mengecat kereta taraf 'showroom', bancuhan warna (color matching), dan ketuk body. Kerjaya yang menggabungkan kemahiran tangan halus dan seni warna."
    },

    # --- SENIBINA & BANGUNAN ---
    "IKBN-CET-006": {
        "headline": "🏛️ Lukisan Senibina: Arkitek Muda",
        "synopsis": "Setiap bangunan ikonik bermula di atas kertas. Anda akan belajar menghasilkan lukisan teknikal yang terperinci untuk bangunan kediaman dan komersial. Menguasai perisian CAD, anda adalah orang kanan kepada Arkitek dan Jurutera. Kerjaya pejabat yang profesional dan bergaji stabil."
    },

    "IKBN-CET-007": {
        "headline": "🏢 Penyelenggaraan Bangunan: Doktor Bangunan",
        "synopsis": "Bangunan tinggi (skyscraper) memerlukan penjagaan rapi 24 jam. Anda belajar segalanya: dari sistem elektrik, paip air, aircond pusat, hingga sistem pencegah kebakaran. Anda adalah wira yang memastikan pejabat, hotel, dan mall beroperasi tanpa masalah."
    },

    # --- ELEKTRIK & AIRCOND (SIJIL) ---
    "IKBN-CET-008": {
        "headline": "⚡ Pendawai Elektrik (PW4): Kuasa Tiga Fasa",
        "synopsis": "Naik taraf kemahiran anda dari rumah biasa ke kilang besar. Lesen PW4 membolehkan anda membuat pendawaian 'Tiga Fasa' (Three Phase) yang digunakan di industri berat. Ini adalah lesen wajib untuk menjadi kontraktor elektrik yang berjaya."
    },

    "IKBN-CET-009": {
        "headline": "❄️ Servis Aircond Domestik: Sejuk & Nyaman",
        "synopsis": "Kerjaya 'pantas dapat duit'. Anda belajar pasang, servis, dan baiki unit aircond rumah dan pejabat kecil. Dengan cuaca panas Malaysia, kemahiran ini ibarat mesin cetak wang tunai. Sesuai untuk anda yang mahu berniaga sendiri sejurus tamat belajar."
    },

    # --- ELEKTRONIK INDUSTRI ---
    "IKBN-CET-010": {
        "headline": "🤖 Elektronik Industri: Otak Kilang",
        "synopsis": "Kawal robot dan mesin automatik! Di kilang moden, semuanya bergerak guna sensor dan cip. Anda belajar membaiki 'otak' mesin ini (PLC, Pneumatik, Hidraulik). Tanpa anda, kilang akan berhenti beroperasi. Sangat kritikal untuk Revolusi Industri 4.0."
    },

    # --- FESYEN (JAHITAN) ---
    "IKBN-CET-011": {
        "headline": "👗 Jahitan Wanita: Seni Busana Eksklusif",
        "synopsis": "Fokus kepada kemahiran tangan yang halus. Anda belajar teknik memotong dan menjahit pakaian wanita yang rumit dan elegan. Dari baju kurung moden hingga gaun pengantin, kemahiran ini membolehkan anda membuka butik tempahan khas yang sangat lumayan."
    },

    # --- HOSPITALITI (HOTEL & MAKANAN) ---
    "IKBN-CET-012": {
        "headline": "🏨 Pengurusan Hotel: Wajah Hadapan Hotel",
        "synopsis": "Anda adalah orang pertama yang menyambut VIP dan pelancong. Belajar seni layanan 5 bintang, sistem tempahan (booking), dan komunikasi profesional. Kerjaya glamor di lobi hotel mewah, resort, atau syarikat penerbangan."
    },

    "IKBN-CET-013": {
        "headline": "🍽️ Penyajian (F&B): Layanan Diraja",
        "synopsis": "Seni melayan tetamu di meja makan (Fine Dining) dan bankuet besar. Anda belajar etika meja, susun atur 'Cutlery', dan cara menghidang makanan dengan gaya profesional. Laluan pantas untuk menjadi Kapten Restoran atau Pengurus F&B di hotel ternama."
    },

    "IKBN-CET-014": {
        "headline": "👨‍🍳 Seni Kulinari: Chef Profesional",
        "synopsis": "Impian menjadi Chef bermula di sini. Kuasai masakan 5 benua: Melayu, Cina, India, dan Barat (Western). Dari hidangan pembuka selera hingga pencuci mulut, anda akan dilatih menguruskan dapur profesional. Bersedialah untuk dunia masakan yang pantas dan kreatif."
    },

    "IKBN-CET-015": {
        "headline": "🍰 Pastri & Roti: Seni Manisan",
        "synopsis": "Dunia manis yang penuh seni. Belajar membakar kek perkahwinan bertingkat, roti artisan, dan biskut rangup. Bukan sekadar resipi, anda belajar teknik dekorasi dan keusahawanan untuk membuka kedai roti (Bakery) atau kafe hipster anda sendiri."
    },

    # --- BAKERY & PASTRY ---
    "IKBN-CET-016": {
        "headline": "🥐 Bakeri & Konfeksionari: Dari Dapur ke Bisnes",
        "synopsis": "Siapa sangka buat roti boleh jadi kerjaya lumayan? Anda akan belajar sains di sebalik roti lembut, pizza Itali, dan muffin gebu. Menggunakan mesin industri moden, anda dilatih bukan sekadar menjadi pembuat roti, tetapi usahawan bakeri yang mampu menghasilkan produk berkualiti tinggi dan bersih."
    },

    # --- KOSMETOLOGI (RAMBUT) ---
    "IKBN-CET-017": {
        "headline": "✂️ Gaya Rambut: Seni Penggayaan Profesional",
        "synopsis": "Rambut adalah mahkota. Anda belajar seni menggunting, mewarna, dan mengerinting rambut dengan teknik terkini. Lebih dari itu, anda diajar menguruskan salon sebenar dan imej personal. Kerjaya kreatif yang membolehkan anda bekerja di salon eksklusif atau menjadi 'Hairstylist' selebriti."
    },

    # --- KOSMETOLOGI (KECANTIKAN) ---
    "IKBN-CET-018": {
        "headline": "💅 Terapi Kecantikan: Pakar Spa & Estetik",
        "synopsis": "Industri kecantikan bernilai bilion ringgit. Anda akan pakar dalam rawatan wajah (facial), manikur/pedikur, dan terapi badan. Bukan sekadar cantik, anda belajar mengendalikan mesin rawatan canggih dan pengurusan spa. Langkah pertama untuk membuka pusat kecantikan sendiri."
    },

    # --- MULTIMEDIA ---
    "IKBN-CET-019": {
        "headline": "🎥 Multimedia Kreatif: Pencipta Kandungan Digital",
        "synopsis": "Sesuai untuk 'Content Creator' masa depan! Anda belajar segalanya: suntingan video, animasi grafik, dan fotografi menggunakan kamera DSLR & dron. Dari Adobe Premiere ke After Effects, anda akan menghasilkan karya digital yang memukau untuk iklan, media sosial, dan TV."
    },

    # --- MARIN (BOT & KAPAL) ---
    "IKBN-CET-020": {
        "headline": "⚓ Teknologi Marin: Jurutera Lautan",
        "synopsis": "Kerjaya yang jarang orang tahu tapi gaji lumayan. Anda belajar membaiki dan menyelenggara enjin bot, kapal, dan jentera marin. Jika anda suka laut dan enjin besar, ini bidang anda. Peluang kerja luas di pelabuhan, limbungan kapal, atau syarikat perkapalan."
    },

    # --- KIMPALAN & BOILER ---
    "IKBN-CET-021": {
        "headline": "🔥 Boilermaker: Pakar Logam Minyak & Gas",
        "synopsis": "Kerjaya 'Heavy Metal' sebenar. Anda belajar membina dan membaiki tangki tekanan tinggi (Pressure Vessel) untuk loji minyak & gas. Kemahiran memotong dan membentuk logam tebal ini sangat kritikal dan dibayar mahal dalam industri O&G."
    },

    "IKBN-CET-022": {
        "headline": "⚡ Kimpalan Arka (SMAW): Seni Sambungan Besi",
        "synopsis": "Asas kepada semua binaan besi. Anda belajar teknik kimpalan SMAW (Shielded Metal Arc Welding) untuk menyambung paip dan plat besi. Kemahiran ini diperlukan di mana-mana—dari tapak pembinaan bangunan hinggalah ke pelantar minyak."
    },

    "IKBN-CET-023": {
        "headline": "💥 Teknologi Kimpalan Maju: Pakar 4 Proses",
        "synopsis": "Jadilah 'Master Welder' yang serba boleh. Anda menguasai 4 jenis kimpalan utama: SMAW, GMAW (MIG), GTAW (TIG), dan SAW. Anda bukan sahaja mengimpal, tapi belajar memeriksa kualiti (QC) kimpalan. Sesuai untuk kilang automotif dan aeroangkasa."
    },

    # --- MEKATRONIK ---
    "IKBN-CET-024": {
        "headline": "🤖 Mekatronik: Gabungan Mekanikal & Elektronik",
        "synopsis": "Jangan pilih satu, kuasai kedua-duanya! Mekatronik adalah gabungan 'Mekanik' + 'Elektronik'. Anda belajar membina sistem automatik, lengan robot, dan sistem hidraulik. Ini adalah kemahiran paling penting untuk bekerja di kilang moden yang menggunakan robot."
    },

    # --- MINYAK & GAS (PAIP) ---
    "IKBN-CET-025": {
        "headline": "🛢️ Fabrikasi Paip (O&G): Laluan ke Offshore",
        "synopsis": "Kerjaya 'Pipe Fitter' sangat dihormati di pelantar minyak. Anda belajar membaca lukisan isometrik yang rumit dan memotong/menyambung paip dengan tepat. Salah satu laluan terpantas untuk bekerja dalam sektor Minyak & Gas."
    },

    # --- PENYELENGGARAAN INDUSTRI ---
    "IKBN-CET-026": {
        "headline": "⚙️ Penyelenggaraan Industri: Wira Kilang",
        "synopsis": "Kilang tidak boleh berhenti. Andalah yang memastikannya terus berjalan. Belajar membaiki segala jenis kerosakan mesin: mekanikal, elektrik, pneumatik, dan hidraulik. Anda adalah 'doktor pakar' untuk mesin industri yang kompleks."
    },

    # --- PESAWAT (BAHAN) ---
    "IKBN-CET-027": {
        "headline": "✈️ Komposit Pesawat: Bahan Masa Depan",
        "synopsis": "Pesawat moden bukan lagi diperbuat daripada besi berat, tapi 'Komposit' yang ringan dan kuat. Anda belajar mencipta dan membaiki struktur canggih ini menggunakan gentian karbon (Carbon Fiber). Kemahiran 'niche' ini sangat mahal harganya dalam industri aeroangkasa."
    },

    "IKBN-CET-028": {
        "headline": "✈️ Struktur Pesawat (Metal): Doktor Kapal Terbang",
        "synopsis": "Jika sayap pesawat retak, andalah yang membaikinya. Fokus kepada membaiki kerangka besi (Sheet Metal) pesawat. Anda belajar teknik menampal (patching), rivet, dan kimpalan khas penerbangan. Kerja yang memerlukan ketelitian tinggi dan disiplin besi."
    },

    # --- REKABENTUK INDUSTRI (SIJIL) ---
    "IKBN-CET-029": {
        "headline": "🎨 Rekabentuk Industri: Cipta Produk Baharu",
        "synopsis": "Dari idea kepada realiti. Anda belajar merekabentuk perabot, pengangkutan, dan peralatan sukan menggunakan perisian CAD. Bukan setakat lukis, anda belajar hasilkan model sebenar (Mock-up). Laluan pantas untuk menjadi pereka yang praktikal."
    },

    # --- CIVIL (SCAFFOLDING) ---
    "IKBN-CET-032": {
        "headline": "🏗️ Scaffolding: Wira Tempat Tinggi",
        "synopsis": "Kerjaya ekstrem di tapak binaan dan pelantar minyak. Anda belajar memasang perancah (scaffolding) yang selamat untuk bangunan tinggi. Sijil ini adalah 'lesen wajib' untuk bekerja di tapak projek mega dan industri Minyak & Gas (Offshore)."
    },

    # --- ELEKTRIK (DOMESTIK) ---
    "IKBN-CET-034": {
        "headline": "🏠 Pendawai Elektrik (PW2): Raja Wiring Rumah",
        "synopsis": "Langkah pertama dalam dunia elektrik. Fokus kepada pendawaian rumah satu fasa. Anda belajar pasang soket, lampu, dan papan agihan (DB). Sijil PW2 membolehkan anda bekerja sebagai Wireman berdaftar atau mengambil upah 'wiring' rumah sendiri."
    },

    # ==========================================
    # ILJTM - COURSES
    # ==========================================

    # --- QUALITY ASSURANCE (QA) ---
    "IJTM-DIP-010": {
        "headline": "✅ Jaminan Kualiti (QA): Polis Kualiti",
        "synopsis": "Sebelum produk dijual, ia mesti lulus di tangan anda. Anda belajar menggunakan alat pengukur mikron (CMM) untuk memastikan setiap skru dan komponen adalah sempurna. Kilang automotif dan aeroangkasa sangat memerlukan pakar QA untuk menjaga standard keselamatan."
    },

    # --- MEKATRONIK (DIPLOMA) ---
    "IJTM-DIP-017": {
        "headline": "🤖 Diploma Mekatronik: Arkitek Robot",
        "synopsis": "Gabungkan kejuruteraan mekanikal, elektrik, dan komputer. Anda akan membina sistem automasi pintar dan lengan robot industri. Kursus ini menyediakan anda untuk menjadi jurutera masa depan yang mampu mengendalikan kilang pintar (Smart Factory)."
    },

    # --- MIKROELEKTRONIK ---
    "IJTM-DIP-019": {
        "headline": "💻 Mikroelektronik: Teknologi Cip Pintar",
        "synopsis": "Belajar di dalam makmal 'Cleanroom' bertaraf dunia—satu-satunya di Malaysia! Anda akan memahami cara cip komputer dan semikonduktor dibuat. Industri E&E adalah eksport terbesar Malaysia, jadi pakar cip sangat diperlukan di kilang gergasi seperti Intel dan Infineon."
    },

    # --- PEMESINAN (CNC) ---
    "IJTM-DIP-022": {
        "headline": "⚙️ Teknologi Pembuatan: Pakar Mesin CNC",
        "synopsis": "Kuasai mesin moden yang boleh memotong besi setepat rambut! Anda belajar mengendalikan mesin CNC (Computer Numerical Control), mesin kisar, dan larik. Anda adalah orang yang menghasilkan komponen enjin kereta dan mesin industri yang presisi."
    },

    # --- AUTOMOTIF (PENGELUARAN) ---
    "IJTM-DIP-024": {
        "headline": "🚗 Pengeluaran Automotif: Nadi Kilang Kereta",
        "synopsis": "Bukan sekadar baiki kereta, tapi BINANYA. Anda belajar proses pemasangan kereta di kilang—dari kerangka hingga ke enjin. Fokus kepada pengurusan barisan pengeluaran (Assembly Line) dan robotik automotif. Sesuai untuk bekerja di Proton, Perodua, atau Honda."
    },

    # --- PENYELENGGARAAN PESAWAT (MRO) ---
    "IJTM-DIP-026": {
        "headline": "✈️ Penyelenggaraan Pesawat (MRO): Lesen Terbang Tinggi",
        "synopsis": "Kerjaya elit dalam dunia penerbangan. Anda belajar menyelenggara keseluruhan pesawat: enjin, sayap, dan sistem avionik. Kursus ini mempersiapkan anda untuk lesen CAAM Part 66 (Kategori A)—tiket untuk bekerja di hangar syarikat penerbangan antarabangsa."
    },

    # --- ELEKTRONIK (DIPLOMA) ---
    "IJTM-DIP-032": {
        "headline": "🔌 Diploma Elektronik: Pakar Litar & Kawalan",
        "synopsis": "Dunia hari ini dikuasai oleh elektronik. Anda akan belajar segalanya: dari membaiki papan litar (PCB) hingga memprogram sistem automasi kompleks menggunakan PLC dan sensor. Kursus ini menjadikan anda pakar yang boleh merekabentuk, menganalisa, dan membaiki apa saja peranti elektronik."
    },

    # --- MEKATRONIK (DIPLOMA - JTM) ---
    "IJTM-DIP-033": {
        "headline": "🤖 Diploma Mekatronik: Jurutera Serba Boleh",
        "synopsis": "Kenapa pilih satu bidang jika boleh kuasai tiga? Mekatronik menggabungkan Mekanikal, Elektronik, dan Komputer. Anda akan mahir membina sistem robotik, menyelenggara mesin industri berteknologi tinggi, dan merekabentuk sistem automasi pintar. Graduan bidang ini sangat laku di pasaran."
    },

    # --- IT & KOMPUTER ---
    "IJTM-DIP-034": {
        "headline": "💻 Diploma Teknologi Komputer: Doktor IT",
        "synopsis": "Bukan sekadar guna komputer, tapi membinanya. Anda belajar memasang perkakasan (hardware), membina rangkaian (network/server), dan menyelenggara sistem komputer pejabat. Anda adalah 'orang penting' yang dicari bila sistem komputer sesebuah syarikat lumpuh."
    },

    # --- PEMESINAN (DIPLOMA) ---
    "IJTM-DIP-035": {
        "headline": "⚙️ Diploma Pembuatan (Pemesinan): Seni Besi Presisi",
        "synopsis": "Mesin CNC adalah jantung industri pembuatan moden. Anda belajar memprogram mesin canggih ini untuk memotong besi dengan ketepatan mikron. Dari rekaan CAD/CAM hingga produk akhir, anda akan menghasilkan komponen enjin dan mesin yang kompleks."
    },

    # --- AUTOMOTIF (AUTOMASI) ---
    "IJTM-CET-001": {
        "headline": "🏭 Automotif Industri: Robotik Kilang Kereta",
        "synopsis": "Kilang kereta moden tidak guna tangan, ia guna robot. Anda belajar mengendalikan 'otak' di sebalik robot ini: PLC, Pneumatik, dan Hidraulik. Anda adalah pakar yang memastikan barisan pengeluaran automatik berjalan lancar tanpa henti."
    },

    # --- AUTOMOTIF (DIE MAKING) ---
    "IJTM-CET-002": {
        "headline": "🛠️ Pembuatan Acuan (Die): Pembentuk Logam",
        "synopsis": "Setiap pintu kereta bermula dari satu acuan (Die). Anda belajar mencipta acuan besi ini menggunakan mesin CNC berteknologi tinggi dan perisian CAD. Ini adalah kemahiran 'niche' yang sangat mahal harganya dalam industri pembuatan komponen kereta."
    },

    # --- AUTOMOTIF (SERVIS) ---
    "IJTM-CET-003": {
        "headline": "🚗 Servis Automotif: Pakar Diagnostik",
        "synopsis": "Lengkapkan diri anda dengan ilmu automotif menyeluruh. Anda akan membedah siasat enjin, gearbox, brek, dan aircond kereta. Fokus kursus ini adalah melahirkan mekanik yang kompeten untuk bekerja di pusat servis jenama besar atau membuka bengkel sendiri."
    },

    "IJTM-CET-004": {
        "headline": "🔧 Teknologi Automotif: Mekanik Bertauliah",
        "synopsis": "Sama seperti di atas, kursus ini memantapkan kemahiran anda dalam penyelenggaraan kenderaan. Dengan Sijil Kemahiran Malaysia (SKM) Tahap 3, anda diiktiraf sebagai mekanik profesional yang layak bekerja di mana-mana pusat servis bertauliah."
    },

    # --- CIVIL (BINAAN) ---
    "IJTM-CET-005": {
        "headline": "🏗️ Teknologi Binaan: Jurutera Tapak Muda",
        "synopsis": "Setiap projek mega perlukan pakar sivil. Anda belajar 'A-Z' pembinaan: dari jalan raya ke sistem saliran, dari ujian konkrit makmal ke penyeliaan tapak sebenar. Ini adalah langkah pertama anda untuk menjadi 'Site Supervisor' yang dihormati di tapak bina."
    },

    # --- CIVIL (PAIP) ---
    "IJTM-CET-006": {
        "headline": "🚿 Paip & Sanitari: Pakar Air",
        "synopsis": "Air adalah keperluan asas. Anda akan pakar memasang dan menyelenggara sistem paip domestik dan industri yang kompleks. Bukan sekadar tukang paip biasa, anda belajar membaca pelan 'blue print' dan merekabentuk sistem air bangunan tinggi."
    },

    # --- CADD (MEKANIKAL) ---
    "IJTM-CET-007": {
        "headline": "🖥️ CADD Mekanikal: Pelukis Pelan Industri",
        "synopsis": "Tinggalkan papan lukis lama, beralih ke komputer. Anda belajar menggunakan perisian CAD canggih untuk melukis komponen enjin dan mesin dengan ketepatan tinggi. Lukisan andalah yang akan digunakan oleh jurutera untuk membina mesin sebenar."
    },

    # --- CADD (SENIBINA) ---
    "IJTM-CET-008": {
        "headline": "🏠 CADD Senibina: Visual Arkitek",
        "synopsis": "Tukarkan imaginasi menjadi visual 3D yang memukau. Anda belajar melukis pelan rumah, perspektif bangunan, dan teknik 'rendering' yang realistik. Kemahiran ini sangat diperlukan oleh firma arkitek untuk membentangkan projek kepada klien."
    },

    # --- ELEKTRIK (TIGA FASA) ---
    "IJTM-CET-009": {
        "headline": "⚡ Pendawai Tiga Fasa: Kuasa Industri",
        "synopsis": "Naik taraf lesen anda! Pendawaian 'Tiga Fasa' digunakan di semua kilang dan bangunan komersial. Anda belajar memasang motor industri, janakuasa, dan sistem kawalan elektrik berkuasa tinggi. Lesen kompeten Suruhanjaya Tenaga (ST) menanti anda."
    },

    # --- ELEKTRONIK INDUSTRI ---
    "IJTM-CET-010": {
        "headline": "🤖 Elektronik Industri: Jantung Kilang Pintar",
        "synopsis": "Kawal mesin dengan hujung jari. Anda belajar sistem PLC (Programmable Logic Controller) yang menggerakkan robot dan mesin automatik di kilang. Gabungan ilmu elektronik digital dan analog menjadikan anda pakar yang boleh menyelesaikan masalah mesin kompleks."
    },

    # --- MINYAK & GAS (FABRIKASI) ---
    "IJTM-CET-011": {
        "headline": "🛢️ Fabrikasi Logam (O&G): Pembina Pelantar",
        "synopsis": "Kerjaya 'Heavy Duty' di sektor Minyak & Gas. Anda belajar memotong, melentur, dan menyambung plat besi tebal untuk membina struktur pelantar minyak. Kemahiran ini adalah tiket anda untuk bekerja di yard fabrikasi antarabangsa."
    },

    "IJTM-CET-012": {
        "headline": "🛢️ Fabrikasi Struktur (O&G): Pakar Besi Berat",
        "synopsis": "Sama seperti di atas, fokus kursus ini adalah membina struktur besi gergasi. Anda akan mahir menggunakan mesin industri untuk membentuk logam mengikut spesifikasi ketat industri minyak dan gas."
    },

    # --- INSTRUMEN ---
    "IJTM-CET-013": {
        "headline": "🎛️ Instrumen Perindustrian: Pengawal Proses",
        "synopsis": "Kilang kimia dan loji penapisan perlukan ketepatan. Anda belajar menjaga 'sensor' yang mengukur suhu, tekanan, dan aliran paip. Jika sensor salah baca, kilang boleh meletup! Anda adalah pakar yang memastikan sistem kawalan sentiasa tepat dan selamat."
    },

    # --- KENDERAAN BERAT ---
    "IJTM-CET-014": {
        "headline": "🚛 Kenderaan Berat: Mekanik Lori & Bas",
        "synopsis": "Enjin besar, gaji besar. Anda pakar membaiki lori kontena, bas ekspres, dan treler. Belajar sistem brek angin, hidraulik, dan enjin diesel turbo. Industri logistik yang sedang berkembang pesat sangat memerlukan mekanik mahir seperti anda."
    },

    # --- KIMPALAN (SIJIL) ---
    "IJTM-CET-015": {
        "headline": "🔥 Teknologi Kimpalan: Pakar Sambungan Besi",
        "synopsis": "Seni mencantum besi dengan api. Anda kuasai 4 teknik utama: SMAW, MIG, TIG, dan SAW. Dari paip minyak ke kerangka bangunan, kemahiran kimpalan anda diperlukan di mana-mana. Kerjaya lasak dengan bayaran lumayan mengikut skil anda."
    },

    # --- IT (SISTEM) ---
    "IJTM-CET-016": {
        "headline": "💻 Sistem Komputer: Bina 'Gaming Rig' & Server",
        "synopsis": "Pernah pasang PC sendiri? Jadikan hobi itu kerjaya. Anda belajar memasang Motherboard, RAM, dan Hard Disk dari kosong sehingga menjadi komputer yang lengkap. Anda juga akan mahir instalasi Windows, Linux, dan menyelenggara server pejabat. Sesuai untuk 'Tech Enthusiast'."
    },

    # --- IT (NETWORK) ---
    "IJTM-CET-017": {
        "headline": "🌐 Rangkaian Komputer: Arkitek Internet",
        "synopsis": "Tanpa internet, dunia berhenti. Anda belajar membina infrastruktur ini—dari kabel LAN hingga konfigurasi Router dan Server canggih. Pakar rangkaian (Network Engineer) adalah kerjaya yang sangat stabil dan kritikal untuk bank, telco, dan syarikat multinasional."
    },

    # --- IT (SISTEM - ALTERNATE) ---
    "IJTM-CET-018": {
        "headline": "🛠️ Penyelenggaraan PC: 'Doktor' Komputer",
        "synopsis": "Komputer rosak? Andalah penyelamatnya. Fokus kursus ini adalah 'Troubleshooting'—mencari punca kerosakan hardware atau software dan membaikinya dengan pantas. Kemahiran wajib untuk bekerja di jabatan IT mana-mana syarikat."
    },

    # --- MEKATRONIK (SIJIL) ---
    "IJTM-CET-019": {
        "headline": "🤖 Mekatronik (Sijil): Langkah Pertama ke Robotik",
        "synopsis": "Permulaan dunia automasi. Anda belajar asas hidraulik (kuasa cecair), pneumatik (kuasa angin), dan elektronik yang menggerakkan mesin kilang. Kursus 'hands-on' ini mempersiapkan anda untuk menjadi juruteknik mahir yang boleh menjaga mesin berteknologi tinggi."
    },

    # --- O&G (LUKISAN) ---
    "IJTM-CET-020": {
        "headline": "🖊️ Lukisan Perpaipan O&G: Pelan Jutawan",
        "synopsis": "Setiap paip di loji minyak bermula dengan lukisan anda. Anda belajar membaca dan melukis pelan paip (Piping Drafting) yang rumit untuk industri Minyak & Gas. Kerjaya ini membolehkan anda bekerja di pejabat syarikat O&G gergasi dengan gaji yang sangat kompetitif."
    },

    # --- O&G (LOJI DOWNSTREAM) ---
    "IJTM-CET-021": {
        "headline": "🏭 Loji Minyak (Downstream): Penjaga Kilang Emas",
        "synopsis": "Bekerja di loji penapisan minyak (Refinery) seperti di Pengerang atau Kerteh. Anda pakar menyelenggara pam, injap, dan jentera berat yang memproses minyak mentah menjadi petrol. Kerjaya yang mementingkan keselamatan tinggi dan disiplin, dengan bayaran elaun yang lumayan."
    },

    "IJTM-CET-022": {
        "headline": "⚓ Mekanikal O&G: Pakar Rigging & Slinging",
        "synopsis": "Lebih mendalam tentang operasi loji. Selain baiki mesin, anda belajar teknik 'Rigging & Slinging' (mengangkat beban berat) yang selamat. Sijil ini sangat laku keras kerana industri O&G memerlukan pekerja yang kompeten dan mematuhi standard keselamatan antarabangsa."
    },

    # --- MULTIMEDIA (SIJIL) ---
    "IJTM-CET-023": {
        "headline": "🎬 Multimedia Interaktif: Kreativiti Tanpa Had",
        "synopsis": "Dunia digital perlukan anda. Belajar sunting video, buat animasi, dan reka grafik untuk web atau aplikasi telefon pintar. Menggunakan perisian Adobe (Photoshop, Premiere, Animate), anda boleh bekerja di agensi pengiklanan atau jadi 'Freelancer' yang bebas."
    },

    # --- O&G (PAIP FITTING) ---
    "IJTM-CET-024": {
        "headline": "🔧 Paip Minyak & Gas: Nadi Tenaga",
        "synopsis": "Kerja lasak untuk jiwa kental. Anda belajar memotong, menyambung (fitting), dan menguji paip tekanan tinggi. Tanpa anda, minyak dan gas tidak boleh disalurkan. Kemahiran ini membuka peluang kerja di tapak pembinaan loji atau pelantar minyak (Offshore)."
    },

    # --- PEMBUATAN (MESIN) ---
    "IJTM-CET-025": {
        "headline": "⚙️ Pemesinan: Pencipta Alat Ganti",
        "synopsis": "Mesin kilang rosak? Anda yang buat alat ganti baharu. Belajar menggunakan mesin larik (Lathe), kisar (Mill), dan canai (Grind) untuk membentuk besi menjadi komponen berguna. Kemahiran asas yang menjadi rebutan di mana-mana bengkel kejuruteraan."
    },

    # --- PEMBUATAN (ACUAN & DIE) ---
    "IJTM-CET-026": {
        "headline": "🛠️ Pembuatan Acuan (Press Die): Pencetak Logam",
        "synopsis": "Setiap komponen kereta yang anda lihat dibentuk oleh 'Die'. Anda belajar mencipta acuan logam yang sangat keras menggunakan mesin CNC canggih. Graduan bidang ini sering bekerja di syarikat gergasi automotif dan aeroangkasa untuk menghasilkan alat ganti kenderaan."
    },
    
    "IJTM-CET-027": {
        "headline": "🛠️ Teknologi Die & Metrologi: Pakar Ukur Halus",
        "synopsis": "Bukan sekadar buat acuan, tapi memastikan ia tepat hingga ke mikron. Anda belajar menggunakan mesin pengukuran (CMM) dan rawatan haba untuk mengeraskan logam. Kemahiran ini menjadikan anda pakar yang sangat diperlukan dalam sektor pembuatan presisi."
    },

    "IJTM-CET-028": {
        "headline": "🧪 Acuan Plastik (Mould): Pencipta Produk Plastik",
        "synopsis": "Botol air, bekas makanan, mainan—semuanya dari plastik. Anda belajar teknik 'Injection Moulding' untuk menghasilkan produk plastik secara besar-besaran. Dari bijih plastik hingga barang siap, andalah yang mengawal mesin pengeluaran."
    },

    # --- PEMESINAN (ASAS) ---
    "IJTM-CET-029": {
        "headline": "⚙️ Pemesinan Am: Mekanik Mesin",
        "synopsis": "Kemahiran wajib untuk mana-mana juruteknik. Belajar mengendalikan mesin larik, kisar, dan canai untuk membaiki alat ganti mesin yang rosak. Asas yang kukuh untuk anda membuka bengkel kejuruteraan sendiri satu hari nanti."
    },

    "IJTM-CET-030": {
        "headline": "🤖 Pembuatan Lanjutan (CNC): Pakar Mesin Robotik",
        "synopsis": "Naik taraf kemahiran pemesinan anda. Fokus kursus ini adalah penggunaan mesin CNC berkomputer dan 'Wire Cut' yang canggih. Anda akan menghasilkan komponen logam yang sangat rumit yang tidak boleh dibuat oleh tangan manusia biasa."
    },

    # --- HVAC (AIRCOND) ---
    "IJTM-CET-031": {
        "headline": "❄️ Penyejukbekuan Komersial: Pakar Chiller",
        "synopsis": "Upgrade dari aircond rumah ke sistem 'Chiller' bangunan besar. Anda belajar menyelenggara sistem penyejukan pusat (Centralize Aircond) di hospital, mall, dan kilang. Anda juga belajar tentang sistem aircond kenderaan. Kerjaya stabil dengan permintaan tinggi."
    },

    # --- PENYELENGGARAAN BANGUNAN ---
    "IJTM-CET-032": {
        "headline": "🏢 Fasiliti Bangunan: Penjaga Harta Benda",
        "synopsis": "Menjaga bangunan bernilai jutaan ringgit. Anda belajar tentang kerja kayu, paip air, lantai jubin, dan asas binaan. Tugas anda memastikan pejabat atau fasiliti kerajaan sentiasa dalam keadaan tiptop dan selamat untuk diduduki."
    },

    # --- PENYELENGGARAAN MEKANIKAL ---
    "IJTM-CET-033": {
        "headline": "🔧 Penyelenggaraan Mekanikal: Jack of All Trades",
        "synopsis": "Syarikat suka pekerja serba boleh. Anda belajar mengimpal, memesin, dan membaiki kerosakan mesin kilang. Kursus ini melatih anda menjadi juruteknik yang boleh 'turu padang' dan selesaikan masalah mekanikal on-the-spot."
    },

    # --- POLIMER ---
    "IJTM-CET-034": {
        "headline": "⚗️ Teknologi Polimer: Sains Plastik",
        "synopsis": "Dunia kejuruteraan plastik. Anda belajar mengendalikan mesin suntikan plastik dan menyelesaikan masalah (troubleshoot) jika produk cacat. Kilang elektronik dan automotif sangat memerlukan pakar polimer untuk menghasilkan casing gajet dan bumper kereta."
    },

    # --- PERABOT & REKABENTUK ---
    "IJTM-CET-035": {
        "headline": "🪑 Rekabentuk Perabot: Tukang Kayu Moden",
        "synopsis": "Gabungan seni pertukangan dan teknologi. Anda bukan sekadar mengetam kayu, tapi merekabentuk perabot ergonomik dan moden. Sesuai untuk anda yang ingin menjadi pereka dalaman atau membuka kilang perabot sendiri."
    },

    "IJTM-CET-036": {
        "headline": "🎨 Rekabentuk Grafik: Visual Artis Digital",
        "synopsis": "Kuasai seni visual menggunakan komputer Apple Mac. Anda belajar Adobe Illustrator dan Photoshop untuk menghasilkan poster, majalah, dan iklan. Langkah pertama untuk menjadi pereka grafik profesional di agensi pengiklanan atau syarikat penerbitan."
    },

    "IJTM-CET-037": {
        "headline": "✏️ Rekabentuk Industri: Pencipta Gajet",
        "synopsis": "Belajar mencipta rupa bentuk produk yang kita guna setiap hari. Dari lakaran tangan hingga ke model 3D komputer, anda akan dilatih untuk menjadikan produk berfungsi dan cantik dipandang."
    },

    # --- TELEKOMUNIKASI ---
    "IJTM-CET-038": {
        "headline": "📡 Telekomunikasi: Pakar Fiber & 5G",
        "synopsis": "Industri 5G sedang meletup! Anda belajar menyambung kabel Fiber Optik (Splicing), memasang antena pemancar, dan menguji isyarat frekuensi. Kerjaya kritikal yang menghubungkan manusia. Kerja lasak tapi gaji sangat lumayan."
    },

    # --- ART & PERFORMANCE ---
    "UA4212003": {
        "headline": "🎭 Diploma Teater: Pentas, Produksi & Pengurusan",
        "synopsis": "Bukan sekadar berlakon! Di UPSI, anda akan mendalami seluruh ekosistem teater—dari falsafah seni, penulisan skrip, hinggalah pengurusan pentas teknikal. Program ini melatih anda menjadi seniman yang bijak mengurus industri, sesuai untuk mereka yang berjiwa seni tetapi mahukan kemahiran organisasi yang profesional."
    },

    # --- FOUNDATION (MILITARY & TECH) ---
    "UZ0520001": {
        "headline": "🛡️ Asasi Kejuruteraan & Teknologi (Pertahanan)",
        "synopsis": "Gabungan unik kejuruteraan awam/mekanikal dengan disiplin ketenteraan. Di UPNM, anda bukan sahaja belajar kalkulus dan fizik, tetapi juga dibina dengan ketahanan mental dan fizikal ala tentera. Sesuai untuk pelajar yang mahu menjadi jurutera berdisiplin tinggi atau pegawai kadet teknikal."
    },

    # --- FOUNDATION (ISLAMIC & SCIENCE) ---
    "UM0221001": {
        "headline": "☪️ Asasi Pengajian Islam & Sains: Integrasi Naqli & Aqli",
        "synopsis": "Program elit Universiti Malaya yang menggabungkan tradisi ilmu Islam dengan metodologi sains moden. Anda akan belajar biologi dan kimia tanpa meninggalkan akar etika Islam. Laluan terbaik untuk menjadi profesional STEM (Doktor/Saintis) yang faqih agama."
    },

    # --- FOUNDATION (STRATEGY) ---
    "UZ0345001": {
        "headline": "♟️ Asasi Pengurusan & Strategi Pertahanan",
        "synopsis": "Belajar cara berfikir seperti seorang Jeneral. Program ini fokus kepada kepimpinan strategik, pengurusan krisis, dan logistik pertahanan. Anda akan dilatih untuk membuat keputusan di bawah tekanan tinggi, sesuai untuk bakal pemimpin dalam sektor korporat atau ketenteraan."
    },

    # --- FOUNDATION (MEDICAL - MILITARY) ---
    "UZ0721001": {
        "headline": "🩺 Asasi Perubatan (Ketenteraan)",
        "synopsis": "Laluan kental ke arah gelaran Doktor Perubatan. Berbeza dengan asasi perubatan biasa, pelajar UPNM dilatih fizikal dan mental untuk berkhidmat dalam suasana mencabar. Pilihan tepat jika anda bercita-cita menjadi doktor tentera atau pakar perubatan kecemasan (trauma)."
    },

    # --- FOUNDATION (SCIENCE & ENTREPRENEURSHIP) ---
    "UL0010001": {
        "headline": "🧪 Asasi Sains: The Science-Preneur",
        "synopsis": "Di UMK, sains bukan hanya untuk makmal, tetapi untuk bisnes. Anda akan belajar subjek sains tulen (Biologi/Kimia) yang disuntik dengan elemen keusahawanan. Matlamatnya adalah melahirkan saintis yang pandai buat duit dan mencipta produk komersial."
    },

    # --- FOUNDATION (AGRICULTURE) ---
    "UP0000001": {
        "headline": "🌾 Asasi Sains Pertanian: Laluan ke UPM",
        "synopsis": "Pintu gerbang utama ke Universiti Putra Malaysia (UPM). Fokus kukuh kepada biologi, kimia, dan fizik sebagai persediaan untuk ijazah berkaitan pertanian moden, veterinar, atau hortikultur. Ini tapak asas untuk menjadi pakar sekuriti makanan negara."
    },

    # --- FOUNDATION (SOCIAL SCIENCE) ---
    "UL0010002": {
        "headline": "🤝 Asasi Sains Sosial & Keusahawanan",
        "synopsis": "Fahami manusia + fahami bisnes. Program ini mengajar teori sosiologi dan psikologi, tetapi dengan fokus bagaimana ilmu ini boleh menjana ekonomi. Sesuai untuk anda yang berminat dengan tingkah laku manusia dan mahu membina karier dalam HR atau pemasaran."
    },

    # --- FOUNDATION (STEM & MARINE) ---
    "UG0010001": {
        "headline": "🌊 Asasi STEM: Robotik & Sains Marin",
        "synopsis": "Fokus unik UMT (Terengganu) ke arah sains lautan. Program ini banyak menekankan 'hands-on' dalam robotik, mikropengawal, dan teknologi marin. Jika anda suka teknologi dan laut, ini adalah laluan 'niche' yang sangat berpotensi."
    },

    # --- FOUNDATION (GIFTED) ---
    "UK0010001": {
        "headline": "🧠 ASASIPintar UKM: Program Minda Genius",
        "synopsis": "Program elit untuk pelajar berpotensi tinggi (Top 1%). Pembelajaran di sini bukan sekadar menghafal buku, tetapi berasaskan penyelidikan (research-oriented) dan pemikiran kritis aras tinggi. Laluan pantas untuk menjadi pakar rujuk dan intelektual negara."
    },

    # --- LANGUAGE & HERITAGE (NEW) ---
    "UA4222001": {
        "headline": "🗣️ Diploma Bahasa Etnik: Warisan Digital",
        "synopsis": "Kursus 'rare' dan baharu! Anda bukan sekadar belajar bahasa Iban atau Kadazandusun, tetapi bagaimana mendigitalkan warisan ini menggunakan teknologi moden. Sesuai untuk anda yang bangga dengan akar umbi dan mahu menjadi pakar rujuk budaya atau pencipta konten etnik yang viral."
    },

    # --- ENGLISH LANGUAGE ---
    "UA4224001": {
        "headline": "🇬🇧 Diploma Bahasa Inggeris: Passport Global",
        "synopsis": "Kuasai Bahasa Inggeris, kuasai dunia. Di UPSI, anda dilatih bukan sahaja untuk bercakap 'slang' yang betul, tetapi memahami komunikasi silang budaya dan linguistik. Skill ini adalah tiket emas untuk bekerja di syarikat multinasional (MNC) atau media antarabangsa."
    },

    # --- E-COMMERCE (NEW) ---
    "UC4340001": {
        "headline": "🛒 Diploma E-Commerce: Raja Bisnes Online",
        "synopsis": "Dari Shopee ke Amazon, dunia kini bergerak secara online. Kursus di UTeM ini mengajar anda selok-belok teknikal dan pengurusan bisnes digital. Jangan sekadar jadi 'dropshipper' biasa; belajar cara bina empayar e-dagang dan urus data pelanggan secara profesional."
    },

    # --- PHYSIOTHERAPY ---
    "UD4726001": {
        "headline": "💪 Diploma Fisioterapi: Hero Pemulihan",
        "synopsis": "Guna model '2u2i' (belajar + praktikal industri). Anda akan menjadi pakar yang membantu pesakit kembali bergerak selepas cedera atau strok. Kerjaya ini sangat 'hands-on' dan memberi kepuasan tinggi apabila melihat pesakit anda sembuh. Sesuai untuk yang minat sains sukan dan biologi."
    },

    # --- DEFENSE FITNESS ---
    "UZ4813001": {
        "headline": "🏋️‍♂️ Diploma Kecergasan Pertahanan: Fitness Taktikal",
        "synopsis": "Ini bukan sekadar kursus 'gym instructor'. Di UPNM, anda belajar sains kecergasan untuk situasi tempur dan pertahanan. Anda akan dilatih menjadi pemimpin yang kental fizikal dan mental. Laluan terbaik untuk menjadi jurulatih taktikal atau menyertai pasukan beruniform."
    },

    # --- ENVIRONMENTAL ENGINEERING (NEW) ---
    "UR4851001": {
        "headline": "🌍 Diploma Kejuruteraan Alam Sekitar: Penyelamat Bumi",
        "synopsis": "Isu perubahan iklim (climate change) perlukan pakar teknikal, bukan sekadar cakap kosong. Di UniMAP, anda belajar teknologi hijau, pengurusan sisa, dan amalan industri lestari. Kerjaya masa depan yang sangat diperlukan oleh kilang-kilang untuk mematuhi piawaian ESG."
    },

    # --- CIVIL ENGINEERING (UTHM) ---
    "UB4526001": {
        "headline": "🏗️ Diploma Kejuruteraan Awam (UTHM): Pembina Negara",
        "synopsis": "UTHM terkenal dengan tradisi teknikal yang kukuh. Anda akan belajar asas pembinaan bangunan, jambatan, dan jalan raya. Kursus ini melatih anda menjadi pakar struktur yang teliti dan bersedia untuk suasana kerja tapak binaan (site) yang sebenar."
    },

    # --- CIVIL ENGINEERING (UMPSA) ---
    "UJ4526001": {
        "headline": "🏗️ Diploma Kejuruteraan Awam (UMPSA): Teknologis Infrastruktur",
        "synopsis": "Di UMPSA, pendekatannya lebih kepada teknologi kejuruteraan dan pengurusan projek. Selain simen dan bata, anda akan didedahkan kepada cara mengurus projek infrastruktur besar. Sesuai untuk mereka yang mahu gabungkan skil teknikal dengan skil pengurusan."
    },

    # --- MATERIALS ENGINEERING ---
    "UR4521002": {
        "headline": "⚙️ Diploma Kejuruteraan Bahan: Sains Material",
        "synopsis": "Pernah tertanya macam mana buat telefon pintar yang tak mudah pecah atau kereta yang ringan tapi kuat? Itu kerja jurutera bahan. Anda akan pakar dalam logam, polimer, dan komposit. Bidang 'niche' yang sangat laku dalam industri automotif dan pembuatan semikonduktor."
    },

    # --- ELECTRICAL ENGINEERING ---
    "UB4522001": {
        "headline": "⚡ Diploma Kejuruteraan Elektrik: Kuasa & Tenaga",
        "synopsis": "Tanpa elektrik, dunia berhenti. Kursus di UTHM ini melatih anda mengendalikan sistem kuasa, pendawaian industri, dan mesin elektrik. Skil yang 'tak akan mati' dan sentiasa diperlukan di mana-mana kilang, bangunan komersial, atau stesen janakuasa."
    },

    # --- ELECTRICAL ENGINEERING (UTeM) ---
    "UC4522001": {
        "headline": "⚡ Dip. Kej. Elektrik (UTeM): The Balanced Pro",
        "synopsis": "UTeM melahirkan jurutera yang 'versatile'. Anda bukan sahaja handal di makmal dengan litar elektrik, tetapi juga diasah dengan 'soft skills' komunikasi dan kepimpinan. Pakej lengkap untuk anda yang mahu naik pangkat cepat menjadi pengurus teknikal di masa hadapan."
    },

    # --- ELECTRICAL ENGINEERING (UniMAP) ---
    "UR4522001": {
        "headline": "⚡ Dip. Kej. Elektrik (UniMAP): Geng TVET Hands-On",
        "synopsis": "Kurang teori, lebih aksi. Program di UniMAP ini direka khas untuk industri pembuatan yang perlukan orang yang 'boleh buat kerja' terus. Fokus TVET bermaksud anda akan banyak masa memegang spanar dan meter, bukan sekadar menghadap buku. Pilihan tepat untuk yang tak suka duduk diam."
    },

    # --- ELECTRICAL & ELECTRONIC (UMPSA) ---
    "UJ4523001": {
        "headline": "🔌 Dip. Kej. Elektrik & Elektronik: The Troubleshooter",
        "synopsis": "Gabungan dua dunia—kuasa elektrik (high voltage) dan cip elektronik (low voltage). UMPSA melatih anda menjadi 'Penyelesai Masalah' yang pakar dalam PLC dan mikropengawal. Jika mesin kilang rosak, andalah orang pertama yang mereka cari."
    },

    # --- ELECTRONIC ENGINEERING (UTeM) ---
    "UC4523001": {
        "headline": "🤖 Dip. Kej. Elektronik (UTeM): Revolusi Industri 4.0",
        "synopsis": "Fokus kepada otak di sebalik mesin. Anda akan mendalami dunia automasi industri dan teknologi tinggi. Ini adalah kursus untuk masa depan—di mana kilang-kilang diuruskan oleh robot dan komputer yang memerlukan kepakaran anda untuk membinanya."
    },

    # --- ELECTRONIC ENGINEERING (UniMAP) ---
    "UR4523003": {
        "headline": "📡 Dip. Kej. Elektronik (UniMAP): Tech & Networking",
        "synopsis": "Belajar elektronik dalam suasana makmal moden yang 'real'. UniMAP menekankan pembelajaran berasaskan pengalaman (experiential learning), terutamanya dalam sistem rangkaian (networking). Sesuai untuk 'tech-geek' yang suka gajet dan sistem komunikasi."
    },

    # --- CHEMICAL ENGINEERING (UMPSA) ---
    "UJ4524001": {
        "headline": "⚗️ Dip. Kej. Kimia (UMPSA): Operasi Loji",
        "synopsis": "Laluan lurus ke sektor industri berat. Fokus utama adalah operasi loji kimia (plant operation). Anda akan belajar bagaimana menukar bahan mentah menjadi produk bernilai dalam skala besar. Graduan UMPSA sangat laku di kawasan perindustrian Gebeng dan Kerteh."
    },

    # --- CHEMICAL ENGINEERING (O&G) (UMS) ---
    "UH4520001": {
        "headline": "🛢️ Dip. Kej. Kimia (Minyak & Gas): Geng Offshore",
        "synopsis": "Impian kerja 'Offshore' bermula di sini. Satu-satunya program diploma di senarai ini yang spesifik 'Minyak & Gas'. Anda akan belajar tentang pemprosesan hidrokarbon dan keselamatan industri yang ketat. Siapkan mental, gaji lumayan menanti mereka yang sanggup kerja keras."
    },

    # --- COMPUTER ENGINEERING (UniMAP) ---
    "UR4523002": {
        "headline": "💻 Dip. Kej. Komputer: Hardware Hacker",
        "synopsis": "Jangan keliru dengan Sains Komputer (IT). Ini adalah KEJURUTERAAN. Anda bukan sekadar coding website, tetapi memprogram 'otak' perkakas (embedded systems) dan cip komputer. Anda adalah jambatan antara perisian (software) dan perkakas keras (hardware)."
    },

    # --- MECHANICAL ENGINEERING (UTHM) ---
    "UB4521002": {
        "headline": "⚙️ Dip. Kej. Mekanikal (UTHM): Design & Troubleshoot",
        "synopsis": "UTHM melatih anda menjadi pakar mekanikal yang sebenar. Fokus kepada reka bentuk mesin dan penyelesaian masalah industri berat. Anda akan belajar melukis pelan mesin dan membaiki kerosakan mekanikal yang kompleks. Sesuai untuk yang berjiwa kental dan teknikal."
    },

    # --- MECHANICAL ENGINEERING (UTeM) ---
    "UC4521001": {
        "headline": "🏭 Dip. Kej. Mekanikal (UTeM): Master Pembuatan",
        "synopsis": "Fokus kepada 'Manufacturing'. Bagaimana menghasilkan produk dengan kos rendah tapi kualiti tinggi? Anda akan menguasai bengkel moden dan teknik pembuatan terkini. Ini adalah nadi kepada ekonomi pengeluaran negara."
    },

    # --- MECHANICAL ENGINEERING (UMPSA) ---
    "UJ4521001": {
        "headline": "⚙️ Dip. Kej. Mekanikal (UMPSA): Projek Realiti",
        "synopsis": "Di UMPSA, anda bukan sekadar hafal teori. Kekuatan program ini ialah 'Project-Based Learning'. Anda akan dibimbing untuk membina sistem mekanikal sebenar dari tahun pertama. Sesuai untuk pelajar yang lebih cepat faham bila tangan mereka kotor membuat kerja praktikal."
    },

    # --- MECHATRONICS ENGINEERING ---
    "UR4523001": {
        "headline": "🤖 Dip. Kej. Mekatronik: The Iron Man Course",
        "synopsis": "Apa jadi bila Mekanikal kahwin dengan Elektronik? Lahirlah Mekatronik. Anda akan belajar membina sistem pintar, lengan robot, dan automasi. Ini adalah skill paling 'hot' dalam era Industri 4.0. Jika anda impikan kerjaya membina robot canggih, ini tempatnya."
    },

    # --- MANUFACTURING ENGINEERING (UTeM) ---
    "UC4540001": {
        "headline": "🏭 Dip. Kej. Pembuatan (UTeM): Inovasi Produk",
        "synopsis": "Fokus kepada 'Competitive Manufacturing'. UTeM melatih anda menggunakan teknologi terkini untuk menjadikan kilang lebih efisien dan produk lebih laku. Anda akan belajar bagaimana menewaskan pesaing dengan strategi pembuatan yang bijak dan inovatif."
    },

    # --- MANUFACTURING ENGINEERING (UniMAP) ---
    "UR4540001": {
        "headline": "📏 Dip. Kej. Pembuatan (UniMAP): Raja Metrologi",
        "synopsis": "UniMAP ada kelebihan dari segi fasiliti makmal canggih (Metrology Labs). Anda akan pakar dalam pengukuran tepat (precision) yang sangat kritikal untuk industri aeroangkasa dan automotif. Jika anda seorang yang teliti (perfectionist), bidang ini menjanjikan gaji lumayan."
    },

    # --- AGRO-TECH ENGINEERING (UPM BINTULU) ---
    "UP4524001": {
        "headline": "🚜 Dip. Kej. Teknologi Pertanian (Bintulu): Mekanik Ladang",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Ini bukan kursus tanam jagung biasa. Anda akan belajar membaiki dan mengendali jentera berat pertanian serta sistem pengairan berteknologi tinggi. Sektor perladangan di Borneo sangat memerlukan pakar teknikal seperti ini."
    },

    # --- OSH (OCCUPATIONAL SAFETY & HEALTH) ---
    "UJ4862001": {
        "headline": "⛑️ Dip. Keselamatan & Kesihatan (OSH): Pemegang Green Book",
        "synopsis": "Laluan pantas untuk menjadi 'Safety Health Officer' (SHO) yang berdaftar. Setiap tapak binaan dan kilang WAJIB ada pegawai keselamatan mengikut undang-undang. Ini bermakna peluang kerja anda sangat cerah. Tugas anda adalah memastikan tiada kemalangan berlaku di tempat kerja."
    },

    # --- ANIMAL HEALTH (UPM BINTULU) ---
    "UP4640001": {
        "headline": "🐾 Dip. Kesihatan Haiwan (Bintulu): Frontliner Veterinar",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Minat jadi doktor haiwan tapi result tak lepas? Ini laluan terbaik. Anda dilatih sebagai separa-profesional (paramedik haiwan) untuk menjaga kesihatan ternakan dan haiwan kesayangan. Sangat praktikal dan 'hands-on'."
    },

    # --- ENTREPRENEURSHIP ---
    "UA4345001": {
        "headline": "💼 Diploma Keusahawanan: Sekolah Boss",
        "synopsis": "UPSI melatih anda bukan untuk makan gaji, tapi untuk memberi gaji. Anda akan belajar segala aspek memulakan bisnes—dari akaun, marketing, hinggalah kepimpinan. Sesuai untuk anda yang berjiwa bebas dan bercita-cita menjadi CEO syarikat sendiri satu hari nanti."
    },

    # --- FINANCE ---
    "UD4343002": {
        "headline": "💰 Diploma Kewangan (UniSZA): Pakar Duit & Etika",
        "synopsis": "Wang bukan segala-galanya, tapi pengurusan wang itu penting. Di UniSZA, anda belajar teori kewangan moden yang disulam dengan nilai-nilai Islam (Patuh Syariah). Graduan yang pandai mengurus duit dan amanah sangat dicari oleh bank dan syarikat korporat."
    },

    # --- MUSIC ---
    "UA4212001": {
        "headline": "🎵 Diploma Muzik: Dari Teori ke Pentas",
        "synopsis": "UPSI adalah tempat lagenda untuk pendidikan muzik. Sama ada anda mahu jadi Cikgu Muzik yang bertauliah atau pemuzik profesional (sessionist), kursus ini memberi asas kukuh dalam teori, komposisi, dan persembahan. Ubah hobi bermain alat muzik menjadi kerjaya profesional."
    },

    # --- MARKETING ---
    "UD4342001": {
        "headline": "📢 Diploma Pemasaran (UniSZA): Psikologi Jualan",
        "synopsis": "Pemasaran bukan sekadar buat iklan viral. Di UniSZA, anda belajar strategi pengurusan dan psikologi pengguna untuk memenangi hati pelanggan. Dengan penerapan nilai etika, anda dilatih menjadi pakar pemasaran yang profesional dan dipercayai dalam dunia korporat."
    },

    # --- HUMAN DEVELOPMENT (UPM BINTULU) ---
    "UP4310001": {
        "headline": "🤝 Dip. Pembangunan Manusia (Bintulu): Arkitek Sosial",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Kursus unik yang menggabungkan sains sosial dengan komuniti pertanian. Anda belajar tentang psikologi keluarga, pembangunan belia, dan kerja sosial. Sangat sesuai untuk mereka yang mahu berkhidmat kepada masyarakat dan NGO, terutamanya di kawasan luar bandar."
    },

    # --- EARLY CHILDHOOD EDUCATION ---
    "UA4143001": {
        "headline": "🧸 Dip. Pendidikan Awal Kanak-Kanak: Cikgu Tadika Pro",
        "synopsis": "Mendidik si cilik memerlukan ilmu, bukan sekadar naluri. UPSI melatih anda memahami psikologi kanak-kanak, pedagogi moden, dan seni mengajar. Bidang ini mempunyai permintaan sangat tinggi kerana ibubapa moden mahukan guru tadika yang bertauliah dan profesional."
    },

    # --- BANKING ---
    "UD4343001": {
        "headline": "🏦 Diploma Pengajian Bank: Banker Masa Depan",
        "synopsis": "Fahami nadi ekonomi negara. Anda akan menguasai operasi bank, pengurusan kredit, dan sistem kewangan antarabangsa. UniSZA memberi kelebihan tambahan dengan penerapan nilai perbankan Islam, sektor yang sedang berkembang pesat di Malaysia dan global."
    },

    # --- INSURANCE ---
    "UD4343003": {
        "headline": "🛡️ Diploma Pengajian Insurans: Pengurus Risiko",
        "synopsis": "Insurans dan Takaful adalah industri berbilion ringgit. Kursus ini melatih anda menjadi pakar dalam menilai risiko dan melindungi aset. Graduan bidang ini sangat dikehendaki oleh syarikat Takaful untuk merangka polisi yang adil dan patuh syariah."
    },

    # --- ISLAMIC TURATH (HERITAGE) ---
    "UA4220001": {
        "headline": "📚 Dip. Pengajian Turath Islami: Klasik & Moden",
        "synopsis": "Jambatan antara kitab lama dan dunia baru. Anda akan mendalami teks-teks klasik Islam (Turath) tetapi diajar cara mengaplikasikannya dalam konteks pendidikan moden. Sesuai untuk bakal asatizah yang mahu ilmu mendalam tetapi relevan dengan cabaran semasa."
    },

    # --- LOGISTICS (DEFENSE) ---
    "UZ4345001": {
        "headline": "🚚 Diploma Pengurusan Logistik: Nadi Pertahanan",
        "synopsis": "Logistik menangkan peperangan. Di UPNM, anda belajar mengurus rantaian bekalan (supply chain) bukan sahaja untuk syarikat komersial, tetapi juga untuk operasi ketenteraan. Graduan UPNM terkenal dengan disiplin tinggi, menjadikan mereka rebutan syarikat logistik antarabangsa."
    },

    # --- FOOD PLANTATION (UPM BINTULU) ---
    "UP4621002": {
        "headline": "🍍 Dip. Pengurusan Ladang Makanan (Bintulu): Sekuriti Makanan",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Fokus kepada tanaman makanan (buah, sayur, padi) dan bukan sekadar kelapa sawit. Anda akan belajar mengurus estet makanan secara komersial untuk memastikan negara cukup makan. Bidang kritikal untuk masa depan Malaysia."
    },

    # --- BUSINESS MANAGEMENT (UPM BINTULU) ---
    "UP4345001": {
        "headline": "📊 Dip. Pengurusan Perniagaan (Bintulu): Agro-Bisnes",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Belajar bisnes dalam suasana industri asas tani. Walaupun subjek terasnya sama (akaun, marketing, HR), contoh dan kes studinya banyak berkait dengan sektor perladangan dan komoditi, menjadikan anda pakar dalam industri terbesar Sarawak."
    },

    # --- HUMAN RESOURCE ---
    "UD4345001": {
        "headline": "👥 Dip. Pengurusan Sumber Manusia: Talent Manager",
        "synopsis": "Syarikat yang hebat dibina oleh orang yang hebat. Anda akan belajar cara merekrut, melatih, dan menjaga kebajikan pekerja. Di UniSZA, aspek pengurusan ini diperkukuh dengan nilai Islam, melahirkan pengurus HR yang adil dan berkemahiran tinggi."
    },

    # --- BUSINESS ADMIN (DEFENSE) ---
    "UZ4340001": {
        "headline": "🏢 Dip. Pentadbiran Perniagaan (UPNM): Urus Aset Negara",
        "synopsis": "Bisnes bukan sekadar untung rugi, tapi keselamatan aset. Di UPNM, anda belajar mentadbir organisasi dengan disiplin ketenteraan. Fokus unik kepada pengurusan aset pertahanan menjadikan graduan ini sangat teliti dan dipercayai untuk memegang amanah syarikat besar."
    },

    # --- ACCOUNTING ---
    "UD4344001": {
        "headline": "📊 Diploma Perakaunan: Bahasa Bisnes",
        "synopsis": "Setiap sen mesti dikira! Ini adalah kemahiran yang 'kalis kemelesetan'—semua syarikat perlukan akauntan. Di UniSZA, anda dilatih bukan sekadar menjadi 'bookkeeper', tetapi penganalisis kewangan yang mampu menasihati bos besar tentang cukai dan audit."
    },

    # --- FORESTRY (UPM BINTULU) ---
    "UP4623001": {
        "headline": "🌲 Diploma Perhutanan (Bintulu): Penjaga Hutan",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Kerjaya untuk yang berjiwa 'adventure'. Anda akan belajar mengurus khazanah hutan negara secara lestari. Daripada teknologi satelit pemetaan hutan hinggalah konservasi hidupan liar, ini adalah kerjaya untuk pelindung alam semula jadi."
    },

    # --- FISHERIES (UMT - MARINE SCIENCE FOCUS) ---
    "UG4624001": {
        "headline": "🐟 Diploma Perikanan (UMT): Sains Samudera",
        "synopsis": "UMT di Terengganu adalah 'Raja Laut'. Kursus ini lebih menekankan aspek saintifik ekologi marin dan pembiakbakaan ikan. Anda akan banyak masa di makmal dan lapangan untuk kaji hidupan akuatik. Sesuai untuk yang serius meminati biologi laut."
    },

    # --- FISHERIES (UPM BINTULU - INDUSTRY FOCUS) ---
    "UP4624001": {
        "headline": "🦐 Diploma Perikanan (Bintulu): Tauke Akuakultur",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Fokus UPM Bintulu adalah 'Production'. Anda belajar bagaimana menternak ikan/udang secara komersial dan memproses hasil laut. Jika cita-cita anda adalah membuka kolam ternakan moden atau kilang keropok lekor eksport, ini jalannya."
    },

    # --- INTERNATIONAL BUSINESS ---
    "UD4340001": {
        "headline": "🌐 Dip. Perniagaan Antarabangsa: Global Trader",
        "synopsis": "Dunia tanpa sempadan. Anda akan belajar selok-belok eksport-import, logistik global, dan cara berurusan dengan budaya asing. Sesuai untuk mereka yang bercita-cita bekerja dengan syarikat multinasional atau membawa produk tempatan ke pasaran dunia."
    },

    # --- AGRIBUSINESS (UPM BINTULU) ---
    "UP4621001": {
        "headline": "💰 Diploma Perniagaantani (Bintulu): Bisnes Makanan",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Gabungan Pertanian + Bisnes. Anda tak perlu pegang cangkul sepanjang masa; tugas anda adalah memastikan hasil ladang terjual dengan harga tinggi. Anda belajar marketing, kewangan, dan rantaian bekalan khusus untuk sektor makanan."
    },

    # --- AGRICULTURE (UPM BINTULU - GENERAL) ---
    "UP4621003": {
        "headline": "🌱 Diploma Pertanian (Bintulu): Asas Tani Kukuh",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Ini adalah kursus 'pure' pertanian. Anda belajar sains tanaman secara menyeluruh—dari tanah, benih, baja, hinggalah menuai. Program ini melahirkan pakar teknikal yang faham bahasa pokok. Asas penting untuk menjadi pengurus ladang yang berjaya."
    },

    # --- RADIOGRAPHY ---
    "UD4725001": {
        "headline": "🩻 Diploma Radiografi: Pakar X-Ray",
        "synopsis": "Mata yang menembusi badan! Anda akan dilatih mengendalikan mesin X-Ray, MRI, dan CT Scan yang canggih. Menggunakan model '2u2i' (belajar sambil kerja), anda akan praktikal di hospital sebenar. Kerjaya profesional yang sangat penting untuk membantu doktor membuat diagnosis."
    },

    # --- GAME DESIGN ---
    "UA4481002": {
        "headline": "🎮 Dip. Reka Bentuk & Pembangunan Permainan: Game Dev",
        "synopsis": "Hobi main game? Tukar jadi kerjaya! Di UPSI, anda belajar coding DAN seni kreatif untuk membina video game sendiri. Dari mereka bentuk karakter hingga memprogram 'gameplay', ini adalah kursus impian untuk mereka yang mahu menyertai industri e-sukan dan pembangunan perisian kreatif."
    },

    # --- INDUSTRIAL DESIGN ---
    "UD4214001": {
        "headline": "🎨 Diploma Rekabentuk Perindustrian: Pencipta Produk",
        "synopsis": "Gabungan seni dan kejuruteraan. Anda bukan melukis potret, tapi mereka bentuk kereta, perabot, dan gajet elektronik. Di UniSZA, anda belajar menjadikan sesuatu produk itu cantik DANN berfungsi. Kerjaya untuk orang kreatif yang mahu melihat rekaan mereka dijual di pasaran."
    },

    # --- SCIENCE (GENERAL/UPSI) ---
    "UA4440001": {
        "headline": "🧪 Diploma Sains (UPSI): Asas Saintis Versatil",
        "synopsis": "Masih belum pasti nak jadi Biologis, Kimiawan, atau Fizikawan? Kursus ini memberi asas kukuh dalam ketiga-tiga bidang. UPSI melatih anda kemahiran makmal dan analisis kritikal, membuka pintu luas untuk menyambung ijazah dalam pelbagai bidang sains tulen atau pendidikan."
    },

    # --- SCIENCE (MATH) ---
    "UA4461001": {
        "headline": "📐 Diploma Sains (Matematik): The Data Wizard",
        "synopsis": "Matematik bukan sekadar kira-kira, ia adalah bahasa alam semesta dan data. Kursus ini melatih otak anda berfikir secara logik dan analitik. Skill ini sangat mahal dalam dunia 'Big Data' sekarang. Sesuai untuk yang suka nombor dan menyelesaikan masalah kompleks."
    },

    # --- APPLIED SCIENCE (UTHM) ---
    "UB4545001": {
        "headline": "🔬 Diploma Sains Gunaan (UTHM): Sains Industri",
        "synopsis": "Sains yang 'boleh pakai' terus. UTHM fokus kepada aplikasi industri—seperti teknologi makanan, kimia industri, dan bioteknologi. Anda takkan terperap dalam bilik kuliah saja; anda belajar bagaimana sains digunakan untuk memproses makanan dan bahan kimia di kilang."
    },

    # --- INDUSTRIAL SCIENCE (UMPSA) ---
    "UJ4545001": {
        "headline": "🏭 Diploma Sains Industri (UMPSA): Revolusi 4.0",
        "synopsis": "Fokus kepada teknologi masa depan. Di UMPSA, anda belajar sains bahan (material science) dan bioteknologi yang digerakkan oleh Revolusi Industri 4.0. Ini adalah sains untuk kilang moden dan sektor pembuatan berteknologi tinggi."
    },

    # --- NURSING ---
    "UD4723001": {
        "headline": "🩺 Diploma Sains Kejururawatan: Wira Putih",
        "synopsis": "Kerjaya mulia yang sentiasa dalam permintaan tinggi. UniSZA melatih anda menjadi jururawat profesional yang cekap secara klinikal dan santun menyantuni pesakit. Latihan praktikal yang intensif di hospital memastikan anda bersedia menjadi 'frontliner' sejurus tamat belajar."
    },

    # --- COMP SCIENCE (UPSI - INTERNET FOCUS) ---
    "UA4481001": {
        "headline": "🌐 Dip. Sains Komputer (UPSI): Web & Internet",
        "synopsis": "Fokus UPSI adalah 'Internet Computing'. Anda akan menguasai asas sistem komputer dan pembangunan aplikasi berasaskan web. Kursus ini sangat 'lab-intensive', bermakna anda akan banyak menghabiskan masa menyelesaikan masalah depan komputer, bukan sekadar teori."
    },

    # --- COMP SCIENCE (UTeM - SOFTWARE FOCUS) ---
    "UC4481002": {
        "headline": "💻 Dip. Sains Komputer (UTeM): Software Engineer Muda",
        "synopsis": "UTeM melatih anda menjadi 'Coder' sebenar. Fokus utama adalah pembangunan perisian menggunakan teknik OOP (Object-Oriented Programming) dan pangkalan data (Database). Jika cita-cita anda adalah membina software atau aplikasi mobile yang kompleks, ini tempatnya."
    },

    # --- COMP SCIENCE (UniSZA - THEORY/SOLUTION FOCUS) ---
    "UD4481003": {
        "headline": "🧠 Dip. Sains Komputer (UniSZA): Problem Solver",
        "synopsis": "Sains Komputer bukan hanya menaip kod, tetapi cara berfikir. Di UniSZA, anda dilatih mencari penyelesaian (solutions) kepada masalah rumit menggunakan prinsip komputer. Anda akan belajar algoritma yang efisien dan teori di sebalik teknologi."
    },

    # --- COMP SCIENCE (UMPSA - DATA FOCUS) ---
    "UJ4481001": {
        "headline": "📊 Dip. Sains Komputer (UMPSA): Data Scientist Muda",
        "synopsis": "Bukan sekadar coding biasa. UMPSA memfokuskan kepada 'Data Science' dan Bioinformatik. Ini adalah skill paling mahal di pasaran sekarang. Anda belajar bagaimana menggunakan komputer untuk menganalisis data besar (Big Data) dan membuat ramalan masa depan."
    },

    # --- COMP SCIENCE (UPM BINTULU) ---
    "UP4481001": {
        "headline": "💻 Dip. Sains Komputer (Bintulu): Arkitek IT Borneo",
        "synopsis": "Lokasi: Kampus Bintulu, Sarawak. Kursus menyeluruh yang merangkumi senibina komputer (hardware) dan pembangunan perisian (software). Graduan UPM Bintulu menjadi tulang belakang transformasi digital di Sarawak dan Sabah yang sedang pesat membangun."
    },

    # --- SPORTS SCIENCE ---
    "UA4813001": {
        "headline": "⚽ Dip. Sains Sukan & Kejurulatihan: Strategis Padang",
        "synopsis": "Suka sukan? Jangan sekadar main, belajar sains di sebaliknya. Di UPSI, anda belajar anatomi, pemulihan (rehab), dan strategi kejurulatihan. Ini bukan kelas PJ sekolah; ini adalah persediaan untuk menjadi jurulatih profesional atau pakar pemulihan atlet."
    },

    # --- TAHFIZ (MILITARY STYLE) ---
    "UZ4221001": {
        "headline": "📖 Dip. Tahfiz & Tafsir (UPNM): Hafiz Berdisiplin",
        "synopsis": "Satu-satunya tempat di mana Al-Quran bertemu disiplin ketenteraan. Anda akan menghafal Al-Quran dan mendalami Tafsir dalam suasana universiti pertahanan. Melahirkan pendakwah dan pemimpin agama yang bukan sahaja alim, tetapi mempunyai jatidiri dan disiplin besi."
    },

    # --- DANCE ---
    "UA4212002": {
        "headline": "💃 Diploma Tari: Seni & Sains Pergerakan",
        "synopsis": "Menari itu satu sains. Anda akan belajar anatomi badan (bagaimana otot bergerak) dan sistem notasi tarian, selain budaya seni. UPSI melahirkan koreografer yang faham sains tubuh, menjadikan persembahan lebih selamat dan artistik."
    },

    # --- ANIMATION TECH ---
    "UB4213001": {
        "headline": "🎨 Diploma Teknologi Animasi: Pencipta Dunia 3D",
        "synopsis": "Impian kerja di studio macam Pixar atau Les' Copaque? UTHM melatih anda teknik 'Modelling' dan 'Rendering' 2D/3D. Anda bukan melukis atas kertas, tapi menggunakan teknologi canggih untuk menghidupkan karakter digital. Industri ini sedang meletup di Malaysia!"
    },

    # --- CHEM ENG TECH (UTHM) ---
    "UB4524001": {
        "headline": "🧪 Dip. Tek. Kej. Kimia (UTHM): Penyelesai Masalah Kilang",
        "synopsis": "Fokus kepada aplikasi. Anda belajar bagaimana menyelesaikan masalah sebenar di loji pemprosesan kimia dan pengurusan sisa buangan. UTHM melahirkan teknologis yang pakar memastikan kilang berjalan lancar tanpa mencemarkan alam sekitar."
    },

    # --- CHEM ENG TECH (UniMAP - NEW) ---
    "UR4524001": {
        "headline": "⚗️ Dip. Tek. Kej. Kimia (UniMAP): Hands-on TVET",
        "synopsis": "Kursus Baharu! Pendekatan TVET yang sangat praktikal. Anda akan banyak masa di makmal melakukan eksperimen industri. Sesuai untuk pelajar yang lebih suka buat kerja praktikal berbanding teori panjang lebar. Sangat laku di kawasan perindustrian utara (Kulim/Penang)."
    },

    # --- MECH ENG TECH (UniMAP) ---
    "UR4521003": {
        "headline": "🛠️ Dip. Tek. Kej. Mekanikal (UniMAP): Pakar Mesin",
        "synopsis": "Ini adalah untuk mereka yang suka membaiki dan mengendali mesin. UniMAP menekankan penggunaan teknologi mekanikal dalam situasi sebenar. Anda akan tamat belajar dengan skil praktikal yang membolehkan anda terus bekerja di mana-mana bengkel atau kilang pembuatan."
    },

    # --- MANUFACTURING ENG TECH (UMPSA) ---
    "UJ4521002": {
        "headline": "🏭 Dip. Tek. Kej. Pembuatan (UMPSA): Belajar Sambil Kerja",
        "synopsis": "Kelebihan utama kursus ini ialah 'Work-Based Learning' (WBL). Pada tahun akhir, anda bukan duduk di dewan kuliah, tapi bekerja terus di kilang sebenar. Ini memberi anda pengalaman industri yang sangat berharga dan peluang cerah untuk diserap masuk kerja sejurus tamat belajar."
    },

    # --- POLYMER ENG TECH (UniMAP) ---
    "UR4543001": {
        "headline": "🧪 Dip. Tek. Kej. Polimer (UniMAP): Pakar Plastik & Getah",
        "synopsis": "Malaysia adalah gergasi industri getah dan polimer dunia (sarung tangan, tayar, komponen kereta). Kursus baharu ini melatih anda mengendalikan mesin pemprosesan polimer. Bidang yang sangat spesifik (niche) dengan gaji lumayan kerana kurang saingan tapi permintaan kilang sangat tinggi."
    },

    # --- IT (UniSZA - MULTIMEDIA FOCUS) ---
    "UD4482001": {
        "headline": "🎨 Dip. Teknologi Maklumat (UniSZA): IT Kreatif",
        "synopsis": "IT bukan sekadar kod yang membosankan. Di UniSZA, fokusnya adalah Multimedia. Anda belajar Graphic Design, 3D Modelling, dan pembinaan laman web yang cantik. Sesuai untuk anda yang minat komputer tetapi ada jiwa seni. Gabungan skill teknikal dan artistik yang sangat dicari agensi digital."
    },

    # --- IT (UTHM - CYBERSECURITY FOCUS) ---
    "UB4481001": {
        "headline": "🛡️ Dip. Teknologi Maklumat (UTHM): Cyber Defender",
        "synopsis": "Fokus UTHM adalah infrastruktur serius: Keselamatan Siber (Cybersecurity) dan Cloud Computing. Anda dilatih menjadi pelindung data dan pengurus sistem pelayan (server). Dalam era di mana data adalah emas, kepakaran menjaga keselamatan data adalah kerjaya masa depan yang paling selamat."
    },

    # --- LAB TECH (UPSI - GENERAL/INDUSTRIAL) ---
    "UA4545001": {
        "headline": "⚗️ Diploma Teknologi Makmal (UPSI): Tulang Belakang Sains",
        "synopsis": "Tanpa Teknologis Makmal, saintis tak boleh bekerja. Anda akan menguasai pengurusan makmal yang efisien—sama ada di sekolah, universiti, atau kilang farmaseutikal. Anda adalah pakar yang memastikan semua peralatan dan bahan kimia sentiasa bersedia dan selamat digunakan."
    },

    # --- MEDICAL LAB TECH (UniSZA - CLINICAL) ---
    "UD4725002": {
        "headline": "🩸 Dip. Tek. Makmal Perubatan (UniSZA): Detektif Penyakit",
        "synopsis": "Berbeza dengan makmal biasa, ini adalah makmal hospital. Tugas anda menganalisis sampel darah dan tisu untuk mengesan penyakit. Doktor bergantung kepada hasil ujian anda untuk merawat pesakit. Kerjaya kritikal di hospital kerajaan dan swasta (Pathlab/Gribbles)."
    },

    # --- MANUFACTURING TECH (UniSZA) ---
    "UD4540001": {
        "headline": "⚙️ Dip. Teknologi Pembuatan (UniSZA): Inovasi Produk",
        "synopsis": "Fokus kepada penghasilan produk inovatif. Anda akan belajar cara mengendalikan mesin moden untuk menukar idea menjadi barang jualan. Kursus ini berorientasikan industri, bermakna anda dilatih supaya 'ready' untuk masuk ke lantai kilang sebagai penyelia atau juruteknik mahir."
    },

    # --- FOUNDATION IN MANAGEMENT (UUM) ---
    "UU0345001": {
        "headline": "👔 Asasi Pengurusan (UUM): CEO Muda",
        "synopsis": "Laluan ekspres ke Universiti Utara Malaysia (UUM), universiti pengurusan tersohor. Program asasi ini mempersiapkan mentaliti anda untuk menjadi pemimpin korporat. Anda akan didedahkan awal kepada asas perakaunan, ekonomi, dan keusahawanan sebelum melangkah ke peringkat Ijazah."
    },

    # --- TAMHIDI (USIM) ---
    "UQ0440005": {
        "headline": "⚛️ Tamhidi Sains Fizikal & Teknologi: Saintis Berjiwa Al-Quran",
        "synopsis": "Program Asasi unik USIM yang menggabungkan Sains Tulen (Fizik/Kimia) dengan ilmu Naqli (Wahyu). Matlamatnya melahirkan profesional STEM—seperti Arkitek atau Jurutera—yang bukan sahaja hebat teknikalnya tetapi kukuh jati diri Islamnya. Laluan ke pelbagai ijazah sains di USIM."
    }

}

# --- FALLBACK FUNCTION ---
def get_course_details(cid, raw_name):
    # If we have the custom description, return it
    if cid in course_info:
        return course_info[cid]
    
    # Else, return a generic placeholder so the app doesn't crash
    return {
        "headline": f"{raw_name}",
        "synopsis": "Kursus ini menyediakan latihan teori dan amali yang komprehensif untuk menyediakan pelajar ke alam pekerjaan. (Maklumat terperinci sedang dikemaskini)."
    }
