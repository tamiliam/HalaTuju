# description.py

# This file contains the "Human-Friendly" descriptions for all Polytechnic Courses.
# It is imported by app.py to display the "Course Details" card.

course_info = {
    # --- AGROTECHNOLOGY ---
    "POLY-DIP-001": {
        "headline": "🌱 Agroteknologi: Pertanian Moden & Pintar",
        "synopsis": "Lupakan imej petani tradisional dengan cangkul. Kursus ini melatih anda menjadi 'Agropreneur Moden'. Anda akan belajar teknologi Fertigasi (tanam gantung), Pertanian Pintar (IoT/Sensor), dan cara mengurus ladang komersial dari benih hingga pemasaran. Sesuai untuk anda yang suka aktiviti luar (outdoor) tetapi mahukan kerjaya berteknologi tinggi.",
        "jobs": ["Agropreneur (Usahawan Tani)", "Penyelia Ladang Moden", "Juruteknik Pertanian", "Pengurus Estet"]
    },
    
    # --- BIOTECHNOLOGY ---
    "POLY-DIP-002": {
        "headline": "🧬 Bioteknologi: Sains Hayat Industri",
        "synopsis": "Anda akan bekerja di makmal untuk menghasilkan produk berasaskan biologi—seperti makanan, ubat-ubatan, atau benih tanaman hibrid. Anda akan menguasai teknik Kultur Tisu, Mikrobiologi, dan Fermentasi. Ini adalah bidang untuk mereka yang teliti, suka eksperimen sains, dan berminat dengan inovasi makmal.",
        "jobs": ["Juruteknik Makmal (Lab Tech)", "Quality Control (QC)", "Pembantu Penyelidik", "Usahawan Bio-Produk"]
    },

    # --- GEOMATICS ---
    "POLY-DIP-003": {
        "headline": "🌍 Geomatik: Peta, Satelit & Dron",
        "synopsis": "Dulu dikenali sebagai 'Ukur Tanah', kini ia menggunakan Satelit (GPS) dan Dron. Tugas anda adalah mengukur bumi untuk menghasilkan peta digital yang tepat bagi pembinaan bangunan, jalan raya, dan perancangan bandar. Kerjaya ini menggabungkan kerja luar (fieldwork) yang lasak dengan analisis komputer yang canggih.",
        "jobs": ["Juruukur Tanah", "Operator Dron Pemetaan", "GIS Technician", "Penolong Pegawai Tanah"]
    },

    # --- RETAIL MANAGEMENT ---
    "POLY-DIP-004": {
        "headline": "🛒 Pengurusan Runcit: Raja Pasaran",
        "synopsis": "Pernah tertanya bagaimana pasar raya besar (Giant/AEON) atau butik fesyen antarabangsa diuruskan? Kursus ini mengajar anda logistik, susun atur kedai (Visual Merchandising), dan strategi jualan. Anda juga akan menjalani latihan industri intensif (WBL) di kedai sebenar untuk merasai pengalaman menjadi pengurus.",
        "jobs": ["Pengurus Cawangan (Store Manager)", "Visual Merchandiser", "Eksekutif Operasi Runcit", "Event Coordinator"]
    },

    # --- INSURANCE ---
    "POLY-DIP-005": {
        "headline": "🛡️ Insurans: Pengurusan Risiko Profesional",
        "synopsis": "Bukan sekadar menjadi ejen insurans. Ini adalah ilmu profesional tentang Pengurusan Risiko Kewangan. Anda akan belajar menilai kerugian, undang-undang kewangan, dan bagaimana syarikat gergasi melindungi aset bernilai jutaan ringgit. Kemahiran ini sangat diperlukan oleh bank dan syarikat korporat.",
        "jobs": ["Penilai Risiko (Underwriter)", "Eksekutif Tuntutan (Claims)", "Perancang Kewangan", "Broker Insurans"]
    },

    # --- ENVIRONMENTAL ENGINEERING ---
    "POLY-DIP-006": {
        "headline": "♻️ Kejuruteraan Alam Sekitar: Wira Bumi",
        "synopsis": "Anda adalah doktor kepada alam sekitar. Belajar cara merawat air sisa, mengurus sisa pepejal (sampah), dan memantau kualiti udara. Tugas anda memastikan pembangunan negara tidak memusnahkan bumi. Sesuai untuk mereka yang peka dengan isu hijau dan mahukan kerjaya teknikal yang memberi impak positif.",
        "jobs": ["Penolong Pegawai Alam Sekitar", "Penyelia Tapak Pelupusan", "Juruteknik Kualiti Air", "Pegawai Keselamatan & Kesihatan (SHO)"]
    },

    # --- CIVIL ENGINEERING ---
    "POLY-DIP-007": {
        "headline": "🏗️ Kejuruteraan Awam: Pembina Negara",
        "synopsis": "Dari jambatan gergasi ke bangunan pencakar langit, andalah yang merealisasikannya. Anda akan belajar melukis pelan struktur, menguji kekuatan konkrit, dan menyelia tapak pembinaan. Kerja ini mungkin panas dan berdebu, tetapi pulangannya lumayan dan hasilnya kekal berdiri megah.",
        "jobs": ["Penyelia Tapak (Site Supervisor)", "Pelukis Pelan (Draughtsman)", "Kontraktor Binaan", "Clerk of Works"]
    },

    # --- ELECTRICAL ENGINEERING ---
    "POLY-DIP-008": {
        "headline": "⚡ Kejuruteraan Elektrik: Kuasa Tinggi",
        "synopsis": "Fokus sepenuhnya kepada tenaga elektrik. Bagaimana ia dijana, dihantar melalui kabel grid kebangsaan, dan diagihkan ke rumah. Anda akan pakar dalam pendawaian (wiring), motor elektrik industri, dan keselamatan voltan tinggi. Graduan kursus ini adalah 'tulang belakang' kepada TNB dan kilang-kilang besar.",
        "jobs": ["Juruteknik Elektrik", "Chargeman (Penjaga Jentera)", "Kontraktor Pendawaian", "Juruteknik Penyelenggaraan"]
    },

    # --- ELECTRICAL & ELECTRONIC ENGINEERING ---
    "POLY-DIP-009": {
        "headline": "🤖 Elektrik & Elektronik: Kuasa & Robotik",
        "synopsis": "Kursus '2-dalam-1' yang paling versatil. Anda belajar asas kuasa (Elektrik) DAN sistem kawalan pintar (Elektronik). Bayangkan anda boleh membuat wiring rumah, dan pada masa sama memprogramkan robot kilang (PLC). Ini menjadikan anda sangat laku dalam pelbagai industri, dari pembinaan hingga pembuatan cip.",
        "jobs": ["Penolong Jurutera", "Penyelia Kilang (Automation)", "Juruteknik Pakar", "Service Engineer"]
    },

    # --- ELECTRICAL & INSTRUMENTATION (PETROCHEM) ---
    "POLY-DIP-010": {
        "headline": "🛢️ Elektrik & Instrumentasi: Pakar Petrokimia",
        "synopsis": "Kursus elit yang direka khusus untuk industri Minyak & Gas (O&G). Selain elektrik, anda belajar tentang 'Instrumentasi'—sensor dan alat kawalan yang memantau paip minyak dan loji kimia. Anda akan belajar sistem DCS dan PLC yang digunakan di loji penapisan (refinery).",
        "jobs": ["Juruteknik Instrumentasi", "Juruteknik O&G", "Penyelia Loji Petrokimia", "Penolong Jurutera Kawalan"]
    },

    # --- ELECTRICAL ENGINEERING (SPECIALIZATIONS) ---
    "POLY-DIP-011": {
        "headline": "⚡ Elektrik (Kecekapan Tenaga): Audit & Jimat",
        "synopsis": "Tenaga adalah wang. Dalam kursus ini, anda belajar bukan sahaja cara *guna* elektrik, tapi cara *urus* elektrik supaya tidak membazir. Anda akan diajar tentang 'Energy Audit', Tenaga Boleh Diperbaharui (Solar/Angin), dan sistem kuasa cekap tenaga. Graduan kursus ini sangat dicari oleh kilang-kilang yang mahu kurangkan bil elektrik mereka.",
        "jobs": ["Auditor Tenaga (Energy Auditor)", "Pegawai Kelestarian (Sustainability)", "Juruteknik Tenaga Hijau", "Penolong Jurutera Elektrik"]
    },
    "POLY-DIP-012": {
        "headline": "🌱 Elektrik (Tenaga Hijau): Masa Depan Bumi",
        "synopsis": "Dunia sedang beralih dari minyak ke tenaga bersih. Anda akan menjadi pakar dalam Teknologi Hijau: Panel Solar, Turbin Angin, dan Kereta Elektrik (EV). Anda belajar memasang, menyelenggara, dan mengintegrasikan sistem ini ke dalam grid nasional. Ini adalah kerjaya masa depan yang kalis kemelesetan.",
        "jobs": ["Pemasang Solar (Solar Installer)", "Juruteknik Turbin Angin", "Juruteknik Kenderaan Elektrik (EV)", "Perunding Tenaga Hijau"]
    },

    # --- ELECTRONIC ENGINEERING (SPECIALIZATIONS) ---
    "POLY-DIP-013": {
        "headline": "💡 Elektronik (Optoelektronik): Cahaya & Laser",
        "synopsis": "Pernah dengar tentang Fiber Optik atau LED? Itu adalah Optoelektronik—menggunakan cahaya untuk hantar data dan kuasa. Anda akan belajar tentang laser, penderia cahaya (sensors), dan pembuatan cip semikonduktor. Sesuai untuk anda yang berminat dengan teknologi di sebalik internet berkelajuan tinggi dan skrin canggih.",
        "jobs": ["Juruteknik Fiber Optik", "Pakar Laser Industri", "Penolong Jurutera Pembuatan", "Juruteknik R&D"]
    },
    "POLY-DIP-014": {
        "headline": "🤖 Elektronik (Kawalan): Otak Robot",
        "synopsis": "Bagaimana lengan robot di kilang kereta bergerak dengan tepat? Itu adalah Sistem Kawalan. Anda belajar memprogramkan 'otak' mesin menggunakan PLC dan sensor. Anda akan menjadi pakar yang memastikan barisan pengeluaran kilang (production line) berjalan secara automatik tanpa henti.",
        "jobs": ["Juruteknik Automasi", "Programmer PLC", "Juruteknik Instrumentasi", "Penyelia Penyelenggaraan"]
    },
    "POLY-DIP-015": {
        "headline": "💻 Elektronik (Komputer): Hardware & Chips",
        "synopsis": "Jika Sains Komputer fokus pada Software, kursus ini fokus pada Hardware. Anda belajar bagaimana komputer *dibina* dari dalam—pemproses (processor), litar memori, dan sistem terbenam (embedded systems). Anda akan mahir membaiki, mereka bentuk, dan menyelenggara sistem komputer industri.",
        "jobs": ["Juruteknik Komputer", "Pakar IoT (Internet of Things)", "Juruteknik Perisian & Hardware", "Technical Support"]
    },
    "POLY-DIP-016": {
        "headline": "📡 Elektronik (Komunikasi): Dunia Tanpa Wayar",
        "synopsis": "Dari 5G ke Satelit, andalah yang menghubungkan dunia. Kursus ini mengajar teknologi di sebalik telefon pintar, menara pemancar, dan rangkaian data. Anda akan belajar tentang frekuensi radio (RF), gentian optik, dan sistem rangkaian tanpa wayar. Kerjaya di syarikat Telco (Maxis/Celcom) menanti anda.",
        "jobs": ["Juruteknik Rangkaian (Network)", "Jurutera 'Drive Test' (Telco)", "Penyelia Menara Pemancar", "RF Technician"]
    },
    "POLY-DIP-017": {
        "headline": "🏥 Elektronik (Perubatan): Doktor Mesin",
        "synopsis": "Gabungan Kejuruteraan dan Perubatan. Hospital penuh dengan mesin canggih (MRI, X-Ray, Mesin Dialisis). Tugas anda adalah memastikan mesin ini berfungsi 100% tepat untuk menyelamatkan nyawa. Anda belajar anatomi manusia asas DAN litar elektronik canggih.",
        "jobs": ["Juruteknik Bioperubatan (Biomedical)", "Pakar Servis Mesin X-Ray/MRI", "Jurutera Klinikal", "Perunding Alat Perubatan"]
    },

    # --- CHEMICAL ENGINEERING ---
    "POLY-DIP-018": {
        "headline": "🧪 Kejuruteraan Kimia: Dari Makmal ke Kilang",
        "synopsis": "Bagaimana minyak mentah jadi petrol? Bagaimana bahan kimia jadi plastik? Anda belajar proses 'skala besar' industri kimia. Anda akan mengendalikan loji kimia, memantau tindak balas kimia dalam reaktor gergasi, dan memastikan sisa buangan selamat untuk alam sekitar. Kerjaya 'high demand' di Pengerang dan Gebeng.",
        "jobs": ["Juruteknik Proses (Process Tech)", "Penyelia Loji Kimia", "Juruteknik Rawatan Air", "Pegawai Kawalan Kualiti (QA)"]
    },

    # --- MECHANICAL ENGINEERING ---
    "POLY-DIP-019": {
        "headline": "⚙️ Kejuruteraan Mekanikal: Asas Kejuruteraan",
        "synopsis": "Kursus kejuruteraan yang paling luas dan fleksibel. Anda belajar tentang semua benda yang bergerak—mesin, enjin, sistem hidraulik, dan bahan. Anda akan mahir menggunakan perisian CAD untuk melukis komponen dan tangan anda akan cekap membaiki mesin. Graduan kursus ini boleh bekerja di mana-mana kilang di dunia.",
        "jobs": ["Juruteknik Mekanikal", "Penyelia Penyelenggaraan", "Operator CNC", "QA/QC Inspector"]
    },
    "POLY-DIP-020": {
        "headline": "🦾 Mekanikal (Automasi): Revolusi Industri 4.0",
        "synopsis": "Kilang masa depan tidak perlukan ramai pekerja, ia perlukan robot. Kursus ini mengajar anda membina dan menyelenggara sistem robotik industri. Anda akan belajar tentang Pneumatik (kuasa udara), Hidraulik (kuasa cecair), dan integrasi robot dengan komputer. Anda adalah arkitek kepada kilang pintar.",
        "jobs": ["Juruteknik Robotik", "Pakar Integrasi Sistem", "Pereka Mesin Automasi", "Penyelia Teknikal"]
    },

    # --- AUTOMOTIVE ENGINEERING ---
    "POLY-DIP-021": {
        "headline": "🏎️ Automotif: Pakar Enjin & Servis",
        "synopsis": "Kursus untuk 'Petrolhead' sejati. Anda bukan sekadar mekanik bawah pokok; anda adalah pakar diagnostik. Anda belajar tentang enjin pembakaran dalam, sistem elektronik kereta moden (ECU), dan pengurusan pusat servis. Sesuai jika anda bercita-cita membuka bengkel moden atau menjadi pengurus di pusat servis jenama terkemuka (Honda/Toyota).",
        "jobs": ["Pengurus Pusat Servis", "Penasihat Servis (Service Advisor)", "Penyelia Bengkel", "Juruteknik Diagnostik"]
    },

    # --- MATERIALS ENGINEERING ---
    "POLY-DIP-022": {
        "headline": "🧪 Kejuruteraan Bahan: Sains di Sebalik Besi",
        "synopsis": "Kenapa kapal terbang dibuat daripada aluminium, bukan besi? Kenapa bumper kereta plastik tapi keras? Anda belajar 'resipi' bahan—logam, polimer (plastik), seramik, dan komposit. Anda akan bekerja di makmal untuk menguji kekuatan bahan dan memastikan produk kilang tidak mudah patah atau karat.",
        "jobs": ["Juruteknik Kawalan Kualiti (QA/QC)", "Penyelia Makmal Ujian", "Juruteknik Logam/Plastik", "Pembantu Penyelidik Bahan"]
    },

    # --- POWER PLANT ENGINEERING ---
    "POLY-DIP-023": {
        "headline": "🏭 Loji Kuasa: Jantung Tenaga Negara",
        "synopsis": "Kerjaya 'Heavy Duty'. Anda belajar mengendalikan mesin gergasi yang menjana elektrik untuk satu negara—Turbin, Dandang (Boiler), dan Generator. Anda akan bekerja di stesen janakuasa (Power Plant) untuk memastikan lampu di rumah kita tidak terpadam. Kerja yang sangat kritikal dan bergaji tinggi.",
        "jobs": ["Juruteknik Operasi Loji", "Boilerman (Juru Dandang)", "Juruteknik Turbin", "Pembantu Jurutera Kuasa"]
    },

    # --- MANUFACTURING ENGINEERING ---
    "POLY-DIP-024": {
        "headline": "🏭 Pembuatan (Manufacturing): Nadi Kilang",
        "synopsis": "Bagaimana telefon pintar dibuat secara besar-besaran? Kursus ini mengajar anda proses pengeluaran kilang. Anda belajar menggunakan mesin CNC (pemotong berkomputer), robotik industri, dan kawalan kualiti. Anda adalah orang penting yang memastikan kilang beroperasi dengan efisien dan produk siap tepat pada masanya.",
        "jobs": ["Penyelia Pengeluaran (Production)", "Programmer CNC", "Juruteknik Pembuatan", "QA Inspector"]
    },

    # --- PACKAGING ENGINEERING ---
    "POLY-DIP-025": {
        "headline": "📦 Pembungkusan Industri: Seni & Sains Kotak",
        "synopsis": "Jangan pandang rendah pada kotak. Pembungkusan melindungi produk bernilai jutaan ringgit. Anda belajar mereka bentuk bungkusan yang tahan lasak, menarik, dan mesra alam. Anda akan mahir tentang bahan (kertas/plastik), mesin pembungkusan automatik, dan reka bentuk grafik untuk kotak. Industri makanan dan logistik sangat memerlukan pakar ini.",
        "jobs": ["Pereka Pembungkusan (Packaging Designer)", "Penyelia Talian Pembungkusan", "Juruteknik Kualiti", "Eksekutif Logistik"]
    },

    # --- AIR-CONDITIONING & REFRIGERATION ---
    "POLY-DIP-026": {
        "headline": "❄️ Penyamanan Udara: Wira Penyejuk",
        "synopsis": "Di Malaysia yang panas, kemahiran ini ibarat emas. Anda belajar sistem HVAC komersial—aircond pusat beli-belah, bilik sejuk beku (cold storage), dan sistem pengudaraan bangunan. Bukan sekadar pasang aircond rumah, tapi merancang dan menyelenggara sistem penyejukan industri yang kompleks.",
        "jobs": ["Juruteknik HVAC", "Kontraktor Aircond", "Penyelia Penyelenggaraan Bangunan", "Pereka Sistem Penyejukan"]
    },

    # --- AGRICULTURAL ENGINEERING ---
    "POLY-DIP-027": {
        "headline": "🚜 Mekanikal (Pertanian): Teknologi Ladang",
        "synopsis": "Gabungan kejuruteraan dan pertanian. Anda belajar membaiki dan mengendalikan jentera ladang besar (traktor, penuai), sistem pengairan automatik, dan struktur rumah hijau. Tugas anda adalah memastikan teknologi ladang berjalan lancar untuk meningkatkan hasil makanan negara.",
        "jobs": ["Juruteknik Jentera Ladang", "Penyelia Mekanisasi Ladang", "Juruteknik Pengairan", "Kontraktor Pertanian"]
    },

    # --- PETROCHEMICAL (MECHANICAL) ---
    "POLY-DIP-028": {
        "headline": "🛢️ Mekanikal (Petrokimia): Pakar Minyak & Gas",
        "synopsis": "Direka khusus untuk industri O&G (Minyak & Gas). Anda belajar menyelenggara paip, injap, dan tangki di loji petrokimia yang berisiko tinggi. Keselamatan adalah nombor satu. Graduan kursus ini biasanya bekerja di hab industri seperti Pengerang, Kerteh, atau Bintulu.",
        "jobs": ["Juruteknik Penyelenggaraan Loji", "Penyelia Paip & Injap", "Juruteknik Mekanikal O&G", "Safety Supervisor"]
    },

    # --- PLASTICS ENGINEERING ---
    "POLY-DIP-029": {
        "headline": "🧸 Plastik Industri: Mencipta Bentuk",
        "synopsis": "Hampir semua barang di sekeliling kita ada plastik. Kursus ini mengajar anda cara mereka bentuk acuan (molds) dan menggunakan mesin suntikan plastik (injection molding) untuk menghasilkan produk—dari botol air hingga komponen kereta. Malaysia ada 1,300 kilang plastik yang memerlukan kepakaran anda.",
        "jobs": ["Pereka Acuan (Mold Designer)", "Juruteknik Mesin Suntikan", "Penyelia Pengeluaran Plastik", "QA Technician"]
    },

    # --- AUTOMOTIVE DESIGN ---
    "POLY-DIP-030": {
        "headline": "🎨 Reka Bentuk Automotif: Seni Kereta",
        "synopsis": "Berbeza dengan kursus 'baik pulih', kursus ini fokus kepada PENCIPTAAN. Anda belajar menggunakan perisian CAD/CAM untuk melukis komponen kereta, mereka bentuk bentuk badan kereta (body styling), dan ergonomik. Sesuai untuk anda yang kreatif dan mahu bekerja di kilang pemasangan kereta (Proton/Perodua).",
        "jobs": ["Pereka Produk Automotif", "Juruteknik CAD/CAM", "Penyelia Pembuatan Kereta", "Quality Control"]
    },

    # --- PRODUCT DESIGN ---
    "POLY-DIP-031": {
        "headline": "🎨 Reka Bentuk Produk: Seni + Fungsi",
        "synopsis": "Lihat sekeliling anda—tetikus komputer, kerusi, botol air. Semuanya direka oleh seseorang. Kursus ini mengajar anda menggabungkan kreativiti (Seni) dengan kejuruteraan (Fungsi). Anda akan belajar melukis lakaran, membuat model 3D (CAD), dan menghasilkan prototaip produk yang sedia untuk dikilangkan. Kerjaya yang sangat kreatif!",
        "jobs": ["Pereka Produk (Industrial Designer)", "Pereka CAD", "Juruteknik R&D", "Penyelia Pengeluaran"]
    },

    # --- MECHATRONICS ---
    "POLY-DIP-032": {
        "headline": "🤖 Mekatronik: Robotik & AI",
        "synopsis": "Gabungan Mekanikal + Elektronik + Komputer. Ini adalah asas kepada Robotik. Anda belajar membina sistem pintar yang bergerak sendiri—seperti lengan robot kilang, dron, atau sistem 'Smart Home'. Anda akan mahir dalam sensor, motor, dan programming (Coding).",
        "jobs": ["Juruteknik Robotik", "Jurutera Automasi", "Penyelia Sistem Kawalan", "Juruteknik Penyelenggaraan Mesin"]
    },

    # --- AIRCRAFT MAINTENANCE ---
    "POLY-DIP-033": {
        "headline": "✈️ Penyenggaraan Pesawat: Kerjaya di Awan Biru",
        "synopsis": "Bercita-cita bekerja di lapangan terbang? Kursus elit ini melatih anda menjadi doktor kepada kapal terbang. Anda belajar membaiki enjin turbin, sistem hidraulik pesawat, dan instrumen kokpit. Lulusan kursus ini bersedia untuk mengambil lesen jurutera pesawat (License A) yang bergaji lumayan.",
        "jobs": ["Juruteknik Pesawat (Aircraft Technician)", "Mekanik Enjin Turbin", "Penyelia Hangar", "Juruteknik Komponen Pesawat"]
    },

    # --- MARINE ENGINEERING ---
    "POLY-DIP-034": {
        "headline": "🚢 Kejuruteraan Perkapalan: Penakluk Lautan",
        "synopsis": "Kerjaya untuk jiwa yang kental. Anda belajar mengendalikan enjin kapal gergasi. Kursus ini unik kerana anda akan menjalani 'Latihan Laut' (belayar) selama 6 bulan. Graduan layak dikecualikan peperiksaan tertentu untuk menjadi Jurutera Laut (Marine Engineer) bertauliah. Gaji dalam USD menanti anda di lautan antarabangsa.",
        "jobs": ["Jurutera Laut (Marine Engineer)", "Pegawai Kapal", "Superintendent Limbungan", "Juruteknik Enjin Marin"]
    },

    # --- BUILDING SERVICES ---
    "POLY-DIP-035": {
        "headline": "🏢 Perkhidmatan Bangunan: Nadi Pencakar Langit",
        "synopsis": "Bangunan tinggi tidak boleh berfungsi tanpa anda. Siapa yang pastikan lif bergerak, aircond sejuk, dan lampu menyala? Kursus ini mengajar anda mengurus 'sistem hidup' bangunan—elektrik, paip, dan keselamatan kebakaran. Kerjaya yang sangat stabil di mana-mana bandar besar.",
        "jobs": ["Penyelia Fasiliti (Facility Manager)", "Penolong Jurutera Bangunan", "Juruteknik Penyelenggaraan", "Penyelia Tapak"]
    },

    # --- PROCESS ENGINEERING (PETROCHEM) ---
    "POLY-DIP-036": {
        "headline": "🧪 Proses (Petrokimia): Kawalan Loji",
        "synopsis": "Fokus kepada 'Proses'—bagaimana menukar bahan mentah menjadi produk kimia. Anda belajar mengawal suhu, tekanan, dan aliran dalam paip loji petrokimia. Anda akan berlatih menggunakan simulasi loji sebenar. Sesuai untuk mereka yang mahu bekerja di hab industri minyak & gas.",
        "jobs": ["Juruteknik Proses (Process Tech)", "Operator Loji", "Penyelia Kawalan Bilik (Control Room)", "Pembantu Jurutera"]
    },

    # --- ENTREPRENEURSHIP ---
    "POLY-DIP-037": {
        "headline": "🚀 Keusahawanan: Bina Bisnes Sendiri",
        "synopsis": "Jangan cari kerja, cipta kerja. Kursus ini bukan sekadar teori; ia adalah 'Inkubator Bisnes'. Anda belajar mencari modal, pemasaran digital, dan undang-undang bisnes. Anda akan dibimbing untuk menubuhkan syarikat sebenar sebelum tamat belajar. Sesuai untuk anda yang berjiwa bos.",
        "jobs": ["Usahawan (Founder)", "Perunding Perniagaan", "Pengurus Francais", "Eksekutif Pemasaran"]
    },

    # --- FINANCE ---
    "POLY-DIP-038": {
        "headline": "💰 Kewangan (Finance): Pakar Duit",
        "synopsis": "Kuasai bahasa wang. Anda belajar menganalisis pasaran saham, mengurus bajet syarikat, dan merancang pelaburan. Ini adalah tiket masuk ke dunia korporat dan perbankan. Anda akan faham bagaimana duit bekerja untuk menghasilkan lebih banyak duit.",
        "jobs": ["Eksekutif Kewangan", "Penganalisis Pelaburan", "Perancang Kewangan", "Pegawai Bank"]
    },

    # --- ISLAMIC FINANCE ---
    "POLY-DIP-039": {
        "headline": "☪️ Kewangan Islam: Perbankan Patuh Syariah",
        "synopsis": "Malaysia adalah hab Kewangan Islam dunia. Kursus ini mengajar sistem perbankan tanpa riba, Takaful (insurans Islam), dan pengurusan harta (Zakat/Waqaf). Industri ini berkembang pesat dan sangat memerlukan tenaga kerja mahir yang faham hukum muamalat.",
        "jobs": ["Pegawai Bank Islam", "Ejen Takaful", "Perancang Kewangan Islam", "Pegawai Zakat/Baitulmal"]
    },

    # --- RECREATIONAL TOURISM ---
    "POLY-DIP-040": {
        "headline": "rafting🚣 Pelancongan Rekreasi: Kerjaya Lasak",
        "synopsis": "Ubah hobi 'hiking' dan 'travel' menjadi kerjaya. Anda belajar mengurus taman tema, resort eko-pelancongan, dan aktiviti luar (outdoor). Anda akan diajar tentang keselamatan rekreasi, pemanduan pelancong alam semulajadi, dan pengurusan acara. Pejabat anda adalah hutan, sungai, dan pulau.",
        "jobs": ["Penyelia Taman Tema", "Pemandu Pelancong (Nature Guide)", "Pengurus Acara (Event)", "Ranger Taman Negara"]
    },

    # --- MARKETING ---
    "POLY-DIP-041": {
        "headline": "📢 Pemasaran: Kuasai Seni Jualan",
        "synopsis": "Kenapa sesetengah jenama 'viral'? Itu adalah kuasa pemasaran. Anda belajar psikologi pembeli, strategi pengiklanan, dan pemasaran digital (TikTok/IG Ads). Bukan sekadar jurujual, anda dilatih menjadi pakar strategi jenama yang tahu cara membuat produk laku keras di pasaran.",
        "jobs": ["Eksekutif Pemasaran Digital", "Pengurus Jenama (Brand Manager)", "Penyelidik Pasaran", "Perancang Acara"]
    },

    # --- BUSINESS STUDIES ---
    "POLY-DIP-042": {
        "headline": "💼 Pengajian Perniagaan: 'Swiss Army Knife' Korporat",
        "synopsis": "Kursus paling fleksibel dalam dunia bisnes. Anda belajar sikit tentang semua—HR (Sumber Manusia), Kewangan, Operasi, dan Pentadbiran. Ini menjadikan anda pekerja serba boleh yang boleh masuk ke mana-mana industri. Asas yang kukuh jika anda mahu menjadi CEO atau Pengurus suatu hari nanti.",
        "jobs": ["Eksekutif Pentadbiran", "Pegawai HR", "Usahawan", "Pengurus Operasi"]
    },

    # --- EVENT MANAGEMENT ---
    "POLY-DIP-043": {
        "headline": "🎉 Pengurusan Acara: Cipta Kenangan",
        "synopsis": "Di sebalik konsert gempak, ekspo mega, dan perkahwinan mewah, ada 'Event Manager' yang sibuk. Anda belajar merancang bajet, mengurus logistik, dan menyelesaikan krisis masa nyata. Kerja ini pantas, tekanan tinggi, tetapi sangat menyeronokkan. Tiada hari yang membosankan!",
        "jobs": ["Event Planner", "Penyelaras Konsert/Ekspo", "Wedding Planner", "Pengurus Pentas"]
    },

    # --- HOTEL MANAGEMENT ---
    "POLY-DIP-044": {
        "headline": "🏨 Pengurusan Hotel: Layanan 5 Bintang",
        "synopsis": "Dunia hospitaliti bukan sekadar senyum. Anda belajar mengurus 'Front Office', operasi 'Housekeeping', dan perkhidmatan makanan (F&B). Keunikan kursus ini: Anda akan menjalani latihan industri (WBL) selama 10 bulan di hotel sebenar—belajar sambil bekerja dalam suasana profesional.",
        "jobs": ["Penyelia Hotel", "Front Office Executive", "Pengurus Restoran", "Concierge"]
    },

    # --- LOGISTICS & SUPPLY CHAIN ---
    "POLY-DIP-045": {
        "headline": "📦 Logistik & Rantaian Bekalan: Nadi Ekonomi",
        "synopsis": "Bagaimana barang dari China sampai ke pintu rumah anda dalam 3 hari? Itu magis Logistik. Anda belajar mengurus gudang, penghantaran kargo (darat/laut/udara), dan inventori. Dalam era E-Commerce (Shopee/Lazada), pakar logistik adalah orang yang paling dicari oleh syarikat.",
        "jobs": ["Eksekutif Logistik", "Pengurus Gudang", "Pegawai Import/Eksport", "Perancang Rantaian Bekalan"]
    },

    # --- TOURISM MANAGEMENT ---
    "POLY-DIP-046": {
        "headline": "✈️ Pengurusan Pelancongan: Duta Negara",
        "synopsis": "Bawa dunia melawat Malaysia. Anda belajar merangka pakej pelancongan, mengurus agensi travel, dan teknik pemandu pelancong. Anda akan mahir tentang destinasi, budaya, dan cara memberikan pengalaman terbaik kepada pelancong. Kerjaya ini membolehkan anda mengembara sambil bekerja.",
        "jobs": ["Pegawai Pelancongan", "Travel Consultant", "Pemandu Pelancong", "Penyelia Agensi Pelancongan"]
    },

    # --- RETAIL MANAGEMENT ---
    "POLY-DIP-047": {
        "headline": "🛍️ Pengurusan Peruncitan: Bukan Sekadar Jaga Kaunter",
        "synopsis": "Industri runcit perlukan pengurus, bukan sekadar juruwang. Anda belajar strategi susun atur kedai, pembelian stok (buying), dan khidmat pelanggan visual. Dari kedai serbaneka hingga butik mewah, andalah yang memastikan kedai untung dan pelanggan gembira.",
        "jobs": ["Pengurus Kedai (Store Manager)", "Visual Merchandiser", "Pembeli Runcit (Buyer)", "Penyelia Jabatan"]
    },

    # --- RESORT MANAGEMENT ---
    "POLY-DIP-048": {
        "headline": "🏝️ Pengurusan Resort: Kerjaya di Syurga Percutian",
        "synopsis": "Beza dengan hotel bandar, resort adalah tentang 'pengalaman santai'. Anda belajar mengurus fasiliti rekreasi, spa, dan aktiviti tetamu di lokasi peranginan (pulau/tanah tinggi). Jika anda suka suasana kerja yang tenang dan cantik, ini kursus untuk anda.",
        "jobs": ["Penyelia Resort", "Pengurus Spa & Rekreasi", "Pegawai Perhubungan Tetamu (GRO)", "Penyelia Acara Resort"]
    },

    # --- ACCOUNTING ---
    "POLY-DIP-049": {
        "headline": "📊 Perakaunan (Accounting): Bahasa Bisnes",
        "synopsis": "Setiap syarikat, dari gerai burger hingga Petronas, perlukan Akauntan. Anda belajar merekod duit masuk/keluar, mengira cukai, dan audit. Ini adalah laluan pantas untuk menjadi akauntan bertauliah (ACCA/CIMA) pada masa depan. Kerjaya yang sangat stabil dan dihormati.",
        "jobs": ["Pembantu Akauntan", "Pegawai Cukai", "Penolong Juruaudit", "Kerani Kewangan"]
    },

    # --- TOWN & REGIONAL PLANNING ---
    "POLY-DIP-050": {
        "headline": "🏙️ Perancang Bandar: Arkitek Bandaraya",
        "synopsis": "Siapa tentukan di mana sekolah, taman, dan kilang patut dibina? Itu tugas Perancang Bandar. Anda belajar melukis pelan guna tanah, undang-undang pembangunan, dan mereka bentuk bandar yang selesa didiami. Anda bekerja rapat dengan PBT (Majlis Perbandaran) untuk membentuk masa depan bandar kita.",
        "jobs": ["Penolong Pegawai Perancang Bandar", "Pelukis Pelan Bandar", "Penolong Pegawai Landskap", "Penyelia Projek Pembangunan"]
    },

    # --- HALAL FOOD SERVICES ---
    "POLY-DIP-051": {
        "headline": "🍽️ Perkhidmatan Makanan Halal: Global Standard",
        "synopsis": "Pasaran Halal dunia bernilai trilion ringgit. Kursus ini bukan sekadar masak; ia tentang Sains Halal. Anda belajar audit Halal, pengurusan dapur patuh syariah, dan nutrisi. Graduan kursus ini sangat dicari oleh hotel 5 bintang dan syarikat makanan antarabangsa yang mahu menembusi pasaran Muslim.",
        "jobs": ["Eksekutif Halal", "Penyelia Restoran", "Pegawai Jaminan Kualiti (QA)", "Usahawan Makanan Halal"]
    },

    # --- INTERNATIONAL BUSINESS ---
    "POLY-DIP-052": {
        "headline": "🌐 Perniagaan Antarabangsa: Bisnes Tanpa Sempadan",
        "synopsis": "Kenapa jual di kampung jika boleh jual satu dunia? Anda belajar selok-belok Import/Eksport, undang-undang perdagangan antarabangsa, dan logistik global. Anda akan faham bagaimana Amazon atau Alibaba beroperasi. Sesuai untuk anda yang mahu kerjaya 'jet-setting' dan berurusan dengan orang luar negara.",
        "jobs": ["Pegawai Import/Eksport", "Penganalisis Pasaran Global", "Pengurus Logistik", "Perunding Perniagaan"]
    },

    # --- FASHION DESIGN ---
    "POLY-DIP-053": {
        "headline": "👗 Reka Bentuk Fesyen: Dari Lakaran ke Runway",
        "synopsis": "Adakah anda 'Trendsetter'? Kursus ini mengajar anda mencipta pakaian dari A sampai Z—melukis ilustrasi, memotong pola (pattern making), dan menjahit. Anda akan belajar fesyen digital (CAD) dan strategi jenama. Kemuncak kursus adalah Pertunjukan Fesyen Akhir di mana koleksi anda diperagakan di pentas.",
        "jobs": ["Pereka Fesyen (Fashion Designer)", "Fashion Buyer", "Pereka Kostum", "Usahawan Fesyen"]
    },

    # --- GRAPHIC DESIGN ---
    "POLY-DIP-054": {
        "headline": "🎨 Reka Bentuk Grafik: Komunikasi Visual",
        "synopsis": "Di zaman Instagram dan TikTok, visual adalah raja. Anda belajar menggunakan Photoshop, Illustrator, dan InDesign untuk mencipta logo, poster, dan grafik media sosial. Anda dilatih berfikir secara kreatif untuk menyelesaikan masalah komunikasi jenama. Skill ini laku keras sebagai Freelancer!",
        "jobs": ["Pereka Grafik", "Content Creator", "Illustrator", "Art Director"]
    },

    # --- INDUSTRIAL DESIGN ---
    "POLY-DIP-055": {
        "headline": "🛋️ Reka Bentuk Industri: Cipta Produk Masa Depan",
        "synopsis": "Gabungan Seni + Kejuruteraan. Anda belajar mereka bentuk perabot, gajet elektronik, atau peralatan dapur supaya nampak cantik DAN berfungsi dengan baik. Anda akan menggunakan printer 3D dan perisian modelling canggih. Anda adalah pencipta yang menjadikan hidup manusia lebih mudah dan bergaya.",
        "jobs": ["Pereka Produk (Product Designer)", "Pereka Perabot", "Pereka Pembungkusan", "Model Maker 3D"]
    },

    # --- SECRETARIAL SCIENCE ---
    "POLY-DIP-056": {
        "headline": "u0025D8u0025A5 Sains Kesetiausahaan: Pengurusan Pejabat Profesional",
        "synopsis": "Setiausaha moden adalah 'Gatekeeper' kepada CEO. Anda belajar mengurus jadual bos, menulis surat rasmi korporat, dan menganjurkan mesyuarat protokol tinggi. Kursus ini melatih anda menjadi sangat teratur, cekap, dan berimej korporat. Anda adalah orang kanan yang paling dipercayai dalam ofis.",
        "jobs": ["Setiausaha Eksekutif (PA)", "Pengurus Pejabat", "Penyelaras Acara", "Pegawai Tadbir"]
    },

    # --- ARCHITECTURE ---
    "POLY-DIP-057": {
        "headline": "🏛️ Seni Bina (Architecture): Arkitek Masa Depan",
        "synopsis": "Sebelum bangunan dibina, ia bermula dalam imaginasi anda. Anda belajar melukis pelan bangunan, membina model skala, dan menggunakan perisian BIM 3D. Anda menggabungkan seni (kecantikan) dengan sains (kekuatan struktur). Ini langkah pertama untuk menjadi Arkitek berdaftar.",
        "jobs": ["Pembantu Teknik Seni Bina", "Penyelia Tapak", "Pelukis Pelan 3D", "Penyelaras Projek"]
    },

    # --- CULINARY ARTS ---
    "POLY-DIP-058": {
        "headline": "👨‍🍳 Seni Kulinari: Master Chef",
        "synopsis": "Dapur profesional bukan tempat main-main. Anda dilatih disiplin ketat ala tentera untuk menghasilkan hidangan bertaraf 5 bintang. Anda belajar masakan Barat, Asia, Pastri, dan pengurusan kos restoran. Latihan industri di hotel terkemuka akan menguji ketahanan mental dan fizikal anda.",
        "jobs": ["Chef (Commis/Demi)", "Pengurus Katering", "Food Stylist", "Usahawan Restoran"]
    },

    # --- NAVAL ARCHITECTURE ---
    "POLY-DIP-059": {
        "headline": "⚓ Seni Bina Kapal: Reka Bentuk Marin",
        "synopsis": "Ini bukan Arkitek bangunan, ini Arkitek Kapal! Anda belajar mereka bentuk bentuk badan kapal (hull) supaya ia laju dan stabil di laut. Anda belajar tentang hidrodinamik dan kestabilan apungan. Graduan kursus ini bekerja di limbungan kapal (shipyard) untuk membina kapal perang, feri, atau kapal kargo.",
        "jobs": ["Arkitek Kapal (Naval Architect)", "Penyelia Pembinaan Kapal", "Juruukur Kapal (Marine Surveyor)", "Superintendent"]
    },

    # --- BUSINESS INFORMATION SYSTEMS ---
    "POLY-DIP-060": {
        "headline": "💻 Sistem Maklumat Perniagaan: IT + Bisnes",
        "synopsis": "Jambatan antara 'Orang IT' dan 'Orang Bisnes'. Anda faham coding (SQL/Database), tapi anda juga faham Akaun dan Marketing. Tugas anda adalah membina sistem komputer yang membantu syarikat buat duit. Contohnya: Membina sistem stok untuk kedai runcit atau aplikasi jualan.",
        "jobs": ["Penganalisis Sistem (System Analyst)", "Pembangun Pangkalan Data", "Penganalisis Perniagaan", "Usahawan E-Dagang"]
    },

    # --- AQUACULTURE ---
    "POLY-DIP-061": {
        "headline": "🐟 Akuakultur: Jutawan Ikan",
        "synopsis": "Industri makanan masa depan bukan di laut, tapi di kolam. Anda belajar menternak ikan, udang, dan rumpai laut secara komersial. Dari pembenihan (breeding) hingga tuaian, anda diajar teknik moden untuk hasil maksimum. Ramai graduan kursus ini menjadi usahawan ternakan yang berjaya.",
        "jobs": ["Pengurus Ladang Akuakultur", "Juruteknik Penetasan (Hatchery)", "Usahawan Ternakan", "Penolong Pegawai Perikanan"]
    },

    # --- WOOD-BASED TECHNOLOGY ---
    "POLY-DIP-062": {
        "headline": "🌲 Teknologi Kayu: Seni & Kejuruteraan",
        "synopsis": "Malaysia adalah pengeksport perabot utama dunia. Anda belajar sifat kayu, teknologi pemprosesan, dan pembuatan perabot moden. Anda akan menggunakan mesin canggih untuk menukar balak mentah menjadi produk bernilai tinggi. Kerjaya yang stabil dalam industri perkayuan negara.",
        "jobs": ["Pereka Perabot", "Penyelia Kilang Kayu", "Juruteknik Penggred Kayu", "Pegawai Kawalan Kualiti"]
    },

    # --- LANDSCAPE HORTICULTURE ---
    "POLY-DIP-063": {
        "headline": "🌳 Landskap: Senibina Alam",
        "synopsis": "Jadikan bandar kita 'Taman dalam Bandar'. Anda belajar mereka bentuk taman, memilih pokok yang sesuai, dan teknologi penyelenggaraan landskap. Anda menggabungkan ilmu botani (pokok) dengan seni reka bentuk. Projek anda boleh jadi taman perumahan, padang golf, atau resort.",
        "jobs": ["Pereka Landskap", "Kontraktor Landskap", "Penyelia Nurseri", "Pengurus Padang Golf"]
    },

    # --- MARINE ELECTRICAL ---
    "POLY-DIP-064": {
        "headline": "⚡ Elektrik Marin: Kuasa di Lautan",
        "synopsis": "Kapal moden adalah 'bandar terapung' yang perlukan kuasa elektrik 24 jam. Anda belajar menyelenggara generator kapal, sistem radar, dan automasi marin. Graduan kursus ini layak menjadi Pegawai Elektro-Teknikal (ETO) di atas kapal dagang dengan gaji lumayan.",
        "jobs": ["Pegawai Elektro-Teknikal (ETO)", "Juruteknik Elektrik Marin", "Juruteknik Offshore", "Penyelia Limbungan"]
    },

    # --- MARINE CONSTRUCTION ---
    "POLY-DIP-065": {
        "headline": "🏗️ Pembinaan Marin: Membina Gergasi Laut",
        "synopsis": "Bagaimana besi berat boleh terapung? Anda belajar membina dan membaiki struktur kapal di limbungan (dry dock). Anda akan mahir dalam kimpalan marin, pemasangan paip kapal, dan struktur terapung. Kerjaya 'hands-on' yang mencabar di pelabuhan dan limbungan kapal.",
        "jobs": ["Penyelia Limbungan (Shipwright)", "Perancang Projek Marin", "QA/QC Inspector", "Juruteknik Kimpalan Marin"]
    },

    # --- CHEMICAL TECHNOLOGY (FAT & OIL) ---
    "POLY-DIP-066": {
        "headline": "palmoil🌴 Teknologi Minyak & Lemak: Emas Sawit",
        "synopsis": "Malaysia adalah raja minyak sawit dunia. Kursus unik ini mengajar anda kimia di sebalik minyak masak, sabun, dan kosmetik. Anda akan bekerja di makmal atau kilang oleokimia untuk memastikan produk sawit kita berkualiti tinggi dan selamat digunakan.",
        "jobs": ["Juruteknik Makmal Kimia", "Penyelia Kilang Oleokimia", "QA/QC Makanan", "Penolong Pegawai Penyelidik"]
    },

    # --- DIGITAL ANIMATION ---
    "POLY-DIP-067": {
        "headline": "🎬 Animasi Digital: Hidupkan Imaginasi",
        "synopsis": "Minat anime atau filem Pixar? Belajar buat sendiri! Anda akan diajar melukis watak, membina model 3D, dan teknik pergerakan (animation). Anda bakal menjadi sebahagian daripada industri kreatif yang menghasilkan siri TV, filem, dan iklan gempak.",
        "jobs": ["Animator 2D/3D", "Character Designer", "Storyboard Artist", "VFX Artist"]
    },

    # --- VIDEO PRODUCTION ---
    "POLY-DIP-068": {
        "headline": "🎥 Produksi Video: Di Sebalik Tabir",
        "synopsis": "Lampu, Kamera, Action! Anda belajar teknik penggambaran, penulisan skrip, dan suntingan video (editing). Anda akan hasilkan filem pendek, dokumentari, dan video muzik anda sendiri. Sesuai untuk anda yang mahu jadi Youtuber profesional atau krew filem.",
        "jobs": ["Videographer", "Video Editor", "Penolong Pengarah", "Penerbit Kandungan (Content Creator)"]
    },

    # --- DIGITAL ART ---
    "POLY-DIP-069": {
        "headline": "🎨 Seni Digital: Multimedia Kreatif",
        "synopsis": "Kursus paling luas dalam bidang kreatif. Anda belajar ilustrasi digital, kesan visual (VFX), dan reka bentuk konsep (Concept Art). Kemahiran ini laku keras dalam industri game, filem, dan pengiklanan. Anda adalah seniman moden yang melukis menggunakan tablet, bukan berus.",
        "jobs": ["Concept Artist", "Illustrator Digital", "Motion Graphic Designer", "Multimedia Artist"]
    },

    # --- FOOD TECHNOLOGY ---
    "POLY-DIP-070": {
        "headline": "🍔 Teknologi Makanan: Sains Di Sebalik Makanan",
        "synopsis": "Bagaimana makanan dalam tin tahan lama? Bagaimana buat burger daging tanpa daging? Anda belajar sains pemprosesan, pengawetan, dan pembungkusan makanan. Anda memastikan makanan yang kita beli di pasar raya adalah selamat, sedap, dan berkualiti.",
        "jobs": ["Juruteknik Teknologi Makanan", "Pegawai Kawalan Kualiti (QA)", "Penyelia Kilang Makanan", "Eksekutif R&D Makanan"]
    },

    # --- HALAL FOOD TECHNOLOGY ---
    "POLY-DIP-071": {
        "headline": "🥗 Teknologi Makanan (Pengurusan Halal)",
        "synopsis": "Industri Halal bukan sekadar 'No Pork'. Ia tentang sains kebersihan, keselamatan, dan pematuhan syariah yang ketat. Anda belajar sains pemprosesan makanan DAN undang-undang Halal JAKIM. Graduan kursus ini mendapat Sijil Eksekutif Halal—lesen mahal yang membolehkan anda menjadi Auditor Halal bertauliah.",
        "jobs": ["Eksekutif Halal", "Auditor Halal", "Pegawai Kawalan Kualiti (QA)", "Penyelia Pengeluaran Makanan"]
    },

    # --- IT: SOFTWARE & APPS ---
    "POLY-DIP-072": {
        "headline": "📱 IT (Software & App Development): Pembangun Aplikasi",
        "synopsis": "Anda ada idea untuk 'Grab' atau 'TikTok' seterusnya? Kursus ini mengajar anda membina perisian dari kosong. Anda belajar coding (Java, Python, C++), mereka bentuk antaramuka (UI/UX), dan membangunkan aplikasi Mobile (Android/iOS). Anda adalah arkitek dunia digital.",
        "jobs": ["App Developer (Android/iOS)", "Software Engineer", "Full Stack Developer", "UI/UX Designer"]
    },

    # --- IT: NETWORKING ---
    "POLY-DIP-073": {
        "headline": "🌐 IT (Networking System): Jurutera Internet",
        "synopsis": "Tanpa anda, Netflix takkan loading. Anda belajar membina dan menjaga infrastruktur internet. Anda akan 'configure' router, switch, dan server. Anda adalah wira di sebalik tabir yang memastikan Wi-Fi laju, server tak 'down', dan data mengalir lancar di seluruh dunia.",
        "jobs": ["Network Engineer", "System Administrator", "Cloud Specialist", "IT Support Executive"]
    },

    # --- IT: INFORMATION SECURITY ---
    "POLY-DIP-074": {
        "headline": "🔐 IT (Information Security): Cyber Warrior",
        "synopsis": "Dunia siber penuh dengan hacker dan scammer. Tugas anda adalah menghalang mereka. Anda belajar tentang 'Ethical Hacking', penyulitan data (Encryption), dan forensik digital. Anda adalah polis siber yang melindungi data sulit bank, kerajaan, dan syarikat besar.",
        "jobs": ["Cybersecurity Analyst", "Penetration Tester (Ethical Hacker)", "Pegawai Keselamatan IT", "Forensik Digital"]
    },

    # --- IT: GAME PROGRAMMING ---
    "POLY-DIP-075": {
        "headline": "🎮 IT (Game Programming): Cipta Dunia Maya",
        "synopsis": "Jangan hanya main game, buat game sendiri! Anda belajar enjin permainan (Unity/Unreal), logik AI untuk musuh dalam game, dan fizik permainan. Kursus ini menggabungkan matematik, seni, dan coding. Sesuai untuk gamers yang mahu menukar hobi menjadi kerjaya profesional.",
        "jobs": ["Game Programmer", "Game Designer", "Level Designer", "VR/AR Developer"]
    },

    # --- IT: WEB DEVELOPMENT ---
    "POLY-DIP-076": {
        "headline": "💻 IT (Web Development): Arkitek Web",
        "synopsis": "Laman web adalah wajah syarikat. Anda belajar membina website yang cantik, pantas, dan selamat. Anda akan menguasai HTML, CSS, JavaScript, dan pangkalan data. Dari laman E-Commerce (Shopee) hingga portal korporat, anda yang membinanya.",
        "jobs": ["Web Developer", "Frontend Developer", "Backend Developer", "E-Commerce Specialist"]
    },

    # --- IT: DATA MANAGEMENT ---
    "POLY-DIP-077": {
        "headline": "📊 IT (Data Management): Saintis Data",
        "synopsis": "Data adalah minyak baharu. Syarikat perlukan orang yang pandai membaca trend dari data lambak (Big Data). Anda belajar mengumpul, menyusun, dan memvisualisasikan data menjadi graf yang bermakna. Skill ini sangat penting untuk syarikat membuat keputusan bisnes.",
        "jobs": ["Data Analyst", "Database Administrator", "Business Intelligence Analyst", "Data Scientist Junior"]
    },

    # --- PRINT MEDIA TECHNOLOGY ---
    "POLY-DIP-078": {
        "headline": "🖨️ Teknologi Media Cetak: Lebih Dari Kertas",
        "synopsis": "Percetakan belum mati, ia berevolusi. Anda belajar teknologi percetakan digital, pembungkusan (packaging), dan penerbitan buku. Anda akan mahir mengendalikan mesin cetak industri dan perisian desktop publishing. Industri ini kritikal untuk pengiklanan dan pembungkusan produk.",
        "jobs": ["Penyelia Percetakan", "Graphic Pre-press Artist", "Pakar Pembungkusan", "Usahawan Percetakan"]
    },

    # --- QUANTITY SURVEYING ---
    "POLY-DIP-079": {
        "headline": "📋 Ukur Bahan (QS): Akauntan Binaan",
        "synopsis": "Dalam pembinaan, setiap bata ada harganya. Tugas QS adalah mengira kos projek dari awal sampai siap. Anda memastikan projek tidak lari bajet, mengurus kontrak, dan membayar kontraktor. Kerjaya ini sangat profesional dan bergaji lumayan di firma pembinaan.",
        "jobs": ["Juruukur Bahan (Quantity Surveyor)", "Contract Executive", "Penyelia Projek", "Estimator"]
    },

    # --- BATIK FASHION DESIGN ---
    "POLY-DIP-080": {
        "headline": "👘 Reka Bentuk Fesyen Batik: Warisan Glamor",
        "synopsis": "Gabungan tradisi dan fesyen moden. Anda belajar teknik mencanting batik asli DAN reka bentuk fesyen kontemporari. Anda bukan sekadar melukis kain, anda mencipta busana 'Haute Couture' berasaskan warisan negara. Sesuai untuk mereka yang berjiwa seni halus.",
        "jobs": ["Pereka Fesyen Batik", "Usahawan Tekstil", "Pereka Kostum", "Pengajar Seni Kraf"]
    },

    # --- CRAFT DESIGN ---
    "POLY-DIP-081": {
        "headline": "🪑 Reka Bentuk Kraf: Perabot & Seni",
        "synopsis": "Gabungan seni tangan tradisional dengan teknologi moden (CNC Machining). Anda belajar mereka bentuk perabot, ukiran kayu, dan produk kraf komersial. Anda bukan sekadar tukang kayu, tetapi pereka yang menghasilkan produk bernilai tinggi untuk pasaran eksport dan hiasan dalaman.",
        "jobs": ["Pereka Perabot", "Usahawan Kraf", "Operator Mesin CNC Kayu", "Pereka Hiasan Dalaman"]
    },

    # --- LOGISTICS (ADDITIONAL) ---
    "POLY-DIP-082": {
        "headline": "🚚 Pengurusan Logistik: Pakar Penghantaran",
        "synopsis": "Dalam dunia E-Dagang, barang perlu bergerak laju. Kursus ini melatih anda menguruskan pergerakan barang dari kilang ke pengguna. Anda belajar tentang gudang, pengangkutan antarabangsa, dan inventori. Kemahiran ini sangat penting untuk memastikan ekonomi negara berjalan lancar.",
        "jobs": ["Pegawai Logistik", "Penyelia Gudang", "Eksekutif Rantaian Bekalan", "Ejen Kargo"]
    },

    # --- CERTIFICATE LEVEL (SIJIL) ---
    "POLY-CET-001": {
        "headline": "👷 Sijil Kejuruteraan Awam: Langkah Mula Binaan",
        "synopsis": "Laluan pantas ke tapak binaan. Anda belajar asas penting: bancuhan konkrit, kerja paip, dan penyeliaan tapak. Sijil ini membolehkan anda terus bekerja sebagai penyelia junior, ATAU sambung belajar ke peringkat Diploma (hanya 2 tahun lagi) untuk kerjaya lebih tinggi.",
        "jobs": ["Penyelia Tapak Junior", "Kontraktor Kecil", "Draughtsman (Pelukis Pelan)", "Usahawan Binaan"]
    },
    "POLY-CET-002": {
        "headline": "⚡ Sijil Kejuruteraan Elektrik: Pakar Wiring",
        "synopsis": "Fokus 100% pada kemahiran tangan. Anda akan mahir membuat pendawaian (wiring) rumah dan pejabat, membaiki kerosakan litar, dan penyelenggaraan asas. Lulusan kursus ini sangat laku sebagai juruteknik mahir, atau boleh terus sambung Diploma untuk menjadi pakar yang lebih besar.",
        "jobs": ["Juruteknik Wiring (Wireman)", "Juruteknik Penyelenggaraan", "Usahawan Elektrik", "Pembantu Teknikal"]
    },
    "POLY-CET-003": {
        "headline": "⚙️ Sijil Kejuruteraan Mekanikal: Mahir Mesin",
        "synopsis": "Anda suka kerja tangan? Kursus ini mengajar anda menggunakan mesin bengkel (welding, memesin) dan melukis pelan CAD asas. Ia adalah asas kukuh untuk menjadi juruteknik kilang yang cekap. Selepas tamat, anda boleh terus bekerja atau naik taraf ke Diploma Kejuruteraan Mekanikal.",
        "jobs": ["Juruteknik Kilang", "Operator Mesin", "Welder (Pengimpal)", "Pembantu Jurutera"]
    },

    # ==========================================
    # KOLEJ KOMUNITI - DIPLOMA COURSES
    # ==========================================

    # --- HAIR DESIGN ---
    "KKOM-DIP-001": {
        "headline": "✂️ Dandanan Rambut: Stylist Profesional",
        "synopsis": "Bukan sekadar potong rambut. Anda belajar kimia pewarna rambut, rawatan kulit kepala, dan pengurusan salun. Kemahiran ini 'kalis kemelesetan'—orang sentiasa perlu gunting rambut. Sesuai untuk anda yang kreatif, suka berfesyen, dan bercita-cita buka kedai sendiri.",
        "jobs": ["Hairstylist Profesional", "Usahawan Salun", "Perunding Imej", "Jurulatih Dandanan"],
        "pathway": "Ijazah Sarjana Muda Seni Kreatif / Pengurusan Perniagaan"
    },

    # --- 3D ANIMATION ---
    "KKOM-DIP-002": {
        "headline": "🎬 Animasi 3D: Hidupkan Karakter",
        "synopsis": "Minat filem Pixar atau game 3D? Belajar cara buat karakter bergerak, ekspresi muka, dan kesan visual (VFX). Kursus ini fokus kepada skil teknikal menggunakan software canggih. Anda akan hasilkan portfolio 'showreel' anda sendiri untuk tunjuk pada majikan.",
        "jobs": ["3D Animator", "3D Modeller", "Game Artist", "Texture Artist"],
        "pathway": "Ijazah Sarjana Muda Animasi / Multimedia Kreatif"
    },

    # --- ARCHITECTURAL TECHNOLOGY ---
    "KKOM-DIP-003": {
        "headline": "🏢 Teknologi Seni Bina: Pelukis Pelan Digital",
        "synopsis": "Anda bukan Arkitek, tapi andalah orang kanan Arkitek. Anda belajar menggunakan perisian BIM (Building Information Modelling) untuk melukis bangunan dalam 3D. Industri pembinaan sekarang Wajib guna BIM, jadi graduan kursus ini sangat laku keras.",
        "jobs": ["BIM Modeller", "Pembantu Teknikal Seni Bina", "Pelukis Pelan (Draughtsman)", "Penyelaras BIM"],
        "pathway": "Ijazah Sarjana Muda Sains Seni Bina / Ukur Bahan"
    },

    # --- CULINARY ARTS ---
    "KKOM-DIP-004": {
        "headline": "🍳 Seni Kulinari: Chef Muda",
        "synopsis": "Belajar masak sambil bekerja! Program ini unik kerana ada 'Work Based Learning'—anda akan bekerja di hotel sebenar selama 8 bulan. Anda belajar masakan Barat, Asia, dan pengurusan dapur. Ini jalan pantas untuk jadi Chef tanpa perlu bayar yuran kolej swasta yang mahal.",
        "jobs": ["Commis Chef", "Katerer", "Penyelia F&B", "Usahawan Makanan"],
        "pathway": "Ijazah Sarjana Muda Seni Kulinari / Pengurusan Hotel"
    },

    # --- ELECTRONICS (INSTRUMENTATION) ---
    "KKOM-DIP-005": {
        "headline": "🎛️ Elektronik (Instrumentasi): Pakar Sensor Kilang",
        "synopsis": "Kilang moden penuh dengan sensor dan robot. Siapa yang pastikan sensor tu tepat? Anda! Kursus ini mengajar anda membaiki, menentukur (calibrate), dan menyelenggara alat elektronik di kilang. Kerja ini sangat spesifik dan bergaji tinggi dalam sektor pembuatan.",
        "jobs": ["Juruteknik Instrumentasi", "Juruteknik Penyelenggaraan", "Penyelia Kilang", "Usahawan Teknikal"],
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektrik / Elektronik"
    },

    # --- GAMES ART ---
    "KKOM-DIP-006": {
        "headline": "🎮 Games Art: Reka Dunia Video Game",
        "synopsis": "Khas untuk 'Gamers'. Anda belajar mereka bentuk senjata, raksasa, kenderaan, dan latar belakang (environment) untuk video game. Anda akan guna 'Game Engine' sebenar. Jangan sekadar main game, jadilah orang yang menciptanya.",
        "jobs": ["Game Artist", "Concept Artist", "Level Designer", "3D Modeller"],
        "pathway": "Ijazah Sarjana Muda Pembangunan Permainan / Multimedia"
    },

    # --- HOTEL MANAGEMENT ---
    "KKOM-DIP-007": {
        "headline": "🏨 Pengurusan Hotel: Kerjaya Hospitaliti",
        "synopsis": "Masuk terus ke industri perhotelan. Anda belajar mengurus tetamu di Front Office, menjaga kebersihan Housekeeping, dan menyelia restoran. Program ini ada latihan industri panjang (WBL), jadi anda tamat belajar dengan pengalaman kerja sebenar.",
        "jobs": ["Penyelia Hotel", "Front Office Assistant", "Housekeeping Supervisor", "Penyelia Restoran"],
        "pathway": "Ijazah Sarjana Muda Pengurusan Hotel / Pelancongan"
    },

    # --- MECHANICAL DESIGN ---
    "KKOM-DIP-008": {
        "headline": "📐 Reka Bentuk Mekanikal: Lukis Paip & Mesin",
        "synopsis": "Fokus kepada lukisan teknikal untuk industri Minyak & Gas serta Kilang. Anda belajar software CAD untuk melukis sistem paip (Piping) dan komponen mesin. Skill ini sangat penting untuk syarikat kejuruteraan yang membina loji atau mesin.",
        "jobs": ["Piping Designer", "Mechanical Draughtsman", "Pembantu Jurutera", "Penyelia Tapak"],
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Mekanikal / Pembuatan"
    },

    # --- MOBILE TECHNOLOGY ---
    "KKOM-DIP-009": {
        "headline": "📱 Teknologi Mudah Alih: Doktor Telefon & Apps",
        "synopsis": "Telefon rosak? Skrin pecah? Anda akan jadi pakar membaiki (repair) telefon pintar dan tablet. Selain hardware, anda juga belajar asas buat Apps dan UI/UX design. Sangat sesuai kalau anda nak buka kedai repair phone sendiri satu hari nanti.",
        "jobs": ["Juruteknik Telefon Bimbit", "Usahawan Gajet", "Junior App Developer", "Technical Support"],
        "pathway": "Ijazah Sarjana Muda Elektronik / Telekomunikasi"
    },

    # --- PATISSERIE ---
    "KKOM-DIP-010": {
        "headline": "🍰 Pastri: Seni Kek & Roti",
        "synopsis": "Khas untuk yang teliti dan berseni. Anda fokus sepenuhnya kepada pembuatan roti, kek, coklat, dan hiasan gula (sugar art). Anda akan berlatih di dapur industri dan hotel. Skill ini laku keras untuk kerja hotel atau jual kek dari rumah (Home Baker).",
        "jobs": ["Pastry Chef", "Baker", "Chocolatier", "Usahawan Bakeri"],
        "pathway": "Ijazah Sarjana Muda Seni Kulinari / Pengurusan Perkhidmatan Makanan"
    },

    # --- RAIL SIGNALLING ---
    "KKOM-DIP-011": {
        "headline": "🚄 Teknologi Rel: Kerjaya di Landasan",
        "synopsis": "Industri kereta api negara (MRT, LRT, ECRL) sedang berkembang pesat. Siapa yang pastikan tren tidak berlanggar? Anda! Kursus ini mengajar sistem isyarat (signalling) dan komunikasi keretapi. Sangat spesifik dan sangat diperlukan oleh syarikat seperti RapidKL dan KTMB.",
        "jobs": ["Juruteknik Rel", "Penyelia Isyarat Tren", "Juruteknik Komunikasi Tren"],
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektrik / Pengangkutan"
    },

    # --- SOUND & LIGHTING ---
    "KKOM-DIP-012": {
        "headline": "lighting💡 Bunyi & Cahaya: Krew Konsert Profesional",
        "synopsis": "Impian bekerja di balik tabir konsert atau rancangan TV? Kursus ini mengajar anda 'setup' sistem bunyi (PA system) dan lampu pentas yang canggih. Anda akan belajar tentang akustik, pendawaian pentas, dan kesan khas. Suasana kerja yang seronok dan tidak membosankan.",
        "jobs": ["Juruteknik Bunyi (Sound Man)", "Juruteknik Lampu", "Krew Pentas", "AV Technician"],
        "pathway": "Ijazah Sarjana Muda Penyiaran / Kejuruteraan Audio"
    },

    # --- TELECOMMUNICATION ---
    "KKOM-DIP-013": {
        "headline": "📡 Telekomunikasi: Wira 5G & Internet",
        "synopsis": "Dunia tak boleh hidup tanpa internet. Anda belajar cara memasang kabel Fiber Optik, menyelenggara menara telekomunikasi, dan sistem rangkaian tanpa wayar. Kerjaya ini menjanjikan masa depan cerah kerana teknologi 5G sedang meletup sekarang.",
        "jobs": ["Juruteknik Fiber Optik", "Juruteknik Telekomunikasi", "Penyelia Tapak Telco"],
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektronik / Komunikasi"
    },

    # --- COMMERCIAL VEHICLE ---
    "KKOM-DIP-014": {
        "headline": "🚛 Kenderaan Perdagangan: Doktor Lori & Bas",
        "synopsis": "Jangan jadi mekanik kereta biasa. Jadilah pakar kenderaan berat! Enjin diesel, sistem brek angin, dan hidraulik lori memerlukan kepakaran khas. Gaji mekanik kenderaan berat selalunya lebih lumayan kerana industri logistik sangat bergantung kepada anda.",
        "jobs": ["Mekanik Diesel", "Juruteknik Bas/Lori", "Penyelia Bengkel Kenderaan Berat"],
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Mekanikal / Automotif"
    },

    # --- SOLAR PHOTOVOLTAIC ---
    "KKOM-DIP-015": {
        "headline": "☀️ Teknologi Solar: Tenaga Hijau",
        "synopsis": "Jadilah sebahagian daripada revolusi tenaga hijau. Anda belajar cara memasang panel solar di bumbung rumah dan bangunan, serta membuat pendawaian sistem solar (PV). Malaysia panas sepanjang tahun, jadi industri ini memang lubuk duit bagi mereka yang mahir.",
        "jobs": ["Pemasang Solar (PV Installer)", "Juruteknik Solar", "Usahawan Tenaga Hijau"],
        "pathway": "Ijazah Sarjana Muda Kejuruteraan Elektrik / Tenaga Boleh Baharu"
    },

    # --- BEAUTY THERAPY ---
    "KKOM-DIP-016": {
        "headline": "💅 Terapi Kecantikan: Pakar Spa & Estetik",
        "synopsis": "Kecantikan adalah bisnes besar. Anda belajar teknik rawatan muka (facial), spa tangan/kaki, dan seni solekan (makeup). Kursus ini juga mengajar anda cara menguruskan kedai spa. Sangat sesuai jika anda bercita-cita membuka spa atau menjadi jurusolek profesional.",
        "jobs": ["Juruterapi Spa", "Make-up Artist (MUA)", "Perunding Kecantikan", "Pengurus Spa"],
        "pathway": "Ijazah Sarjana Muda Pengurusan Pelancongan / Kesejahteraan (Wellness)"
    },

    # ==========================================
    # KOLEJ KOMUNITI - CERTIFICATE (SIJIL)
    # ==========================================

    # --- CULINARY (CERT) ---
    "KKOM-CET-001": {
        "headline": "👨‍🍳 Sijil Kulinari: Langkah Mula Chef",
        "synopsis": "Kursus pantas untuk masuk ke dapur profesional. Belajar asas memotong, memasak lauk Barat & Asia, dan disiplin dapur. Tamat belajar boleh terus kerja hotel, atau sambung Diploma untuk gaji lebih besar.",
        "jobs": ["Pembantu Dapur (Commis)", "Tukang Masak"],
        "pathway": "Diploma Seni Kulinari / Pengurusan Hotel (Politeknik/KK)"
    },

    # --- F&B SERVICE (CERT) ---
    "KKOM-CET-002": {
        "headline": "☕ Sijil Servis Makanan & Minuman: Profesional F&B",
        "synopsis": "Menjadi pelayan (waiter) profesional bukan sekadar hantar makanan. Anda belajar seni hidangan 'Fine Dining', bancuhan air (Barista), dan layanan tetamu VIP. Hotel 5 bintang sentiasa mencari staf yang terlatih sebegini.",
        "jobs": ["Pramusaji (Waiter)", "Barista", "Krew Bankuet"],
        "pathway": "Diploma Pengurusan Hotel / Pelancongan (Politeknik/KK)"
    },

    # --- RECREATIONAL TOURISM (CERT) ---
    "KKOM-CET-003": {
        "headline": "rafting🚣 Sijil Pelancongan Rekreasi: Kerjaya Outdoor",
        "synopsis": "Suka aktiviti lasak? Kursus ini ajar anda jadi jurupandu (guide) untuk aktiviti seperti hiking, water rafting, dan kem rekreasi. Belajar teknik keselamatan (First Aid) dan cara melayan pelancong. Kerja sambil main!",
        "jobs": ["Pembantu Jurupandu Arah", "Krew Taman Tema", "Renjer Hutan"],
        "pathway": "Diploma Pelancongan Rekreasi / Pengurusan Acara (Politeknik/KK)"
    },

    # --- AGROTECHNOLOGY (CERT) ---
    "KKOM-CET-004": {
        "headline": "🌱 Sijil Agroteknologi: Asas Pertanian",
        "synopsis": "Belajar cara tanam pokok, buat baja, dan urus tapak semaian (nursery). Kursus ini 100% praktikal di ladang. Sesuai untuk anda yang suka berbudi pada tanah atau nak tolong usahakan tanah keluarga.",
        "jobs": ["Pembantu Ladang", "Penyelia Nurseri", "Usahawan Tani Kecil"],
        "pathway": "Diploma Agroteknologi / Hortikultur Landskap (Politeknik)"
    },
    
    # --- 2D ANIMATION (CERT) ---
    "KKOM-CET-005": {
        "headline": "🎬 Sijil Animasi 2D: Kartun & Grafik",
        "synopsis": "Minat melukis anime atau kartun? Kursus ini ajar anda asas animasi 2D—dari lukisan tangan hingga digital. Anda akan belajar buat watak (Character Design) dan Papan Cerita (Storyboard). Langkah pertama untuk kerja di studio animasi Malaysia yang sedang naik.",
        "jobs": ["2D Animator", "Storyboard Artist", "Illustrator"],
        "pathway": "Diploma Rekabentuk Grafik / Animasi (WBL)"
    },

    # --- 3D ANIMATION (CERT) ---
    "KKOM-CET-006": {
        "headline": "🧊 Sijil Animasi 3D: Dunia Maya",
        "synopsis": "Belajar buat model 3D menggunakan komputer. Anda akan cipta watak, kenderaan, dan bangunan dalam bentuk 3D. Kursus ini fokus kepada teknikal—modelling, texturing, dan rendering. Sesuai untuk gamers yang nak tahu macam mana game dibuat.",
        "jobs": ["3D Modeller", "Texture Artist", "Junior Animator"],
        "pathway": "Diploma Animasi 3D / Games Art (WBL)"
    },

    # --- HAIR DESIGN (CERT) ---
    "KKOM-CET-007": {
        "headline": "✂️ Sijil Dandanan Rambut: Gunting & Gaya",
        "synopsis": "Kemahiran gunting rambut adalah kemahiran seumur hidup. Anda belajar teknik gunting lelaki & wanita, mewarna, dan kerinting rambut. Kursus ini juga ajar cara buka kedai gunting rambut sendiri. Modal kecil, untung besar!",
        "jobs": ["Hairstylist", "Barber", "Usahawan Salun"],
        "pathway": "Diploma Dandanan Rambut (WBL) / Terapi Kecantikan"
    },

    # --- FASHION & APPAREL (CERT) ---
    "KKOM-CET-008": {
        "headline": "👗 Sijil Fesyen & Pakaian: Jahit Baju Sendiri",
        "synopsis": "Dari lakaran ke baju siap. Anda belajar memotong kain, menjahit baju kurung/kemeja, dan menghias pakaian. Tak perlu beli baju lagi, anda boleh buat sendiri atau ambil tempahan orang. Ramai graduan kursus ini berjaya buka butik atau bisnes jahitan dari rumah.",
        "jobs": ["Tukang Jahit (Tailor)", "Usahawan Fesyen", "Pembantu Pereka"],
        "pathway": "Diploma Reka Bentuk Fesyen"
    },

    # --- CULINARY (CERT) - Same title but different ID from previous batch? ---
    # Check if duplicate. Assuming specific ID:
    "KKOM-CET-009": {
        "headline": "🍳 Sijil Kulinari: Asas Masakan Hotel",
        "synopsis": "Masuk dapur dengan yakin. Anda belajar potong, masak, dan hias makanan ala hotel. Kursus ini merangkumi masakan panas (Hot Kitchen) dan keselamatan makanan. Sangat praktikal untuk anda yang nak kerja restoran atau hotel cepat.",
        "jobs": ["Pembantu Dapur (Commis)", "Tukang Masak"],
        "pathway": "Diploma Seni Kulinari / Pengurusan Hotel"
    },

    # --- LANDSCAPE (CERT) ---
    "KKOM-CET-010": {
        "headline": "🌳 Sijil Landskap: Taman & Bunga",
        "synopsis": "Suka pokok dan alam? Anda belajar cara tanam pokok hiasan, reka bentuk taman mini, dan penjagaan rumput turf. Kerja ini menenangkan dan sentiasa ada permintaan untuk rumah-rumah baru dan projek perbandaran.",
        "jobs": ["Penyelia Nurseri", "Kontraktor Landskap", "Tukang Kebun Profesional"],
        "pathway": "Diploma Teknologi Hortikultur Landskap / Agroteknologi"
    },

    # --- CREATIVE ADVERTISING (CERT) ---
    "KKOM-CET-011": {
        "headline": "📢 Sijil Pengiklanan Multimedia: Design & Iklan",
        "synopsis": "Belajar buat poster iklan, bunting, dan grafik media sosial yang menarik. Anda akan guna software grafik (Photoshop/Illustrator) dan belajar asas fotografi. Skill ini sangat penting untuk semua jenis bisnes yang nak buat marketing.",
        "jobs": ["Pereka Grafik Junior", "Jurufoto Produk", "Pereka Iklan"],
        "pathway": "Diploma Rekabentuk Grafik / Media Cetak"
    },

    # --- HOTEL OPERATIONS (CERT) ---
    "KKOM-CET-012": {
        "headline": "🛎️ Sijil Operasi Perhotelan: Servis Tetamu",
        "synopsis": "Kursus 'All-in-One' untuk kerja hotel. Anda belajar sikit tentang Front Office (Reception), Housekeeping (Kemas Bilik), dan F&B (Hidang Makanan). Ini menjadikan anda pekerja serba boleh yang disukai oleh pengurus hotel.",
        "jobs": ["Front Office Assistant", "Housekeeping Crew", "Pramusaji"],
        "pathway": "Diploma Pengurusan Hotel / Pelancongan"
    },

    # --- PASTRY (CERT) ---
    "KKOM-CET-013": {
        "headline": "🍰 Sijil Pastri: Roti & Kek",
        "synopsis": "Fokus kepada 'Baking'. Belajar buat roti, kek hari jadi, dan biskut raya. Anda akan diajar teknik menghias kek (icing) yang cantik. Ramai graduan kursus ini buat duit dengan menjual kek dari rumah secara online.",
        "jobs": ["Baker", "Pembantu Pastri", "Usahawan Kek (Home Baker)"],
        "pathway": "Diploma Pastri / Seni Kulinari"
    },

    # --- TRAVEL & TOURISM (CERT) ---
    "KKOM-CET-014": {
        "headline": "✈️ Sijil Pengembaraan Pelancongan: Kerja Travel",
        "synopsis": "Nak kerja sambil jalan-jalan? Kursus ini ajar anda jadi Pemandu Pelancong (Tour Guide) dan cara urus tiket/tempahan. Anda belajar bercakap dengan yakin depan orang ramai. Sesuai untuk personaliti yang ceria dan suka jumpa orang.",
        "jobs": ["Pemandu Pelancong (Tour Guide)", "Kerani Agensi Pelancongan", "Krew Lapangan Terbang"],
        "pathway": "Diploma Pengurusan Pelancongan"
    },

    # --- EVENT MANAGEMENT (CERT) ---
    "KKOM-CET-015": {
        "headline": "🎉 Sijil Pengendalian Acara: Krew Majlis",
        "synopsis": "Suka suasana meriah? Belajar cara menguruskan majlis perkahwinan, acara sukan, dan katering. Anda akan diajar protokol, susun atur dewan, dan layanan tetamu. Kerjaya yang seronok dan membolehkan anda jumpa ramai orang baru setiap hari.",
        "jobs": ["Krew Acara (Event Crew)", "Penyelaras Majlis", "Usahawan Katering"],
        "pathway": "Diploma Pengurusan Acara / Pelancongan"
    },

    # --- BUSINESS OPERATIONS (CERT) ---
    "KKOM-CET-016": {
        "headline": "💼 Sijil Pengoperasian Perniagaan: Asas Bisnes",
        "synopsis": "Nak tahu cara jalankan bisnes? Kursus ini ajar anda asas perakaunan, pemasaran, dan pengurusan stok. Sesuai untuk anda yang nak jadi kerani akaun yang cekap ATAU nak buka bisnes sendiri dengan ilmu yang betul.",
        "jobs": ["Kerani Akaun", "Pembantu Jualan", "Usahawan Kecil"],
        "pathway": "Diploma Pengajian Perniagaan / Pemasaran"
    },

    # --- BUILDING MAINTENANCE (CERT) ---
    "KKOM-CET-017": {
        "headline": "🛠️ Sijil Penyelenggaraan Bangunan: Handyman Profesional",
        "synopsis": "Bangunan rosak? Anda yang baiki! Belajar asas paip, elektrik, aircond, dan kimpalan. Anda akan jadi 'Handyman' serba boleh yang sangat diperlukan oleh pejabat, hotel, dan sekolah. Kerja stabil dan gaji lumayan.",
        "jobs": ["Juruteknik Penyelenggaraan", "Tukang Paip/Elektrik", "Kontraktor Kecil"],
        "pathway": "Diploma Kejuruteraan Perkhidmatan Bangunan / Awam"
    },

    # --- CONSTRUCTION SUPERVISION (CERT) ---
    "KKOM-CET-018": {
        "headline": "👷 Sijil Penyeliaan Tapak Bina: Kapten Tapak",
        "synopsis": "Jadilah ketua di tapak binaan. Anda belajar membaca pelan bangunan, menyelia pekerja, dan memastikan keselamatan tapak. Sesuai untuk anda yang suka kerja luar (outdoor) dan berjiwa kepimpinan.",
        "jobs": ["Penyelia Tapak (Site Supervisor)", "Safety Supervisor", "Kontraktor Binaan"],
        "pathway": "Diploma Kejuruteraan Awam / Seni Bina"
    },

    # --- LOGISTICS (CERT) ---
    "KKOM-CET-019": {
        "headline": "📦 Sijil Perkhidmatan Logistik: Urus Kargo",
        "synopsis": "Belajar cara barang bergerak di seluruh dunia. Anda akan diajar mengurus gudang, stok, dan penghantaran lori. Dalam zaman Shopee/Lazada ni, pakar logistik memang laku keras!",
        "jobs": ["Penyelia Gudang", "Kerani Logistik", "Ejen Penghantaran"],
        "pathway": "Diploma Pengurusan Logistik / Perniagaan"
    },

    # --- INTERIOR DESIGN (CERT) ---
    "KKOM-CET-020": {
        "headline": "🛋️ Sijil Rekabentuk Dalaman: Hias Rumah",
        "synopsis": "Minat menghias bilik? Belajar cara susun perabot, pilih warna, dan lukis pelan hiasan dalaman (ID). Anda akan guna komputer untuk buat design 3D. Boleh kerja dengan firma ID atau jadi perunding hiasan bebas.",
        "jobs": ["Pembantu Pereka Dalaman", "Pelukis Pelan ID", "Usahawan Hiasan"],
        "pathway": "Diploma Seni Bina / Rekabentuk Dalaman"
    },

    # --- FURNITURE MAKING (CERT) ---
    "KKOM-CET-021": {
        "headline": "🪑 Sijil Pembuatan Perabot: Tukang Kayu Moden",
        "synopsis": "Gabungan seni pertukangan dan mesin moden. Belajar buat kerusi, meja, dan kabinet dapur yang berkualiti tinggi. Anda juga belajar ukiran kayu. Skill ini sangat mahal harganya dan membolehkan anda buka bengkel perabot sendiri.",
        "jobs": ["Pembuat Perabot", "Tukang Kayu", "Operator Mesin Perabot"],
        "pathway": "Diploma Teknologi Berasaskan Kayu / Reka Bentuk Kraf"
    },

    # --- CREATIVE VISUAL ART (CERT) ---
    "KKOM-CET-022": {
        "headline": "🎨 Sijil Seni Visual Kreatif: Produk Kraf",
        "synopsis": "Buat duit dengan seni. Belajar buat cenderamata, batik, dan seramik yang boleh dijual. Kursus ini fokus kepada keusahawanan seni—bukan sekadar buat cantik, tapi buat yang orang nak beli.",
        "jobs": ["Usahawan Kraf", "Pereka Batik", "Pembuat Cenderamata"],
        "pathway": "Diploma Reka Bentuk Kraf / Fesyen"
    },

    # --- AQUACULTURE (CERT) ---
    "KKOM-CET-023": {
        "headline": "🐟 Sijil Teknologi Akuakultur: Ternak Ikan",
        "synopsis": "Belajar menternak ikan air tawar dan udang. Anda akan diajar teknik pembenihan, penjagaan kolam, dan rawatan penyakit ikan. Industri makanan sentiasa hidup, jadi peluang untuk jadi usahawan ternakan sangat cerah.",
        "jobs": ["Penternak Ikan", "Pembantu Penetasan", "Usahawan Akuakultur"],
        "pathway": "Diploma Teknologi Akuakultur (Politeknik)"
    },

    # --- AUTOMOTIVE (CERT) ---
    "KKOM-CET-024": {
        "headline": "🚗 Sijil Teknologi Automotif: Mekanik Mahir",
        "synopsis": "Kursus wajib untuk 'kaki kereta'. Belajar servis enjin, sistem brek, dan aircond kereta. Anda akan jadi mekanik bertauliah yang boleh kerja di pusat servis Honda/Toyota atau buka bengkel sendiri.",
        "jobs": ["Mekanik Kereta", "Juruteknik Servis", "Usahawan Bengkel"],
        "pathway": "Diploma Kejuruteraan Mekanikal (Automotif)"
    },

    # --- ELECTRICAL TECHNOLOGY (CERT) ---
    "KKOM-CET-025": {
        "headline": "⚡ Sijil Teknologi Elektrik: Asas Pendawaian",
        "synopsis": "Belajar buat wiring rumah dan kilang. Anda akan diajar pasang suis, soket, dan papan agihan (DB). Ini adalah langkah pertama untuk mendapatkan lesen kompetensi PW2/PW4 dari Suruhanjaya Tenaga. Kemahiran wajib ada untuk jadi kontraktor elektrik.",
        "jobs": ["Juruelektrik (Wireman)", "Juruteknik Penyelenggaraan", "Usahawan Elektrik"],
        "pathway": "Diploma Kejuruteraan Elektrik / Elektronik"
    },

    # --- ELECTRICAL INSTALLATION (CERT) - Specific Specialization ---
    "KKOM-CET-026": {
        "headline": "🔌 Sijil Pemasangan Elektrik: Pendawaian Industri",
        "synopsis": "Fokus kepada pendawaian Tiga Fasa (3-Phase) yang digunakan di kilang dan bangunan besar. Anda belajar kawalan motor elektrik dan sistem kuasa industri. Gaji pendawai industri selalunya lebih tinggi daripada pendawai rumah biasa.",
        "jobs": ["Pendawai Elektrik (PW2/PW4)", "Juruteknik Industri", "Penyelia Elektrik"],
        "pathway": "Diploma Kejuruteraan Elektrik (Kuasa/Industri)"
    },

    # --- INFORMATION TECHNOLOGY (CERT) ---
    "KKOM-CET-027": {
        "headline": "💻 Sijil Teknologi Maklumat: Juruteknik IT",
        "synopsis": "Jadilah orang yang semua orang cari bila komputer rosak. Anda belajar format PC, pasang network (LAN), dan asas database. Anda juga diajar asas coding dan keselamatan siber. Kerja stabil di mana-mana ofis atau sekolah.",
        "jobs": ["Juruteknik Komputer", "Helpdesk Support", "Pentadbir Rangkaian Junior"],
        "pathway": "Diploma Teknologi Maklumat / Rangkaian"
    },

    # --- BUILDING CONSTRUCTION (CERT) ---
    "KKOM-CET-028": {
        "headline": "🏗️ Sijil Teknologi Pembinaan: Bina Rumah",
        "synopsis": "Belajar cara bina bangunan dari A sampai Z. Anda akan buat kerja konkrit, ikat bata, dan pasang bumbung. Kursus ini sangat praktikal. Tamat belajar, anda boleh kerja dengan kontraktor besar atau ambil upah ubah suai rumah.",
        "jobs": ["Tukang Rumah", "Penyelia Tapak Junior", "Sub-Kontraktor"],
        "pathway": "Diploma Kejuruteraan Awam / Seni Bina"
    },

    # --- MANUFACTURING TECHNOLOGY (CERT) ---
    "KKOM-CET-029": {
        "headline": "🏭 Sijil Teknologi Pembuatan: Operator Mesin",
        "synopsis": "Kilang perlukan orang yang pandai guna mesin. Anda belajar kendalikan mesin Lathe, Milling, dan CNC. Anda juga belajar baca pelan kejuruteraan. Graduan kursus ini sangat laku di kawasan perindustrian seperti Shah Alam, Penang, dan Johor.",
        "jobs": ["Operator Mesin CNC", "Juruteknik Pembuatan", "Machinist"],
        "pathway": "Diploma Kejuruteraan Mekanikal (Pembuatan)"
    },

    # --- FOOD PROCESSING (CERT) ---
    "KKOM-CET-030": {
        "headline": "🥫 Sijil Pemprosesan Makanan: Kilang Makanan",
        "synopsis": "Belajar cara buat makanan tahan lama (canning, packaging) dan produk sejuk beku. Anda juga belajar tentang kawalan kualiti (QC) dan persijilan Halal. Sesuai untuk anda yang nak kerja di kilang makanan atau buat produk jenama sendiri (IKS).",
        "jobs": ["Operator Pengeluaran Makanan", "Pembantu QC", "Usahawan IKS"],
        "pathway": "Diploma Teknologi Makanan / Halal"
    },

    # --- AIR-CONDITIONING (CERT) ---
    "KKOM-CET-031": {
        "headline": "❄️ Sijil Penyejukan & Penyamanan Udara: Pakar Aircond",
        "synopsis": "Di Malaysia yang panas, tukang aircond tak pernah putus kerja. Anda belajar pasang, servis, dan repair aircond rumah serta sistem chiller bangunan. Modal untuk mula bisnes sendiri sangat rendah, tapi pulangannya lumayan.",
        "jobs": ["Juruteknik Aircond", "Kontraktor HVAC", "Usahawan Servis"],
        "pathway": "Diploma Kejuruteraan Mekanikal (Penyamanan Udara)"
    },

    # --- 4WD MAINTENANCE (CERT) ---
    "KKOM-CET-032": {
        "headline": "🚙 Sijil Penyelenggaraan 4WD: Mekanik Offroad",
        "synopsis": "Bukan kereta biasa, ini kereta pacuan 4 roda (4x4). Anda belajar sistem transmisi 4WD, suspensi lasak, dan enjin diesel turbo. Peminat offroad sanggup bayar mahal untuk mekanik yang faham kereta mereka. Jadilah pakar dalam niche ini.",
        "jobs": ["Mekanik 4x4", "Pakar Suspensi", "Juruteknik Diesel"],
        "pathway": "Diploma Kejuruteraan Mekanikal (Automotif)"
    },

    # --- INDUSTRIAL MAINTENANCE (CERT) ---
    "KKOM-CET-033": {
        "headline": "⚙️ Sijil Penyenggaraan Industri: Doktor Kilang",
        "synopsis": "Mesin kilang tak boleh rosak lama-lama. Anda belajar sistem hidraulik, pneumatik (angin), dan kimpalan asas untuk membaiki mesin. Anda adalah 'doktor' yang memastikan kilang terus beroperasi 24 jam.",
        "jobs": ["Juruteknik Penyelenggaraan", "Juruteknik Hidraulik", "Fitter"],
        "pathway": "Diploma Kejuruteraan Mekanikal / Mekatronik"
    },

    # --- SUPERBIKE MAINTENANCE (CERT) ---
    "KKOM-CET-034": {
        "headline": "🏍️ Sijil Motosikal Berkuasa Tinggi: Mekanik Superbike",
        "synopsis": "Minat motor besar? Belajar servis enjin superbike, setting suspensi, dan sistem suntikan bahan api (fuel injection). Mekanik kapcai biasa tak reti buat ni. Ini adalah kemahiran premium untuk kedai motor eksklusif.",
        "jobs": ["Mekanik Superbike", "Tuner Motor", "Usahawan Bengkel Motor"],
        "pathway": "Diploma Kejuruteraan Mekanikal"
    },

    # --- MOBILE DEVICE TECHNOLOGY (CERT) ---
    "KKOM-CET-035": {
        "headline": "📱 Sijil Teknologi Peranti Mudah Alih: Doktor Telefon",
        "synopsis": "Telefon rosak, skrin pecah, bateri kong? Itu masalah semua orang. Kursus ini ajar anda membaiki (repair) telefon pintar dan tablet. Anda juga belajar asas buat Apps Android. Ini adalah kemahiran 'kalis zaman'—selagi orang guna telefon, anda ada kerja!",
        "jobs": ["Juruteknik Telefon (Phone Repair)", "Usahawan Gajet", "Technical Support"],
        "pathway": "Diploma Mobile Technology / Kejuruteraan Elektronik"
    },

    # --- ARCHITECTURE TECHNOLOGY (CERT) ---
    "KKOM-CET-036": {
        "headline": "🏛️ Sijil Teknologi Senibina: Pelukis Pelan",
        "synopsis": "Minat tengok bangunan cantik? Belajar cara melukis pelan rumah dan bangunan menggunakan komputer (CAD & BIM). Anda juga akan belajar buat model bangunan 3D. Skill ini sangat diperlukan oleh arkitek dan pemaju perumahan.",
        "jobs": ["Pelukis Pelan (Draughtsman)", "BIM Modeller", "Penyelia Tapak"],
        "pathway": "Diploma Seni Bina / Kejuruteraan Awam"
    },

    # --- TELECOMMUNICATION (CERT) ---
    "KKOM-CET-037": {
        "headline": "📡 Sijil Teknologi Telekomunikasi: Wira Internet",
        "synopsis": "Pastikan Malaysia kekal 'online'. Anda belajar cara pasang kabel Fiber Optik, menyelenggara rangkaian internet, dan sistem telekomunikasi. Tanpa juruteknik ini, tiada WiFi dan tiada 5G. Kerja teknikal yang mencabar tapi gajinya berbaloi.",
        "jobs": ["Juruteknik Fiber Optik", "Penyelia Rangkaian", "Juruteknik Telco"],
        "pathway": "Diploma Teknologi Telekomunikasi / Kejuruteraan Elektronik"
    },

    # --- BEAUTY & SPA THERAPY (CERT) ---
    "KKOM-CET-038": {
        "headline": "💅 Sijil Terapi Kecantikan & Spa: Bisnes Cantik",
        "synopsis": "Ubah minat bersolek jadi kerjaya profesional. Belajar teknik rawatan muka (facial), urutan spa, dan solekan pengantin (MUA). Industri kecantikan adalah industri bernilai jutaan ringgit. Ramai graduan kursus ini berjaya buka spa sendiri atau jadi MUA terkenal.",
        "jobs": ["Juruterapi Spa", "Make-up Artist (MUA)", "Usahawan Kecantikan"],
        "pathway": "Diploma Terapi Kecantikan / Pengurusan Perniagaan"
    },

    # ==========================================
    # IKBN - COURSES
    # ==========================================

    # --- ELEKTRIK (CHARGEMAN) ---
    "IKBN-DIP-001": {
        "headline": "⚡ Kuasa Elektrik: Nadi Industri",
        "synopsis": "Bayangkan satu kilang bergelap tanpa anda. Kursus ini melatih anda menjadi 'Chargeman' (Penjaga Jentera)—orang paling penting yang memastikan elektrik berjalan lancar. Lesen A1 yang anda dapat di sini adalah 'pasport emas' untuk gaji lumayan dalam sektor tenaga.",
        "jobs": ["Penjaga Jentera (Chargeman)", "Juruteknik Voltan Tinggi", "Kontraktor Elektrik"]
    },

    # --- HVAC (AIRCOND) ---
    "IKBN-DIP-002": {
        "headline": "❄️ Pakar Penyejukan: Kerjaya Sentiasa 'Cool'",
        "synopsis": "Di Malaysia yang panas, pakar aircond tidak akan pernah hilang kerja. Anda bukan sekadar servis aircond rumah; anda belajar merekabentuk sistem penyejukan gergasi untuk pasar raya dan kilang. Kerjaya teknikal yang sangat stabil dan sentiasa diperlukan.",
        "jobs": ["Pakar HVAC", "Perekabentuk Sistem Penyejukan", "Kontraktor Aircond", "Juruteknik Bangunan"]
    },

    # --- FESYEN ---
    "IKBN-DIP-003": {
        "headline": "👗 Rekaan Fesyen: Dari Lakaran ke 'Runway'",
        "synopsis": "Tukarkan idea kreatif anda menjadi jenama sebenar. Anda belajar segalanya: melakar fesyen, membuat pola, hingga menjahit busana 'Haute Couture'. Jangan sekadar menjahit baju orang, belajar cipta 'trend' dan buka butik jenama anda sendiri.",
        "jobs": ["Pereka Fesyen (Fashion Designer)", "Usahawan Butik", "Pembuat Pola", "Perunding Imej"]
    },

    # --- REKABENTUK INDUSTRI ---
    "IKBN-DIP-006": {
        "headline": "🎨 Rekabentuk Produk: Cipta Gajet Masa Depan",
        "synopsis": "Lihat barang di sekeliling anda—tetikus, botol, kerusi—semuanya bermula dari lakaran pereka. Anda belajar menggunakan perisian canggih (CAD) dan '3D Printer' untuk mencipta produk baharu. Sesuai untuk anda yang berjiwa seni tapi minat teknologi.",
        "jobs": ["Perekabentuk Produk (Industrial Designer)", "Pelukis Pelan 3D", "Penyelia Model Prototyping"]
    },

    # --- MAKANAN (KILANG) ---
    "IKBN-DIP-007": {
        "headline": "🏭 Teknologi Makanan: Chef Industri",
        "synopsis": "Masak di dapur itu biasa, tapi bagaimana menguruskan pengeluaran 1,000 tin saderi sejam? Ini adalah sains pengeluaran makanan skala besar. Anda belajar tentang keselamatan makanan (Halal/HACCP), pembungkusan, dan kualiti. Anda adalah 'gatekeeper' makanan negara.",
        "jobs": ["Penyelia Pengeluaran Makanan", "Pegawai Kawalan Kualiti (QC)", "Usahawan Produk IKS", "Eksekutif Halal"]
    },

    # --- JENTERA BERAT ---
    "IKBN-CET-001": {
        "headline": "🚜 Jentera Berat: Kendalikan 'Gergasi Besi'",
        "synopsis": "Kerjaya untuk yang berjiwa kental. Anda akan pakar membaiki dan menyelenggara raksasa pembinaan seperti Jentolak (Bulldozer) dan Jengkaut (Excavator). Kemahiran hidraulik dan diesel yang anda belajar di sini sangat bernilai di tapak perlombongan dan pembinaan.",
        "jobs": ["Mekanik Jentera Berat", "Juruteknik Hidraulik", "Penyelia Tapak Bina", "Usahawan Servis Jentera"]
    },

    # --- KENDERAAN PERDAGANGAN ---
    "IKBN-CET-002": {
        "headline": "🚛 Logistik & Pengangkutan: Nadi Ekonomi",
        "synopsis": "Lori dan bas adalah darah yang menggerakkan ekonomi negara. Anda belajar servis enjin diesel gergasi, sistem brek angin, dan transmisi lori. Bidang ini menjanjikan kerja tetap di syarikat logistik besar atau syarikat pengangkutan awam.",
        "jobs": ["Mekanik Lori & Bas", "Juruteknik Fleet", "Penyelia Bengkel Logistik"]
    },

    # --- AUTOMOTIF (KERETA) ---
    "IKBN-CET-003": {
        "headline": "🛠️ Automotif: Doktor Kereta",
        "synopsis": "Langkah pertama untuk buka bengkel sendiri. Anda akan bedah siasat enjin, gearbox, dan sistem kereta sehingga anda boleh selesaikan apa saja masalah kenderaan. Kursus 'hands-on' sepenuhnya untuk menjadikan anda pomen yang disegani.",
        "jobs": ["Mekanik Kereta", "Penasihat Servis", "Pengusaha Bengkel", "Foreman"]
    },

    # --- EV (ELEKTRIK) ---
    "IKBN-CET-004": {
        "headline": "⚡🚗 Kereta Elektrik (EV): Mekanik Masa Depan",
        "synopsis": "Dunia sedang beralih ke arah elektrik (EV). Jadilah orang pertama yang mahir membaiki kereta hibrid dan elektrik sepenuhnya. Anda belajar tentang bateri voltan tinggi dan sistem motor elektrik. Kemahiran 'high-tech' yang sangat laku di masa depan.",
        "jobs": ["Pakar Teknikal EV & Hibrid", "Diagnostik Kenderaan", "Juruteknik Automotif Moden"]
    },

    # --- CAT KERETA ---
    "IKBN-CET-005": {
        "headline": "✨ 'Body & Paint': Seni Cantikkan Kereta",
        "synopsis": "Kereta calar? Warna kusam? Andalah penyelamatnya. Belajar seni mengecat kereta taraf 'showroom', bancuhan warna (color matching), dan ketuk body. Kerjaya yang menggabungkan kemahiran tangan halus dan seni warna.",
        "jobs": ["Penyembur Cat (Sprayer)", "Pakar 'Body & Paint'", "Color Matcher", "Detailer Kereta"]
    },

    # --- SENIBINA & BANGUNAN ---
    "IKBN-CET-006": {
        "headline": "🏛️ Lukisan Senibina: Arkitek Muda",
        "synopsis": "Setiap bangunan ikonik bermula di atas kertas. Anda akan belajar menghasilkan lukisan teknikal yang terperinci untuk bangunan kediaman dan komersial. Menguasai perisian CAD, anda adalah orang kanan kepada Arkitek dan Jurutera. Kerjaya pejabat yang profesional dan bergaji stabil.",
        "jobs": ["Pelukis Pelan (Draughtsman)", "Pembantu Teknikal Senibina", "Penyelia Tapak Bina"]
    },

    "IKBN-CET-007": {
        "headline": "🏢 Penyelenggaraan Bangunan: Doktor Bangunan",
        "synopsis": "Bangunan tinggi (skyscraper) memerlukan penjagaan rapi 24 jam. Anda belajar segalanya: dari sistem elektrik, paip air, aircond pusat, hingga sistem pencegah kebakaran. Anda adalah wira yang memastikan pejabat, hotel, dan mall beroperasi tanpa masalah.",
        "jobs": ["Penyelia Fasiliti (Facility Manager)", "Juruteknik Bangunan", "Kontraktor Penyelenggaraan"]
    },

    # --- ELEKTRIK & AIRCOND (SIJIL) ---
    "IKBN-CET-008": {
        "headline": "⚡ Pendawai Elektrik (PW4): Kuasa Tiga Fasa",
        "synopsis": "Naik taraf kemahiran anda dari rumah biasa ke kilang besar. Lesen PW4 membolehkan anda membuat pendawaian 'Tiga Fasa' (Three Phase) yang digunakan di industri berat. Ini adalah lesen wajib untuk menjadi kontraktor elektrik yang berjaya.",
        "jobs": ["Pendawai Elektrik (Wireman PW4)", "Juruteknik Kilang", "Kontraktor Elektrik Berdaftar"]
    },

    "IKBN-CET-009": {
        "headline": "❄️ Servis Aircond Domestik: Sejuk & Nyaman",
        "synopsis": "Kerjaya 'pantas dapat duit'. Anda belajar pasang, servis, dan baiki unit aircond rumah dan pejabat kecil. Dengan cuaca panas Malaysia, kemahiran ini ibarat mesin cetak wang tunai. Sesuai untuk anda yang mahu berniaga sendiri sejurus tamat belajar.",
        "jobs": ["Juruteknik Aircond", "Usahawan Servis Penyejukan", "Pemasang HVAC"]
    },

    # --- ELEKTRONIK INDUSTRI ---
    "IKBN-CET-010": {
        "headline": "🤖 Elektronik Industri: Otak Kilang",
        "synopsis": "Kawal robot dan mesin automatik! Di kilang moden, semuanya bergerak guna sensor dan cip. Anda belajar membaiki 'otak' mesin ini (PLC, Pneumatik, Hidraulik). Tanpa anda, kilang akan berhenti beroperasi. Sangat kritikal untuk Revolusi Industri 4.0.",
        "jobs": ["Juruteknik Automasi", "Penyelia Elektronik Kilang", "Pakar PLC & Robotik"]
    },

    # --- FESYEN (JAHITAN) ---
    "IKBN-CET-011": {
        "headline": "👗 Jahitan Wanita: Seni Busana Eksklusif",
        "synopsis": "Fokus kepada kemahiran tangan yang halus. Anda belajar teknik memotong dan menjahit pakaian wanita yang rumit dan elegan. Dari baju kurung moden hingga gaun pengantin, kemahiran ini membolehkan anda membuka butik tempahan khas yang sangat lumayan.",
        "jobs": ["Tukang Jahit (Tailor)", "Pembuat Pola Wanita", "Pengusaha Kedai Jahit"]
    },

    # --- HOSPITALITI (HOTEL & MAKANAN) ---
    "IKBN-CET-012": {
        "headline": "🏨 Pengurusan Hotel: Wajah Hadapan Hotel",
        "synopsis": "Anda adalah orang pertama yang menyambut VIP dan pelancong. Belajar seni layanan 5 bintang, sistem tempahan (booking), dan komunikasi profesional. Kerjaya glamor di lobi hotel mewah, resort, atau syarikat penerbangan.",
        "jobs": ["Penyambut Tetamu (Front Office)", "Resepsionis Hotel", "Pegawai Khidmat Pelanggan"]
    },

    "IKBN-CET-013": {
        "headline": "🍽️ Penyajian (F&B): Layanan Diraja",
        "synopsis": "Seni melayan tetamu di meja makan (Fine Dining) dan bankuet besar. Anda belajar etika meja, susun atur 'Cutlery', dan cara menghidang makanan dengan gaya profesional. Laluan pantas untuk menjadi Kapten Restoran atau Pengurus F&B di hotel ternama.",
        "jobs": ["Kapten Restoran", "Pramusaji (Waiter/Waitress)", "Penyelia Bankuet", "Steward Kapal Persiaran"]
    },

    "IKBN-CET-014": {
        "headline": "👨‍🍳 Seni Kulinari: Chef Profesional",
        "synopsis": "Impian menjadi Chef bermula di sini. Kuasai masakan 5 benua: Melayu, Cina, India, dan Barat (Western). Dari hidangan pembuka selera hingga pencuci mulut, anda akan dilatih menguruskan dapur profesional. Bersedialah untuk dunia masakan yang pantas dan kreatif.",
        "jobs": ["Chef (Commis/Demi)", "Tukang Masak Katering", "Usahawan Makanan (Food Truck/Kafe)"]
    },

    "IKBN-CET-015": {
        "headline": "🍰 Pastri & Roti: Seni Manisan",
        "synopsis": "Dunia manis yang penuh seni. Belajar membakar kek perkahwinan bertingkat, roti artisan, dan biskut rangup. Bukan sekadar resipi, anda belajar teknik dekorasi dan keusahawanan untuk membuka kedai roti (Bakery) atau kafe hipster anda sendiri.",
        "jobs": ["Chef Pastri", "Pembuat Roti (Baker)", "Usahawan Kafe & Bakeri", "Dekorator Kek"]
    },

    # --- BAKERY & PASTRY ---
    "IKBN-CET-016": {
        "headline": "🥐 Bakeri & Konfeksionari: Dari Dapur ke Bisnes",
        "synopsis": "Siapa sangka buat roti boleh jadi kerjaya lumayan? Anda akan belajar sains di sebalik roti lembut, pizza Itali, dan muffin gebu. Menggunakan mesin industri moden, anda dilatih bukan sekadar menjadi pembuat roti, tetapi usahawan bakeri yang mampu menghasilkan produk berkualiti tinggi dan bersih.",
        "jobs": ["Pembuat Roti (Baker)", "Penyelia Pengeluaran Bakeri", "Usahawan Pizza & Pastri", "Chef Konfeksionari"]
    },

    # --- KOSMETOLOGI (RAMBUT) ---
    "IKBN-CET-017": {
        "headline": "✂️ Gaya Rambut: Seni Penggayaan Profesional",
        "synopsis": "Rambut adalah mahkota. Anda belajar seni menggunting, mewarna, dan mengerinting rambut dengan teknik terkini. Lebih dari itu, anda diajar menguruskan salon sebenar dan imej personal. Kerjaya kreatif yang membolehkan anda bekerja di salon eksklusif atau menjadi 'Hairstylist' selebriti.",
        "jobs": ["Pendandan Rambut (Hairstylist)", "Colorist Profesional", "Pengurus Salon", "Perunding Gaya Rambut"]
    },

    # --- KOSMETOLOGI (KECANTIKAN) ---
    "IKBN-CET-018": {
        "headline": "💅 Terapi Kecantikan: Pakar Spa & Estetik",
        "synopsis": "Industri kecantikan bernilai bilion ringgit. Anda akan pakar dalam rawatan wajah (facial), manikur/pedikur, dan terapi badan. Bukan sekadar cantik, anda belajar mengendalikan mesin rawatan canggih dan pengurusan spa. Langkah pertama untuk membuka pusat kecantikan sendiri.",
        "jobs": ["Juruterapi Kecantikan (Beautician)", "Perunding Kecantikan", "Pengurus Spa", "Nail Artist"]
    },

    # --- MULTIMEDIA ---
    "IKBN-CET-019": {
        "headline": "🎥 Multimedia Kreatif: Pencipta Kandungan Digital",
        "synopsis": "Sesuai untuk 'Content Creator' masa depan! Anda belajar segalanya: suntingan video, animasi grafik, dan fotografi menggunakan kamera DSLR & dron. Dari Adobe Premiere ke After Effects, anda akan menghasilkan karya digital yang memukau untuk iklan, media sosial, dan TV.",
        "jobs": ["Penyunting Video (Video Editor)", "Pereka Grafik Multimedia", "Jurugambar/Videografer", "Content Creator"]
    },

    # --- MARIN (BOT & KAPAL) ---
    "IKBN-CET-020": {
        "headline": "⚓ Teknologi Marin: Jurutera Lautan",
        "synopsis": "Kerjaya yang jarang orang tahu tapi gaji lumayan. Anda belajar membaiki dan menyelenggara enjin bot, kapal, dan jentera marin. Jika anda suka laut dan enjin besar, ini bidang anda. Peluang kerja luas di pelabuhan, limbungan kapal, atau syarikat perkapalan.",
        "jobs": ["Mekanik Marin", "Juruteknik Enjin Bot", "Penyelia Limbungan (Dockyard)", "Kontraktor Marin"]
    },

    # --- KIMPALAN & BOILER ---
    "IKBN-CET-021": {
        "headline": "🔥 Boilermaker: Pakar Logam Minyak & Gas",
        "synopsis": "Kerjaya 'Heavy Metal' sebenar. Anda belajar membina dan membaiki tangki tekanan tinggi (Pressure Vessel) untuk loji minyak & gas. Kemahiran memotong dan membentuk logam tebal ini sangat kritikal dan dibayar mahal dalam industri O&G.",
        "jobs": ["Boilermaker", "Juruteknik Fabrikasi Logam", "Fitter Minyak & Gas"]
    },

    "IKBN-CET-022": {
        "headline": "⚡ Kimpalan Arka (SMAW): Seni Sambungan Besi",
        "synopsis": "Asas kepada semua binaan besi. Anda belajar teknik kimpalan SMAW (Shielded Metal Arc Welding) untuk menyambung paip dan plat besi. Kemahiran ini diperlukan di mana-mana—dari tapak pembinaan bangunan hinggalah ke pelantar minyak.",
        "jobs": ["Jurukimpal (Welder) 3G/4G", "Fitter Struktur", "Kontraktor Besi"]
    },

    "IKBN-CET-023": {
        "headline": "💥 Teknologi Kimpalan Maju: Pakar 4 Proses",
        "synopsis": "Jadilah 'Master Welder' yang serba boleh. Anda menguasai 4 jenis kimpalan utama: SMAW, GMAW (MIG), GTAW (TIG), dan SAW. Anda bukan sahaja mengimpal, tapi belajar memeriksa kualiti (QC) kimpalan. Sesuai untuk kilang automotif dan aeroangkasa.",
        "jobs": ["Jurukimpal TIG/MIG", "Inspektor Kimpalan (QC)", "Penyelia Fabrikasi", "Jurulatih Kimpalan"]
    },

    # --- MEKATRONIK ---
    "IKBN-CET-024": {
        "headline": "🤖 Mekatronik: Gabungan Mekanikal & Elektronik",
        "synopsis": "Jangan pilih satu, kuasai kedua-duanya! Mekatronik adalah gabungan 'Mekanik' + 'Elektronik'. Anda belajar membina sistem automatik, lengan robot, dan sistem hidraulik. Ini adalah kemahiran paling penting untuk bekerja di kilang moden yang menggunakan robot.",
        "jobs": ["Juruteknik Mekatronik", "Pakar Automasi", "Penyelenggara Robotik", "Juruteknik Elektromekanikal"]
    },

    # --- MINYAK & GAS (PAIP) ---
    "IKBN-CET-025": {
        "headline": "🛢️ Fabrikasi Paip (O&G): Laluan ke Offshore",
        "synopsis": "Kerjaya 'Pipe Fitter' sangat dihormati di pelantar minyak. Anda belajar membaca lukisan isometrik yang rumit dan memotong/menyambung paip dengan tepat. Salah satu laluan terpantas untuk bekerja dalam sektor Minyak & Gas.",
        "jobs": ["Pipe Fitter", "Fabricator Paip", "Juruteknik O&G", "Penyelia Piping"]
    },

    # --- PENYELENGGARAAN INDUSTRI ---
    "IKBN-CET-026": {
        "headline": "⚙️ Penyelenggaraan Industri: Wira Kilang",
        "synopsis": "Kilang tidak boleh berhenti. Andalah yang memastikannya terus berjalan. Belajar membaiki segala jenis kerosakan mesin: mekanikal, elektrik, pneumatik, dan hidraulik. Anda adalah 'doktor pakar' untuk mesin industri yang kompleks.",
        "jobs": ["Juruteknik Penyelenggaraan (Maintenance)", "Jurutera Loji", "Penyelia Teknikal Kilang"]
    },

    # --- PESAWAT (BAHAN) ---
    "IKBN-CET-027": {
        "headline": "✈️ Komposit Pesawat: Bahan Masa Depan",
        "synopsis": "Pesawat moden bukan lagi diperbuat daripada besi berat, tapi 'Komposit' yang ringan dan kuat. Anda belajar mencipta dan membaiki struktur canggih ini menggunakan gentian karbon (Carbon Fiber). Kemahiran 'niche' ini sangat mahal harganya dalam industri aeroangkasa.",
        "jobs": ["Juruteknik Komposit Pesawat", "Pakar Laminasi (Laminator)", "Inspektor Struktur Pesawat"]
    },

    "IKBN-CET-028": {
        "headline": "✈️ Struktur Pesawat (Metal): Doktor Kapal Terbang",
        "synopsis": "Jika sayap pesawat retak, andalah yang membaikinya. Fokus kepada membaiki kerangka besi (Sheet Metal) pesawat. Anda belajar teknik menampal (patching), rivet, dan kimpalan khas penerbangan. Kerja yang memerlukan ketelitian tinggi dan disiplin besi.",
        "jobs": ["Juruteknik Struktur Pesawat (Sheet Metal)", "Inspektor Kerangka Pesawat", "Mekanik Pesawat"]
    },

    # --- REKABENTUK INDUSTRI (SIJIL) ---
    "IKBN-CET-029": {
        "headline": "🎨 Rekabentuk Industri: Cipta Produk Baharu",
        "synopsis": "Dari idea kepada realiti. Anda belajar merekabentuk perabot, pengangkutan, dan peralatan sukan menggunakan perisian CAD. Bukan setakat lukis, anda belajar hasilkan model sebenar (Mock-up). Laluan pantas untuk menjadi pereka yang praktikal.",
        "jobs": ["Pereka Produk Industri", "Pembuat Model (Model Maker)", "Pakar CAD/CAM"]
    },

    # --- CIVIL (SCAFFOLDING) ---
    "IKBN-CET-032": {
        "headline": "🏗️ Scaffolding: Wira Tempat Tinggi",
        "synopsis": "Kerjaya ekstrem di tapak binaan dan pelantar minyak. Anda belajar memasang perancah (scaffolding) yang selamat untuk bangunan tinggi. Sijil ini adalah 'lesen wajib' untuk bekerja di tapak projek mega dan industri Minyak & Gas (Offshore).",
        "jobs": ["Juruperancah (Scaffolder)", "Penyelia Keselamatan Tapak", "Inspektor Scaffolding"]
    },

    # --- ELEKTRIK (DOMESTIK) ---
    "IKBN-CET-034": {
        "headline": "🏠 Pendawai Elektrik (PW2): Raja Wiring Rumah",
        "synopsis": "Langkah pertama dalam dunia elektrik. Fokus kepada pendawaian rumah satu fasa. Anda belajar pasang soket, lampu, dan papan agihan (DB). Sijil PW2 membolehkan anda bekerja sebagai Wireman berdaftar atau mengambil upah 'wiring' rumah sendiri.",
        "jobs": ["Pendawai Elektrik (Wireman PW2)", "Juruteknik Penyelenggaraan", "Kontraktor Wiring Kecil"]
    },

    # ==========================================
    # ILJTM - COURSES
    # ==========================================

    # --- QUALITY ASSURANCE (QA) ---
    "IJTM-DIP-010": {
        "headline": "✅ Jaminan Kualiti (QA): Polis Kualiti",
        "synopsis": "Sebelum produk dijual, ia mesti lulus di tangan anda. Anda belajar menggunakan alat pengukur mikron (CMM) untuk memastikan setiap skru dan komponen adalah sempurna. Kilang automotif dan aeroangkasa sangat memerlukan pakar QA untuk menjaga standard keselamatan.",
        "jobs": ["Pegawai Kawalan Kualiti (QA/QC)", "Inspektor Kualiti", "Juruteknik Kalibrasi"]
    },

    # --- MEKATRONIK (DIPLOMA) ---
    "IJTM-DIP-017": {
        "headline": "🤖 Diploma Mekatronik: Arkitek Robot",
        "synopsis": "Gabungkan kejuruteraan mekanikal, elektrik, dan komputer. Anda akan membina sistem automasi pintar dan lengan robot industri. Kursus ini menyediakan anda untuk menjadi jurutera masa depan yang mampu mengendalikan kilang pintar (Smart Factory).",
        "jobs": ["Penolong Jurutera Mekatronik", "Pakar Automasi & Robotik", "Penyelia Penyelenggaraan Loji"]
    },

    # --- MIKROELEKTRONIK ---
    "IJTM-DIP-019": {
        "headline": "💻 Mikroelektronik: Teknologi Cip Pintar",
        "synopsis": "Belajar di dalam makmal 'Cleanroom' bertaraf dunia—satu-satunya di Malaysia! Anda akan memahami cara cip komputer dan semikonduktor dibuat. Industri E&E adalah eksport terbesar Malaysia, jadi pakar cip sangat diperlukan di kilang gergasi seperti Intel dan Infineon.",
        "jobs": ["Juruteknik Semikonduktor", "Penyelia Proses Cleanroom", "Pembantu Jurutera R&D Cip"]
    },

    # --- PEMESINAN (CNC) ---
    "IJTM-DIP-022": {
        "headline": "⚙️ Teknologi Pembuatan: Pakar Mesin CNC",
        "synopsis": "Kuasai mesin moden yang boleh memotong besi setepat rambut! Anda belajar mengendalikan mesin CNC (Computer Numerical Control), mesin kisar, dan larik. Anda adalah orang yang menghasilkan komponen enjin kereta dan mesin industri yang presisi.",
        "jobs": ["Juruteknik CNC (Machinist)", "Programmer CNC", "Penyelia Pembuatan", "Pembuat Acuan (Die Maker)"]
    },

    # --- AUTOMOTIF (PENGELUARAN) ---
    "IJTM-DIP-024": {
        "headline": "🚗 Pengeluaran Automotif: Nadi Kilang Kereta",
        "synopsis": "Bukan sekadar baiki kereta, tapi BINANYA. Anda belajar proses pemasangan kereta di kilang—dari kerangka hingga ke enjin. Fokus kepada pengurusan barisan pengeluaran (Assembly Line) dan robotik automotif. Sesuai untuk bekerja di Proton, Perodua, atau Honda.",
        "jobs": ["Penyelia Pengeluaran Automotif", "Juruteknik Pemasangan (Assembly)", "Pegawai Kawalan Kualiti Kereta"]
    },

    # --- PENYELENGGARAAN PESAWAT (MRO) ---
    "IJTM-DIP-026": {
        "headline": "✈️ Penyelenggaraan Pesawat (MRO): Lesen Terbang Tinggi",
        "synopsis": "Kerjaya elit dalam dunia penerbangan. Anda belajar menyelenggara keseluruhan pesawat: enjin, sayap, dan sistem avionik. Kursus ini mempersiapkan anda untuk lesen CAAM Part 66 (Kategori A)—tiket untuk bekerja di hangar syarikat penerbangan antarabangsa.",
        "jobs": ["Juruteknik Pesawat (Aircraft Technician)", "Mekanik MRO", "Penyelia Hangar"]
    },

    # --- ELEKTRONIK (DIPLOMA) ---
    "IJTM-DIP-032": {
        "headline": "🔌 Diploma Elektronik: Pakar Litar & Kawalan",
        "synopsis": "Dunia hari ini dikuasai oleh elektronik. Anda akan belajar segalanya: dari membaiki papan litar (PCB) hingga memprogram sistem automasi kompleks menggunakan PLC dan sensor. Kursus ini menjadikan anda pakar yang boleh merekabentuk, menganalisa, dan membaiki apa saja peranti elektronik.",
        "jobs": ["Juruteknik Elektronik Kanan", "Pakar Pembaikan PCB", "Juruteknik Automasi", "Penyelia Kawalan Kualiti"]
    },

    # --- MEKATRONIK (DIPLOMA - JTM) ---
    "IJTM-DIP-033": {
        "headline": "🤖 Diploma Mekatronik: Jurutera Serba Boleh",
        "synopsis": "Kenapa pilih satu bidang jika boleh kuasai tiga? Mekatronik menggabungkan Mekanikal, Elektronik, dan Komputer. Anda akan mahir membina sistem robotik, menyelenggara mesin industri berteknologi tinggi, dan merekabentuk sistem automasi pintar. Graduan bidang ini sangat laku di pasaran.",
        "jobs": ["Juruteknik Mekatronik", "Pakar Robotik Industri", "Jurutera Automasi", "Penyelia Penyelenggaraan"]
    },

    # --- IT & KOMPUTER ---
    "IJTM-DIP-034": {
        "headline": "💻 Diploma Teknologi Komputer: Doktor IT",
        "synopsis": "Bukan sekadar guna komputer, tapi membinanya. Anda belajar memasang perkakasan (hardware), membina rangkaian (network/server), dan menyelenggara sistem komputer pejabat. Anda adalah 'orang penting' yang dicari bila sistem komputer sesebuah syarikat lumpuh.",
        "jobs": ["Juruteknik Komputer", "Pentadbir Rangkaian (Network Admin)", "Penyelia IT", "Usahawan Kedai Komputer"]
    },

    # --- PEMESINAN (DIPLOMA) ---
    "IJTM-DIP-035": {
        "headline": "⚙️ Diploma Pembuatan (Pemesinan): Seni Besi Presisi",
        "synopsis": "Mesin CNC adalah jantung industri pembuatan moden. Anda belajar memprogram mesin canggih ini untuk memotong besi dengan ketepatan mikron. Dari rekaan CAD/CAM hingga produk akhir, anda akan menghasilkan komponen enjin dan mesin yang kompleks.",
        "jobs": ["Juruteknik CNC (Machinist)", "Penyelia Pengeluaran", "Programmer CAD/CAM", "Pembuat Acuan (Tool & Die)"]
    },

    # --- AUTOMOTIF (AUTOMASI) ---
    "IJTM-CET-001": {
        "headline": "🏭 Automotif Industri: Robotik Kilang Kereta",
        "synopsis": "Kilang kereta moden tidak guna tangan, ia guna robot. Anda belajar mengendalikan 'otak' di sebalik robot ini: PLC, Pneumatik, dan Hidraulik. Anda adalah pakar yang memastikan barisan pengeluaran automatik berjalan lancar tanpa henti.",
        "jobs": ["Juruteknik Automasi Industri", "Penyelenggara Robotik", "Pakar PLC"]
    },

    # --- AUTOMOTIF (DIE MAKING) ---
    "IJTM-CET-002": {
        "headline": "🛠️ Pembuatan Acuan (Die): Pembentuk Logam",
        "synopsis": "Setiap pintu kereta bermula dari satu acuan (Die). Anda belajar mencipta acuan besi ini menggunakan mesin CNC berteknologi tinggi dan perisian CAD. Ini adalah kemahiran 'niche' yang sangat mahal harganya dalam industri pembuatan komponen kereta.",
        "jobs": ["Pembuat Acuan (Tool & Die Maker)", "Juruteknik CNC", "Perekabentuk Acuan"]
    },

    # --- AUTOMOTIF (SERVIS) ---
    "IJTM-CET-003": {
        "headline": "🚗 Servis Automotif: Pakar Diagnostik",
        "synopsis": "Lengkapkan diri anda dengan ilmu automotif menyeluruh. Anda akan membedah siasat enjin, gearbox, brek, dan aircond kereta. Fokus kursus ini adalah melahirkan mekanik yang kompeten untuk bekerja di pusat servis jenama besar atau membuka bengkel sendiri.",
        "jobs": ["Mekanik Kereta", "Penasihat Servis", "Foreman", "Usahawan Bengkel"]
    },

    "IJTM-CET-004": {
        "headline": "🔧 Teknologi Automotif: Mekanik Bertauliah",
        "synopsis": "Sama seperti di atas, kursus ini memantapkan kemahiran anda dalam penyelenggaraan kenderaan. Dengan Sijil Kemahiran Malaysia (SKM) Tahap 3, anda diiktiraf sebagai mekanik profesional yang layak bekerja di mana-mana pusat servis bertauliah.",
        "jobs": ["Mekanik Bertauliah", "Juruteknik Automotif", "Penyelia Bengkel"]
    },

    # --- CIVIL (BINAAN) ---
    "IJTM-CET-005": {
        "headline": "🏗️ Teknologi Binaan: Jurutera Tapak Muda",
        "synopsis": "Setiap projek mega perlukan pakar sivil. Anda belajar 'A-Z' pembinaan: dari jalan raya ke sistem saliran, dari ujian konkrit makmal ke penyeliaan tapak sebenar. Ini adalah langkah pertama anda untuk menjadi 'Site Supervisor' yang dihormati di tapak bina.",
        "jobs": ["Penyelia Tapak Bina (Site Supervisor)", "Juruteknik Sivil", "Pembantu Jurutera"]
    },

    # --- CIVIL (PAIP) ---
    "IJTM-CET-006": {
        "headline": "🚿 Paip & Sanitari: Pakar Air",
        "synopsis": "Air adalah keperluan asas. Anda akan pakar memasang dan menyelenggara sistem paip domestik dan industri yang kompleks. Bukan sekadar tukang paip biasa, anda belajar membaca pelan 'blue print' dan merekabentuk sistem air bangunan tinggi.",
        "jobs": ["Juruteknik Perpaipan (Plumber)", "Kontraktor Paip & Sanitari", "Penyelia M&E"]
    },

    # --- CADD (MEKANIKAL) ---
    "IJTM-CET-007": {
        "headline": "🖥️ CADD Mekanikal: Pelukis Pelan Industri",
        "synopsis": "Tinggalkan papan lukis lama, beralih ke komputer. Anda belajar menggunakan perisian CAD canggih untuk melukis komponen enjin dan mesin dengan ketepatan tinggi. Lukisan andalah yang akan digunakan oleh jurutera untuk membina mesin sebenar.",
        "jobs": ["Pelukis Pelan Mekanikal (Draughtsman)", "Pembantu Teknikal CAD", "Perekabentuk Komponen"]
    },

    # --- CADD (SENIBINA) ---
    "IJTM-CET-008": {
        "headline": "🏠 CADD Senibina: Visual Arkitek",
        "synopsis": "Tukarkan imaginasi menjadi visual 3D yang memukau. Anda belajar melukis pelan rumah, perspektif bangunan, dan teknik 'rendering' yang realistik. Kemahiran ini sangat diperlukan oleh firma arkitek untuk membentangkan projek kepada klien.",
        "jobs": ["Pelukis Pelan Senibina", "Visualiser 3D", "Pembantu Arkitek"]
    },

    # --- ELEKTRIK (TIGA FASA) ---
    "IJTM-CET-009": {
        "headline": "⚡ Pendawai Tiga Fasa: Kuasa Industri",
        "synopsis": "Naik taraf lesen anda! Pendawaian 'Tiga Fasa' digunakan di semua kilang dan bangunan komersial. Anda belajar memasang motor industri, janakuasa, dan sistem kawalan elektrik berkuasa tinggi. Lesen kompeten Suruhanjaya Tenaga (ST) menanti anda.",
        "jobs": ["Pendawai Elektrik Kompeten (PW4)", "Juruteknik Elektrik Industri", "Kontraktor Elektrik"]
    },

    # --- ELEKTRONIK INDUSTRI ---
    "IJTM-CET-010": {
        "headline": "🤖 Elektronik Industri: Jantung Kilang Pintar",
        "synopsis": "Kawal mesin dengan hujung jari. Anda belajar sistem PLC (Programmable Logic Controller) yang menggerakkan robot dan mesin automatik di kilang. Gabungan ilmu elektronik digital dan analog menjadikan anda pakar yang boleh menyelesaikan masalah mesin kompleks.",
        "jobs": ["Juruteknik Automasi", "Programmer PLC", "Penyelia Elektronik Kilang"]
    },

    # --- MINYAK & GAS (FABRIKASI) ---
    "IJTM-CET-011": {
        "headline": "🛢️ Fabrikasi Logam (O&G): Pembina Pelantar",
        "synopsis": "Kerjaya 'Heavy Duty' di sektor Minyak & Gas. Anda belajar memotong, melentur, dan menyambung plat besi tebal untuk membina struktur pelantar minyak. Kemahiran ini adalah tiket anda untuk bekerja di yard fabrikasi antarabangsa.",
        "jobs": ["Fabricator Struktur O&G", "Fitter Logam", "Juruteknik Pembinaan Pelantar"]
    },

    "IJTM-CET-012": {
        "headline": "🛢️ Fabrikasi Struktur (O&G): Pakar Besi Berat",
        "synopsis": "Sama seperti di atas, fokus kursus ini adalah membina struktur besi gergasi. Anda akan mahir menggunakan mesin industri untuk membentuk logam mengikut spesifikasi ketat industri minyak dan gas.",
        "jobs": ["Structural Fitter", "Penyelia Fabrikasi", "Juruteknik O&G"]
    },

    # --- INSTRUMEN ---
    "IJTM-CET-013": {
        "headline": "🎛️ Instrumen Perindustrian: Pengawal Proses",
        "synopsis": "Kilang kimia dan loji penapisan perlukan ketepatan. Anda belajar menjaga 'sensor' yang mengukur suhu, tekanan, dan aliran paip. Jika sensor salah baca, kilang boleh meletup! Anda adalah pakar yang memastikan sistem kawalan sentiasa tepat dan selamat.",
        "jobs": ["Juruteknik Instrumen (Instrumentation Tech)", "Juruteknik Kalibrasi", "Penyelia Loji"]
    },

    # --- KENDERAAN BERAT ---
    "IJTM-CET-014": {
        "headline": "🚛 Kenderaan Berat: Mekanik Lori & Bas",
        "synopsis": "Enjin besar, gaji besar. Anda pakar membaiki lori kontena, bas ekspres, dan treler. Belajar sistem brek angin, hidraulik, dan enjin diesel turbo. Industri logistik yang sedang berkembang pesat sangat memerlukan mekanik mahir seperti anda.",
        "jobs": ["Mekanik Kenderaan Perdagangan", "Juruteknik Fleet Logistik", "Foreman Lori"]
    },

    # --- KIMPALAN (SIJIL) ---
    "IJTM-CET-015": {
        "headline": "🔥 Teknologi Kimpalan: Pakar Sambungan Besi",
        "synopsis": "Seni mencantum besi dengan api. Anda kuasai 4 teknik utama: SMAW, MIG, TIG, dan SAW. Dari paip minyak ke kerangka bangunan, kemahiran kimpalan anda diperlukan di mana-mana. Kerjaya lasak dengan bayaran lumayan mengikut skil anda.",
        "jobs": ["Jurukimpal (Welder) 3G/6G", "Jurukimpal TIG/MIG", "Fitter Kimpalan"]
    },

    # --- IT (SISTEM) ---
    "IJTM-CET-016": {
        "headline": "💻 Sistem Komputer: Bina 'Gaming Rig' & Server",
        "synopsis": "Pernah pasang PC sendiri? Jadikan hobi itu kerjaya. Anda belajar memasang Motherboard, RAM, dan Hard Disk dari kosong sehingga menjadi komputer yang lengkap. Anda juga akan mahir instalasi Windows, Linux, dan menyelenggara server pejabat. Sesuai untuk 'Tech Enthusiast'.",
        "jobs": ["Juruteknik Komputer", "Sistem Administrator", "Penyelia Sokongan IT", "Usahawan Kedai Komputer"]
    },

    # --- IT (NETWORK) ---
    "IJTM-CET-017": {
        "headline": "🌐 Rangkaian Komputer: Arkitek Internet",
        "synopsis": "Tanpa internet, dunia berhenti. Anda belajar membina infrastruktur ini—dari kabel LAN hingga konfigurasi Router dan Server canggih. Pakar rangkaian (Network Engineer) adalah kerjaya yang sangat stabil dan kritikal untuk bank, telco, dan syarikat multinasional.",
        "jobs": ["Juruteknik Rangkaian (Network Tech)", "Pentadbir Sistem", "Penyelia IT", "Kontraktor Kabel Fiber"]
    },

    # --- IT (SISTEM - ALTERNATE) ---
    "IJTM-CET-018": {
        "headline": "🛠️ Penyelenggaraan PC: 'Doktor' Komputer",
        "synopsis": "Komputer rosak? Andalah penyelamatnya. Fokus kursus ini adalah 'Troubleshooting'—mencari punca kerosakan hardware atau software dan membaikinya dengan pantas. Kemahiran wajib untuk bekerja di jabatan IT mana-mana syarikat.",
        "jobs": ["Juruteknik Helpdesk", "Penyelia Penyelenggaraan IT", "Jurukomputer"]
    },

    # --- MEKATRONIK (SIJIL) ---
    "IJTM-CET-019": {
        "headline": "🤖 Mekatronik (Sijil): Langkah Pertama ke Robotik",
        "synopsis": "Permulaan dunia automasi. Anda belajar asas hidraulik (kuasa cecair), pneumatik (kuasa angin), dan elektronik yang menggerakkan mesin kilang. Kursus 'hands-on' ini mempersiapkan anda untuk menjadi juruteknik mahir yang boleh menjaga mesin berteknologi tinggi.",
        "jobs": ["Juruteknik Automasi", "Operator Mesin Robotik", "Mekanik Elektromekanikal"]
    },

    # --- O&G (LUKISAN) ---
    "IJTM-CET-020": {
        "headline": "🖊️ Lukisan Perpaipan O&G: Pelan Jutawan",
        "synopsis": "Setiap paip di loji minyak bermula dengan lukisan anda. Anda belajar membaca dan melukis pelan paip (Piping Drafting) yang rumit untuk industri Minyak & Gas. Kerjaya ini membolehkan anda bekerja di pejabat syarikat O&G gergasi dengan gaji yang sangat kompetitif.",
        "jobs": ["Pelukis Pelan Paip (Piping Drafter)", "Pembantu Jurutera O&G", "Penyelia Dokumen Teknikal"]
    },

    # --- O&G (LOJI DOWNSTREAM) ---
    "IJTM-CET-021": {
        "headline": "🏭 Loji Minyak (Downstream): Penjaga Kilang Emas",
        "synopsis": "Bekerja di loji penapisan minyak (Refinery) seperti di Pengerang atau Kerteh. Anda pakar menyelenggara pam, injap, dan jentera berat yang memproses minyak mentah menjadi petrol. Kerjaya yang mementingkan keselamatan tinggi dan disiplin, dengan bayaran elaun yang lumayan.",
        "jobs": ["Juruteknik Loji (Plant Technician)", "Penyelia Penyelenggaraan Mekanikal", "Fitter Loji"]
    },

    "IJTM-CET-022": {
        "headline": "⚓ Mekanikal O&G: Pakar Rigging & Slinging",
        "synopsis": "Lebih mendalam tentang operasi loji. Selain baiki mesin, anda belajar teknik 'Rigging & Slinging' (mengangkat beban berat) yang selamat. Sijil ini sangat laku keras kerana industri O&G memerlukan pekerja yang kompeten dan mematuhi standard keselamatan antarabangsa.",
        "jobs": ["Rigger & Slinger", "Juruteknik Mekanikal O&G", "Penyelia Operasi Loji"]
    },

    # --- MULTIMEDIA (SIJIL) ---
    "IJTM-CET-023": {
        "headline": "🎬 Multimedia Interaktif: Kreativiti Tanpa Had",
        "synopsis": "Dunia digital perlukan anda. Belajar sunting video, buat animasi, dan reka grafik untuk web atau aplikasi telefon pintar. Menggunakan perisian Adobe (Photoshop, Premiere, Animate), anda boleh bekerja di agensi pengiklanan atau jadi 'Freelancer' yang bebas.",
        "jobs": ["Pereka Grafik", "Editor Video", "Pembangun Kandungan Digital", "Jurufoto Korporat"]
    },

    # --- O&G (PAIP FITTING) ---
    "IJTM-CET-024": {
        "headline": "🔧 Paip Minyak & Gas: Nadi Tenaga",
        "synopsis": "Kerja lasak untuk jiwa kental. Anda belajar memotong, menyambung (fitting), dan menguji paip tekanan tinggi. Tanpa anda, minyak dan gas tidak boleh disalurkan. Kemahiran ini membuka peluang kerja di tapak pembinaan loji atau pelantar minyak (Offshore).",
        "jobs": ["Pipe Fitter", "Juruteknik Paip Gas", "Penyelia Pembinaan Paip"]
    },

    # --- PEMBUATAN (MESIN) ---
    "IJTM-CET-025": {
        "headline": "⚙️ Pemesinan: Pencipta Alat Ganti",
        "synopsis": "Mesin kilang rosak? Anda yang buat alat ganti baharu. Belajar menggunakan mesin larik (Lathe), kisar (Mill), dan canai (Grind) untuk membentuk besi menjadi komponen berguna. Kemahiran asas yang menjadi rebutan di mana-mana bengkel kejuruteraan.",
        "jobs": ["Juruteknik Mesin (Machinist)", "Penyelia Bengkel", "Pembuat Komponen Logam"]
    },

    # --- PEMBUATAN (ACUAN & DIE) ---
    "IJTM-CET-026": {
        "headline": "🛠️ Pembuatan Acuan (Press Die): Pencetak Logam",
        "synopsis": "Setiap komponen kereta yang anda lihat dibentuk oleh 'Die'. Anda belajar mencipta acuan logam yang sangat keras menggunakan mesin CNC canggih. Graduan bidang ini sering bekerja di syarikat gergasi automotif dan aeroangkasa untuk menghasilkan alat ganti kenderaan.",
        "jobs": ["Pembuat Acuan (Tool & Die Maker)", "Juruteknik CNC", "Penyelia Pengeluaran"]
    },
    
    "IJTM-CET-027": {
        "headline": "🛠️ Teknologi Die & Metrologi: Pakar Ukur Halus",
        "synopsis": "Bukan sekadar buat acuan, tapi memastikan ia tepat hingga ke mikron. Anda belajar menggunakan mesin pengukuran (CMM) dan rawatan haba untuk mengeraskan logam. Kemahiran ini menjadikan anda pakar yang sangat diperlukan dalam sektor pembuatan presisi.",
        "jobs": ["Metrologist", "Juruteknik Rawatan Haba", "Pembuat Acuan"]
    },

    "IJTM-CET-028": {
        "headline": "🧪 Acuan Plastik (Mould): Pencipta Produk Plastik",
        "synopsis": "Botol air, bekas makanan, mainan—semuanya dari plastik. Anda belajar teknik 'Injection Moulding' untuk menghasilkan produk plastik secara besar-besaran. Dari bijih plastik hingga barang siap, andalah yang mengawal mesin pengeluaran.",
        "jobs": ["Juruteknik Injection Moulding", "Penyelia Kilang Plastik", "Setter Mesin"]
    },

    # --- PEMESINAN (ASAS) ---
    "IJTM-CET-029": {
        "headline": "⚙️ Pemesinan Am: Mekanik Mesin",
        "synopsis": "Kemahiran wajib untuk mana-mana juruteknik. Belajar mengendalikan mesin larik, kisar, dan canai untuk membaiki alat ganti mesin yang rosak. Asas yang kukuh untuk anda membuka bengkel kejuruteraan sendiri satu hari nanti.",
        "jobs": ["Machinist", "Juruteknik Bengkel", "Kontraktor Kejuruteraan"]
    },

    "IJTM-CET-030": {
        "headline": "🤖 Pembuatan Lanjutan (CNC): Pakar Mesin Robotik",
        "synopsis": "Naik taraf kemahiran pemesinan anda. Fokus kursus ini adalah penggunaan mesin CNC berkomputer dan 'Wire Cut' yang canggih. Anda akan menghasilkan komponen logam yang sangat rumit yang tidak boleh dibuat oleh tangan manusia biasa.",
        "jobs": ["Programmer CNC", "Operator Mesin EDM", "Penyelia Teknikal"]
    },

    # --- HVAC (AIRCOND) ---
    "IJTM-CET-031": {
        "headline": "❄️ Penyejukbekuan Komersial: Pakar Chiller",
        "synopsis": "Upgrade dari aircond rumah ke sistem 'Chiller' bangunan besar. Anda belajar menyelenggara sistem penyejukan pusat (Centralize Aircond) di hospital, mall, dan kilang. Anda juga belajar tentang sistem aircond kenderaan. Kerjaya stabil dengan permintaan tinggi.",
        "jobs": ["Juruteknik HVAC Komersial", "Penyelia Penyelenggaraan Bangunan", "Kontraktor Aircond"]
    },

    # --- PENYELENGGARAAN BANGUNAN ---
    "IJTM-CET-032": {
        "headline": "🏢 Fasiliti Bangunan: Penjaga Harta Benda",
        "synopsis": "Menjaga bangunan bernilai jutaan ringgit. Anda belajar tentang kerja kayu, paip air, lantai jubin, dan asas binaan. Tugas anda memastikan pejabat atau fasiliti kerajaan sentiasa dalam keadaan tiptop dan selamat untuk diduduki.",
        "jobs": ["Penyelia Fasiliti", "Handyman Bangunan", "Kontraktor Ubahsuai"]
    },

    # --- PENYELENGGARAAN MEKANIKAL ---
    "IJTM-CET-033": {
        "headline": "🔧 Penyelenggaraan Mekanikal: Jack of All Trades",
        "synopsis": "Syarikat suka pekerja serba boleh. Anda belajar mengimpal, memesin, dan membaiki kerosakan mesin kilang. Kursus ini melatih anda menjadi juruteknik yang boleh 'turu padang' dan selesaikan masalah mekanikal on-the-spot.",
        "jobs": ["Juruteknik Penyelenggaraan", "Mekanik Loji", "Penyelia Teknikal"]
    },

    # --- POLIMER ---
    "IJTM-CET-034": {
        "headline": "⚗️ Teknologi Polimer: Sains Plastik",
        "synopsis": "Dunia kejuruteraan plastik. Anda belajar mengendalikan mesin suntikan plastik dan menyelesaikan masalah (troubleshoot) jika produk cacat. Kilang elektronik dan automotif sangat memerlukan pakar polimer untuk menghasilkan casing gajet dan bumper kereta.",
        "jobs": ["Juruteknik Polimer", "Penyelia Kualiti Plastik", "Operator Mesin Injection"]
    },

    # --- PERABOT & REKABENTUK ---
    "IJTM-CET-035": {
        "headline": "🪑 Rekabentuk Perabot: Tukang Kayu Moden",
        "synopsis": "Gabungan seni pertukangan dan teknologi. Anda bukan sekadar mengetam kayu, tapi merekabentuk perabot ergonomik dan moden. Sesuai untuk anda yang ingin menjadi pereka dalaman atau membuka kilang perabot sendiri.",
        "jobs": ["Pereka Perabot", "Tukang Kayu Mahir", "Usahawan Perabot"]
    },

    "IJTM-CET-036": {
        "headline": "🎨 Rekabentuk Grafik: Visual Artis Digital",
        "synopsis": "Kuasai seni visual menggunakan komputer Apple Mac. Anda belajar Adobe Illustrator dan Photoshop untuk menghasilkan poster, majalah, dan iklan. Langkah pertama untuk menjadi pereka grafik profesional di agensi pengiklanan atau syarikat penerbitan.",
        "jobs": ["Pereka Grafik", "Artis DTP (Desktop Publishing)", "Freelance Designer"]
    },

    "IJTM-CET-037": {
        "headline": "✏️ Rekabentuk Industri: Pencipta Gajet",
        "synopsis": "Belajar mencipta rupa bentuk produk yang kita guna setiap hari. Dari lakaran tangan hingga ke model 3D komputer, anda akan dilatih untuk menjadikan produk berfungsi dan cantik dipandang.",
        "jobs": ["Perekabentuk Produk", "CAD Modeler", "Pembantu Pereka R&D"]
    },

    # --- TELEKOMUNIKASI ---
    "IJTM-CET-038": {
        "headline": "📡 Telekomunikasi: Pakar Fiber & 5G",
        "synopsis": "Industri 5G sedang meletup! Anda belajar menyambung kabel Fiber Optik (Splicing), memasang antena pemancar, dan menguji isyarat frekuensi. Kerjaya kritikal yang menghubungkan manusia. Kerja lasak tapi gaji sangat lumayan.",
        "jobs": ["Juruteknik Fiber Optik", "Penyelia Tapak Telekomunikasi", "Rigger Menara"]
    },
}

# --- FALLBACK FUNCTION ---
def get_course_details(cid, raw_name):
    # If we have the custom description, return it
    if cid in course_info:
        return course_info[cid]
    
    # Else, return a generic placeholder so the app doesn't crash
    return {
        "headline": f"{raw_name}",
        "synopsis": "Kursus ini menyediakan latihan teori dan amali yang komprehensif untuk menyediakan pelajar ke alam pekerjaan. (Maklumat terperinci sedang dikemaskini).",
        "jobs": ["Juruteknik", "Penyelia", "Usahawan"]
    }
