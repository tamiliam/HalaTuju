"""
Populate metadata fields for university_courses.csv
Infers department, field, and frontend_label from course names
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
COURSES_FILE = DATA_DIR / "university_courses.csv"

# Fixed frontend_label categories (from existing poly/kk courses)
FRONTEND_LABELS = [
    "Perniagaan & Perdagangan",
    "Mekanikal & Automotif",
    "Elektrik & Elektronik",
    "Sivil, Seni Bina & Pembinaan",
    "Seni Reka & Kreatif",
    "Hospitaliti, Kulinari & Pelancongan",
    "Pertanian & Bio-Industri",
    "Aero, Marin, Minyak & Gas",
    "Komputer, IT & Multimedia"
]

def infer_metadata(course_name, level):
    """
    Infer department, field, and frontend_label from course name
    """
    name_lower = course_name.lower()

    # Default values
    department = ""
    field = ""
    frontend_label = ""

    # Engineering courses
    if "kejuruteraan" in name_lower or "asasi kejuruteraan" in name_lower:
        department = "Kejuruteraan"

        # Determine specific field
        if "awam" in name_lower or "sivil" in name_lower:
            field = "Kejuruteraan Awam"
            frontend_label = "Sivil, Seni Bina & Pembinaan"
        elif "elektrik" in name_lower and "elektronik" in name_lower:
            field = "Kejuruteraan Elektrik Dan Elektronik"
            frontend_label = "Elektrik & Elektronik"
        elif "elektrik" in name_lower:
            field = "Kejuruteraan Elektrik"
            frontend_label = "Elektrik & Elektronik"
        elif "elektronik" in name_lower:
            field = "Kejuruteraan Elektronik"
            frontend_label = "Elektrik & Elektronik"
        elif "mekanikal" in name_lower:
            field = "Kejuruteraan Mekanikal"
            frontend_label = "Mekanikal & Automotif"
        elif "mekatronik" in name_lower:
            field = "Kejuruteraan Mekatronik"
            frontend_label = "Mekanikal & Automotif"
        elif "automotif" in name_lower:
            field = "Kejuruteraan Automotif"
            frontend_label = "Mekanikal & Automotif"
        elif "bahan" in name_lower:
            field = "Kejuruteraan Bahan"
            frontend_label = "Mekanikal & Automotif"
        elif "kimia" in name_lower:
            if "minyak" in name_lower or "gas" in name_lower:
                field = "Kejuruteraan Kimia (Minyak Dan Gas)"
                frontend_label = "Aero, Marin, Minyak & Gas"
            else:
                field = "Kejuruteraan Kimia"
                frontend_label = "Pertanian & Bio-Industri"
        elif "komputer" in name_lower:
            field = "Kejuruteraan Komputer"
            frontend_label = "Komputer, IT & Multimedia"
        elif "alam sekitar" in name_lower:
            field = "Kejuruteraan Alam Sekitar"
            frontend_label = "Sivil, Seni Bina & Pembinaan"
        elif "pembuatan" in name_lower:
            field = "Kejuruteraan Pembuatan"
            frontend_label = "Mekanikal & Automotif"
        elif "pertanian" in name_lower:
            field = "Kejuruteraan Teknologi Pertanian"
            frontend_label = "Pertanian & Bio-Industri"
        else:
            # Generic engineering
            field = "Kejuruteraan"
            frontend_label = "Mekanikal & Automotif"

    # Business/Commerce courses
    elif any(word in name_lower for word in ["perniagaan", "e-commerce", "keusahawanan", "perakaunan", "kewangan", "pemasaran", "pengurusan perniagaan"]):
        department = "Perniagaan Dan Pengurusan"
        if "e-commerce" in name_lower:
            field = "E-Commerce"
        elif "keusahawanan" in name_lower:
            field = "Keusahawanan"
        elif "perakaunan" in name_lower:
            field = "Perakaunan"
        elif "kewangan" in name_lower:
            field = "Kewangan"
        else:
            field = "Perniagaan"
        frontend_label = "Perniagaan & Perdagangan"

    # IT/Computer courses
    elif any(word in name_lower for word in ["teknologi maklumat", "sains komputer", "multimedia", "rangkaian komputer"]):
        department = "Teknologi Maklumat"
        field = "Teknologi Maklumat"
        frontend_label = "Komputer, IT & Multimedia"

    # Agriculture/Bio courses
    elif any(word in name_lower for word in ["pertanian", "haiwan", "peternakan", "akuakultur"]):
        department = "Pertanian Dan Bio-Industri"
        if "pertanian" in name_lower:
            field = "Pertanian"
        elif "haiwan" in name_lower or "peternakan" in name_lower:
            field = "Kesihatan Haiwan Dan Peternakan"
        else:
            field = "Pertanian"
        frontend_label = "Pertanian & Bio-Industri"

    # Hospitality/Tourism
    elif any(word in name_lower for word in ["hospitaliti", "kulinari", "pelancongan", "hotel"]):
        department = "Hospitaliti Dan Pelancongan"
        field = "Hospitaliti"
        frontend_label = "Hospitaliti, Kulinari & Pelancongan"

    # Health/Medical
    elif any(word in name_lower for word in ["perubatan", "kesihatan", "fisioterapi", "paramedik"]):
        department = "Kesihatan"
        if "perubatan" in name_lower:
            field = "Perubatan"
        elif "fisioterapi" in name_lower:
            field = "Fisioterapi"
        else:
            field = "Kesihatan"
        frontend_label = "Pertanian & Bio-Industri"  # Closest match

    # Science courses
    elif "sains" in name_lower:
        department = "Sains"
        if "pertanian" in name_lower:
            field = "Sains Pertanian"
            frontend_label = "Pertanian & Bio-Industri"
        elif "sosial" in name_lower:
            field = "Sains Sosial"
            frontend_label = "Perniagaan & Perdagangan"
        elif "komputer" in name_lower:
            field = "Sains Komputer"
            frontend_label = "Komputer, IT & Multimedia"
        else:
            field = "Sains"
            frontend_label = "Pertanian & Bio-Industri"

    # Management/Administration
    elif any(word in name_lower for word in ["pengurusan", "pentadbiran", "strategi"]):
        department = "Pengurusan"
        if "strategi" in name_lower:
            field = "Pengurusan Dan Strategi"
        else:
            field = "Pengurusan"
        frontend_label = "Perniagaan & Perdagangan"

    # Languages
    elif any(word in name_lower for word in ["bahasa", "language"]):
        department = "Bahasa Dan Komunikasi"
        if "inggeris" in name_lower:
            field = "Bahasa Inggeris"
        else:
            field = "Bahasa"
        frontend_label = "Seni Reka & Kreatif"

    # Design/Creative
    elif any(word in name_lower for word in ["seni", "reka bentuk", "grafik", "multimedia"]):
        department = "Seni Dan Reka Bentuk"
        field = "Seni Reka"
        frontend_label = "Seni Reka & Kreatif"

    # Safety/Defense
    elif any(word in name_lower for word in ["keselamatan", "pertahanan", "kecergasan"]):
        department = "Keselamatan Dan Pertahanan"
        if "keselamatan" in name_lower and "kesihatan" in name_lower:
            field = "Keselamatan Dan Kesihatan Pekerjaan"
        elif "kecergasan" in name_lower:
            field = "Kecergasan Pertahanan"
        else:
            field = "Keselamatan"
        frontend_label = "Sivil, Seni Bina & Pembinaan"  # Closest match

    # STEM (Science, Technology, Engineering, Math)
    elif "stem" in name_lower:
        department = "STEM"
        field = "STEM"
        frontend_label = "Komputer, IT & Multimedia"

    # Islamic studies (should not appear after filtering, but just in case)
    elif "islam" in name_lower:
        department = "Pengajian Islam"
        field = "Pengajian Islam"
        frontend_label = "Seni Reka & Kreatif"  # Default

    # Default fallback
    if not department or not field or not frontend_label:
        department = "Umum"
        field = "Umum"
        frontend_label = "Perniagaan & Perdagangan"

    return department, field, frontend_label


def main():
    print("=" * 60)
    print("University Courses Metadata Populator")
    print("=" * 60)

    # Load university courses
    df = pd.read_csv(COURSES_FILE)
    print(f"\nLoaded {len(df)} university courses")

    # Convert columns to string type to avoid dtype issues
    df['department'] = df['department'].astype(str)
    df['field'] = df['field'].astype(str)
    df['frontend_label'] = df['frontend_label'].astype(str)

    # Populate metadata
    print("\nInferring metadata from course names...")
    departments = []
    fields = []
    frontend_labels = []

    for idx, row in df.iterrows():
        course_name = row['course']
        level = row['level']

        department, field, frontend_label = infer_metadata(course_name, level)

        departments.append(department)
        fields.append(field)
        frontend_labels.append(frontend_label)

        print(f"  [{idx+1}/{len(df)}] {row['course_id']}")
        print(f"      Department: {department}")
        print(f"      Field: {field}")
        print(f"      Label: {frontend_label}")

    # Assign all at once
    df['department'] = departments
    df['field'] = fields
    df['frontend_label'] = frontend_labels

    # Save updated file
    df.to_csv(COURSES_FILE, index=False)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Updated {len(df)} courses")
    print(f"\nFrontend label distribution:")
    print(df['frontend_label'].value_counts())
    print(f"\nFile saved to: {COURSES_FILE}")


if __name__ == "__main__":
    main()
