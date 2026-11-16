import sys, base64, io
sys.path.insert(0, "C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/gen_v2")
from common import *
from PIL import Image
BASE = "C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/designs/"
REF = BASE + "refc/"
OUT = BASE + "samples_v2/"

def crop(f, box):
    im = Image.open(REF + f).convert("RGB").crop(box)
    b = io.BytesIO(); im.save(b, "PNG")
    return base64.b64encode(b.getvalue()).decode()

def panel_(x, y, items):
    out = [T(x, y, "What we check", 18, "bold", RED)]
    yy = y + 23
    for n, lines in items:
        out.append(f'<circle cx="{x+10}" cy="{yy}" r="10" fill="{RED}"/>' + T(x+10, yy+4, str(n), 12, "bold", "#fff", "middle"))
        for i, l in enumerate(lines):
            out.append(T(x+30, yy+5+i*18, l, 14, "normal", "#333"))
        yy += 50
    return "".join(out)

def stamps(cx, cy, logo):
    ls = 'letter-spacing="8"'
    s = (f'<g transform="rotate(-45 {cx} {cy})" opacity="0.22">'
         f'<rect x="{cx-215}" y="{cy-115}" width="430" height="230" rx="20" fill="none" stroke="{RED}" stroke-width="7"/>'
         + T(cx, cy-5, "CONTOH", 100, "bold", RED, "middle", extra=ls)
         + T(cx, cy+85, "SAMPLE", 100, "bold", RED, "middle", extra=ls) + '</g>')
    lx, ly = logo
    ls2 = 'letter-spacing="3.5"'
    s += (f'<g transform="rotate(-18 {lx} {ly})" opacity="0.3">'
          f'<rect x="{lx-95}" y="{ly-50}" width="190" height="101" rx="9" fill="none" stroke="{RED}" stroke-width="3"/>'
          + T(lx, ly-2, "CONTOH", 44, "bold", RED, "middle", extra=ls2)
          + T(lx, ly+38, "SAMPLE", 44, "bold", RED, "middle", extra=ls2) + '</g>')
    return s

def page_wrap(inner, st, callouts, items):
    W, H = 1208, 1163
    o = [R(0, 0, W, H, "#f4f5f7"), R(24, 25, 794, 1123, "#000", extra='opacity=".12"'),
         f'<g transform="translate(20 20)">{R(0,0,794,1123,"#fff","#ccc")}{inner}</g>',
         f'<g transform="translate(20 20)">{st}</g>']
    for cx, cy, tx, ty, n in callouts:
        o.append(callout(cx, cy, tx+20, ty+20, n))
    o.append(R(858, 20, 330, 256, "#fdf3f2", RED, 1.2, 8))
    o.append(panel_(876, 52, items))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">' + "".join(o) + '</svg>'

# ---------------- birth certificate ----------------
def birth():
    S = 0.702; GR = "#bdf0b0"; BD = "#9fe28f"; LN = "#3d5c39"
    b = []
    b.append('<defs><pattern id="dm" width="46" height="46" patternUnits="userSpaceOnUse">'
             '<polygon points="23,0 46,23 23,46 0,23" fill="none" stroke="#a9e69a" stroke-width="1.3"/>'
             '<polygon points="0,0 23,0 0,23" fill="#b2eba3"/><polygon points="46,46 23,46 46,23" fill="#b2eba3"/></pattern></defs>')
    b.append('<clipPath id="pg"><rect width="794" height="1123"/></clipPath>')
    b.append(f'<g clip-path="url(#pg)"><g transform="scale({S})">')
    b.append(R(0, 0, 1131, 1600, GR) + R(0, 0, 1131, 1600, "url(#dm)"))
    b.append(R(0, 0, 1131, 36, BD))
    b.append(T(24, 26, "PENDAFTARANEGARAMALAYSIAJABATANPENDAFTARANEGARAMALAYSIAJABATANPENDAFTARANEGARAMALAYSIAJABATANPENDAFTARANEGARAMA", 19, "bold", "#cdf5c3"))
    b.append(R(1096, 36, 35, 1564, BD))
    b.append('<g transform="translate(1124 60) rotate(90)">' + T(0, 0, "TANPENDAFTARANEGARAMALAYSIAJABATANPENDAFTARANEGARAMALAYSIAJABATANPENDAFTARANEGARAMALAYSIAJABATANPENDAFTARAN", 19, "bold", "#cdf5c3") + '</g>')
    b.append(T(38, 60, "JPN. LM15", 13))
    b.append(f'<image x="215" y="48" width="135" height="106" href="data:image/png;base64,{crop("bc4.jpg",(215,48,350,154))}"/>')
    b.append(f'<image x="772" y="44" width="106" height="106" href="data:image/png;base64,{crop("bc4.jpg",(772,44,878,150))}"/>')
    b.append(T(565, 82, "KERAJAAN MALAYSIA", 15, a="middle") + T(565, 96, "GOVERNMENT OF MALAYSIA", 10, a="middle", style="italic"))
    b.append(T(565, 122, "SIJIL KELAHIRAN", 21, "bold", "#222", "middle") + T(565, 140, "BIRTH CERTIFICATE", 15, "bold", "#222", "middle", style="italic"))
    b.append(T(558, 175, "Kaedah-Kaedah Pendaftaran Kelahiran dan Kematian 1958 ( Kaedah 16 )", 13.5, a="middle") + T(558, 188, "Births and Deaths Registration Rules 1958 ( Rule 16 )", 9, a="middle", style="italic"))
    b.append(R(893, 45, 195, 80, "#fff", LN, 1.5) + bars(901, 53, 179, 64, 7))
    b.append(T(897, 142, "No. Daftar :", 12.5) + T(897, 153, "Register No.", 8.5, style="italic"))
    b.append(T(905, 181, "A000000", 21, "bold"))

    def cell(x, y, w, h, ms, en):
        return R(x, y, w, h, "none", LN, 1.5) + T(x+10, y+22, ms, 16, fill="#333") + T(x+10, y+36, en, 11, fill="#444", style="italic")

    def V(x, y, s):
        return T(x, y, s, 17, "bold", "#111")

    def band(y, ms, en):
        return R(33, y, 1055, 30, BD, LN, 1.5) + T(560, y+21, ms + " /", 17, "normal", "#444", "end") + T(566, y+21, en, 16, "bold", "#444", style="italic")

    b.append(cell(33, 197, 525, 103, "Kawasan Pendaftaran", "Registration Area") + V(68, 275, "NEGERI CONTOH"))
    b.append(cell(558, 197, 530, 103, "Pusat Pendaftaran", "Registration Centre") + V(585, 275, "PUSAT CONTOH"))
    b.append(band(300, "KANAK-KANAK", "CHILD"))
    b.append(cell(33, 330, 1055, 56, "Nama Penuh", "Full Name") + V(330, 366, "NAMA CONTOH A/L CONTOH"))
    b.append(cell(33, 386, 525, 56, "Tarikh dan Waktu Kelahiran", "Date and Time of Birth") + V(330, 412, "01 JANUARI 2008") + V(330, 434, "12:00 PM"))
    b.append(cell(33, 442, 525, 52, "Keturunan", "Race") + V(330, 474, "MELAYU"))
    b.append(cell(558, 386, 530, 108, "Tempat Kelahiran", "Place of Birth") + V(585, 450, "HOSPITAL CONTOH") + V(585, 474, "BANDAR CONTOH"))
    b.append(cell(33, 494, 407, 55, "Taraf Kewarganegaraan", "Status of Citizenship") + V(230, 545, "WARGANEGARA"))
    b.append(cell(440, 494, 323, 55, "Jantina", "Gender") + V(540, 545, "LELAKI"))
    b.append(cell(763, 494, 325, 55, "Agama", "Religion") + V(850, 545, "ISLAM"))

    def person(y0, ms, en, name, age):
        r = band(y0, ms, en)
        r += cell(33, y0+30, 1055, 57, "Nama", "Name") + V(330, y0+66, name)
        r += cell(33, y0+87, 407, 55, "No. Kad Pengenalan", "Identity Card No.") + V(210, y0+137, "000000-00-0000")
        r += cell(440, y0+87, 118, 55, "Umur", "Age") + V(448, y0+137, age + " TAHUN")
        r += cell(558, y0+87, 530, 110, "Jenis dan No. Dokumen Lain", "Types and No. of Other Document") + V(590, y0+160, "Maklumat Tidak Berkenaan")
        r += cell(33, y0+142, 525, 55, "Taraf Kewarganegaraan", "Status of Citizenship") + V(230, y0+193, "WARGANEGARA")
        return r

    b.append(person(548, "BAPA", "FATHER", "NAMA BAPA CONTOH BIN CONTOH", "38"))
    b.append(person(745, "IBU", "MOTHER", "NAMA IBU CONTOH BINTI CONTOH", "36"))
    y = 942
    b.append(band(y, "PEMBERI MAKLUMAT", "INFORMANT"))
    b.append(cell(33, y+30, 1055, 57, "Nama", "Name") + V(330, y+66, "NAMA BAPA CONTOH BIN CONTOH"))
    b.append(cell(33, y+87, 525, 57, "No. Kad Pengenalan", "Identity Card No.") + V(210, y+130, "000000-00-0000"))
    b.append(cell(558, y+87, 530, 57, "Hubungan dengan Kanak-kanak", "Relationship to Child") + V(850, y+130, "BAPA"))
    y = 1103
    b.append(cell(33, y, 525, 70, "Tarikh Pendaftaran", "Date of Registration") + V(330, y+55, "15 JANUARI 2008"))
    b.append(cell(558, y, 530, 70, "Pendaftar", "Registrar"))
    b.append(cell(33, y+70, 525, 70, "Tarikh Cabutan", "Date of Extract") + V(330, y+125, "01 JANUARI 2026"))
    b.append(cell(558, y+70, 530, 70, "Cap Jabatan", "Departmental Stamp"))
    b.append(T(560, y+176, "SIJIL INI DIKELUARKAN OLEH JABATAN PENDAFTARAN NEGARA MALAYSIA", 11.5, "bold", "#444", "middle"))
    b.append(T(560, y+194, "THIS CERTIFICATE IS ISSUED BY THE NATIONAL REGISTRATION DEPARTMENT MALAYSIA", 10, "normal", "#444", "middle", style="italic"))
    b.append('</g></g>')
    inner = "".join(b)
    st = stamps(397, 560, (190, 72))
    co = [(826, 358*S+20, 1092*S, 358*S, 1), (826, 181*S+20, 1015*S, 181*S, 2), (826, 614*S+20, 1092*S, 614*S, 3), (826, 811*S+20, 1092*S, 811*S, 4)]
    items = [(1, ["Child's full name, same", "as the MyKad / IC"]), (2, ["Register No. (No. Daftar)", "and issuer: JPN Malaysia"]),
             (3, ["Father's name and IC", "number are shown"]), (4, ["Mother's name and IC", "number are shown"])]
    return page_wrap(inner, st, co, items)

# ---------------- school leaving certificate ----------------
def leaving():
    s = 1.398; ox = (794 - 530*s) / 2
    b = [f'<g transform="translate({ox:.1f} 0) scale({s})">']
    def dots(x1, x2, y):
        return f'<line x1="{x1}" y1="{y+3}" x2="{x2}" y2="{y+3}" stroke="#555" stroke-width=".8" stroke-dasharray="1 2"/>'
    def num(n, y, label):
        return T(58, y, f"{n}.", 10) + T(73, y, label, 10)
    def val(x, y, v):
        return T(x, y, v, 10.5, "normal", "#111")
    it = dict(style="italic")
    b.append(T(357, 67, "No.", 14, "bold") + '<line x1="378" y1="68" x2="432" y2="68" stroke="#222" stroke-width=".8"/>' + T(405, 64, "0000", 14, "bold", "#222", "middle"))
    b.append('<path d="M50 68 Q92 74 134 68 L134 106 Q134 130 92 144 Q50 130 50 106Z" fill="#1f8a3d" stroke="#e8c020" stroke-width="4"/>'
             '<path d="M92 76 l8 18 19 2-14 13 5 19-18-10-18 10 5-19-14-13 19-2z" fill="#f2d22a" stroke="#fff" stroke-width="1"/>'
             '<rect x="62" y="126" width="60" height="10" rx="2" fill="#f2d22a"/>')
    b.append(T(152, 110, "Sekolah Menengah Kebangsaan Contoh", 17.5, "bold", "#111"))
    b.append(T(180, 125, "Jalan Contoh, 00000 Bandar Contoh, Negeri Contoh.", 10, "normal", "#111"))
    b.append(T(265, 160, "SIJIL BERHENTI SEKOLAH", 14, "normal", "#111", "middle", fam="Georgia, serif", extra='letter-spacing="1.5" text-decoration="underline"'))
    b.append(num(1, 188, "Nama") + dots(100, 380, 188) + T(380, 188, "Jantina", 10) + dots(418, 470, 188) + val(110, 186, "NAMA CONTOH A/L CONTOH") + val(422, 186, "LELAKI"))
    b.append(num(2, 206, "Nama Bapa/Penjaga") + dots(165, 470, 206) + val(170, 204, "NAMA BAPA CONTOH BIN CONTOH"))
    b.append(num(3, 224, "No. Kad Pengenalan") + dots(170, 255, 224) + val(172, 222, "000000-00-0000") + T(262, 224, "4.", 10) + T(277, 224, "Tarikh Lahir", 10) + dots(335, 470, 224) + val(340, 222, "01.01.2008"))
    b.append(num(5, 242, "No. Sijil Lahir") + dots(150, 255, 242) + val(153, 240, "A 000000") + T(262, 242, "6.", 10) + T(277, 242, "Tempat Lahir", 10) + dots(340, 470, 242) + val(345, 240, "BANDAR CONTOH"))
    b.append(num(7, 261, "Bil. Kemasukan Sekolah") + dots(190, 255, 261) + val(193, 259, "00000") + T(262, 261, "8.", 10) + T(277, 261, "Tarikh Masuk Sekolah", 10) + dots(383, 470, 261) + val(386, 259, "JANUARI 2021"))
    b.append(T(58, 283, "9.", 10) + T(73, 283, "Tingkatan Mulai Masuk", 10) + dots(73, 255, 298) + val(95, 296, "TINGKATAN SATU")
             + T(262, 283, "10.", 10) + T(277, 283, "Tingkatan Tertinggi Yang Akhir", 10) + T(432, 283, "(Tulis dengan perkataan)", 6.5, **it) + dots(262, 470, 298) + val(285, 296, "TINGKATAN LIMA"))
    b.append(num(11, 316, "Pencapaian") + T(140, 316, "(a)  PMR", 10) + dots(190, 330, 316) + T(340, 316, "Tahun", 10) + dots(368, 470, 316) + val(372, 314, "TIADA"))
    b.append(T(140, 332, "(b)  SPM", 10) + dots(190, 330, 332) + T(340, 332, "Tahun", 10) + dots(368, 470, 332) + val(372, 330, "2025"))
    b.append(T(140, 348, "(c)  STPM", 10) + dots(190, 330, 348) + T(340, 348, "Tahun", 10) + dots(368, 470, 348) + val(372, 346, "TIADA"))
    b.append(num(12, 368, "Kedatangan") + dots(135, 470, 368) + val(140, 366, "BAIK"))
    b.append(num(13, 388, "Nama dan Alamat Sekolah Dahulu") + dots(228, 470, 388) + val(232, 386, "SEKOLAH RENDAH KEBANGSAAN") + dots(73, 470, 404) + val(78, 402, "CONTOH, BANDAR CONTOH"))
    b.append(T(58, 426, "14.", 10) + T(73, 426, "Aktiviti:", 10, "bold"))
    b.append(T(73, 440, "(a)  Jawatan Khas", 10) + dots(165, 470, 440) + val(170, 438, "PENGAWAS") + T(175, 452, "(Seperti Ketua Tingkatan, Pengawas dan lain-lain)", 7, **it))
    b.append(T(73, 466, "(b)  Pasukan Beruniform", 10) + dots(195, 470, 466) + val(200, 464, "TIADA") + T(180, 477, "(Sebutkan jawatan jika ada)", 7, **it))
    b.append(T(73, 490, "(c)  Persatuan", 10) + dots(140, 470, 490) + val(150, 488, "KELAB CONTOH (SETIAUSAHA)") + T(180, 502, "(Sebutkan jawatan jika ada)", 7, **it))
    for head, y0 in [("(d)  Permainan", 516), ("(e)  Olahraga", 567)]:
        b.append(T(73, y0, head, 10))
        for i, l in enumerate(["(i)    Mengambil Bahagian", "(ii)   Mewakili Negara/Negeri*/Daerah/Sekolah/Rumah", "(iii)  Jawatan Disandang"]):
            y = y0 + 13 + i*13; xe = 335 if i == 1 else (215 if i == 0 else 205)
            b.append(T(88, y, l, 9.5) + dots(xe, 470, y) + val(xe+5, y-2, "TIADA"))
    b.append(num(15, 620, "Kelakuan") + dots(125, 470, 620) + val(135, 618, "BAIK"))
    b.append(num(16, 640, "Tarikh Berhenti Sekolah") + dots(192, 470, 640) + val(197, 638, "30.11.2025"))
    b.append(num(17, 660, "Sebab Berhenti") + dots(148, 470, 660) + val(152, 658, "TAMAT PERSEKOLAHAN TINGKATAN 5"))
    b.append(num(18, 680, "Catatan Tambahan") + dots(150, 470, 680) + dots(73, 470, 700))
    b.append(L(58, 733, 200, 733, "#222", .7) + L(315, 733, 470, 733, "#222", .7))
    b.append(T(130, 746, "Tandatangan Murid", 8.5, "normal", "#222", "middle", **it))
    b.append(T(392, 746, "Tandatangan Pengetua dan Cop", 8.5, "normal", "#222", "middle", **it))
    b.append(T(58, 772, "Tarikh", 8.5, **it) + T(315, 772, "Tarikh", 8.5, **it) + L(88, 773, 200, 773, "#222", .5) + L(345, 773, 470, 773, "#222", .5))
    b.append(T(58, 792, "* Potong yang tidak berkenaan.", 7, **it))
    b.append('</g>')
    inner = "".join(b)
    def P(x, y): return ox + x*s, y*s
    st = stamps(397, 560, (ox + 92*s, 100*s))
    co = [(826, 186*s+20, P(478, 186)[0], 186*s, 1), (826, 222*s+20, P(478, 222)[0], 222*s, 2),
          (826, 106*s+20, P(496, 110)[0], 106*s, 3), (826, 638*s+20, P(478, 638)[0], 638*s, 4)]
    items = [(1, ["Student name matches", "the MyKad"]), (2, ["IC number and date of", "birth are correct"]),
             (3, ["School name and address", "(the issuer) at the top"]), (4, ["Leaving date and reason,", "with Principal's sign and stamp"])]
    return page_wrap(inner, st, co, items)

for n, f in [("birth_certificate", birth), ("school_leaving_cert", leaving)]:
    open(OUT + n + ".svg", "w", encoding="utf-8").write(f())
