"""STPM: eligibility, ranking, search and the course page."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..bumiputera import resolve_bumiputera, search_bumiputera
from ..models import StpmCourse
from ..serializers import MascoOccupationSerializer, normalize_gender, normalize_nationality
from ..stpm_engine import check_stpm_eligibility
from ..stpm_ranking import get_result_framing, get_stpm_ranked_results


class StpmEligibilityCheckView(APIView):
    """POST /api/v1/stpm/eligibility/check/ — check STPM degree eligibility."""
    permission_classes = [AllowAny]

    def post(self, request):
        stpm_grades = request.data.get('stpm_grades')
        spm_grades = request.data.get('spm_grades', {})
        cgpa = request.data.get('cgpa')
        muet_band = request.data.get('muet_band')

        if not stpm_grades or cgpa is None or muet_band is None:
            return Response(
                {'error': 'stpm_grades, cgpa, and muet_band are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normalise demographics to the engine's values — the profile sends raw
        # 'male'/'malaysian', but the engine compares against 'Lelaki'/'Warganegara'.
        # Without this, every Malaysian-required course (all of them) is excluded → 0.
        nationality = normalize_nationality(request.data.get('nationality', 'Warganegara'))
        results = check_stpm_eligibility(
            stpm_grades=stpm_grades,
            spm_grades=spm_grades,
            cgpa=float(cgpa),
            muet_band=int(muet_band),
            gender=normalize_gender(request.data.get('gender', '')),
            nationality=nationality,
            colorblind=request.data.get('colorblind', False),
            # Bumi coverage Sprint B: course guide only; a foreign student is never Bumi.
            bumiputera=resolve_bumiputera(request.data.get('bumiputera'), nationality),
        )

        return Response({
            'eligible_courses': results,
            'total_eligible': len(results),
        })


class StpmRankingView(APIView):
    """POST /api/v1/stpm/ranking/ — rank eligible STPM courses by fit score."""
    permission_classes = [AllowAny]

    def post(self, request):
        courses = request.data.get('eligible_courses')
        if courses is None:
            return Response(
                {'error': 'eligible_courses is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        student_cgpa = float(request.data.get('student_cgpa', 0))
        signals = request.data.get('student_signals', {})

        # W11: When no quiz signals, derive RIASEC seed from STPM subjects
        # so pre-quiz ranking uses field alignment instead of CGPA-only.
        if not signals.get('riasec_seed'):
            stpm_subjects = request.data.get('stpm_subjects', [])
            if stpm_subjects:
                from ..stpm_quiz_engine import calculate_riasec_seed
                riasec_scores = calculate_riasec_seed(stpm_subjects)
                if riasec_scores:
                    # Convert {R: 5, I: 3} → {riasec_R: 5, riasec_I: 3}
                    seed = {
                        f'riasec_{k}': v for k, v in riasec_scores.items()
                    }
                    signals = {**signals, 'riasec_seed': seed}

        ranked = get_stpm_ranked_results(courses, student_cgpa, signals)
        framing = get_result_framing(signals)
        return Response({
            'ranked_courses': ranked,
            'total': len(ranked),
            'framing': framing,
        })


class StpmSearchView(APIView):
    """
    GET /api/v1/stpm/search/
    Browse and search STPM degree courses with filters.
    Public endpoint — no auth required.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        qs = StpmCourse.objects.select_related('requirement').filter(is_active=True)
        # Bumi-only courses: CourseSearchView's rule (Sprint B). `visible` also feeds the filters.
        visible = StpmCourse.objects.filter(is_active=True)
        if not search_bumiputera(request.query_params):
            qs = qs.exclude(requirement__req_bumiputera=True)
            visible = visible.exclude(requirement__req_bumiputera=True)

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(course_name__icontains=q)

        university = request.query_params.get('university', '').strip()
        if university:
            qs = qs.filter(university=university)

        stream = request.query_params.get('stream', '').strip()
        if stream:
            if stream in ('science', 'arts'):
                qs = qs.filter(stream__in=[stream, 'both'])
            else:
                qs = qs.filter(stream=stream)

        total_count = qs.count()

        try:
            limit = int(request.query_params.get('limit', 0)) or 10000
        except (ValueError, TypeError):
            limit = 24
        try:
            offset = max(int(request.query_params.get('offset', 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        courses = qs.order_by('university', 'course_name')[offset:offset + limit]

        results = []
        for prog in courses:
            req = getattr(prog, 'requirement', None)
            results.append({
                'course_id': prog.course_id,
                'course_name': prog.course_name,
                'university': prog.university,
                'stream': prog.stream,
                'min_cgpa': req.min_cgpa if req else 2.0,
                'min_muet_band': req.min_muet_band if req else 1,
                'req_interview': req.req_interview if req else False,
                'no_colorblind': req.no_colorblind if req else False,
            })

        filters = {
            'universities': sorted(
                visible.values_list('university', flat=True)
                .distinct().order_by('university')
            ),
            'streams': sorted(
                visible.values_list('stream', flat=True)
                .distinct().order_by('stream')
            ),
        }

        return Response({
            'courses': results,
            'total_count': total_count,
            'filters': filters,
        })


class StpmCourseDetailView(APIView):
    """GET /api/v1/stpm/courses/<course_id>/ — single STPM course detail."""
    permission_classes = [AllowAny]

    STPM_SUBJECT_FIELDS = [
        ('stpm_req_pa', 'Pengajian Am'),
        ('stpm_req_math_t', 'Mathematics (T)'),
        ('stpm_req_math_m', 'Mathematics (M)'),
        ('stpm_req_physics', 'Physics'),
        ('stpm_req_chemistry', 'Chemistry'),
        ('stpm_req_biology', 'Biology'),
        ('stpm_req_economics', 'Economics'),
        ('stpm_req_accounting', 'Accounting'),
        ('stpm_req_business', 'Business Studies'),
    ]

    SPM_PREREQ_FIELDS = [
        ('spm_credit_bm', 'Bahasa Melayu (credit)'),
        ('spm_pass_sejarah', 'Sejarah (pass)'),
        ('spm_credit_bi', 'Bahasa Inggeris (credit)'),
        ('spm_pass_bi', 'Bahasa Inggeris (pass)'),
        ('spm_credit_math', 'Matematik (credit)'),
        ('spm_pass_math', 'Matematik (pass)'),
        ('spm_credit_addmath', 'Matematik Tambahan (credit)'),
        ('spm_credit_science', 'Sains (credit)'),
    ]

    STPM_SUBJECT_DISPLAY = {
        'PA': 'Pengajian Am', 'MATH_T': 'Mathematics (T)', 'MATH_M': 'Mathematics (M)',
        'PHYSICS': 'Physics', 'CHEMISTRY': 'Chemistry', 'BIOLOGY': 'Biology',
        'ECONOMICS': 'Economics', 'ACCOUNTING': 'Accounting', 'BUSINESS': 'Business Studies',
        'BAHASA_MELAYU': 'Bahasa Melayu', 'BAHASA_CINA': 'Bahasa Cina',
        'BAHASA_TAMIL': 'Bahasa Tamil', 'BAHASA_ARAB': 'Bahasa Arab',
        'SEJARAH': 'Sejarah', 'GEOGRAFI': 'Geografi',
        'KESUSASTERAAN_MELAYU': 'Kesusasteraan Melayu',
        'LITERATURE_IN_ENGLISH': 'Literature in English',
        'SENI_VISUAL': 'Seni Visual', 'SAINS_SUKAN': 'Sains Sukan', 'ICT': 'ICT',
        'SYARIAH': 'Syariah', 'USULUDDIN': 'Usuluddin', 'TAHFIZ_AL_QURAN': 'Tahfiz Al-Quran',
    }

    SPM_SUBJECT_DISPLAY = {
        'BM': 'Bahasa Melayu', 'BI': 'Bahasa Inggeris', 'MATH': 'Matematik',
        'ADD_MATH': 'Matematik Tambahan', 'SEJARAH': 'Sejarah',
        'SCIENCE_SPM': 'Sains', 'SAINS_TAMBAHAN_SPM': 'Sains Tambahan',
        'APPLIED_SCIENCE_SPM': 'Sains Gunaan',
        'PHYSICS_SPM': 'Fizik', 'CHEMISTRY_SPM': 'Kimia', 'BIOLOGY_SPM': 'Biologi',
        'EKONOMI_SPM': 'Ekonomi', 'EKONOMI_ASAS_SPM': 'Ekonomi Asas',
        'PRINSIP_PERAKAUNAN_SPM': 'Prinsip Perakaunan',
        'PERNIAGAAN_SPM': 'Perniagaan', 'PERDAGANGAN_SPM': 'Perdagangan',
        'GEOGRAFI_SPM': 'Geografi',
        'PENDIDIKAN_MORAL_SPM': 'Pendidikan Moral',
        'PENDIDIKAN_ISLAM_SPM': 'Pendidikan Islam',
        'ICT_SPM': 'ICT', 'SAINS_KOMPUTER_SPM': 'Sains Komputer',
        'PENDIDIKAN_SENI_VISUAL_SPM': 'Pendidikan Seni Visual',
        'LUKISAN_KEJURUTERAAN_SPM': 'Lukisan Kejuruteraan',
        'GRAFIK_KOMUNIKASI_TEKNIKAL_SPM': 'Grafik Komunikasi Teknikal',
        'TEKNOLOGI_KEJURUTERAAN_SPM': 'Teknologi Kejuruteraan',
        'REKA_CIPTA_SPM': 'Reka Cipta',
        'SAINS_SUKAN_SPM': 'Sains Sukan',
        'PENGETAHUAN_SAINS_SUKAN_SPM': 'Pengetahuan Sains Sukan',
        'SAINS_RUMAH_TANGGA_SPM': 'Sains Rumah Tangga',
        'EKONOMI_RUMAH_TANGGA_SPM': 'Ekonomi Rumah Tangga',
        'SAINS_PERTANIAN_SPM': 'Sains Pertanian',
        'PERTANIAN_SPM': 'Pertanian',
        'PENGAJIAN_KEUSAHAWANAN_SPM': 'Pengajian Keusahawanan',
        'BAHASA_TAMIL_SPM': 'Bahasa Tamil', 'BAHASA_CINA_SPM': 'Bahasa Cina',
        'BAHASA_ARAB_SPM': 'Bahasa Arab', 'BAHASA_ARAB_TINGGI_SPM': 'Bahasa Arab Tinggi',
        'BAHASA_ARAB_MUASIRAH_SPM': "Al-Lughah Al-'Arabiah Al-Mu'asirah",
        'BAHASA_IBAN_SPM': 'Bahasa Iban', 'BAHASA_KADAZANDUSUN_SPM': 'Bahasa Kadazandusun',
        'BAHASA_SEMAI_SPM': 'Bahasa Semai',
        'KESUSASTERAAN_MELAYU_SPM': 'Kesusasteraan Melayu',
        'KESUSASTERAAN_INGGERIS_SPM': 'Kesusasteraan Inggeris',
        'KESUSASTERAAN_TAMIL_SPM': 'Kesusasteraan Tamil',
        'KESUSASTERAAN_CINA_SPM': 'Kesusasteraan Cina',
        'LITERATURE_IN_ENGLISH_SPM': 'Literature in English',
        'REKA_BENTUK_GRAFIK_SPM': 'Reka Bentuk Grafik',
        'REKA_BENTUK_GRAFIK_DIGITAL_SPM': 'Reka Bentuk Grafik Digital',
        'KOMUNIKASI_VISUAL_SPM': 'Komunikasi Visual',
        'PRODUKSI_MULTIMEDIA_SPM': 'Produksi Multimedia',
        'GRAFIK_BERKOMPUTER_SPM': 'Grafik Berkomputer',
        'PENDIDIKAN_SYARIAH_ISLAMIAH_SPM': 'Pendidikan Syariah Islamiah',
        'PENDIDIKAN_AL_QURAN_SPM': 'Pendidikan Al-Quran dan Al-Sunnah',
        'TASAWWUR_ISLAM_SPM': 'Tasawwur Islam',
        'AL_SYARIAH_SPM': 'Al-Syariah', 'USUL_AL_DIN_SPM': 'Usul Al-Din',
        'MANAHIJ_SPM': "Manahij Al-'Ulum Al-Islamiah", 'AL_ADAB_SPM': 'Al-Adab Wa Al-Balaghah',
        'TURATH_BAHASA_ARAB_SPM': 'Turath Bahasa Arab',
        'TURATH_DIRASAT_ISLAMIAH_SPM': 'Turath Dirasat Islamiah',
        'TURATH_AL_QURAN_SPM': 'Turath Al-Quran dan Al-Sunnah',
        'MAHARAT_AL_QURAN_SPM': 'Maharat Al-Quran',
        'HIFZ_AL_QURAN_SPM': 'Hifz Al-Quran',
        'PRINSIP_ELEKTRIK_SPM': 'Prinsip Elektrik',
        'APLIKASI_ELEKTRIK_SPM': 'Aplikasi Elektrik',
        'APLIKASI_KOMPUTER_PERNIAGAAN_SPM': 'Aplikasi Komputer Perniagaan',
        'KEJURUTERAAN_AWAM_SPM': 'Kejuruteraan Awam',
        'KEJURUTERAAN_EE_SPM': 'Kejuruteraan Elektrik & Elektronik',
        'KEJURUTERAAN_MEKANIKAL_SPM': 'Kejuruteraan Mekanikal',
        'TEKNOLOGI_BINAAN_SPM': 'Teknologi Binaan',
        'TEKNOLOGI_BINAAN_BANGUNAN_SPM': 'Teknologi Binaan Bangunan',
        'HIASAN_DALAMAN_SPM': 'Hiasan Dalaman',
        'BAHAN_BINAAN_SPM': 'Bahan Binaan',
        'KATERING_SPM': 'Katering', 'KIMPALAN_SPM': 'Kimpalan',
        'MENSERVIS_AUTOMOBIL_SPM': 'Menservis Automobil',
        'MENSERVIS_MOTOSIKAL_SPM': 'Menservis Motosikal',
        'MENSERVIS_ELEKTRIK_SPM': 'Menservis Elektrik',
        'MENSERVIS_PENYEJUKAN_SPM': 'Menservis Penyejukan',
        'PEMBINAAN_DOMESTIK_SPM': 'Pembinaan Domestik',
        'PEMBUATAN_PERABOT_SPM': 'Pembuatan Perabot',
        'PEMESINAN_BERKOMPUTER_SPM': 'Pemesinan Berkomputer',
        'PEMPROSESAN_MAKANAN_SPM': 'Pemprosesan Makanan',
        'PENDAWAIAN_DOMESTIK_SPM': 'Pendawaian Domestik',
        'KERJA_PAIP_SPM': 'Kerja Paip',
        'REKAAN_JAHITAN_SPM': 'Rekaan Jahitan',
        'PENJAGAAN_MUKA_SPM': 'Penjagaan Muka',
        'ASUHAN_KANAK_KANAK_SPM': 'Asuhan Kanak-kanak',
        'GERONTOLOGI_SPM': 'Gerontologi',
        'AKUAKULTUR_SPM': 'Akuakultur',
        'LANDSKAP_DAN_NURSERI_SPM': 'Landskap dan Nurseri',
        'TANAMAN_MAKANAN_SPM': 'Tanaman Makanan',
        'ASAS_KELESTARIAN_SPM': 'Asas Kelestarian',
        'SENI_REKA_TANDA_SPM': 'Seni Reka Tanda',
        'PRODUKSI_REKA_TANDA_SPM': 'Produksi Reka Tanda',
        'REKA_BENTUK_INDUSTRI_SPM': 'Reka Bentuk Industri',
        'REKA_BENTUK_KRAF_SPM': 'Reka Bentuk Kraf',
        'MULTIMEDIA_KREATIF_SPM': 'Multimedia Kreatif',
        'SENI_HALUS_3D_SPM': 'Seni Halus 3D',
        'SENI_HALUS_2D_SPM': 'Seni Halus 2D',
        'SEJARAH_PENGURUSAN_SENI_SPM': 'Sejarah Pengurusan Seni',
        'PENDIDIKAN_MUZIK_SPM': 'Pendidikan Muzik',
        'AURAL_TEORI_MUZIK_SPM': 'Aural Teori Muzik',
        'MUZIK_KOMPUTER_SPM': 'Muzik Komputer',
        'ALAT_MUZIK_UTAMA_SPM': 'Alat Muzik Utama',
        'PRODUKSI_SENI_PERSEMBAHAN_SPM': 'Produksi Seni Persembahan',
        'SINOGRAFI_SPM': 'Sinografi', 'PENULISAN_SKRIP_SPM': 'Penulisan Skrip',
        'LAKONAN_SPM': 'Lakonan',
        'APRESIASI_TARI_SPM': 'Apresiasi Tari',
        'KOREOGRAFI_TARI_SPM': 'Koreografi Tari',
        'TARIAN_SPM': 'Tarian',
        'LUKISAN_SPM': 'Lukisan',
    }

    @staticmethod
    def _build_groups_display(groups_json, display_map):
        """Transform subject group JSON into display-ready list."""
        if not groups_json:
            return []
        result = []
        for group in groups_json:
            if not isinstance(group, dict):
                continue
            entry = {
                'min_count': group.get('min_count', 1),
                'min_grade': group.get('min_grade', 'C'),
                'any_subject': group.get('subjects') is None,
                'subjects': [],
                'exclude': [],
            }
            if group.get('subjects'):
                entry['subjects'] = [
                    display_map.get(code, code.replace('_', ' ').title())
                    for code in group['subjects']
                ]
            if group.get('exclude'):
                entry['exclude'] = list(dict.fromkeys(
                    display_map.get(code, code.replace('_', ' ').title())
                    for code in group['exclude']
                ))
            result.append(entry)
        return result

    def get(self, request, course_id):
        try:
            prog = StpmCourse.objects.select_related('requirement', 'institution').prefetch_related(
                'career_occupations'
            ).get(course_id=course_id)
        except StpmCourse.DoesNotExist:
            return Response(
                {'error': 'Course not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        req = getattr(prog, 'requirement', None)

        stpm_subjects = []
        if req:
            for field_name, label in self.STPM_SUBJECT_FIELDS:
                if getattr(req, field_name, False):
                    stpm_subjects.append(label)

        spm_prerequisites = []
        if req:
            for field_name, label in self.SPM_PREREQ_FIELDS:
                if getattr(req, field_name, False):
                    spm_prerequisites.append(label)

        requirements = {}
        if req:
            requirements = {
                'min_cgpa': req.min_cgpa,
                'min_muet_band': req.min_muet_band,
                'stpm_min_subjects': req.stpm_min_subjects,
                'stpm_min_grade': req.stpm_min_grade,
                'stpm_subjects': stpm_subjects,
                'stpm_subject_group': req.stpm_subject_group,
                'spm_prerequisites': spm_prerequisites,
                'spm_subject_group': req.spm_subject_group,
                'stpm_subject_groups_display': self._build_groups_display(
                    req.stpm_subject_group, self.STPM_SUBJECT_DISPLAY
                ),
                'spm_subject_groups_display': self._build_groups_display(
                    req.spm_subject_group, self.SPM_SUBJECT_DISPLAY
                ),
                'req_interview': req.req_interview,
                'no_colorblind': req.no_colorblind,
                'req_medical_fitness': req.req_medical_fitness,
                'req_malaysian': req.req_malaysian,
                'req_bumiputera': req.req_bumiputera,
                'req_male': req.req_male,
                'req_female': req.req_female,
                'single': req.single,
                'no_disability': req.no_disability,
            }

        # Use FK to get institution data (no extra query thanks to select_related)
        institution_data = None
        inst = prog.institution
        if inst:
            institution_data = {
                'institution_id': inst.institution_id,
                'institution_name': inst.institution_name,
                'acronym': inst.acronym or '',
                'type': inst.type or '',
                'category': inst.category or '',
                'state': inst.state or '',
                'url': inst.url or '',
            }

        return Response({
            'course_id': prog.course_id,
            'course_name': prog.course_name,
            'university': prog.university,
            'stream': prog.stream,
            'field': prog.field,
            'field_key': prog.field_key_id or '',
            'description': prog.description,
            'headline': prog.headline,
            'merit_score': prog.merit_score,
            'mohe_url': prog.mohe_url or '',
            'requirements': requirements,
            'institution': institution_data,
            'career_occupations': MascoOccupationSerializer(
                prog.career_occupations.all(), many=True
            ).data,
        })
