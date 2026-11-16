import sys
sys.path.insert(0,"C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/gen_v2")
from common import T,R,L,callout,RED
OUT="C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/designs/samples_v2/"
GREY="#e3e5e8"
def logo(x,y,w,h):
    return R(x,y,w,h,GREY,"#b8bcc2",1,4)+T(x+w/2,y+h/2+4,"LOGO",12,"bold","#8a9099","middle")
def table(x,y,cols,rows,rh=22,hdr=True,fs=11):
    # cols: (title, width, anchor)
    tw=sum(c[1] for c in cols); o=[]
    o.append(R(x,y,tw,rh,"#eceef1","#555",.8))
    cx=x
    for t,w,a in cols:
        tx=cx+6 if a=="start" else (cx+w/2 if a=="middle" else cx+w-6)
        o.append(T(tx,y+rh/2+4,t,fs-1,"bold","#222",a)); cx+=w
    yy=y+rh
    for r in rows:
        o.append(R(x,yy,tw,rh,"none","#999",.5)); cx=x
        for (t,w,a),v in zip(cols,r):
            tx=cx+6 if a=="start" else (cx+w/2 if a=="middle" else cx+w-6)
            o.append(T(tx,yy+rh/2+4,v,fs,"normal","#111",a)); cx+=w
        yy+=rh
    return "".join(o),yy
def kv(x,y,label,val,lw=110,fs=11,vx=None):
    return T(x,y,label,fs,"normal","#333")+T(x+lw,y,":",fs)+T(x+lw+10,y,val,fs,"bold","#111")
def stamps(sx,sy):
    return (f'<g transform="translate(20 20)"><g transform="rotate(-45 397 560)" opacity="0.22"><rect x="182" y="445" width="430" height="230" rx="20" fill="none" stroke="#d92d20" stroke-width="7"/><text x="397" y="555" font-size="100" font-weight="bold" fill="#d92d20" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" letter-spacing="8">CONTOH</text><text x="397" y="645" font-size="100" font-weight="bold" fill="#d92d20" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" letter-spacing="8">SAMPLE</text></g>'
     f'<g transform="rotate(-18 {sx} {sy})" opacity="0.3"><rect x="{sx-95}" y="{sy-50}" width="190" height="101" rx="9" fill="none" stroke="#d92d20" stroke-width="3"/><text x="{sx}" y="{sy-2}" font-size="44" font-weight="bold" fill="#d92d20" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" letter-spacing="3.5">CONTOH</text><text x="{sx}" y="{sy+38}" font-size="44" font-weight="bold" fill="#d92d20" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" letter-spacing="3.5">SAMPLE</text></g></g>')
def panelbox(items):
    h=56+50*len(items)
    o=[R(858,20,330,h,"#fdf3f2",RED,1.2,8),T(876,52,"What we check",18,"bold",RED)]
    for i,(a,b) in enumerate(items):
        y=75+50*i
        o.append(f'<circle cx="886" cy="{y}" r="10" fill="#d92d20"/>'+T(886,y+4,str(i+1),12,"bold","#fff","middle")+T(906,y+5,a,14,"normal","#333")+T(906,y+23,b,14,"normal","#333"))
    return "".join(o)
def build(name,page,calls,items,sp):
    b=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1208 1163" width="1208" height="1163"><rect x="0" y="0" width="1208" height="1163" fill="#f4f5f7"/><rect x="24" y="25" width="794" height="1123" fill="#000" opacity=".12"/><g transform="translate(20 20)"><rect x="0" y="0" width="794" height="1123" fill="#fff" stroke="#ccc" stroke-width="1"/>{page}</g>'
    b+=stamps(*sp)
    for n,(y,tx) in enumerate(calls,1):
        b+=callout(826,y+20,tx+20,y+20,n)
    b+=panelbox(items)+"</svg>"
    open(OUT+name+".svg","w",encoding="utf-8").write(b)
def head(title1,title2,org,sub):
    return (logo(50,40,80,80)+T(397,70,org,22,"bold","#111","middle","Georgia, serif")+T(397,92,sub,11,"normal","#444","middle")
      +L(50,138,744,138,"#222",1.5)+T(397,170,title1,16,"bold","#111","middle","Georgia, serif")+T(397,188,title2,11,"normal","#444","middle",style="italic"))
G=lambda s:s

# ---------- 1 semester result
p=head("SLIP KEPUTUSAN PEPERIKSAAN SEMESTER","Semester Examination Result Slip","UNIVERSITI CONTOH","Pejabat Pendaftar  |  Bahagian Hal Ehwal Akademik  |  Jalan Contoh, 00000 Bandar Contoh")
r=[("Nama","CONTOH A/L CONTOH"),("No. Matrik","0000/1234"),("No. Kad Pengenalan","000000-00-0000"),("Program","Sarjana Muda Sains Komputer (Contoh)"),("Fakulti","Fakulti Sains Komputer Contoh"),("Sesi Akademik","2024/2025"),("Semester","Semester 2 (Tahun 1)")]
for i,(a,b) in enumerate(r): p+=kv(60,222+i*22,a,b,130,12)
rows=[("CS1013","PENGATURCARAAN ASAS","3","A","4.00","12.00"),("CS1023","MATEMATIK DISKRIT","3","B+","3.33","9.99"),("CS1033","STRUKTUR DATA","3","A-","3.67","11.01"),("CS1042","SISTEM DIGIT","2","B","3.00","6.00"),("MP1012","TITAS","2","A-","3.67","7.34"),("MP1022","KOKURIKULUM I","2","A","4.00","8.00"),("EN1012","BAHASA INGGERIS KOMUNIKASI","2","B+","3.33","6.66")]
cols=[("Kod Kursus",90,"start"),("Nama Kursus",270,"start"),("Kredit",70,"middle"),("Gred",70,"middle"),("Nilai Gred",90,"middle"),("Mata Gred",104,"middle")]
t,yy=table(50,395,cols,rows,24)
p+=t
p+=R(50,yy,694,24,"#f5f6f8","#999",.5)+T(60,yy+16,"JUMLAH",11,"bold")+T(50+90+270+35,yy+16,"16",11,"bold","#111","middle")+T(50+694-52,yy+16,"61.00",11,"bold","#111","middle")
yy+=50
p+=R(50,yy,330,100,"#fff","#555",1,4)
p+=T(64,yy+26,"PURATA NILAI GRED SEMESTER (GPA)",11,"bold")+T(330,yy+27,"3.81",18,"bold","#111","end")
p+=L(64,yy+40,366,yy+40,"#bbb",.8)+T(64,yy+66,"PURATA NILAI GRED KUMULATIF (CGPA)",11,"bold")+T(330,yy+68,"3.74",18,"bold","#111","end")
p+=T(64,yy+88,"Status: LULUS / Pass",11,"normal","#333")
p+=T(50,yy+130,"Skala Gred / Grade scale:",10,"bold","#333")
for i,g in enumerate(["A 4.00","A- 3.67","B+ 3.33","B 3.00","B- 2.67","C+ 2.33","C 2.00","F 0.00"]):
    p+=T(190+i*68,yy+130,g,10,"normal","#444")
p+=T(50,yy+160,"Slip ini dijana oleh komputer. / This slip is computer generated.",9,"normal","#555",style="italic")
p+=T(50,980,"Tarikh cetakan: 00 / 00 / 0000",9,"normal","#555")
p+=L(560,1010,744,1010,"#222",.6)+T(652,1024,"Pendaftar / Registrar",9,"normal","#333","middle")
p+=f'<path d="M575 1000 q10 -22 20 -4 t18 -2 t16 -10 t14 8 t14 -4" fill="none" stroke="#2a3f8f" stroke-width="1.4"/>'
build("semester_result",p,[(232,470),(343,470),(yy+50,382),(95,744)],
 [("Name and matric no. match","the MyKad and offer"),("Session and semester are","the one being asked for"),("GPA and CGPA shown at","the end of the slip"),("University name (the issuer)","at the top of the slip")],(640,260))

# ---------- 2 STPM
p=head("KEPUTUSAN PEPERIKSAAN SIJIL TINGGI PERSEKOLAHAN MALAYSIA","Malaysian Higher School Certificate Examination Results (STPM) - Tahun 2025","MAJLIS PEPERIKSAAN MALAYSIA","Malaysian Examinations Council  |  Persiaran Contoh, 00000 Bandar Contoh")
r=[("Nama Calon","CONTOH A/P CONTOH"),("No. Kad Pengenalan","000000-00-0000"),("Angka Giliran","0000/1234"),("Pusat Peperiksaan","SMK CONTOH (KOD 0000)"),("Tahun Peperiksaan","2025")]
for i,(a,b) in enumerate(r): p+=kv(60,232+i*24,a,b,130,12)
rows=[("900","PENGAJIAN AM","A-"),("954","MATHEMATICS (T)","B+"),("962","CHEMISTRY","A"),("964","PHYSICS","B+")]
cols=[("Kod",90,"middle"),("Mata Pelajaran / Subject",400,"start"),("Gred / Grade",204,"middle")]
t,yy=table(50,375,cols,rows,28,fs=12); p+=t
p+=R(50,yy+30,694,56,"#fff","#555",1,4)+T(66,yy+64,"PNGK (CGPA)",15,"bold")+T(728,yy+66,"3.58",24,"bold","#111","end")
p+=T(50,yy+120,"Keputusan: Memperoleh Sijil Tinggi Persekolahan Malaysia / Result: Certificate awarded",11,"bold","#333")
p+=T(50,yy+150,"Skala Gred / Grade scale:",10,"bold","#333")
for i,g in enumerate(["A 4.00","A- 3.67","B+ 3.33","B 3.00","B- 2.67","C+ 2.33","C 2.00","C- 1.67","D+ 1.33","D 1.00","F 0.00"]):
    p+=T(190+i*50,yy+150,g,9,"normal","#444")
p+=T(50,yy+172,"PNGK dikira daripada gred terbaik subjek termasuk Pengajian Am. / CGPA is worked out from the subject grades.",9,"normal","#555",style="italic")
p+=L(560,1010,744,1010,"#222",.6)+T(652,1024,"Ketua Eksekutif / Chief Executive",9,"normal","#333","middle")
build("higher_results_stpm",p,[(244,470),(280,470),(yy-14,744),(yy+58,744)],
 [("Candidate name and IC number","match the MyKad"),("Index number (Angka Giliran)","and the exam centre"),("Subject grades, with","Pengajian Am included"),("Overall PNGK (CGPA) as","Majlis Peperiksaan prints it")],(640,245))
# fix issuer callout later: panel item 4 mentions issuer

# ---------- 3 Matric
p=head("SLIP KEPUTUSAN PEPERIKSAAN PROGRAM MATRIKULASI","Matriculation Programme Examination Result Slip","KOLEJ MATRIKULASI CONTOH","Bahagian Matrikulasi, Kementerian Pendidikan Malaysia  |  Jalan Contoh, 00000 Bandar Contoh")
r=[("Nama","CONTOH A/L CONTOH"),("No. Kad Pengenalan","000000-00-0000"),("No. Matrik","0000/1234"),("Kolej","KOLEJ MATRIKULASI CONTOH"),("Sesi","2025/2026"),("Aliran","Sains")]
for i,(a,b) in enumerate(r): p+=kv(60,222+i*21,a,b,130,12)
cols=[("Kod",80,"start"),("Nama Kursus",334,"start"),("Kredit",90,"middle"),("Gred",90,"middle"),("Nilai Gred",100,"middle")]
y0=372
p+=T(50,y0,"SEMESTER 1",11,"bold","#111")
rows=[("SM015","MATHEMATICS I","3","B+","3.33"),("SP015","PHYSICS I","4","A-","3.67"),("SK015","CHEMISTRY I","4","A-","3.67"),("DK011","BAHASA INGGERIS I","2","A","4.00")]
t,y1=table(50,y0+6,cols,rows,22); p+=t
p+=T(740,y1+16,"PNGS (GPA) Semester 1 :  3.64",11,"bold","#111","end")
y2=y1+44
p+=T(50,y2,"SEMESTER 2",11,"bold","#111")
rows=[("SM025","MATHEMATICS II","3","A-","3.67"),("SP025","PHYSICS II","4","B+","3.33"),("SK025","CHEMISTRY II","4","A","4.00"),("DK021","BAHASA INGGERIS II","2","A-","3.67")]
t,y3=table(50,y2+6,cols,rows,22); p+=t
p+=T(740,y3+16,"PNGS (GPA) Semester 2 :  3.67",11,"bold","#111","end")
y4=y3+36
p+=R(50,y4,694,50,"#fff","#555",1,4)+T(66,y4+31,"PNGK (CGPA) KESELURUHAN",14,"bold")+T(728,y4+33,"3.65",22,"bold","#111","end")
p+=T(50,y4+80,"Kokurikulum :  Gred A   |   Markah 88.00",11,"bold","#333")
p+=T(50,y4+104,"Skala Gred / Grade scale:",10,"bold","#333")
for i,g in enumerate(["A 4.00","A- 3.67","B+ 3.33","B 3.00","B- 2.67","C+ 2.33","C 2.00","F 0.00"]):
    p+=T(190+i*68,y4+104,g,10,"normal","#444")
p+=T(50,y4+126,"Slip ini dijana oleh komputer. / This slip is computer generated.",9,"normal","#555",style="italic")
p+=L(560,1010,744,1010,"#222",.6)+T(652,1024,"Pengarah Kolej / College Director",9,"normal","#333","middle")
build("higher_results_matric",p,[(222+10,470),(222+4*21+...,470)] if False else [(228,470),(95,744),(222+4*21-4,470),(y4+25,744)],
 [("Student name, IC and matric","number match the MyKad"),("College name and the Bahagian","Matrikulasi (the issuer)"),("Session, with Semester 1 and","Semester 2 results"),("Overall PNGK (CGPA) and","the Kokurikulum grade")],(640,260))
