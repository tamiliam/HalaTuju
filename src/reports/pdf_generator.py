import io
import re
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch

class PDFReportGenerator:
    """
    Generates a professional, mobile-readable PDF report used in career counseling.
    Focus: Clean layout, clear headers, and structured tables for SPM results.
    """
    
    def __init__(self):
        self.buffer = io.BytesIO()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        # 1. Main Title
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            leading=20,
            alignment=1, # Center
            spaceAfter=6,
            textColor=colors.midnightblue
        ))
        
        # 2. Subtitle
        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=1, # Center
            textColor=colors.grey,
            spaceAfter=20
        ))
        
        # 3. Section Headers (A, B, C...)
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            leading=18,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.darkblue,
            keepWithNext=True
        ))
        
        # 4. Body Text (Readable on Mobile/Print)
        # BodyText usually exists in sample sheet, so we create a custom one or override carefully.
        # Let's use a unique name.
        self.styles.add(ParagraphStyle(
            name='ReportBody',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=15,
            spaceAfter=8
        ))
        
        # 5. Bullet Points
        self.styles.add(ParagraphStyle(
            name='ReportBullet',
            parent=self.styles['ReportBody'],
            leftIndent=20,
            bulletIndent=10,
            spaceAfter=4
        ))

    def generate_pdf(self, student_profile, report_markdown, counsellor_name="HalaTuju (AI Kaunselor)"):
        """
        Main entry point. Returns BytesIO buffer containing the PDF.
        """
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=50, leftMargin=50,
            topMargin=50, bottomMargin=50
        )
        
        story = []
        
        # 1. Add Header
        self._add_header(story, student_profile, counsellor_name)
        
        # 2. Add SPM Result Table (Mandatory)
        self._add_spm_table(story, student_profile)
        
        # 3. Parse and Add Markdown Sections
        self._parse_markdown_to_story(story, report_markdown)
        
        # 4. Add Footer/Disclaimer
        self._add_footer(story)
        
        # Build
        doc.build(story)
        
        # Rewind buffer
        self.buffer.seek(0)
        return self.buffer

    def _add_header(self, story, profile, counsellor_name):
        # Title
        story.append(Paragraph("Laporan Konsultasi Laluan Kerjaya Pasca-SPM (TVET)", self.styles['ReportTitle']))
        
        # Metadata
        gen_date = datetime.now().strftime("%d %B %Y")
        # Masked ID for privacy (e.g. last 6 chars of ID or just 'Anon')
        masked_id = str(profile.get('id', 'N/A'))[-6:]
        subtitle = f"Dijana oleh: {counsellor_name} | {gen_date} | Ref: {masked_id}"
        
        story.append(Paragraph(subtitle, self.styles['ReportSubtitle']))
        story.append(Spacer(1, 10))
        
        # Student Name (Lightly masked or first name only if desired, strict req says AnonID but usually nice to see name)
        # User requirement said: "Maklumat Pelajar (anonim)" and also "Nama fail PDF: ... AnonID".
        # We will separate the Ref ID.
        # Let's put a "Profil Pelajar" block but keep it minimal.
        
    def _add_spm_table(self, story, profile):
        story.append(Paragraph("Ringkasan Keputusan SPM", self.styles['SectionHeader']))
        
        grades = profile.get('grades', {})
        if not grades:
            story.append(Paragraph("Tiada rekod keputusan SPM.", self.styles['ReportBody']))
            return
            
        # Prepare Data: [Subject, Grade]
        data = [['Subjek', 'Gred']]
        
        # Sort or list standard subjects? Just iterate keys.
        for subj, grade in grades.items():
            # Translate keys if needed, or capitalize
            s_name = subj.replace('_', ' ').title()
            
            # Special translations for common keys
            map_name = {
                "bm": "Bahasa Melayu", "eng": "Bahasa Inggeris", "hist": "Sejarah",
                "math": "Matematik", "sci": "Sains", "bio": "Biologi",
                "chem": "Kimia", "phy": "Fizik", "addmath": "Mat. Tambahan",
                "pai": "P. Islam", "moral": "P. Moral"
            }
            s_final = map_name.get(subj, s_name)
            
            data.append([s_final, grade])
            
        # Create Table
        t = Table(data, colWidths=[3.5*inch, 1.5*inch])
        
        # Style Table
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.aliceblue), # Header BG
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.midnightblue),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'), # Center Grades
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey)
        ]))
        
        story.append(t)
        story.append(Spacer(1, 20))

    def _parse_markdown_to_story(self, story, text):
        """
        Parses Markdown text into Paragraphs.
        Handles:
        - ### Headers -> SectionHeader
        - - Bullet points -> BulletPoint style
        - **Bold** -> <b>Tags</b>
        """
        # 1. Clean Text
        # Replace bold markdown with XML tags ReportLab understands
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        # 2. Split by Headers (### X. Title)
        # Using lookahead to keep the delimiter or just split and check
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('###'):
                # Header
                clean_header = line.replace('###', '').strip()
                story.append(Spacer(1, 10))
                story.append(Paragraph(clean_header, self.styles['SectionHeader']))
            elif line.startswith('- ') or line.startswith('* '):
                # Bullet
                clean_bullet = line[2:].strip()
                story.append(Paragraph(f"<bullet>&bull;</bullet> {clean_bullet}", self.styles['ReportBullet']))
            else:
                # Normal Text
                story.append(Paragraph(line, self.styles['ReportBody']))

    def _add_footer(self, story):
        story.append(Spacer(1, 30))
        disclaimer = "Nota: Laporan ini bertujuan membantu perbincangan dengan ibu bapa/guru kaunseling. Ini adalah analisis bantuan AI dan bukan jaminan kemasukan atau pekerjaan rasmi."
        
        story.append(Paragraph(disclaimer, ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=1 # Center
        )))
