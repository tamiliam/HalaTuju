from common import *
F="Arial, Helvetica, sans-serif"; FS=15.5
def t(x,y,s,w="normal",a="start",sz=FS,fill="#111",extra=""): return T(x,y,s,sz,w,fill,a,F,extra=extra)
def dots(x1,x2,y): return f'<line x1="{x1}" y1="{y+3}" x2="{x2}" y2="{y+3}" stroke="#555" stroke-width="1.3" stroke-dasharray="1.2 3"/>'
b=[R(0,0,827,1169,"#fff","#ccc",1), R(35,33,758,1104,"none","#444",1)]
def title(y,s,sz=16):
    return t(413,y,s,"bold","middle",sz,extra='text-decoration="underline"')
b.append(title(152,"SURAT AKUAN PENGESAHAN PENDAPATAN"))
# applicant
b.append(t(112,234,"Saya")); b.append(dots(150,498,234)); b.append(t(155,231,"CONTOH A/L CONTOH"))
b.append(t(502,234,"No. K/P :")); b.append(dots(566,716,234)); b.append(t(570,231,"000000-00-0000"))
b.append(t(112,261,"Beralamat")); b.append(dots(182,716,261)); b.append(t(187,258,"No. 1, Jalan Contoh, Kampung Contoh,"))
b.append(dots(112,716,288)); b.append(t(117,285,"00000 Bandar Contoh, Selangor"))
b.append(t(112,315,"Dengan ini mengesahkan bahawa saya ")); b.append(t(375,315,"(bekerja sendiri/tidak bekerja)","bold")); b.append(t(625,315,"sebagai"))
b.append(dots(112,312,342)); b.append(t(117,339,"Penoreh getah"))
b.append(t(318,342,"dengan pendapatan sebanyak RM")); b.append(dots(568,650,342)); b.append(t(572,339,"1,200.00")); b.append(t(660,342,"sebulan."))
def row(y,lab,val=""):
    o=t(150,y,lab)+t(302,y,":")+dots(350,610,y)
    if val: o+=t(356,y-3,val)
    return o
b.append(row(390,"Tandatangan")); b.append(row(426,"No. Kad Pengenalan","000000-00-0000")); b.append(row(462,"Tarikh","03/11/2026"))
b.append('<path d="M362 392 C372 366 380 372 384 388 C388 396 394 372 402 376 C410 382 404 396 420 380 C436 366 440 392 470 382" fill="none" stroke="#1a237e" stroke-width="1.8"/>')
# approver
b.append(title(551,"PENGESAHAN DARI",15.5)); b.append(title(580,"KETUA KAMPUNG/ KETUA PENDUDUK/ PESURUHJAYA SUMPAH",15.5))
b.append(t(112,634,"Saya")); b.append(dots(150,498,634)); b.append(t(155,631,"CONTOH BIN CONTOH"))
b.append(t(502,634,"No. K/P:")); b.append(dots(560,716,634)); b.append(t(564,631,"000000-00-0000"))
for i,s in enumerate(["Dengan ini mengesahkan bahawa penama sememangnya tinggal di kawasan ini. Saya","dengan ini juga mengesahkan penama sememangnya tinggal di kawasan ini. Saya"]):
    b.append(t(112,661+i*27,s))
b.append(t(112,715,"dengan ini juga mengesahkan penama sememangnya ")); b.append(t(490,715,"(bekerja sendiri/ tidak bekerja)","bold"))
b.append(t(112,742,"dan pendapatannya adalah seperti yang dinyatakan di atas."))
b.append(row(790,"Tandatangan")); b.append(row(826,"No. Kad Pengenalan","000000-00-0000")); b.append(row(862,"Jawatan","Ketua Kampung")); b.append(row(898,"Tarikh","05/11/2026"))
b.append('<path d="M360 792 C372 764 380 772 386 790 C392 800 398 766 410 772 C420 780 412 798 432 778 C446 764 452 790 482 780" fill="none" stroke="#1a237e" stroke-width="1.8"/>')
b.append(t(150,1012,"Cop Rasmi :")); b.append(dots(238,420,1012))
# village head stamp (round, blue-violet ink), centred over Cop Rasmi
I="#2a3b9c"
st=(f'<g transform="translate(0 14) rotate(-8 330 985) translate(330 985) scale(1.2) translate(-330 -985)" opacity="0.85"><circle cx="330" cy="985" r="76" fill="none" stroke="{I}" stroke-width="3.5"/><circle cx="330" cy="985" r="68" fill="none" stroke="{I}" stroke-width="1.2"/><circle cx="330" cy="985" r="38" fill="none" stroke="{I}" stroke-width="1.2"/>'
 '<defs><path id="a1" d="M330 985 m-53 0 a53 53 0 1 1 106 0"/><path id="a2" d="M330 985 m-57 0 a57 57 0 0 0 114 0"/></defs>'
 f'<text font-size="15" font-weight="bold" fill="{I}" font-family="{F}" letter-spacing="1.5"><textPath href="#a1" startOffset="50%" text-anchor="middle">KETUA KAMPUNG</textPath></text>'
 f'<text font-size="13" font-weight="bold" fill="{I}" font-family="{F}" letter-spacing="1.5"><textPath href="#a2" startOffset="50%" text-anchor="middle">KAMPUNG CONTOH</textPath></text>'
 f'<text x="330" y="981" font-size="11" font-weight="bold" fill="{I}" text-anchor="middle" font-family="{F}">COP</text><text x="330" y="995" font-size="11" font-weight="bold" fill="{I}" text-anchor="middle" font-family="{F}">RASMI</text></g>')
b.append(st)
b.append(t(785,1108,"Borang Bantuan Pendidikan AA-BAKTIDESA KKDW 4 | 4","normal","end",12.5,"#7a8fbf",'font-style="italic"'))
page="".join(b)
page+=callout(842,420,722,231,2) if False else ""
co=[callout(560,1080,420,1030,1), callout(790,231,722,231,2), callout(790,339,724,339,3), callout(790,898,616,898,4)]
page+="".join(co)
page+=stamp(413,560,600,104,74,-24)+stamp(413,150,560,66,42,-3)
items=[(1,["Official stamp (cop rasmi) and","signature of the Ketua Kampung","The stamp must be inside this","section, with the signature"]),
       (2,["Parent's name and IC","Must match the parent","in the application"]),
       (3,["Monthly income (RM)","The amount we use for the","household income check"]),
       (4,["Date","Signed and dated recently"])]
S=0.9
body=f'<g transform="translate(20,20) scale({S})">{page}</g>'+panel(900,70,480,items,19)
open("../designs/samples_v2/income_support_doc.svg","w",encoding="utf-8").write(svg(1400,1092,body))
