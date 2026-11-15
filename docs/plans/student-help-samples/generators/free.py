import sys, random, textwrap
sys.path.insert(0, "C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/gen_v2")
from common import *
OUT = "C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/designs/samples_v2/"
SER = "'Times New Roman', Times, serif"
INK = "#1d2a6b"; STP = "#2b3a9e"

def panel_(x, y, items):
    out = [T(x, y, "What we check", 18, "bold", RED)]
    yy = y + 23
    for n, lines in items:
        out.append(f'<circle cx="{x+10}" cy="{yy}" r="10" fill="{RED}"/>' + T(x+10, yy+4, str(n), 12, "bold", "#fff", "middle"))
        for i, l in enumerate(lines):
            out.append(T(x+30, yy+5+i*18, l, 14, "normal", "#333"))
        yy += 18*len(lines) + 14
    return "".join(out)

def stamps(cx, cy, logo, small_only=False):
    s = ""
    if not small_only:
        s += (f'<g transform="rotate(-45 {cx} {cy})" opacity="0.22">'
         f'<rect x="{cx-215}" y="{cy-115}" width="430" height="230" rx="20" fill="none" stroke="{RED}" stroke-width="7"/>'
         + T(cx, cy-5, "CONTOH", 100, "bold", RED, "middle", extra='letter-spacing="8"')
         + T(cx, cy+85, "SAMPLE", 100, "bold", RED, "middle", extra='letter-spacing="8"') + '</g>')
    lx, ly = logo
    s += (f'<g transform="rotate(-18 {lx} {ly})" opacity="0.3">'
          f'<rect x="{lx-95}" y="{ly-50}" width="190" height="101" rx="9" fill="none" stroke="{RED}" stroke-width="3"/>'
          + T(lx, ly-2, "CONTOH", 44, "bold", RED, "middle", extra='letter-spacing="3.5"')
          + T(lx, ly+38, "SAMPLE", 44, "bold", RED, "middle", extra='letter-spacing="3.5"') + '</g>')
    return s

def page_wrap(inner, st, callouts, items, panel_h=256):
    W, H = 1208, 1163
    o = [R(0, 0, W, H, "#f4f5f7"), R(24, 25, 794, 1123, "#000", extra='opacity=".12"'),
         f'<g transform="translate(20 20)">{R(0,0,794,1123,"#fff","#ccc")}{inner}</g>',
         f'<g transform="translate(20 20)">{st}</g>']
    for cx, cy, tx, ty, n in callouts:
        o.append(callout(cx, cy, tx+20, ty+20, n))
    o.append(R(858, 20, 330, panel_h, "#fdf3f2", RED, 1.2, 8))
    o.append(panel_(876, 52, items))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">' + "".join(o) + '</svg>'

def scribble(x, y, w, seed, h=34):
    r = random.Random(seed); d = f"M{x} {y}"; px = x
    n = 7
    for i in range(n):
        nx = x + w*(i+1)/n; up = r.choice([-1, 1])
        d += f" C{px+w/n*.2:.0f} {y+up*h*r.uniform(.6,1.3):.0f} {nx-w/n*.3:.0f} {y-up*h*r.uniform(.5,1.2):.0f} {nx:.0f} {y+r.uniform(-8,8):.0f}"
        px = nx
    d += f" L{x+w+10} {y+6}"
    return f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="1.8" stroke-linecap="round" opacity=".9"/>'

def official(cx, cy, rx, ry, lines, rot=-8, fs=13):
    o = [f'<g transform="rotate({rot} {cx} {cy})" opacity=".78">',
         f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="{STP}" stroke-width="2.6"/>',
         f'<ellipse cx="{cx}" cy="{cy}" rx="{rx-6}" ry="{ry-6}" fill="none" stroke="{STP}" stroke-width="1"/>']
    n = len(lines); y0 = cy - (n-1)*fs*0.75 + fs*0.35
    for i, (l, b) in enumerate(lines):
        o.append(T(cx, y0 + i*fs*1.5, l, fs if b else fs-2.5, "bold" if b else "normal", STP, "middle"))
    o.append('</g>')
    return "".join(o)

def para(x, y, text, size=14, lh=24, width=88, fam=SER, w="normal"):
    out = []; lines = textwrap.wrap(text, width)
    for i, l in enumerate(lines):
        out.append(T(x, y+i*lh, l, size, w, "#111", fam=fam))
    return "".join(out), y + len(lines)*lh

def shield(x, y, s=1):
    return (f'<g transform="translate({x} {y}) scale({s})"><path d="M0 0 Q35 8 70 0 L70 44 Q70 72 35 88 Q0 72 0 44Z" fill="#c9cdd2" stroke="#aeb3b9" stroke-width="2"/>'
            '<path d="M35 14 l7 16 17 2-13 12 4 17-15-9-15 9 4-17-13-12 17-2z" fill="#e3e6e9"/></g>')

# ---------------- 1. reference letter ----------------
def reference():
    b = [shield(62, 40, 0.95)]
    b.append(T(432, 72, "SMK CONTOH", 27, "bold", "#111", "middle", fam=SER))
    b.append(T(432, 92, "SEKOLAH MENENGAH KEBANGSAAN CONTOH", 12.5, "normal", "#111", "middle", fam=SER))
    b.append(T(432, 109, "No. 1, Jalan Contoh, 00000 Bandar Contoh, Negeri Contoh", 12, "normal", "#111", "middle", fam=SER))
    b.append(T(432, 124, "Tel: 00-000 0000   |   E-mel: contoh@moe.edu.my", 12, "normal", "#111", "middle", fam=SER))
    b.append(L(55, 142, 739, 142, "#111", 2.2) + L(55, 146, 739, 146, "#111", .8))
    b.append(T(70, 182, "Ruj. Kami : SMKC/SS/000/2026", 14, fam=SER))
    b.append(T(70, 206, "Tarikh      : 14 November 2026", 14, fam=SER))
    b.append(T(70, 254, "Kepada Sesiapa Yang Berkenaan,", 14, fam=SER))
    b.append(T(70, 290, "Tuan/Puan,", 14, fam=SER))
    b.append(T(70, 328, "SURAT SOKONGAN : NAMA CONTOH A/L CONTOH (NO. K/P: 000000-00-0000)", 14, "bold", fam=SER))
    b.append(L(70, 333, 640, 333, "#111", 1))
    y = 368
    for t in ["Dengan segala hormatnya perkara di atas adalah dirujuk.",
              "2.  Dimaklumkan bahawa NAMA CONTOH A/L CONTOH (No. K/P: 000000-00-0000) merupakan bekas murid Tingkatan 5 di SMK Contoh dan telah menduduki Sijil Pelajaran Malaysia (SPM) pada tahun 2025.",
              "3.  Sepanjang berada di sekolah ini, beliau seorang murid yang berdisiplin, rajin dan bertanggungjawab. Beliau berasal daripada keluarga yang kurang berkemampuan dan layak dipertimbangkan untuk menerima bantuan pendidikan.",
              "4.  Sehubungan itu, pihak sekolah menyokong permohonan beliau untuk melanjutkan pengajian ke peringkat yang lebih tinggi. Sokongan ini diberikan atas permintaan pelajar berkenaan.",
              "Sekian, terima kasih."]:
        s, y = para(70, y, t, 14, 24, 86); b.append(s); y += 14
    b.append(T(70, y+6, "Yang benar,", 14, fam=SER))
    sy = y + 70
    b.append(scribble(80, sy, 130, 3))
    b.append(official(270, sy+10, 98, 54, [("GURU BESAR", True), ("SMK CONTOH", True), ("00000 BANDAR CONTOH", False)], -7))
    b.append(L(70, sy+60, 260, sy+60, "#111", .8))
    b.append(T(70, sy+82, "(NAMA CONTOH BIN CONTOH)", 14, "bold", fam=SER))
    b.append(T(70, sy+102, "Guru Besar", 14, fam=SER))
    b.append(T(70, sy+120, "SMK Contoh, 00000 Bandar Contoh", 14, fam=SER))
    st = stamps(397, 560, (640, 860))
    co = [(826, sy+90+20, 262, sy+90, 1), (826, sy+10+20, 372, sy+10, 2), (826, 328+20, 650, 328, 3), (826, 206+20, 262, 206, 4)]
    items = [(1, ["Writer's full name and post", "(Guru Besar, Ketua Kampung)"]), (2, ["Signature and the official", "stamp of the school / office"]),
             (3, ["Student's name and IC number", "match the MyKad"]), (4, ["Date of the letter", "(recent, not old)"])]
    return page_wrap("".join(b), st, co, items)

# ---------------- 2. guardianship letter ----------------
def guardian():
    b = []
    b.append(T(397, 78, "SURAT AKUAN PENJAGA", 22, "bold", "#111", "middle", fam=SER) + L(262, 85, 532, 85, "#111", 1.4))
    b.append(T(397, 104, "(Pengakuan Penjagaan Pelajar)", 12.5, "normal", "#111", "middle", fam=SER, style="italic"))
    b.append(T(724, 150, "Tarikh : 14 November 2026", 13, "normal", "#111", "end", fam=SER))
    s, y = para(70, 190, "Saya, NAMA PENJAGA CONTOH BIN CONTOH, No. Kad Pengenalan 000000-00-0000, beralamat di No. 1, Jalan Contoh, Kampung Contoh, 00000 Bandar Contoh, dengan ini mengaku bahawa saya ialah PENJAGA kepada pelajar berikut:", 14, 24, 86); b.append(s)
    ty = y + 12
    rows = [("Nama pelajar", "NAMA CONTOH A/L CONTOH"), ("No. Kad Pengenalan", "000000-00-0000"), ("Hubungan dengan saya", "CUCU (SAYA ATUK SEBELAH BAPA)")]
    for i, (k, v) in enumerate(rows):
        yy = ty + i*28
        b.append(T(100, yy, k, 14, fam=SER) + T(290, yy, ":", 14, fam=SER) + T(306, yy, v, 14, "bold", fam=SER))
    y = ty + 3*28 + 14
    for t in ["1.  Pelajar tersebut tinggal bersama dan berada di bawah jagaan saya sejak tahun 2015 kerana ibu bapanya tidak dapat menjaganya.",
              "2.  Saya bertanggungjawab ke atas pelajar tersebut dan memberi kebenaran kepadanya untuk memohon bantuan pendidikan.",
              "3.  Segala maklumat di atas adalah benar. Saya faham bahawa pengakuan palsu boleh dikenakan tindakan undang-undang."]:
        s, y = para(70, y, t, 14, 24, 86); b.append(s); y += 8
    sy = y + 60
    b.append(scribble(80, sy, 120, 11))
    b.append(L(70, sy+30, 260, sy+30, "#111", .8))
    b.append(T(70, sy+50, "(NAMA PENJAGA CONTOH BIN CONTOH)", 13, "bold", fam=SER))
    b.append(T(70, sy+68, "Penjaga   |   No. K/P: 000000-00-0000", 12.5, fam=SER))
    cy0 = sy + 110
    b.append(T(70, cy0+26, "PENGESAHAN", 14, "bold", fam=SER))
    s, yb = para(70, cy0+50, "Saya mengesahkan bahawa pengakuan di atas dibuat oleh penjaga yang bernama di atas dan beliau ialah penjaga kepada pelajar tersebut.", 13.5, 22, 90); b.append(s)
    ky = yb + 62
    b.append(scribble(85, ky, 120, 5))
    b.append(official(450, ky-6, 92, 50, [("KETUA KAMPUNG", True), ("KAMPUNG CONTOH", True), ("00000 BANDAR CONTOH", False)], -6))
    b.append(L(70, ky+34, 260, ky+34, "#111", .8))
    b.append(T(70, ky+54, "(NAMA KETUA KAMPUNG CONTOH BIN CONTOH)", 13, "bold", fam=SER))
    b.append(T(70, ky+72, "Ketua Kampung / Penghulu / Pesuruhjaya Sumpah*", 12.5, fam=SER))
    b.append(T(70, ky+90, "Tarikh: 14 November 2026", 12.5, fam=SER))
    b.append(R(55, cy0, 684, ky+130-cy0, "none", "#555", 1))
    b.append(T(70, ky+112, "* Potong yang tidak berkenaan.", 10.5, fam=SER, style="italic"))
    st = stamps(397, 560, (640, 640))
    co = [(826, 190+20, 690, 190, 1), (826, ty+20, 520, ty, 2), (826, ty+56+20, 590, ty+56, 3), (826, ky-6+20, 552, ky-6, 4)]
    items = [(1, ["Guardian's full name and IC", "number, written in full"]), (2, ["Student's full name and IC", "number (as on the MyKad)"]),
             (3, ["Relationship to the student", "(e.g. grandfather, uncle)"]), (4, ["Signature and stamp of the", "Ketua Kampung / Penghulu /", "Commissioner for Oaths"])]
    return page_wrap("".join(b), st, co, items, 290)

# ---------------- 3. statement of intent ----------------
def soi():
    A = "Arial, Helvetica, sans-serif"; b = []
    b.append(T(397, 88, "STATEMENT OF INTENT", 20, "bold", "#111", "middle", fam=A))
    for i, (k, v) in enumerate([("Name", "NAMA CONTOH A/L CONTOH"), ("IC No.", "000000-00-0000"),
                                ("Address", "No. 1, Jalan Contoh, 00000 Bandar Contoh"),
                                ("Course", "Diploma in Mechanical Engineering, Politeknik Contoh")]):
        yy = 140 + i*24
        b.append(T(70, yy, k, 13.5, "bold", fam=A) + T(140, yy, ":", 13.5, fam=A) + T(154, yy, v, 13.5, fam=A))
    b.append(L(70, 244, 724, 244, "#999", .8))
    b.append(T(70, 280, "To the Selection Committee,", 14, fam=A))
    y = 316; ys = []
    for t in ["I am writing to apply for support to continue my studies. I have just finished SPM and I have been offered a place to study Mechanical Engineering, because I want to become an engineer who repairs and maintains machines in factories near my hometown.",
              "I come from a small family. My father works as a lorry driver and my mother helps at home. Our monthly income is small and we have five people in the household, so paying for fees, books and transport is very hard for us.",
              "At school I was a prefect and the secretary of the Robotics Club. I enjoy fixing broken fans and radios for my neighbours. These experiences taught me to be patient and to work in a team.",
              "If I receive this support, I promise to study hard and to help other students in my kampung once I have graduated. Thank you for reading my statement and for your kind consideration."]:
        ys.append(y)
        s, y = para(70, y, t, 14, 24, 88, fam=A); b.append(s); y += 18
    b.append(T(70, y+10, "Yours sincerely,", 14, fam=A))
    sy = y + 64
    b.append(scribble(80, sy, 120, 21))
    b.append(L(70, sy+28, 250, sy+28, "#111", .8))
    b.append(T(70, sy+48, "NAMA CONTOH A/L CONTOH", 14, "bold", fam=A))
    b.append(T(70, sy+68, "Date: 14 November 2026", 14, fam=A))
    st = stamps(397, 560, (640, 880))
    co = [(826, 207+20, 505, 207, 1), (826, ys[0]+30, 665, ys[0]+30, 2), (826, ys[1]+30, 665, ys[1]+30, 3), (826, sy+68+20, 240, sy+64, 4)]
    items = [(1, ["Your name, IC number and", "the course you want to study"]), (2, ["Your goals: what you want", "to do after your studies"]),
             (3, ["Your background: family,", "interests, experiences"]), (4, ["Your signature (or typed", "name) and the date"])]
    return page_wrap("".join(b), st, co, items)

# ---------------- 4. photo ----------------
def person(x, y, w, h, bg="#f2f3f5", skin="#aab0b7", cloth="#6b7480", hs=1.0, dx=0, dy=0, tilt=0, extra_bg="", cid="c"):
    cx = x + w/2 + dx; hr = w*0.19*hs; hy = y + h*0.40 + dy
    return (f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>'
            f'<g clip-path="url(#{cid})"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}"/>{extra_bg}'
            f'<g transform="rotate({tilt} {cx} {hy})">'
            f'<path d="M{cx-w*0.42*hs} {y+h+4} Q{cx-w*0.40*hs} {hy+hr*1.9} {cx-hr*0.5} {hy+hr*1.45} L{cx+hr*0.5} {hy+hr*1.45} Q{cx+w*0.40*hs} {hy+hr*1.9} {cx+w*0.42*hs} {y+h+4}Z" fill="{cloth}"/>'
            f'<rect x="{cx-hr*0.38}" y="{hy+hr*0.7}" width="{hr*0.76}" height="{hr*0.95}" fill="{skin}"/>'
            f'<ellipse cx="{cx}" cy="{hy}" rx="{hr*0.86}" ry="{hr}" fill="{skin}"/></g></g>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#9aa0a6" stroke-width="1.5"/>')

def tick(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="19" fill="#1f8a3d"/><path d="M{cx-9} {cy} l6 7 l12 -14" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>')
def cross(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="17" fill="{RED}"/><path d="M{cx-7} {cy-7} l14 14 M{cx+7} {cy-7} l-14 14" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/>')

def photo():
    A = "Arial, Helvetica, sans-serif"; b = []
    b.append('<defs><filter id="blur" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="7"/></filter>'
             '<linearGradient id="shade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset=".55" stop-color="#000" stop-opacity=".55"/><stop offset="1" stop-color="#000" stop-opacity=".78"/></linearGradient></defs>')
    b.append(T(70, 72, "Photo: what to upload", 22, "bold", "#111", fam=A))
    b.append(T(70, 96, "A recent passport-style photo of yourself (drawn examples only)", 13, "normal", "#555", fam=A))
    gx, gy, gw, gh = 100, 140, 250, 333
    b.append(person(gx, gy, gw, gh, cid="g"))
    b.append(tick(gx+gw-6, gy+6))
    b.append(T(gx, gy+gh+34, "GOOD", 20, "bold", "#1f8a3d", fam=A))
    for i, t in enumerate(["Plain, light background", "Face centred, looking at the camera", "No hat, filter or heavy editing", "Sharp, clear and recent"]):
        b.append(f'<path d="M{gx} {gy+gh+62+i*26} l5 6 l10 -12" fill="none" stroke="#1f8a3d" stroke-width="2.6" stroke-linecap="round"/>' + T(gx+24, gy+gh+66+i*26, t, 14, fam=A, fill="#333"))
    b.append(T(420, 128, "DO NOT UPLOAD", 16, "bold", RED, fam=A))
    bw, bh = 170, 227; bx = 420
    labels = [["Blurry or out of focus"], ["Too dark, shadow", "on the face"], ["Selfie, busy background,", "head cropped"]]
    ys = [146, 416, 686]
    b.append(f'<g filter="url(#blur)">{person(bx, ys[0], bw, bh, cid="b1")}</g>')
    b.append(f'<rect x="{bx}" y="{ys[0]}" width="{bw}" height="{bh}" fill="none" stroke="#9aa0a6" stroke-width="1.5"/>')
    b.append(person(bx, ys[1], bw, bh, bg="#2b2d31", skin="#4a4d52", cloth="#34363a", cid="b2"))
    b.append(f'<rect x="{bx}" y="{ys[1]}" width="{bw}" height="{bh}" fill="url(#shade)"/>')
    busy = ''.join([f'<rect x="{bx+5}" y="{ys[2]+10}" width="50" height="90" fill="#e0a458"/>', f'<rect x="{bx+130}" y="{ys[2]+20}" width="55" height="70" fill="#5aa2c6"/>',
                    f'<rect x="{bx+60}" y="{ys[2]+150}" width="40" height="80" fill="#7ab87a"/>', f'<circle cx="{bx+160}" cy="{ys[2]+170}" r="22" fill="#d56b6b"/>',
                    f'<path d="M{bx} {ys[2]+120} l40 -30 l40 30 l40 -30 l40 30" stroke="#8a6bb5" stroke-width="8" fill="none"/>'])
    b.append(person(bx, ys[2], bw, bh, bg="#d9d3c3", extra_bg=busy, hs=1.35, dy=-bh*0.30, dx=22, tilt=-14, cid="b3"))
    for yb, lab in zip(ys, labels):
        for i, l in enumerate(lab):
            b.append(T(bx+bw+20, yb+bh/2-6+i*20, l, 14, fam=A, fill="#333"))
        b.append(cross(bx+bw-4, yb+6))
    st = stamps(397, 560, (640, 1000), small_only=True)
    out = page_wrap("".join(b), st, [], [(1, ["Plain, light background", "with nothing behind you"]), (2, ["Face centred and sharp,", "looking straight ahead"]),
        (3, ["No hat, filter or heavy", "editing; head fully shown"]), (4, ["Avoid blur, dark light,", "selfies and cropped heads"])])
    def ptr(cx, cy, tx, ty, n): return callout(cx+20, cy+20, tx+20, ty+20, n)
    extra = (ptr(44, gy+60, gx+20, gy+60, 1) + ptr(44, gy+190, gx+gw/2-40, gy+190, 2) + ptr(44, gy+20, gx+gw/2-20, gy+20, 3)
             + ptr(372, 380, bx-4, 380, 4))
    return out.replace("</svg>", extra + "</svg>")

def guardian():
    b = []
    b.append(T(397, 78, "SURAT KUASA / KEBENARAN PENJAGA", 21, "bold", "#111", "middle", fam=SER) + L(212, 85, 582, 85, "#111", 1.4))
    b.append(T(397, 104, "(Surat Akuan Ibu / Bapa)", 12.5, "normal", "#111", "middle", fam=SER, style="italic"))
    b.append(T(70, 150, "No. 1, Jalan Contoh,", 13, fam=SER) + T(70, 168, "Kampung Contoh, 00000 Bandar Contoh", 13, fam=SER))
    b.append(T(724, 150, "Tarikh : 14 November 2026", 13, "normal", "#111", "end", fam=SER))
    s, y = para(70, 214, "Saya, NAMA BAPA CONTOH BIN CONTOH, No. Kad Pengenalan 000000-00-0000, ialah BAPA kepada pelajar yang dinamakan di bawah:", 14, 24, 86); b.append(s)
    ty = y + 14
    rows = [("Nama pelajar", "NAMA CONTOH A/L CONTOH"), ("No. Kad Pengenalan", "000000-00-0000")]
    for i, (k, v) in enumerate(rows):
        yy = ty + i*28
        b.append(T(100, yy, k, 14, fam=SER) + T(290, yy, ":", 14, fam=SER) + T(306, yy, v, 14, "bold", fam=SER))
    gy = ty + 2*28 + 18
    s, y = para(70, gy, "Dengan ini saya membenarkan dan melantik orang yang dinamakan di bawah sebagai PENJAGA pelajar tersebut:", 14, 24, 86); b.append(s)
    gy2 = y + 14
    rows = [("Nama penjaga", "NAMA PENJAGA CONTOH BIN CONTOH"), ("No. Kad Pengenalan", "000000-00-0000"), ("Hubungan dengan pelajar", "BAPA SAUDARA")]
    for i, (k, v) in enumerate(rows):
        yy = gy2 + i*28
        b.append(T(100, yy, k, 14, fam=SER) + T(290, yy, ":", 14, fam=SER) + T(306, yy, v, 14, "bold", fam=SER))
    y = gy2 + 3*28 + 18
    s, y = para(70, y, "Penjaga tersebut diberi kuasa untuk bertindak bagi pihak saya dan pelajar itu dalam permohonan bantuan pendidikan ini, termasuk memberi persetujuan dan menandatangani borang yang berkaitan. Pelajar itu tinggal di bawah jagaannya kerana saya tidak dapat menjaganya sepenuhnya.", 14, 24, 86); b.append(s)
    s, y = para(70, y+10, "Saya mengesahkan bahawa maklumat di atas adalah benar.", 14, 24, 86); b.append(s)
    sy = y + 80
    b.append(scribble(80, sy, 120, 11))
    b.append(L(70, sy+30, 260, sy+30, "#111", .8))
    b.append(T(70, sy+50, "(NAMA BAPA CONTOH BIN CONTOH)", 13, "bold", fam=SER))
    b.append(T(70, sy+68, "Bapa pelajar   |   No. K/P: 000000-00-0000", 12.5, fam=SER))
    b.append(T(70, sy+86, "Tarikh: 14 November 2026", 12.5, fam=SER))
    st = stamps(397, 560, (640, 860))
    co = [(826, 214+20, 690, 214, 1), (826, ty+20, 520, ty, 3), (826, gy2+20, 580, gy2, 2), (826, gy2+56+20, 450, gy2+56, 2), (826, sy+20, 215, sy, 4)]
    co = [(826, 214+20, 690, 214, 1), (826, ty+20, 520, ty, 2), (826, gy2+20, 640, gy2, 3), (826, sy+20, 215, sy, 4)]
    items = [(1, ["Parent's full name and IC", "number (father or mother)"]), (2, ["Student's full name and IC", "number (as on the MyKad)"]),
             (3, ["Guardian's name, IC number", "and relationship to student"]), (4, ["Parent's signature", "and the date"])]
    return page_wrap("".join(b), st, co, items)

for n, f in [("reference_letter", reference), ("guardianship_letter", guardian), ("statement_of_intent", soi), ("photo", photo)]:
    open(OUT + n + ".svg", "w", encoding="utf-8").write(f())
print("ok")
