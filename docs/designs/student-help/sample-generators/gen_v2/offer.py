from common import *
V="Verdana, Tahoma, 'DejaVu Sans', Arial, sans-serif"
def t(x,y,s,size=23,w="normal",fill="#222",a="start",tl=None,style=""):
    return T(x,y,s,size,w,fill,a,V,tl,style)
BL="#3b3a98"
b=[R(0,0,1304,1844,"#fff")]
# crest (drawn) + UPNM wordmark
b.append('<circle cx="157" cy="115" r="74" fill="#3d7fc4"/><circle cx="157" cy="115" r="62" fill="#e8d44d"/><circle cx="157" cy="115" r="46" fill="#c8312b"/><circle cx="157" cy="115" r="30" fill="#f2e6a0"/><circle cx="157" cy="115" r="9" fill="#3b3a98"/>')
b.append(t(240,118,"UPNM",92,"bold",BL,tl=207))
b.append(R(243,132,203,32,"#333"))
b.append(t(246,144,"National Defence University of Malaysia",9.5,"normal","#fff",style="italic"))
b.append(t(260,158,"Kewajipan  ▪  Maruah  ▪  Integriti",9,"normal","#ddd"))
b.append(t(518,56,"Bahagian Pengurusan Akademik",19,"bold","#333"))
b.append(t(518,78,"Academic Management Division",13,"normal","#777",style="italic"))
for i,l in enumerate(["Aras 1, Bangunan Bestari","UPNM, Kem Perdana Sungai Besi","57000 Kuala Lumpur, Malaysia"]): b.append(t(518,162+i*17,l,12.5,"normal","#555"))
for (x,y,s) in [(806,158,"+603 - 9051 0000"),(806,198,"+603 - 9051 0000")]:
    b.append(f'<circle cx="{x+9}" cy="{y-5}" r="11" fill="#555"/>'); b.append(t(x+30,y,s,12,"normal","#555"))
b.append(t(838,175,"Samb. 0000/0000/0000",10,"normal","#777"))
for (x,y,s) in [(1046,158,"bpa@contoh.edu.my"),(1046,198,"www.contoh.edu.my")]:
    b.append(f'<circle cx="{x+9}" cy="{y-5}" r="11" fill="#555"/>'); b.append(t(x+30,y,s,12,"normal","#555"))
b.append(R(1090,40,105,80,"#e8e8e8","#555",2)); b.append(R(1102,52,28,32,"#444")); b.append(R(1148,52,30,32,"#999")); b.append(R(1100,92,86,10,"#bbb"))
b.append(R(50,234,790,12,BL)); b.append(R(855,234,187,12,"#e03a3a")); b.append(R(1053,234,189,12,"#1e9bd7"))
b.append(t(595,281,"Rujukan Kami : UPNM(BPA)04.03/03 - 0000000",23))
b.append(t(683,318,"Tarikh : 15/07/2026",23))
for y,s,w in [(362,"NAMA CONTOH BIN CONTOH","bold"),(393,"NO. 1, JALAN CONTOH","bold"),(424,"TAMAN CONTOH","bold"),(455,"00000 BANDAR CONTOH","bold"),(486,"NEGERI CONTOH","bold")]:
    b.append(t(50,y,s,24,w,"#111"))
b.append(t(50,580,"TAWARAN KEMASUKAN KE UNIVERSITI AWAM SESI AKADEMIK",24,"bold","#111",tl=1190))
b.append(t(50,611,"2026/2027",24,"bold","#111"))
b.append(t(50,680,"Sukacita dimaklumkan bahawa anda telah terpilih untuk mengikuti Program Asasi bagi Sesi",23,"normal","#222",tl=1190))
b.append(t(50,711,"Akademik 2026/2027. Butir-butir tawaran adalah seperti berikut :",23))
rows=[(789,"No. Matrik",["000000"]),(830,"Program Pengajian",["Asasi Kejuruteraan Dan Teknologi"]),(870,"Kod Program",["Z000"]),(911,"Tempoh Pengajian",["1 Tahun (2 Semester)"]),
      (983,"Tarikh Sistem eTawaran",["15 Julai 2026 hingga 23 Julai 2026","(Pelajar WAJIB melengkapkan maklumat diri secara dalam","talian di Sistem e-Tawaran)"]),
      (1055,"Tarikh Pendaftaran",["03/08/2026 (Isnin)"]),
      (1135,"Tempat Pendaftaran",["Kolej Kediaman Pelajar","Universiti Awam Contoh","Kem Sg. Besi, 57000 Sungai Besi","W.P. Kuala Lumpur"]),
      (1230,"Emel",["nama.contoh@contoh.com"]),(1273,"Yuran Pendaftaran",["RM 1,500.00"])]
for y,lab,vals in rows:
    b.append(t(57,y,lab,24,"bold","#111")); b.append(t(413,y,":",24,"bold","#111"))
    n=len(vals); y0=y-(n-1)*15.5
    for i,v in enumerate(vals): b.append(t(450,y0+i*31,v,24,"bold","#111"))
b.append(t(652,1346,"Arahan : Sila Muat Turun Dokumen-dokumen Penting Seperti di Lampiran Pada Sistem e-",22,"bold","#111","middle",tl=1165))
b.append(t(652,1377,"Tawaran",22,"bold","#111","middle"))
b.append(t(50,1450,"Sebarang pertukaran program adalah TIDAK dibenarkan. Sila muat turun dokumen-dokumen penting",23,"normal","#222",tl=1190))
b.append(t(50,1481,"dan baca dengan teliti setiap kembaran yang dilampirkan.",23))
b.append(t(50,1542,"Sekian, terima kasih.",23))
b.append(t(50,1577,"\"KEWAJIPAN, MARUAH, INTEGRITI\"",23,"bold","#111"))
b.append(t(50,1640,"Bahagian Pengurusan Akademik",23)); b.append(t(50,1671,"Universiti Awam Contoh",23))
b.append(t(50,1760,"Surat tawaran ini adalah janaan komputer. Tidak memerlukan tandatangan",19,"normal","#333",style="italic"))
b.append(t(432,1840,"Kewajipan, Maruah, Integriti",13,"normal","#444",style="italic")); b.append(t(680,1840,"Duty, Honour, Integrity",13,"normal","#444",style="italic"))
page="".join(b)
page+=callout(640,362,560,362,1,24,28)+callout(1120,830,960,830,2,24,28)+callout(1120,1055,900,1055,3,24,28)+callout(500,110,456,110,4,24,28)
page+=stamp(652,900,1100,190,150,-35,0.2)+stamp(450,130,880,130,105,-10,0.2)
items=[(1,["Your name","Must match your MyKad"]),
       (2,["Course and institution","Public university, polytechnic","or community college"]),
       (3,["Registration / intake date","Must be the coming intake"]),
       (4,["Official letterhead","and reference number"])]
body=f'<defs><clipPath id="c"><rect width="1304" height="1844"/></clipPath></defs><g transform="translate(20,20)"><g clip-path="url(#c)">{page}</g></g>'+panel(1380,110,520,items,30)
open("../designs/samples_v2/offer_letter.svg","w",encoding="utf-8").write(svg(1930,1884,body))
