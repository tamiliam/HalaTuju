from common import *
import random
b=[R(0,0,720,1020,"#fff")]
# right grey panel
b.append(R(463,143,232,790,"#ececec",rx=18))
b.append(T(540,80,"INVOIS",19,"normal","#555"))
b.append(T(512,130,"BIL AIR",36,"bold","#222"))
# logo (drawn): droplet + wordmark
b.append('<circle cx="80" cy="66" r="17" fill="#8d8d8d"/><circle cx="66" cy="55" r="6" fill="#bdbdbd"/><path d="M62 68 q14 14 36 -6 q-8 22 -36 6z" fill="#6f6f6f"/>')
b.append(T(104,74,"Air Selangor",31,"bold","#555"))
# barcodes (non-decodable random bars)
b.append(bars(66,117,192,15,1)); b.append(T(265,131,"102",7,"normal","#333")); b.append(T(66,145,"0000000",7))
addr=["NAMA CONTOH BIN CONTOH","NO 1 JALAN CONTOH","TAMAN CONTOH","00000 BANDAR CONTOH","SELANGOR"]
for i,l in enumerate(addr): b.append(T(66,160+i*13.2,l,12.3,"normal","#111"))
b.append(bars(66,258,102,20,2)); b.append(bars(347,258,64,20,3))
b.append(T(75,306,"0000000000",8)); b.append(T(375,306,"57.85",8))
f=[("No. Akaun",": 0000000000 (Baharu)",163),("",": 0000000000 (Lama)",176),("No. Invois",": 0000000000",189),("No. Meter",": 0000000000",202),
   ("Cagaran",": RM 40.00",216),("Kategori",": 10 Domestik",229),("Wilayah",": Contoh",242),("Tarikh",": 05/02/2026",256)]
for lab,v,y in f:
    bold = lab=="Kategori"
    b.append(T(483,y,lab,11,"bold" if bold else "normal","#222")); b.append(T(538,y,v,11,"bold" if bold else "normal","#222"))
# JomPAY
b.append(R(481,280,36,40,"#222",rx=5)); b.append(T(499,296,"Jom",9,"bold","#fff","middle")); b.append(T(499,308,"PAY",10,"bold","#fff","middle"))
b.append(R(525,277,152,43,"#fff","#222",1)); b.append(T(542,292,"Biller Code  :  4200",9)); b.append(T(542,309,"Ref-1 : 0000000000",9,"bold"))
b.append(T(481,332,"JomPAY online di Perbankan Internet dan Telefon Mudah",6.5,"normal","#333")); b.append(T(481,340,"Alih dengan akaun semasa, simpanan atau kad kredit",6.5,"normal","#333"))
b.append(T(483,351,"ALAMAT PREMIS:",11,"bold","#222"))
for i,l in enumerate(["NO 1 JALAN CONTOH","TAMAN CONTOH","00000 BANDAR CONTOH","SELANGOR"]): b.append(T(483,366+i*12.5,l,10.5,"normal","#222"))
# promo card
b.append(R(469,428,219,246,"#fff",rx=6))
b.append(R(469,428,219,92,"#5a5a5a",rx=6)); b.append(R(469,470,219,50,"#5a5a5a"))
b.append(T(578,453,"Layari laman web dan muat turun",11.5,"bold","#fff","middle")); b.append(T(578,467,"aplikasi baharu kami",11.5,"bold","#fff","middle"))
b.append(R(519,483,120,56,"#8a8a8a","#ddd",2)); b.append(R(527,490,104,40,"#c9d3d8")); b.append(R(570,539,18,8,"#8a8a8a")); b.append(R(480,505,26,48,"#444",rx=3)); b.append(R(648,510,22,40,"#444",rx=3))
b.append(T(578,586,"Imbas kod QR dan alami pengalaman",8.5,"normal","#333","middle")); b.append(T(578,597,"baharu bersama kami",8.5,"normal","#333","middle"))
b.append(R(502,610,44,44,"#bbb",rx=10)); b.append(T(524,662,"Air Selangor 2.0",5,"normal","#555","middle"))
rnd=random.Random(7)
for gx in range(15):
    for gy in range(15):
        if rnd.random()<.5: b.append(R(582+gx*4.4,606+gy*4.4,4.4,4.4,"#111"))
b.append(R(582,606,18,18,"#fff","#111",3)); b.append(R(630,606,18,18,"#fff","#111",3)); b.append(R(582,654,18,18,"#fff","#111",3))
b.append(T(473,714,"Hubungi kami untuk sebarang pertanyaan atau",10,"bold","#222")); b.append(T(473,727,"maklumat dalam saluran komunikasi rasmi kami:",10,"bold","#222"))
for i in range(3): b.append(R(473+i*20,734,16,16,"#222",rx=3))
b.append(T(538,746,"Media Sosial Air Selangor",10,"bold","#222"))
b.append(R(473,762,16,16,"#222",rx=8)); b.append(T(497,774,"Hubungi 15300",10,"bold","#222"))
b.append(T(473,792,"Muat Turun Aplikasi Air Selangor",9.5,"bold","#222"))
for i,l in enumerate(["App Store","Google Play","AppGallery"]):
    b.append(R(473+i*66,798,62,20,"#111",rx=4)); b.append(T(473+i*66+31,811,l,8,"bold","#fff","middle"))
def tab(x,y,w,label):
    return (R(x,y,w+40,26,"#e4e4e4",rx=13)+f'<polygon points="{x+w-6},{y} {x+w+66},{y} {x+w+66},{y+26} {x+w-14},{y+26}" fill="#222"/>'
            +T(x+14,y+17.5,label,12,"bold","#222")+T(x+w+30,y+17.5,"BIL",12,"bold","#fff","middle"))
b.append(tab(38,322,104,"RINGKASAN"))
b.append(R(38,358,417,132,"#fff","#222",2.5))
rows=[("Baki Terdahulu","RM 38.40"),("Bayaran Sehingga Kini","RM 0.00"),("Baki Belum Dijelaskan","RM 38.40"),("Bil Semasa (Bayar Sebelum 08/03/2026)","RM 19.45")]
for i,(a,v) in enumerate(rows):
    y=359+i*26; b.append(T(46,y+19,a,11.5,"normal","#111")); b.append(T(447,y+19,v,11.5,"normal","#111","end"))
    if i: b.append(L(38,y,455,y,"#555",1))
b.append(L(38,463,455,463,"#555",1)); b.append(R(39,464,415,25,"#d6d6d6")); b.append(L(314,359,314,463,"#555",1))
b.append(T(46,481,"Jumlah Perlu Dibayar",11.5,"bold")); b.append(T(447,481,"RM 57.85",11.5,"bold","#111","end"))
b.append(tab(38,500,104,"BUTIRAN"))
hx=[(40,"Meter No","start"),(125,"Tarikh","start"),(212,"Tempoh Bacaan","middle"),(268,"Bacaan","start"),(318,"Jenis Bacaan","start"),(420,"Penggunaan","middle")]
for x,t,a in hx: b.append(T(x,547,t,10.5,"bold","#222",a))
b.append(T(212,558,"(Hari)",10.5,"bold","#222","middle")); b.append(T(420,558,"(m3)",10.5,"bold","#222","middle"))
b.append(T(40,576,"0000000000",10.5)); b.append(T(125,576,"05/02/2026",10.5)); b.append(T(206,576,"28",10.5)); b.append(T(272,576,"886",10.5)); b.append(T(342,576,"N",10.5)); b.append(T(420,576,"37",10.5,"normal","#222","middle"))
b.append(T(125,591,"08/01/2026",10.5)); b.append(T(272,591,"849",10.5)); b.append(T(342,591,"N",10.5))
b.append(T(40,622,"Jumlah penggunaan yang dibilkan",10.5)); b.append(T(449,622,"37",10.5,"normal","#222","end"))
b.append(T(40,655,"Keterangan",10.5,"bold")); b.append(T(449,655,"Amaun (RM)",10.5,"bold","#222","end"))
ln=[(40,"Caj Penggunaan - 10 Domestik","19.45",676),(58,"Caj bagi 20.00 m3 pada RM0.57 per m3","11.40",689),(58,"Caj bagi 15.00 m3 pada RM1.03 per m3","15.45",702),(58,"Caj bagi 2.00 m3 pada RM2.00 per m3","4.00",715),
    (58,"Bayaran air 20m3 pertama (Oleh Kerajaan Negeri Selangor)","-11.40",728),(40,"Pelarasan","0.00",742),(40,"Baki Belum Dijelaskan","38.40",758),(40,"Penggenapan","0.00",790)]
for x,t,v,y in ln: b.append(T(x,y,t,10.5)); b.append(T(449,y,v,10.5,"normal","#222","end"))
b.append(R(38,795,417,17,"#d6d6d6")); b.append(T(40,807,"Jumlah Perlu Dibayar",10.5,"bold")); b.append(T(449,807,"57.85",10.5,"bold","#222","end"))
b.append(T(360,942,"Pengurusan Air Selangor Sdn. Bhd. (000000000000)",11,"bold","#333","middle"))
b.append(T(360,953,"A Member of Air Selangor Holdings Berhad Group",6.5,"normal","#555","middle"))
b.append(T(360,965,"Head Office, Jalan Pantai Baharu, 59200 Kuala Lumpur",11,"normal","#333","middle"))
b.append(T(360,988,"www.airselangor.com        15300",9.5,"normal","#333","middle"))
b.append(T(360,1005,"Gunalah Air Secara Berhemah, Gunalah Produk Cekap Air",10.5,"bold","#222","middle"))
page="".join(b)
page+=callout(300,172,262,162,1,12,15)+callout(690,170,654,170,2,12,15)+callout(690,256,650,256,3,12,15)+callout(20,475,36,475,4,12,15)
page+=stamp(360,520,640,110,80,-35,0.2)+stamp(200,80,330,60,42,-10,0.22)
items=[(1,["Name and address","Must match the parent or","guardian"]),
       (2,["Account number","Shows it is a real Air Selangor","account"]),
       (3,["Bill date","Must be a recent bill","(last 3 months)"]),
       (4,["Jumlah Perlu Dibayar","Amount due on the bill"])]
body=f'<g transform="translate(20,20)">{page}</g>'+panel(780,90,330,items,17)
open("../designs/samples_v2/water_bill.svg","w",encoding="utf-8").write(svg(1130,1060,body))
