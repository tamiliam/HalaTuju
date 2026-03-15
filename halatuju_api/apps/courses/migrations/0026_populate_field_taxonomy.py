"""
Data migration: Populate FieldTaxonomy with 37 canonical field entries.

Groups (~9 parent keys) are inserted first, then leaf entries reference them.
"""
from django.db import migrations


# Parent groups (no parent_key)
GROUPS = [
    ('engineering', 'Engineering & Technical', 'Kejuruteraan & Teknikal', 'பொறியியல் & தொழில்நுட்பம்', 'kejuruteraan-am', 1),
    ('it', 'IT & Digital', 'IT & Digital', 'IT & டிஜிட்டல்', 'it-perisian', 2),
    ('business', 'Business & Commerce', 'Perniagaan & Perdagangan', 'வணிகம் & வர்த்தகம்', 'perniagaan', 3),
    ('hospitality', 'Hospitality & Lifestyle', 'Hospitaliti & Gaya Hidup', 'விருந்தோம்பல் & வாழ்க்கை முறை', 'hospitaliti-pelancongan', 4),
    ('agriculture', 'Agriculture & Environment', 'Pertanian & Alam Sekitar', 'வேளாண்மை & சுற்றுச்சூழல்', 'pertanian-agro', 5),
    ('design', 'Design & Creative', 'Reka Bentuk & Kreatif', 'வடிவமைப்பு & படைப்பாற்றல்', 'senireka-fesyen', 6),
    ('health', 'Health & Medical', 'Kesihatan & Perubatan', 'சுகாதாரம் & மருத்துவம்', 'perubatan-kesihatan', 7),
    ('sciences', 'Sciences', 'Sains', 'அறிவியல்', 'sains-stem', 8),
    ('education', 'Education', 'Pendidikan', 'கல்வி', 'pendidikan-stem', 9),
    ('humanities', 'Social Sciences & Humanities', 'Sains Sosial & Kemanusiaan', 'சமூக அறிவியல் & மானுடவியல்', 'umum-kemanusiaan', 10),
]

# Leaf entries: (key, name_en, name_ms, name_ta, image_slug, parent_group_key, sort_order)
FIELDS = [
    # Engineering & Technical (10)
    ('mekanikal', 'Mechanical & Manufacturing', 'Mekanikal & Pembuatan', 'எந்திரவியல் & உற்பத்தி', 'mekanikal-am', 'engineering', 11),
    ('automotif', 'Automotive & Vehicles', 'Automotif & Kenderaan', 'வாகனவியல் & வாகனங்கள்', 'automotif', 'engineering', 12),
    ('elektrik', 'Electrical & Electronics', 'Elektrik & Elektronik', 'மின்சாரம் & மின்னணுவியல்', 'elektrik-kuasa', 'engineering', 13),
    ('sivil', 'Civil, Architecture & Construction', 'Sivil, Seni Bina & Pembinaan', 'சிவில், கட்டடக்கலை & கட்டுமானம்', 'sivil-struktur', 'engineering', 14),
    ('kimia-proses', 'Chemical & Process Engineering', 'Kejuruteraan Kimia & Proses', 'வேதியியல் & செயல்முறை பொறியியல்', 'kimia-alam-sekitar', 'engineering', 15),
    ('minyak-gas', 'Oil, Gas & Energy', 'Minyak, Gas & Tenaga', 'எண்ணெய், எரிவாயு & ஆற்றல்', 'minyak-gas', 'engineering', 16),
    ('aero', 'Aerospace & Aviation', 'Aero & Penerbangan', 'விண்வெளி & வானூர்தி', 'aero-penerbangan', 'engineering', 17),
    ('marin', 'Marine & Shipbuilding', 'Marin & Perkapalan', 'கடல்சார் & கப்பல் கட்டுமானம்', 'marin-perkapalan', 'engineering', 18),
    ('mekatronik', 'Mechatronics & Automation', 'Mekatronik & Automasi', 'மெக்காட்ரானிக்ஸ் & தன்னியக்கம்', 'mekanikal-mekatronik', 'engineering', 19),
    ('kejuruteraan-am', 'General Engineering', 'Kejuruteraan Am', 'பொது பொறியியல்', 'kejuruteraan-am', 'engineering', 20),

    # IT & Digital (3)
    ('it-perisian', 'IT & Software', 'Teknologi Maklumat & Perisian', 'தகவல் தொழில்நுட்பம் & மென்பொருள்', 'it-perisian', 'it', 21),
    ('it-rangkaian', 'Networking & Cybersecurity', 'Rangkaian & Keselamatan Siber', 'வலையமைப்பு & சைபர் பாதுகாப்பு', 'it-rangkaian', 'it', 22),
    ('multimedia', 'Multimedia, Animation & Digital Arts', 'Multimedia, Animasi & Seni Digital', 'பல்லூடகம், அசைவூட்டம் & டிஜிட்டல் கலை', 'multimedia-animasi', 'it', 23),

    # Business & Commerce (3)
    ('perniagaan', 'Business & Entrepreneurship', 'Perniagaan & Keusahawanan', 'வணிகம் & தொழில்முனைவு', 'perniagaan', 'business', 24),
    ('perakaunan', 'Accounting & Finance', 'Perakaunan & Kewangan', 'கணக்கியல் & நிதி', 'perakaunan-kewangan', 'business', 25),
    ('pengurusan', 'Management & Logistics', 'Pengurusan & Logistik', 'மேலாண்மை & தளவாடம்', 'pengurusan-logistik', 'business', 26),

    # Hospitality & Lifestyle (3)
    ('hospitaliti', 'Hospitality & Tourism', 'Hospitaliti & Pelancongan', 'விருந்தோம்பல் & சுற்றுலா', 'hospitaliti-pelancongan', 'hospitality', 27),
    ('kulinari', 'Culinary & Food Science', 'Kulinari & Sains Makanan', 'சமையற்கலை & உணவு அறிவியல்', 'kulinari-makanan', 'hospitality', 28),
    ('kecantikan', 'Beauty & Lifestyle', 'Kecantikan & Gaya Hidup', 'அழகு & வாழ்க்கை முறை', 'kecantikan-gayahidup', 'hospitality', 29),

    # Agriculture & Environment (2)
    ('pertanian', 'Agriculture & Agro-Industry', 'Pertanian & Agro-Industri', 'வேளாண்மை & வேளாண் தொழில்', 'pertanian-agro', 'agriculture', 30),
    ('alam-sekitar', 'Environmental Science', 'Sains Alam Sekitar', 'சுற்றுச்சூழல் அறிவியல்', 'alam-sekitar', 'agriculture', 31),

    # Design & Creative (2)
    ('senireka', 'Design & Fashion', 'Seni Reka & Fesyen', 'வடிவமைப்பு & நாகரீகம்', 'senireka-fesyen', 'design', 32),
    ('senibina', 'Architecture & Landscape', 'Seni Bina & Landskap', 'கட்டடக்கலை & இயற்கை அமைப்பு', 'senibina-landskap', 'design', 33),

    # Health & Medical (4)
    ('perubatan', 'Medicine', 'Perubatan', 'மருத்துவம்', 'perubatan-kesihatan', 'health', 34),
    ('farmasi', 'Pharmacy', 'Farmasi', 'மருந்தாளுநர்', 'farmasi', 'health', 35),
    ('kejururawatan', 'Nursing & Allied Health', 'Kejururawatan & Kesihatan Bersekutu', 'செவிலியம் & துணை சுகாதாரம்', 'kejururawatan', 'health', 36),
    ('pergigian', 'Dentistry', 'Pergigian', 'பல் மருத்துவம்', 'pergigian', 'health', 37),

    # Sciences (3)
    ('sains-hayat', 'Life Sciences', 'Sains Hayat (Biologi, Kimia)', 'உயிர் அறிவியல் (உயிரியல், வேதியியல்)', 'sains-stem', 'sciences', 38),
    ('sains-fizikal', 'Physical Sciences', 'Sains Fizikal (Fizik, Matematik)', 'இயற்பியல் அறிவியல் (இயற்பியல், கணிதம்)', 'sains-fizikal', 'sciences', 39),
    ('sains-data', 'Data Science & Statistics', 'Sains Data & Statistik', 'தரவு அறிவியல் & புள்ளியியல்', 'sains-data', 'sciences', 40),

    # Education (1)
    ('pendidikan', 'Education & Teacher Training', 'Pendidikan & Latihan Guru', 'கல்வி & ஆசிரியர் பயிற்சி', 'pendidikan-stem', 'education', 41),

    # Social Sciences & Humanities (5)
    ('undang-undang', 'Law', 'Undang-undang', 'சட்டம்', 'undang-undang', 'humanities', 42),
    ('sains-sosial', 'Social Sciences & Psychology', 'Sains Sosial & Psikologi', 'சமூக அறிவியல் & உளவியல்', 'sains-sosial', 'humanities', 43),
    ('komunikasi', 'Communication & Media', 'Komunikasi & Media', 'தொடர்பாடல் & ஊடகம்', 'komunikasi', 'humanities', 44),
    ('bahasa', 'Languages & Linguistics', 'Bahasa & Kesusasteraan', 'மொழிகள் & மொழியியல்', 'bahasa', 'humanities', 45),
    ('pengajian-islam', 'Islamic & Religious Studies', 'Pengajian Islam & Agama', 'இஸ்லாமிய & சமயப் படிப்புகள்', 'pengajian-islam', 'humanities', 46),

    # Catch-all (1)
    ('umum', 'General & Humanities', 'Umum & Kemanusiaan', 'பொது & மானுடவியல்', 'umum-kemanusiaan', 'humanities', 47),
]


def populate_taxonomy(apps, schema_editor):
    FieldTaxonomy = apps.get_model('courses', 'FieldTaxonomy')

    # Insert parent groups first
    for key, name_en, name_ms, name_ta, image_slug, sort_order in GROUPS:
        FieldTaxonomy.objects.create(
            key=key,
            name_en=name_en,
            name_ms=name_ms,
            name_ta=name_ta,
            image_slug=image_slug,
            parent_key=None,
            sort_order=sort_order,
        )

    # Insert leaf entries with parent FK
    for key, name_en, name_ms, name_ta, image_slug, parent_key, sort_order in FIELDS:
        parent = FieldTaxonomy.objects.get(key=parent_key) if parent_key else None
        FieldTaxonomy.objects.create(
            key=key,
            name_en=name_en,
            name_ms=name_ms,
            name_ta=name_ta,
            image_slug=image_slug,
            parent_key=parent,
            sort_order=sort_order,
        )


def depopulate_taxonomy(apps, schema_editor):
    FieldTaxonomy = apps.get_model('courses', 'FieldTaxonomy')
    FieldTaxonomy.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0025_field_taxonomy'),
    ]

    operations = [
        migrations.RunPython(populate_taxonomy, depopulate_taxonomy),
    ]
