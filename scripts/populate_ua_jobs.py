"""
Populate jobs field for UA courses based on MASCO occupation mapping.
Maps course names to relevant career paths.
"""

import pandas as pd
import re

# MASCO-based job mapping by course field pattern
# Format: (pattern, [list of jobs in BM/EN])
COURSE_JOB_MAPPING = [
    # Engineering - Civil
    (r'kejuruteraan awam', [
        'Jurutera Awam', 'Civil Engineer',
        'Pengurus Projek Pembinaan', 'Construction Project Manager'
    ]),

    # Engineering - Electrical
    (r'kejuruteraan elektrik(?! dan)', [
        'Jurutera Elektrik', 'Electrical Engineer',
        'Juruteknik Elektrik', 'Electrical Technician'
    ]),

    # Engineering - Electronics
    (r'kejuruteraan elektronik|elektrik dan elektronik', [
        'Jurutera Elektronik', 'Electronics Engineer',
        'Jurutera Telekomunikasi', 'Telecommunications Engineer'
    ]),

    # Engineering - Mechanical
    (r'kejuruteraan mekanikal', [
        'Jurutera Mekanikal', 'Mechanical Engineer',
        'Jurutera Automotif', 'Automotive Engineer'
    ]),

    # Engineering - Chemical
    (r'kejuruteraan kimia', [
        'Jurutera Kimia', 'Chemical Engineer',
        'Jurutera Proses', 'Process Engineer'
    ]),

    # Engineering - Manufacturing
    (r'kejuruteraan pembuatan|teknologi kejuruteraan pembuatan|teknologi pembuatan', [
        'Jurutera Pembuatan', 'Manufacturing Engineer',
        'Jurutera Kualiti', 'Quality Engineer'
    ]),

    # Engineering - Mechatronics
    (r'kejuruteraan mekatronik', [
        'Jurutera Mekatronik', 'Mechatronics Engineer',
        'Jurutera Automasi', 'Automation Engineer'
    ]),

    # Engineering - Computer
    (r'kejuruteraan komputer', [
        'Jurutera Perisian', 'Software Engineer',
        'Jurutera Sistem', 'Systems Engineer'
    ]),

    # Engineering - Environmental
    (r'kejuruteraan alam sekitar', [
        'Jurutera Alam Sekitar', 'Environmental Engineer',
        'Pegawai Pengurusan Sisa', 'Waste Management Officer'
    ]),

    # Engineering - Materials
    (r'kejuruteraan bahan', [
        'Jurutera Bahan', 'Materials Engineer',
        'Saintis Bahan', 'Materials Scientist'
    ]),

    # Engineering - Polymer
    (r'kejuruteraan polimer', [
        'Jurutera Polimer', 'Polymer Engineer',
        'Jurutera Plastik', 'Plastics Engineer'
    ]),

    # Engineering - Agricultural
    (r'kejuruteraan teknologi pertanian', [
        'Jurutera Pertanian', 'Agricultural Engineer',
        'Pakar Teknologi Pertanian', 'Agricultural Technology Specialist'
    ]),

    # IT - Computer Science
    (r'sains komputer', [
        'Pembangun Perisian', 'Software Developer',
        'Pengaturcara', 'Programmer',
        'Penganalisis Sistem', 'Systems Analyst'
    ]),

    # IT - Information Technology
    (r'teknologi maklumat', [
        'Pegawai IT', 'IT Officer',
        'Pentadbir Sistem', 'System Administrator',
        'Pakar Sokongan Teknikal', 'Technical Support Specialist'
    ]),

    # IT - Game Development
    (r'pembangunan permainan', [
        'Pembangun Permainan', 'Game Developer',
        'Pereka Permainan', 'Game Designer'
    ]),

    # IT - Animation
    (r'animasi', [
        'Animator', 'Animator',
        'Artis 3D', '3D Artist',
        'Pereka Grafik', 'Graphic Designer'
    ]),

    # Business - Accounting
    (r'perakaunan', [
        'Akauntan', 'Accountant',
        'Juruaudit', 'Auditor',
        'Penganalisis Kewangan', 'Financial Analyst'
    ]),

    # Business - Marketing
    (r'pemasaran', [
        'Eksekutif Pemasaran', 'Marketing Executive',
        'Pengurus Jenama', 'Brand Manager',
        'Pakar Pemasaran Digital', 'Digital Marketing Specialist'
    ]),

    # Business - HR
    (r'sumber manusia', [
        'Eksekutif Sumber Manusia', 'HR Executive',
        'Pengurus HR', 'HR Manager',
        'Pakar Pengambilan', 'Recruitment Specialist'
    ]),

    # Business - Finance
    (r'kewangan', [
        'Eksekutif Kewangan', 'Finance Executive',
        'Penganalisis Kewangan', 'Financial Analyst',
        'Perancang Kewangan', 'Financial Planner'
    ]),

    # Business - Banking
    (r'pengajian bank', [
        'Pegawai Bank', 'Bank Officer',
        'Eksekutif Perbankan', 'Banking Executive',
        'Penasihat Kewangan', 'Financial Advisor'
    ]),

    # Business - Insurance
    (r'pengajian insurans', [
        'Ejen Insurans', 'Insurance Agent',
        'Penaja Jamin', 'Underwriter',
        'Penganalisis Risiko', 'Risk Analyst'
    ]),

    # Business - International Business
    (r'perniagaan antarabangsa', [
        'Eksekutif Perdagangan', 'Trade Executive',
        'Pengurus Eksport', 'Export Manager',
        'Pakar Perniagaan Antarabangsa', 'International Business Specialist'
    ]),

    # Business - Entrepreneurship
    (r'keusahawanan', [
        'Usahawan', 'Entrepreneur',
        'Pengurus Perniagaan', 'Business Manager',
        'Pemilik Perniagaan', 'Business Owner'
    ]),

    # Business - Administration / Business Management
    (r'pentadbiran perniagaan|pengurusan perniagaan', [
        'Eksekutif Pentadbiran', 'Administrative Executive',
        'Pengurus Pejabat', 'Office Manager',
        'Pentadbir Perniagaan', 'Business Administrator'
    ]),

    # Business - Logistics
    (r'pengurusan logistik', [
        'Pengurus Logistik', 'Logistics Manager',
        'Perancang Rantaian Bekalan', 'Supply Chain Planner',
        'Eksekutif Penghantaran', 'Shipping Executive'
    ]),

    # Business - E-Commerce
    (r'e-commerce', [
        'Pengurus E-Dagang', 'E-Commerce Manager',
        'Pakar Pemasaran Digital', 'Digital Marketing Specialist',
        'Penganalisis E-Perniagaan', 'E-Business Analyst'
    ]),

    # Healthcare - Physiotherapy
    (r'fisioterapi', [
        'Ahli Fisioterapi', 'Physiotherapist',
        'Pakar Pemulihan', 'Rehabilitation Specialist'
    ]),

    # Healthcare - Nursing
    (r'kejururawatan', [
        'Jururawat', 'Nurse',
        'Jururawat Berdaftar', 'Registered Nurse',
        'Jururawat Klinikal', 'Clinical Nurse'
    ]),

    # Healthcare - Radiography
    (r'radiografi', [
        'Radiografer', 'Radiographer',
        'Juruteknik X-Ray', 'X-Ray Technician',
        'Juruteknik Pengimejan Perubatan', 'Medical Imaging Technician'
    ]),

    # Healthcare - Medical Lab
    (r'teknologi makmal perubatan|makmal perubatan', [
        'Juruteknologi Makmal Perubatan', 'Medical Lab Technologist',
        'Saintis Makmal', 'Lab Scientist'
    ]),

    # Agriculture - General
    (r'pertanian(?! teknologi)', [
        'Pegawai Pertanian', 'Agricultural Officer',
        'Pakar Agronomi', 'Agronomist',
        'Pengurus Ladang', 'Farm Manager'
    ]),

    # Agriculture - Fisheries
    (r'perikanan', [
        'Pegawai Perikanan', 'Fisheries Officer',
        'Pakar Akuakultur', 'Aquaculture Specialist',
        'Pengurus Ternakan Ikan', 'Fish Farm Manager'
    ]),

    # Agriculture - Forestry
    (r'perhutanan', [
        'Pegawai Perhutanan', 'Forestry Officer',
        'Ahli Silvikultur', 'Silviculturist',
        'Pengurus Hutan', 'Forest Manager'
    ]),

    # Agriculture - Agribusiness
    (r'perniagaantani', [
        'Eksekutif Agroperniagaan', 'Agribusiness Executive',
        'Pengurus Pemasaran Pertanian', 'Agricultural Marketing Manager'
    ]),

    # Agriculture - Plantation
    (r'perladangan', [
        'Pengurus Ladang', 'Plantation Manager',
        'Pegawai Tanaman', 'Crop Officer'
    ]),

    # Agriculture - Veterinary
    (r'kesihatan haiwan|peternakan', [
        'Juruteknik Veterinar', 'Veterinary Technician',
        'Pembantu Veterinar', 'Veterinary Assistant',
        'Pegawai Ternakan', 'Livestock Officer'
    ]),

    # Arts - Music
    (r'muzik', [
        'Pemuzik', 'Musician',
        'Guru Muzik', 'Music Teacher',
        'Komposer', 'Composer'
    ]),

    # Arts - Dance
    (r'tari', [
        'Penari', 'Dancer',
        'Koreografer', 'Choreographer',
        'Pengajar Tarian', 'Dance Instructor'
    ]),

    # Arts - Theatre
    (r'teater', [
        'Pelakon', 'Actor',
        'Pengarah Teater', 'Theatre Director',
        'Pengurus Produksi', 'Production Manager'
    ]),

    # Arts - Industrial Design
    (r'rekabentuk perindustrian', [
        'Pereka Perindustrian', 'Industrial Designer',
        'Pereka Produk', 'Product Designer'
    ]),

    # Language - Ethnic Languages
    (r'bahasa etnik', [
        'Penterjemah', 'Translator',
        'Guru Bahasa', 'Language Teacher',
        'Pegawai Warisan Budaya', 'Cultural Heritage Officer'
    ]),

    # Language - English
    (r'bahasa inggeris', [
        'Guru Bahasa Inggeris', 'English Teacher',
        'Penterjemah', 'Translator',
        'Penulis Kandungan', 'Content Writer'
    ]),

    # Science - General
    (r'^diploma sains$|sains gunaan|sains industri', [
        'Saintis', 'Scientist',
        'Juruteknik Makmal', 'Lab Technician',
        'Pembantu Penyelidik', 'Research Assistant'
    ]),

    # Science - Mathematics
    (r'sains \(matematik\)', [
        'Guru Matematik', 'Mathematics Teacher',
        'Penganalisis Data', 'Data Analyst',
        'Aktuari', 'Actuary'
    ]),

    # Science - Lab Technology
    (r'teknologi makmal(?! perubatan)', [
        'Juruteknologi Makmal', 'Lab Technologist',
        'Juruteknik Makmal', 'Lab Technician',
        'Penganalisis Kualiti', 'Quality Analyst'
    ]),

    # Sports Science
    (r'sains sukan|kecergasan', [
        'Saintis Sukan', 'Sports Scientist',
        'Jurulatih', 'Coach',
        'Pengajar Kecergasan', 'Fitness Instructor'
    ]),

    # Islamic Studies
    (r'pengajian islam|turath islami', [
        'Guru Pendidikan Islam', 'Islamic Studies Teacher',
        'Pegawai Hal Ehwal Islam', 'Islamic Affairs Officer'
    ]),

    # Islamic Studies - Tahfiz
    (r'tahfiz', [
        'Guru Al-Quran', 'Quran Teacher',
        'Imam', 'Imam',
        'Pegawai Agama', 'Religious Officer'
    ]),

    # Early Childhood Education
    (r'pendidikan awal kanak-kanak', [
        'Guru Tadika', 'Kindergarten Teacher',
        'Pendidik Awal Kanak-Kanak', 'Early Childhood Educator',
        'Pengurus Pusat Asuhan', 'Childcare Center Manager'
    ]),

    # Safety & Health
    (r'keselamatan dan kesihatan', [
        'Pegawai Keselamatan', 'Safety Officer',
        'Pegawai K3', 'OSH Officer',
        'Pengurus HSE', 'HSE Manager'
    ]),

    # Human Development
    (r'pembangunan manusia', [
        'Pegawai Pembangunan Komuniti', 'Community Development Officer',
        'Kaunselor', 'Counselor',
        'Pegawai Kebajikan', 'Welfare Officer'
    ]),

    # Foundation/Asasi programs - general pathways
    (r'^asasi kejuruteraan', [
        'Jurutera', 'Engineer',
        'Juruteknik', 'Technician'
    ]),

    (r'^asasi sains$|^asasi stem|tamhidi sains', [
        'Saintis', 'Scientist',
        'Penyelidik', 'Researcher',
        'Doktor', 'Doctor'
    ]),

    (r'^asasi sains pertanian', [
        'Saintis Pertanian', 'Agricultural Scientist',
        'Pegawai Pertanian', 'Agricultural Officer'
    ]),

    (r'^asasi sains sosial', [
        'Pegawai Penyelidik', 'Research Officer',
        'Penganalisis Dasar', 'Policy Analyst',
        'Pekerja Sosial', 'Social Worker'
    ]),

    (r'^asasi pengurusan|program asasi pengurusan', [
        'Eksekutif Pengurusan', 'Management Executive',
        'Pentadbir', 'Administrator'
    ]),

    (r'^asasi perubatan', [
        'Doktor', 'Doctor',
        'Pakar Perubatan', 'Medical Specialist'
    ]),

    (r'^asasipintar', [
        'Penyelidik', 'Researcher',
        'Saintis', 'Scientist',
        'Akademik', 'Academic'
    ]),
]

def get_jobs_for_course(course_name: str) -> str:
    """Map course name to relevant jobs based on MASCO categories."""
    name_lower = course_name.lower().strip()

    for pattern, jobs in COURSE_JOB_MAPPING:
        if re.search(pattern, name_lower):
            # Return first 3-4 jobs, comma-separated
            return ', '.join(jobs[:4])

    return ''  # No match found

def main():
    import sys

    # Check for --dry-run flag
    dry_run = '--dry-run' in sys.argv

    # Load courses.csv
    courses_df = pd.read_csv('data/courses.csv')

    # Track unmapped courses
    unmapped = []
    mapped_count = 0
    updated_count = 0

    # Process UA courses only
    for idx, row in courses_df.iterrows():
        course_id = row['course_id']

        # Only process UA courses (start with 'U')
        if not str(course_id).startswith('U'):
            continue

        course_name = row['course']
        if not course_name or pd.isna(course_name):
            continue

        # Get jobs mapping
        jobs = get_jobs_for_course(course_name)

        if jobs:
            current_career = row.get('career', '')
            if pd.isna(current_career) or current_career == '' or current_career.strip() == '':
                # Update the career column
                courses_df.at[idx, 'career'] = jobs
                print(f"[UPDATE] {course_id}: {course_name[:35]:<35} -> {jobs[:50]}")
                updated_count += 1
            else:
                print(f"[SKIP]   {course_id}: Already has career data")
            mapped_count += 1
        else:
            unmapped.append((course_id, course_name))

    print(f"\n{'='*70}")
    print(f"Mapped: {mapped_count} courses")
    print(f"Updated: {updated_count} courses")
    print(f"Unmapped: {len(unmapped)} courses")

    if unmapped:
        print(f"\nUNMAPPED COURSES (need MASCO lookup):")
        for cid, cname in unmapped:
            print(f"  - {cid}: {cname}")

    # Save if not dry run
    if not dry_run and updated_count > 0:
        courses_df.to_csv('data/courses.csv', index=False)
        print(f"\nSaved {updated_count} updates to data/courses.csv")
    elif dry_run:
        print(f"\n[DRY RUN] No changes written. Run without --dry-run to apply.")

if __name__ == '__main__':
    main()
