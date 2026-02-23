"""
Generate realistic field/category images for HalaTuju courses using Gemini.

Uses Gemini 2.5 Flash Image to generate one photo per course image category,
then uploads to Supabase Storage (field-images bucket).

37 image categories covering all 383 courses with max 15 per image.

Usage:
    cd HalaTuju
    python tools/generate_field_images.py
    python tools/generate_field_images.py --skip-existing   # skip already-generated

Requires:
    - GOOGLE_AI_API_KEY in .env
    - google-genai package
    - Supabase 'field-images' bucket (public, created via migration)

Output:
    - Images saved to .tmp/field_images/
    - Uploaded to Supabase Storage: field-images/{slug}.png
    - Prints public URLs for each image
"""
import os
import sys
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

GOOGLE_AI_API_KEY = os.environ.get('GOOGLE_AI_API_KEY')
if not GOOGLE_AI_API_KEY:
    print('[ERROR] GOOGLE_AI_API_KEY not found in .env')
    sys.exit(1)

# Supabase config
SUPABASE_URL = 'https://pbrrlyoyyiftckqvzvvo.supabase.co'
SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBicnJseW95eWlmdGNrcXZ6dnZvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg1MDA4NjYsImV4cCI6MjA4NDA3Njg2Nn0.rl7fo7AmqY-QqNZ97bUO-ajH7-niGtO8_yPLj_PSLos'
BUCKET = 'field-images'

OUTPUT_DIR = Path(__file__).parent.parent / '.tmp' / 'field_images'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 37 image categories ----------
# Each prompt describes a realistic, landscape-oriented photo in a Malaysian
# educational setting.  Images display at 144px height on course cards, so
# subjects must be clearly visible even at small sizes.

FIELDS = [
    # ── Pendidikan (5 sub-images) ──────────────────────────────────────
    {
        'slug': 'pendidikan-bahasa',
        'name': 'Pendidikan — Bahasa',
        'prompt': (
            'A realistic photo of a bright Malaysian primary school classroom '
            'for language learning. A young teacher writing multilingual text '
            'on the whiteboard — Malay, English, Chinese, Tamil scripts visible. '
            'Colourful alphabet posters on walls. Students engaged in reading. '
            'Warm natural lighting, Southeast Asian school setting.'
        ),
    },
    {
        'slug': 'pendidikan-stem',
        'name': 'Pendidikan — STEM',
        'prompt': (
            'A realistic photo of Malaysian teacher-training students in a '
            'science education lab. Young students conducting a chemistry experiment '
            'with test tubes and beakers. Maths equations on a whiteboard behind them. '
            'Bright, modern classroom with microscopes and calculators visible.'
        ),
    },
    {
        'slug': 'pendidikan-seni',
        'name': 'Pendidikan — Seni & Muzik',
        'prompt': (
            'A realistic photo of a Malaysian art and music classroom. Young '
            'teacher-training students painting at easels and playing traditional '
            'instruments (gamelan, kompang). Colourful artwork displayed on walls. '
            'Creative, inspiring atmosphere with natural light.'
        ),
    },
    {
        'slug': 'pendidikan-kemanusiaan',
        'name': 'Pendidikan — Kemanusiaan',
        'prompt': (
            'A realistic photo of Malaysian teacher-training students in a '
            'humanities classroom discussion. Students seated in a circle with '
            'history textbooks and maps. A timeline poster on the wall. '
            'Warm, engaged learning atmosphere. Diverse Malaysian students.'
        ),
    },
    {
        'slug': 'pendidikan-khas',
        'name': 'Pendidikan — Khas & Prasekolah',
        'prompt': (
            'A realistic photo of an inclusive Malaysian classroom. A young '
            'teacher helping children with learning activities — building blocks, '
            'sensory toys, picture cards. Bright, cheerful room with colourful '
            'decorations. Early childhood and special education setting.'
        ),
    },

    # ── Mekanikal (4 sub-images) ───────────────────────────────────────
    {
        'slug': 'mekanikal-kimpalan',
        'name': 'Mekanikal — Kimpalan & Fabrikasi',
        'prompt': (
            'A realistic photo of a Malaysian TVET student welding metal in a '
            'workshop. Bright sparks flying, student wearing a welding mask and '
            'safety gloves. Steel workpieces and welding equipment visible. '
            'Industrial workshop setting with good ventilation.'
        ),
    },
    {
        'slug': 'mekanikal-pemesinan',
        'name': 'Mekanikal — Pemesinan & CNC',
        'prompt': (
            'A realistic photo of a Malaysian polytechnic student operating a '
            'CNC milling machine. Metal shavings visible, precision tooling on '
            'the workbench. Clean, well-lit modern machining workshop with '
            'safety guards and digital readouts.'
        ),
    },
    {
        'slug': 'mekanikal-mekatronik',
        'name': 'Mekanikal — Mekatronik & Automasi',
        'prompt': (
            'A realistic photo of Malaysian students working with a robotic arm '
            'in a mechatronics lab. Sensors, Arduino boards, and wiring on the '
            'workbench. One student programming on a laptop while another adjusts '
            'the robot. Modern, tech-forward lab setting.'
        ),
    },
    {
        'slug': 'mekanikal-am',
        'name': 'Mekanikal — Am & Penyelenggaraan',
        'prompt': (
            'A realistic photo of Malaysian mechanical engineering students in '
            'a general workshop. Students examining engine components, using '
            'hand tools and measuring instruments. Workbenches with mechanical '
            'parts. Well-organised industrial training facility.'
        ),
    },

    # ── Elektrik & Elektronik (3 sub-images) ───────────────────────────
    {
        'slug': 'elektrik-kuasa',
        'name': 'Elektrik & Kuasa',
        'prompt': (
            'A realistic photo of a Malaysian electrical engineering student '
            'wiring an electrical panel. Cable trays, circuit breakers, and a '
            'multimeter visible. Solar panel model in the background. '
            'Clean, well-lit electrical training lab with safety signage.'
        ),
    },
    {
        'slug': 'elektronik-telekom',
        'name': 'Elektronik & Telekomunikasi',
        'prompt': (
            'A realistic photo of a Malaysian student soldering a circuit board '
            'in an electronics lab. Oscilloscope and signal generator on the '
            'workbench. Telecom equipment and fibre optic cables visible. '
            'Modern technical laboratory with blue-tinted lighting.'
        ),
    },
    {
        'slug': 'elektronik-kawalan',
        'name': 'Elektronik — Kawalan & Instrumentasi',
        'prompt': (
            'A realistic photo of a Malaysian student in a control systems lab. '
            'PLC panels, SCADA screens, and instrument gauges visible. Student '
            'monitoring industrial control displays. Clean, technical environment '
            'with status indicator lights.'
        ),
    },

    # ── IT & Komputer (2 sub-images) ───────────────────────────────────
    {
        'slug': 'it-perisian',
        'name': 'IT — Perisian & Pembangunan',
        'prompt': (
            'A realistic photo of Malaysian computer science students coding '
            'in a modern lab. Multiple monitors showing colourful code editors '
            'and web applications. Students collaborating, one pointing at '
            'a screen. Contemporary tech workspace with good lighting.'
        ),
    },
    {
        'slug': 'it-rangkaian',
        'name': 'IT — Rangkaian & Keselamatan',
        'prompt': (
            'A realistic photo of a Malaysian student configuring network '
            'equipment in a server room. Rack-mounted servers, blinking LEDs, '
            'and structured cabling visible. Student holding a networking cable. '
            'Cool blue lighting, data centre aesthetic.'
        ),
    },

    # ── Sivil & Pembinaan (2 sub-images) ───────────────────────────────
    {
        'slug': 'sivil-struktur',
        'name': 'Sivil & Struktur',
        'prompt': (
            'A realistic photo of Malaysian civil engineering students on a '
            'construction site. Hard hats and safety vests, reviewing large '
            'blueprints spread on a table. A concrete structure under construction '
            'in the background. Clear sky, tropical Southeast Asian setting.'
        ),
    },
    {
        'slug': 'sivil-bangunan',
        'name': 'Sivil — Bangunan & Fasiliti',
        'prompt': (
            'A realistic photo of a Malaysian building maintenance student '
            'inspecting plumbing pipes in a modern building. Tool belt, '
            'clipboard, and pipe fittings visible. Clean building interior '
            'with exposed services. Professional maintenance training.'
        ),
    },

    # ── Minyak, Gas & Kimia (2 sub-images) ─────────────────────────────
    {
        'slug': 'minyak-gas',
        'name': 'Minyak & Gas',
        'prompt': (
            'A realistic photo of Malaysian oil and gas students near a '
            'refinery training facility. Wearing coveralls and hard hats, '
            'examining pipeline valves. Industrial towers and pipes in '
            'background. Professional petrochemical training environment.'
        ),
    },
    {
        'slug': 'kimia-alam-sekitar',
        'name': 'Kejuruteraan Kimia & Alam Sekitar',
        'prompt': (
            'A realistic photo of Malaysian chemical engineering students in '
            'a laboratory. Fume hood, beakers with coloured liquids, safety '
            'goggles. One student pipetting a sample. Environmental monitoring '
            'equipment visible. Clean, bright laboratory setting.'
        ),
    },

    # ── Hospitaliti Cluster (3 images) ─────────────────────────────────
    {
        'slug': 'hospitaliti-pelancongan',
        'name': 'Hospitaliti & Pelancongan',
        'prompt': (
            'A realistic photo of Malaysian hospitality students at a hotel '
            'reception training area. Students in smart uniforms practising '
            'guest check-in. Elegant lobby with tropical flowers. Professional, '
            'welcoming atmosphere. Southeast Asian hotel setting.'
        ),
    },
    {
        'slug': 'kulinari-makanan',
        'name': 'Kulinari & Sains Makanan',
        'prompt': (
            'A realistic photo of Malaysian culinary students in a professional '
            'kitchen. White chef uniforms and tall hats. Plating colourful '
            'Malaysian dishes — nasi, curry, garnishes. Stainless steel kitchen '
            'equipment. Steam rising, warm inviting atmosphere.'
        ),
    },
    {
        'slug': 'kecantikan-gayahidup',
        'name': 'Kecantikan & Gaya Hidup',
        'prompt': (
            'A realistic photo of Malaysian beauty therapy students in a '
            'training salon. One student styling hair, another doing skincare. '
            'Modern salon mirrors, beauty products, and styling tools visible. '
            'Clean, well-lit professional beauty school environment.'
        ),
    },

    # ── Business Cluster (3 images) ────────────────────────────────────
    {
        'slug': 'perniagaan',
        'name': 'Perniagaan & Keusahawanan',
        'prompt': (
            'A realistic photo of Malaysian business students presenting a '
            'startup pitch. One student at a whiteboard with business model '
            'canvas, others with laptops. Smart casual attire. Modern, bright '
            'classroom with entrepreneurship posters.'
        ),
    },
    {
        'slug': 'perakaunan-kewangan',
        'name': 'Perakaunan & Kewangan',
        'prompt': (
            'A realistic photo of Malaysian accounting students working with '
            'financial spreadsheets on computers. Calculators, ledger books, '
            'and financial statements on desks. Professional office-style '
            'classroom. Focused, studious atmosphere.'
        ),
    },
    {
        'slug': 'pengurusan-logistik',
        'name': 'Pengurusan & Logistik',
        'prompt': (
            'A realistic photo of Malaysian logistics management students in '
            'a simulated warehouse. Clipboard in hand, checking inventory on '
            'shelves. Boxes, pallets, and a forklift in background. '
            'Organised supply chain training facility.'
        ),
    },

    # ── Single-image Categories (already under 15) ─────────────────────
    {
        'slug': 'automotif',
        'name': 'Automotif',
        'prompt': (
            'A realistic photo of a Malaysian automotive student working on '
            'a car engine in a modern workshop. Hood open, engine components '
            'visible. Diagnostic tools and car lift in background. Clean, '
            'well-equipped automotive training centre.'
        ),
    },
    {
        'slug': 'senireka-fesyen',
        'name': 'Seni Reka & Fesyen',
        'prompt': (
            'A realistic photo of Malaysian design students in a creative '
            'studio. Drawing tablets, fabric swatches, fashion sketches, and '
            'colour palettes on desks. One student draping fabric on a '
            'mannequin. Bright, inspiring creative workspace.'
        ),
    },
    {
        'slug': 'multimedia-animasi',
        'name': 'Multimedia & Animasi',
        'prompt': (
            'A realistic photo of Malaysian animation students working at '
            'digital workstations. Large monitors showing 3D character models '
            'and animation timelines. Drawing tablets and styluses in use. '
            'Dark room with glowing screens, creative tech environment.'
        ),
    },
    {
        'slug': 'pertanian-agro',
        'name': 'Pertanian & Agro',
        'prompt': (
            'A realistic photo of Malaysian agriculture students in a modern '
            'greenhouse. Examining tropical plants, wearing lab coats and '
            'gloves. Hydroponic systems and plant specimens visible. Green, '
            'bright, tropical agricultural training setting.'
        ),
    },
    {
        'slug': 'sains-stem',
        'name': 'Sains & STEM',
        'prompt': (
            'A realistic photo of Malaysian science students in a modern lab. '
            'Microscopes, test tubes with coloured solutions, and lab notebooks. '
            'Students wearing safety goggles examining specimens. Bright, clean '
            'laboratory environment with periodic table poster.'
        ),
    },
    {
        'slug': 'perubatan-kesihatan',
        'name': 'Perubatan & Kesihatan',
        'prompt': (
            'A realistic photo of Malaysian medical students in a clinical '
            'training room. Stethoscopes, anatomical models, and medical charts '
            'visible. Students in white coats practising on a simulation mannequin. '
            'Clean, professional healthcare training environment.'
        ),
    },
    {
        'slug': 'senibina-landskap',
        'name': 'Seni Bina & Landskap',
        'prompt': (
            'A realistic photo of Malaysian architecture students working on '
            'building models in a design studio. Architectural drawings, scale '
            'models, and drafting tools on large tables. Student carefully '
            'assembling a cardboard building model. Natural lighting.'
        ),
    },
    {
        'slug': 'marin-perkapalan',
        'name': 'Marin & Perkapalan',
        'prompt': (
            'A realistic photo of Malaysian marine engineering students at a '
            'shipyard training facility. Ship hull under construction in '
            'background. Students in safety gear examining marine engine '
            'components. Dock cranes and water visible. Industrial maritime setting.'
        ),
    },
    {
        'slug': 'aero-penerbangan',
        'name': 'Penerbangan & Aero',
        'prompt': (
            'A realistic photo of Malaysian aerospace students examining a '
            'small aircraft engine in a hangar. Wearing safety gear, using '
            'inspection tools. Aircraft fuselage and propeller visible in '
            'background. Large, well-lit aviation training hangar.'
        ),
    },
    {
        'slug': 'kejuruteraan-am',
        'name': 'Kejuruteraan Am',
        'prompt': (
            'A realistic photo of Malaysian engineering students reviewing '
            'technical drawings in a workshop. Mixed equipment — mechanical, '
            'electrical, and structural tools visible. Students collaborating '
            'over blueprints. General polytechnic engineering lab.'
        ),
    },
    {
        'slug': 'umum-kemanusiaan',
        'name': 'Umum & Kemanusiaan',
        'prompt': (
            'A realistic photo of Malaysian university students studying in '
            'a modern library. Books, laptops, and notebooks on desks. Warm '
            'natural light from large windows. Bookshelves in background. '
            'Peaceful, focused academic atmosphere.'
        ),
    },

    # ── Future STPM (pre-created) ──────────────────────────────────────
    {
        'slug': 'undang-undang',
        'name': 'Undang-undang',
        'prompt': (
            'A realistic photo of Malaysian law students in a moot court room. '
            'Wooden podium, Malaysian flag, and legal books on shelves. Students '
            'in formal attire reviewing case files. Dignified, professional '
            'legal training environment.'
        ),
    },
    {
        'slug': 'farmasi',
        'name': 'Farmasi',
        'prompt': (
            'A realistic photo of Malaysian pharmacy students in a dispensary '
            'lab. Medicine bottles, pill counters, and prescription pads visible. '
            'Students in white coats examining pharmaceutical products. '
            'Clean, organised pharmacy training facility.'
        ),
    },
]


def generate_image(client: genai.Client, prompt: str, output_path: Path) -> bool:
    """Generate a single image with Gemini and save to disk."""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=['Image'],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                # Save raw image bytes
                with open(output_path, 'wb') as f:
                    f.write(part.inline_data.data)
                return True

        print(f'  [WARN] No image in response')
        return False

    except Exception as e:
        print(f'  [ERROR] {e}')
        return False


def upload_to_supabase(file_path: Path, object_name: str) -> str | None:
    """Upload a file to Supabase Storage and return the public URL."""
    url = f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{object_name}'

    with open(file_path, 'rb') as f:
        response = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'apikey': SUPABASE_ANON_KEY,
                'Content-Type': 'image/png',
                'x-upsert': 'true',
            },
            data=f.read(),
        )

    if response.status_code in (200, 201):
        public_url = f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{object_name}'
        return public_url
    else:
        print(f'  [ERROR] Upload failed ({response.status_code}): {response.text}')
        return None


def main():
    parser = argparse.ArgumentParser(description='Generate course field images')
    parser.add_argument('--skip-existing', action='store_true',
                        help='Skip images that already exist locally')
    args = parser.parse_args()

    client = genai.Client(api_key=GOOGLE_AI_API_KEY)

    print(f'[*] Generating {len(FIELDS)} field images with Gemini 2.5 Flash')
    print(f'[*] Output: {OUTPUT_DIR}')
    if args.skip_existing:
        print(f'[*] Skipping existing files')
    print()

    results = []
    skipped = 0

    for i, field in enumerate(FIELDS, 1):
        slug = field['slug']
        name = field['name']
        output_path = OUTPUT_DIR / f'{slug}.png'

        print(f'[{i}/{len(FIELDS)}] {name}')

        # Skip if exists and flag set
        if args.skip_existing and output_path.exists():
            file_size = output_path.stat().st_size / 1024
            print(f'  Exists ({file_size:.0f} KB) — uploading only')
            public_url = upload_to_supabase(output_path, f'{slug}.png')
            if public_url:
                print(f'  OK: {public_url}')
                results.append({'slug': slug, 'name': name, 'url': public_url})
            skipped += 1
            continue

        # Generate
        print(f'  Generating...')
        success = generate_image(client, field['prompt'], output_path)

        if not success:
            print(f'  FAILED — skipping')
            continue

        file_size = output_path.stat().st_size / 1024
        print(f'  Saved ({file_size:.0f} KB)')

        # Upload
        print(f'  Uploading to Supabase...')
        public_url = upload_to_supabase(output_path, f'{slug}.png')

        if public_url:
            print(f'  OK: {public_url}')
            results.append({'slug': slug, 'name': name, 'url': public_url})
        else:
            print(f'  Upload failed')

        # Rate limiting — be polite to the API
        if i < len(FIELDS):
            time.sleep(3)

    # Summary
    print(f'\n{"=" * 60}')
    print(f'[*] DONE: {len(results)}/{len(FIELDS)} images generated and uploaded')
    if skipped:
        print(f'[*] Skipped (existing): {skipped}')
    print(f'{"=" * 60}\n')

    for r in results:
        print(f'  {r["name"]}')
        print(f'    {r["url"]}\n')


if __name__ == '__main__':
    main()
