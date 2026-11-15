from hr import *
def mpm_logo(x,y,w):
    h=w; c=w/2
    st="".join(f'<polygon points="{i*16-w},{h} {i*16-w+7},{h} {i*16+7},0 {i*16},0" fill="#f2c200"/>' for i in range(0,int(2*w/16)+3))
    return (f'<g transform="translate({x} {y})"><defs><clipPath id="dm"><polygon points="{c},0 {w},{c} {c},{h} 0,{c}"/></clipPath></defs>'
      f'<polygon points="{c},0 {w},{c} {c},{h} 0,{c}" fill="#111"/><g clip-path="url(#dm)">{st}</g>'
      f'<rect x="{w*.2}" y="{c-9}" width="{w*.6}" height="18" fill="#111"/>'
      f'<text x="{c}" y="{c+6}" font-size="{w*.24}" font-weight="bold" fill="#f2c200" text-anchor="middle" font-family="{SANS}">MPM</text></g>')
# ---------------- STPM
p=""
for i,r in enumerate([300,255,210,165,120]):
    p+=f'<polygon points="397,{560-r} {397+r},560 397,{560+r} {397-r},560" fill="none" stroke="#ececec" stroke-width="{6 if i%2==0 else 3}"/>'
p+=T(397,590,"MPM",90,"bold","#efefef","middle",GEO)
p+=crest(38,30,62)+mpm_logo(108,38,62)
p+=T(190,56,"MAJLIS PEPERIKSAAN MALAYSIA",16,"bold","#111","start",GEO)
p+=T(190,78,"SIJIL TINGGI PERSEKOLAHAN MALAYSIA (STPM)",14.5,"bold","#111","start",GEO)
p+=T(190,99,"Slip Keputusan Peperiksaan STPM 2025",14.5,"bold","#111","start",GEO)
p+=L(40,126,754,126,"#aaa",1)
rows=[("Nama","NAMA CONTOH BINTI CONTOH"),("No. Kad Pengenalan","000000-00-0000"),("Angka Giliran","SE0000/0000"),("No. Siri","0000000"),("Bil. Mata Pelajaran Didaftarkan","4"),("Purata Nilai Gred Keseluruhan (PNGK)","3.09")]
for i,(a,b) in enumerate(rows):
    y=164+i*27
    p+=T(40,y,a,14,"normal","#111")+T(318,y,":",14)+T(332,y,b,15,"bold","#111","start",GEO)
    if i==1: p+=L(332,y+3,332+len(b)*9.3,y+3,"#111",1)
cols=[("KOD",52),("MATA PELAJARAN",290),("WAJARAN (%)",80),("GRED KERTAS",80),("GRED MATA PELAJARAN",96),("NILAI GRED MATA PELAJARAN",116)]
x0=40; ty=338; hh=40
p+=R(x0,ty,714,hh,"#cfe3f4","#111",1)
cx=x0
hl={"GRED KERTAS":["GRED","KERTAS"],"WAJARAN (%)":["WAJARAN","(%)"],"NILAI GRED MATA PELAJARAN":["NILAI GRED","MATA PELAJARAN"],"GRED MATA PELAJARAN":["GRED MATA","PELAJARAN"]}
for n,(t,w) in enumerate(cols):
    if n: p+=L(cx,ty,cx,ty+hh,"#111",1)
    lines=hl.get(t,[t])
    y=ty+hh/2+4-(len(lines)-1)*6
    for l in lines: p+=T(cx+w/2,y,l,10.5,"bold","#111","middle"); y+=12
    cx+=w
subs=[("900","PENGAJIAN AM","B-","2.67",[("PENGAJIAN AM 1","29.0","B-"),("PENGAJIAN AM 2","22.0","D+"),("PENGAJIAN AM 3","29.0","C"),("PENGAJIAN AM 4","20.0","A")]),
("922","KESUSASTERAAN MELAYU KOMUNIKATIF","B-","2.67",[("KESUSASTERAAN MELAYU KOMUNIKATIF 1","26.67","C+"),("KESUSASTERAAN MELAYU KOMUNIKATIF 2","26.67","C"),("KESUSASTERAAN MELAYU KOMUNIKATIF 3","26.67","C+"),("KESUSASTERAAN MELAYU KOMUNIKATIF 4","20.0","A")]),
("940","SEJARAH","A-","3.67",[("SEJARAH 1","29.0","A-"),("SEJARAH 2","22.0","A"),("SEJARAH 3","29.0","B"),("SEJARAH 4","20.0","A")]),
("970","SENI VISUAL","B+","3.33",[("SENI VISUAL 1","40.0","B-"),("SENI VISUAL 2","35.0","A-"),("SENI VISUAL 3","25.0","A-")])]
y=ty+hh; xs=[x0]
for _,w in cols: xs.append(xs[-1]+w)
for code,name,g,v,papers in subs:
    bh=22+len(papers)*17+4
    p+=R(x0,y,714,bh,"none","#111",1)
    p+=T(x0+26,y+16,code,11.5,"bold","#111","middle")+T(xs[1]+6,y+16,name,11.5,"bold","#111")
    p+=T((xs[4]+xs[5])/2,y+16,g,11.5,"bold","#111","middle",GEO)+T((xs[5]+xs[6])/2,y+16,v,11.5,"bold","#111","middle",GEO)
    for i,(pn,wj,gk) in enumerate(papers):
        yy=y+36+i*17
        p+=T(xs[1]+22,yy,pn,10.5)+T((xs[2]+xs[3])/2,yy,wj,10.5,"normal","#111","middle")+T((xs[3]+xs[4])/2,yy,gk,10.5,"normal","#111","middle")
    for xx in xs[1:-1]: p+=L(xx,y,xx,y+bh,"#111",1)
    y+=bh
tbl_end=y
p+=tx(397,y+20,[("Nota",'bold',"normal"),(": Keputusan gred kertas yang dicatatkan ialah keputusan yang terbaik.","normal","normal")],10,SANS,"middle")
y+=62
p+=T(40,y,"NAMA KETUA EKSEKUTIF",11.5,"bold")+T(40,y+16,"Ketua Eksekutif",11.5,"bold")+T(40,y+32,"Majlis Peperiksaan Malaysia",11.5,"bold")
p+=tx(754,y+16,[("Tarikh Keputusan Dikeluarkan: 18 Jun 2026","bold","normal")],11.5,SANS,"end")
y+=62
p+=T(40,y,"Nota Penting:",11,"bold")
paras=[[("Slip keputusan ini ",0),("bukan",1),(" sijil STPM. Majlis Peperiksaan Malaysia berhak meminda butiran pada slip keputusan ini sebelum sijil dikeluarkan. Keputusan muktamad adalah seperti yang tercatat dalam sijil. Gred mata pelajaran adalah berdasarkan jumlah markah yang diperoleh dalam semua kertas mata pelajaran berkenaan dan wajaran kertas mata pelajaran berkenaan.",0)],
[("Pencapaian gred kertas diberikan gred A hingga F. Pencapaian gred mata pelajaran pada peringkat lulus penuh diberikan gred A hingga C, lulus sebahagian diberikan gred C- hingga D, dan gagal diberikan gred F.",0)],
[("Sijil STPM akan dianugerahkan kepada calon yang mendapat sekurang-kurangnya lulus sebahagian dalam satu mata pelajaran.",0)]]
y+=17
for n,para in enumerate(paras,1):
    words=[]
    for t,b in para:
        for w_ in t.split(" "):
            if w_: words.append((w_,b))
    lines=[[]]; cnt=0
    for w_,b in words:
        if cnt+len(w_)+1>122 and lines[-1]: lines.append([]); cnt=0
        lines[-1].append((w_,b)); cnt+=len(w_)+1
    p+=T(40,y,f"{n}.",10)
    for li in lines:
        parts=[(w_+(" " if j<len(li)-1 else ""),"bold" if b else "normal","normal") for j,(w_,b) in enumerate(li)]
        p+=tx(58,y,parts,10); y+=14.5
    y+=4
print("stpm",tbl_end,y)
build("higher_results_stpm",p,[(150,183,520),(240,222,500),(316,300,430),(430,430,744)],
 [("Name and IC number match","the student's MyKad"),("Angka Giliran (index number)","as printed by Majlis Peperiksaan"),("PNGK (CGPA) over all the","subjects registered"),("Subjects and grades; exam","year in the slip title")],(150,95))

# ---------------- MATRIC
K="#111"; p=""
p+=crest(40,26,74,mono=True)
hx=128
p+=T(hx,44,"KEMENTERIAN PENDIDIKAN MALAYSIA",12.5,"bold",K)
p+=T(hx,60,"MINISTRY OF EDUCATION MALAYSIA",11.5,"bold",K,style="italic")
p+=T(hx,76,"BAHAGIAN MATRIKULASI",10.5,"normal",K)
p+=T(hx,90,"MATRICULATION DIVISION",10.5,"normal",K,style="italic")
p+=T(hx,104,"ARAS 6 & 7, BLOK E15, KOMPLEKS E",10.5,"normal",K)
p+=T(hx,118,"PUSAT PENTADBIRAN KERAJAAN PERSEKUTUAN",10.5,"normal",K)
p+=T(hx,132,"62604 PUTRAJAYA",10.5,"bold",K)+T(hx,146,"MALAYSIA",10.5,"bold",K)
rx=585
for yy,lab_,val in [(44,"Telefon:","03 - 0000 0000"),(76,"Faks:","03 - 0000 0000 and 03 - 0000 0000"),(108,"Laman Sesawang:","www.moe.gov.my")]:
    p+=T(rx,yy,lab_,10,"bold",K)+T(rx,yy+13,val,10,"normal",K)
p+=tx(397,186,[("TRANSKRIP AKADEMIK / ","bold","normal"),("ACADEMIC TRANSCRIPT","bold","italic")],15,SANS,"middle",K)
def lab(x,y,m,e,colon,val):
    s=tx(x,y,[(m,"normal","normal"),(e,"normal","italic")],11,TIM)
    return s+T(colon,y,":",11,"normal",K,"start",TIM)+T(colon+14,y,val,11,"normal",K,"start",TIM)
def it(x,y,s): return T(x,y,s,11,"normal",K,"start",TIM,style="italic")
p+=lab(40,222,"NAMA/","NAME",170,"NAMA CONTOH BIN CONTOH")
p+=lab(40,240,"KOLEJ/","COLLEGE",170,"KOLEJ MATRIKULASI CONTOH")+it(184,254,"CONTOH MATRICULATION COLLEGE")
p+=lab(40,272,"JURUSAN/","MAJOR",170,"SAINS (SAINS HAYAT)")+it(184,286,"SCIENCE (LIFE SCIENCES)")
p+=lab(40,304,"SESI/","SESSION",170,"2024/2025")
p+=lab(450,222,"NO. KP/ ","IC NO.",575,"000000000000")
p+=lab(450,240,"NO. MATRIK/ ","MATRIC NO.",575,"MS0000000000")
p+=lab(450,258,"JANTINA/ ","GENDER",575,"LELAKI")+it(589,272,"MALE")
p+=L(40,322,754,322,K,1)
def hdr(x,y,m,e,a): return T(x,y,m,10,"bold",K,a,TIM)+T(x,y+12,e,10,"normal",K,a,TIM,style="italic")
p+=hdr(40,336,"KOD/","CODE","start")+hdr(112,336,"KURSUS/","COURSE","start")+hdr(490,336,"KREDIT/","CREDIT","middle")+hdr(580,336,"GRED/","GRADE","middle")+hdr(690,336,"MATA NILAIAN/","VALUE POINT","middle")
p+=L(40,356,754,356,K,1)
def sem(y,title,rows,gpa):
    s=T(40,y,title,10.5,"bold",K); y+=17
    for code,name,cr,gr,vp in rows:
        s+=T(40,y,code,10.5,"normal",K)+T(112,y,name,10.5,"normal",K)+T(490,y,cr,10.5,"normal",K,"middle")+T(580,y,gr,10.5,"normal",K,"middle")
        if vp: s+=T(690,y,vp,10.5,"normal",K,"middle")
        y+=16
    s+=T(754,y+2,"PNGS/ GPA : "+gpa,10.5,"bold",K,"end")
    return s,y+2
s,y=sem(374,"SEMESTER I",[("SB015","BIOLOGY 1","5","A-","3.67"),("SK015","CHEMISTRY 1","5","A","4.00"),("SM015","MATHEMATICS 1","5","B+","3.33"),("SP015","PHYSICS 1","5","A-","3.67"),("WE013","ENGLISH 1","3","C1",""),("WK002","KOKURIKULUM/ CO-CURRICULUM","2","A","")],"3.67"); p+=s
s,y=sem(y+26,"SEMESTER II",[("SB025","BIOLOGY 2","5","A","4.00"),("SK025","CHEMISTRY 2","5","A-","3.67"),("SM025","MATHEMATICS 2","5","B","3.00"),("SP025","PHYSICS 2","5","A","4.00"),("WE023","ENGLISH 2","3","C1",""),("WI001","PENDIDIKAN ISLAM/ ISLAMIC EDUCATION","1","A",""),("WP001","PENGAJIAN AM MATRIKULASI/ MATRICULATION GENERAL STUDIES","1","A","")],"3.67"); p+=s
y+=14; p+=L(40,y,754,y,K,1)
p+=T(397,y+22,"PURATA GRED BAGI KURSUS TERAS DAN ENGLISH",11,"bold",K,"middle",TIM)+T(397,y+36,"AVERAGE GRADE FOR CORE COURSES AND ENGLISH",11,"normal",K,"middle",TIM,style="italic")
ly=y+62
for i,(s_,g_) in enumerate([("BIOLOGY","A"),("CHEMISTRY","A"),("MATHEMATICS","B+"),("PHYSICS","A"),("ENGLISH","C1")]):
    p+=T(250,ly+i*17,s_,10.5,"normal",K)+T(540,ly+i*17,g_,10.5,"normal",K,"middle")
p+=tx(397,ly+5*17+14,[("PNGK/ CGPA: ","normal","normal"),("3.67","bold","normal")],11,TIM,"middle")
ox=ly+20; ink="#1c2340"
p+=f'<g opacity=".82">'
p+=T(335,ox,"Disahkan Benar Salinan Asal",8.5,"normal",ink,"start",TIM,style="italic")
p+=f'<path d="M342 {ox+26} c6 -18 12 -22 14 -8 c2 12 6 -16 12 -14 c6 2 -2 18 8 10 c6 -5 10 -12 14 -4 c4 8 12 -6 20 -2 l22 -6" fill="none" stroke="{ink}" stroke-width="1.4"/><path d="M340 {ox+30} q40 6 90 -4" fill="none" stroke="{ink}" stroke-width=".9"/>'
p+=T(340,ox+42,"NAMA PEGAWAI CONTOH",8,"normal",ink)+T(340,ox+53,"JAWATAN CONTOH",8,"normal",ink)
p+=f'<g transform="rotate(-8 480 {ox+36})"><rect x="440" y="{ox+16}" width="84" height="26" fill="none" stroke="{ink}" stroke-width="1.5" rx="2"/>'+T(482,ox+34,"18 SEP 2025",11,"bold",ink,"middle")+'</g></g>'
sy=ly+5*17+50
p+=T(40,sy+20,"STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI",13,"bold",K,"start",TIM)
p+=T(40,sy+36,"PASS AND COMPLETED MATRICULATION PROGRAMME",11.5,"normal",K,"start",TIM,style="italic")
by=sy+96
p+=tx(754,by,[("PENGARAH / ","normal","normal"),("DIRECTOR","normal","italic")],11,TIM,"end")
p+=T(754,by+16,"1 JULAI 2025/ 1 JULY 2025",11,"normal",K,"end",TIM)+T(754,by+32,"A000000",11,"bold",K,"end",TIM)
p+=T(40,by+36,"PM 00000000",26,"normal",K)
print("matric",by+36)
build("higher_results_matric",p,[(200,222,690),(262,240,690),(330,304,260),(sy-2,sy+16,560)],
 [("Name and IC number match","the student's MyKad"),("College name and matric","number (issuer check)"),("Session (year) of the","matriculation programme"),("PNGK/CGPA and the STATUS","line: pass and completed")],(150,95))
