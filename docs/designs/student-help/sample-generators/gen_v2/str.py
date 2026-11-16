from common import *
F="Roboto, 'Segoe UI', Arial, sans-serif"
def t(x,y,s,size=15,w="normal",fill="#222",a="start"): return T(x,y,s,size,w,fill,a,F)
NAVY="#0b3a7a"
W,H=390,860
b=[R(0,0,W,H,"#fff")]
# status bar of browser header
b.append(R(0,0,W,56,NAVY))
for i in range(3): b.append(R(16,20+i*7,20,3,"#fff",rx=1))
b.append(R(300,12,76,34,"#fff",rx=6));
b.append('<circle cx="323" cy="29" r="7" fill="none" stroke="#333" stroke-width="3"/>')
b.append('<polygon points="345,27 357,27 351,34" fill="#333"/>')
# MySTR bar
b.append(t(20,88,"Semakan Permohonan 2026",18,"bold",NAVY))
b.append(L(20,100,370,100,"#e3e7ee",1))
b.append(t(20,128,"Nama",13,"normal","#777")); b.append(t(20,150,"NAMA CONTOH BIN CONTOH",16,"bold","#222"))
b.append(t(20,184,"No. MyKad",13,"normal","#777")); b.append(t(20,206,"000000-00-0000",16,"bold","#222"))
b.append(t(20,240,"Tidak",14,"normal","#222"))
b.append(t(20,268,"Status Permohonan Semasa",14,"bold","#222"))
b.append('<circle cx="29" cy="289" r="8" fill="#0a2a8a"/>'); b.append(t(29,293,"i",11,"bold","#fff","middle"))
b.append(R(16,302,360,38,"#e8f6ec",rx=4)); b.append(t(28,328,"Lulus",19,"bold","#1b7f3b"))
b.append(t(20,380,"Fasa Bayaran",14,"bold","#222"))
for i,h in enumerate(["Fasa 1","Fasa 2","Fasa 3","Fasa 4"]):
    b.append(t(20+i*84,410,h,14,"bold","#222"))
b.append(L(20,420,370,420,"#ddd",1))
for i,v in enumerate(["500","500","500","0"]): b.append(t(20+i*84,448,v,15,"normal","#222"))
b.append(L(20,462,370,462,"#ddd",1))
b.append(t(20,496,"Jumlah Telah Dibayar",14,"bold","#222")); b.append(t(20,520,"RM 1,500",15,"normal","#222"))
b.append(t(20,554,"Jumlah Bayaran Keseluruhan",14,"bold","#222")); b.append(t(20,574,"STR",14,"bold","#222"))
b.append('<circle cx="64" cy="569" r="8" fill="#0a2a8a"/>'); b.append(t(64,573,"i",11,"bold","#fff","middle"))
b.append(t(20,598,"RM 2,000",15,"normal","#222"))
for i,lab in enumerate(["Sumbangan Asas Rahmah","Alasan Permohonan","Maklumat Pembayaran","Maklumat Anak"]):
    y=630+i*54
    b.append(R(0,y,W,53,"#e9f2fb","#d5e3f3",1)); b.append(t(20,y+32,lab,15,"bold","#222"))
    b.append(f'<polyline points="350,{y+30} 358,{y+22} 366,{y+30}" fill="none" stroke="#333" stroke-width="2"/>')
b.append(R(120,850,150,10,"#2b8be0",rx=3))
page="".join(b)
page+=callout(354,160,278,150,1,15,17)+callout(354,315,300,315,2,15,17)+callout(360,428,330,428,3,15,17)+callout(330,594,100,594,4,15,17)
page+=stamp(195,470,520,90,56,-50,0.22)+stamp(195,130,360,60,34,-12,0.22)
items=[(1,["Name and MyKad","Must match the student","or parent"]),
       (2,["Status Permohonan Semasa","Must say Lulus (approved)"]),
       (3,["Fasa Bayaran","Payment phases for this year"]),
       (4,["Jumlah Bayaran","Total STR amount"])]
body=f'<defs><clipPath id="c"><rect width="{W}" height="{H}"/></clipPath></defs><g transform="translate(20,20)"><g clip-path="url(#c)">{R(0,0,W,H,"#fff","#bbb",1)}{page}</g></g>'+panel(450,60,300,items,16)
open("../designs/samples_v2/str.svg","w",encoding="utf-8").write(svg(770,900,body))
