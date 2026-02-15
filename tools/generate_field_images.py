"""
Generate realistic field/category images for HalaTuju courses using Gemini.

Uses Gemini 2.5 Flash Image to generate one photo per course field,
then uploads to Supabase Storage (field-images bucket).

Usage:
    cd HalaTuju
    python tools/generate_field_images.py

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

# The 9 course fields and their image prompts
FIELDS = [
    {
        'slug': 'mekanikal-automotif',
        'name': 'Mekanikal & Automotif',
        'prompt': (
            'A realistic photo of a young Malaysian student working on an automotive engine '
            'in a modern polytechnic workshop. Clean, well-lit industrial setting with tools '
            'and car parts visible. Professional training environment. Natural lighting.'
        ),
    },
    {
        'slug': 'perniagaan-perdagangan',
        'name': 'Perniagaan & Perdagangan',
        'prompt': (
            'A realistic photo of young Malaysian business students in a modern classroom, '
            'presenting a business plan on a whiteboard. Smart casual attire, laptops on desks, '
            'collaborative atmosphere. Bright, professional setting.'
        ),
    },
    {
        'slug': 'elektrik-elektronik',
        'name': 'Elektrik & Elektronik',
        'prompt': (
            'A realistic photo of a young Malaysian student soldering a circuit board in an '
            'electronics lab. Oscilloscope and multimeter visible on the workbench. '
            'Clean, modern technical laboratory setting.'
        ),
    },
    {
        'slug': 'pertanian-bio-industri',
        'name': 'Pertanian & Bio-Industri',
        'prompt': (
            'A realistic photo of young Malaysian agriculture students working in a modern '
            'greenhouse with tropical plants. Wearing lab coats and gloves, examining plant '
            'specimens. Green, bright, tropical setting.'
        ),
    },
    {
        'slug': 'sivil-senibina-pembinaan',
        'name': 'Sivil, Seni Bina & Pembinaan',
        'prompt': (
            'A realistic photo of young Malaysian civil engineering students on a construction '
            'site, reviewing blueprints together. Hard hats and safety vests. Modern building '
            'structure in background. Clear sky, Southeast Asian setting.'
        ),
    },
    {
        'slug': 'hospitaliti-kulinari-pelancongan',
        'name': 'Hospitaliti, Kulinari & Pelancongan',
        'prompt': (
            'A realistic photo of young Malaysian culinary students in a professional kitchen, '
            'plating food. White chef uniforms and hats. Stainless steel kitchen equipment. '
            'Warm, inviting atmosphere with steam rising.'
        ),
    },
    {
        'slug': 'komputer-it-multimedia',
        'name': 'Komputer, IT & Multimedia',
        'prompt': (
            'A realistic photo of young Malaysian IT students working at computers in a modern '
            'computer lab. Multiple monitors showing code and design software. '
            'Cool blue lighting, contemporary tech environment.'
        ),
    },
    {
        'slug': 'aero-marin-minyakgas',
        'name': 'Aero, Marin, Minyak & Gas',
        'prompt': (
            'A realistic photo of young Malaysian aerospace students examining a small aircraft '
            'engine in a hangar. Wearing safety gear. Aircraft parts and tools visible. '
            'Large, well-lit industrial hangar setting.'
        ),
    },
    {
        'slug': 'senireka-kreatif',
        'name': 'Seni Reka & Kreatif',
        'prompt': (
            'A realistic photo of young Malaysian design students working on creative projects '
            'in a bright art studio. Drawing tablets, colour swatches, and sketches visible. '
            'Colourful, inspiring creative workspace.'
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
    client = genai.Client(api_key=GOOGLE_AI_API_KEY)

    print(f'[*] Generating {len(FIELDS)} field images with Gemini 2.5 Flash')
    print(f'[*] Output: {OUTPUT_DIR}\n')

    results = []

    for i, field in enumerate(FIELDS, 1):
        slug = field['slug']
        name = field['name']
        output_path = OUTPUT_DIR / f'{slug}.png'

        print(f'[{i}/{len(FIELDS)}] {name}')

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
            time.sleep(2)

    # Summary
    print(f'\n{"=" * 60}')
    print(f'[*] DONE: {len(results)}/{len(FIELDS)} images generated and uploaded')
    print(f'{"=" * 60}\n')

    for r in results:
        print(f'  {r["name"]}')
        print(f'    {r["url"]}\n')

    # Output SQL for field_images table
    if results:
        print('\n-- SQL to insert into field_images table:')
        for r in results:
            print(f"INSERT INTO public.field_images (slug, name, image_url) VALUES ('{r['slug']}', '{r['name']}', '{r['url']}');")


if __name__ == '__main__':
    main()
