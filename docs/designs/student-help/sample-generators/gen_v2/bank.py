from common import *
F="Arial, Helvetica, sans-serif"
CJ="'Microsoft YaHei','Noto Sans CJK SC',Arial,sans-serif"
def t(x,y,s,sz=8.5,w="normal",a="start",fam=F,fill="#111"): return T(x,y,s,sz,w,fill,a,fam)
b=[R(25,0,625,520,"#fff","#ccc",1)]
# logo: Maybank Islamic yellow block with tiger stripes mark
b.append(R(282,42,112,34,"#ffcc00"))
b.append(t(346,64,"Maybank",16,"bold","middle",F))
b.append(f'<g transform="translate(286,48) scale(.8)"><path d="M0 22 L6 4 L10 14 L14 2 L18 14 L22 6 L22 22 Z" fill="#111"/><path d="M5 22 L5 12 M11 22 L11 16 M17 22 L17 14" stroke="#ffcc00" stroke-width="1.6"/></g>')
b.append(t(346,73,"Islamic",8,"bold","middle",F))
b.append(t(338,84,"Maybank Islamic Berhad (787435-M)",5.6,"normal","middle"))
b.append(t(338,92,"15th Floor, Tower A, Dataran Maybank, 1, Jalan Maarof, 59000 Kuala Lumpur",5.2,"normal","middle"))
# left header block
b.append(t(55,109,"000001",8.5)); b.append(t(118,109,"IBS BANDAR CONTOH MAIN",8.5))
b.append(t(118,139,"CONTOH A/L CONTOH",8.5)); b.append(t(118,151,"NO. 1, JALAN CONTOH",8.5))
b.append(t(118,163,"00000 BANDAR CONTOH",8.5)); b.append(t(118,175,"SELANGOR",8.5))
# right labelled fields
def lab(y,my,en,val,cn=None):
    o=[t(406,y,my,5.6,"bold")]
    if cn: o.append(t(406,y+8,cn,6,"normal","start",CJ))
    o.append(t(406,y+(16 if cn else 8),en,5.6,"normal")); o.append(t(482,y+(8 if cn else 4),":",8))
    return "".join(o)
b.append(t(406,106,"MUKA/",5.6,"bold")); b.append(t(432,106,"/PAGE",5.6)); b.append(t(482,109,":",8)); b.append(t(620,109,"1",8.5,"normal","end"))
b.append(lab(126,"TARIKH PENYATA","STATEMENT DATE","","结单日期")); b.append(t(620,139,"31/10/26",8.5,"normal","end"))
b.append(lab(166,"NOMBOR AKAUN","ACCOUNT","","户口号码")); b.append(t(406,191,"NUMBER",5.6))
b.append(t(620,181,"0000 0000 0000",8.5,"normal","end"))
b.append(t(55,220,"PROTECTED BY PIDM UP TO RM250,000 FOR EACH DEPOSITOR",7.2)); b.append(t(620,220,"SAVINGS ACCOUNT-i",7.2,"normal","end"))
b.append(L(55,226,620,226,"#111",1.4)); b.append(L(55,228,620,228,"#111",.6))
b.append(t(337,239,"URUSNIAGA AKAUN/",9.5,"normal","end")); b.append(t(343,239,"户口交易",9,"normal","start",CJ)); b.append(t(383,239,"/ACCOUNT TRANSACTIONS",9.5))
b.append(L(172,241,505,241,"#111",1))
cols=[55,131,404,512,620]
for x in cols: b.append(L(x,243,x,480,"#111",.8))
b.append(L(55,243,620,243,"#111",.8)); b.append(L(55,278,620,278,"#111",1.2))
hd=[(93,"TARIKH MASUK","日期","ENTRY DATE"),(268,"BUTIR URUSNIAGA","交易说明","TRANSACTION DESCRIPTION"),(458,"JUMLAH URUSNIAGA","金额","TRANSACTION AMOUNT"),(566,"BAKI PENYATA","结单余额","STATEMENT BALANCE")]
for x,a,c,e in hd:
    b.append(t(x,252,a,5.6,"bold","middle")); b.append(t(x,260,c,6,"normal","middle",CJ)); b.append(t(x,270,e,5.2,"normal","middle"))
b.append(t(138,291,"BEGINNING BALANCE")); b.append(t(612,291,"80.64","end" and 8.5,"normal","end"))
rows=[("03/10/26","SVG GIRO CR","1,000.00+","1,080.64",["PENDAPATAN CONTOH"]),
      ("12/10/26","DEBIT ADVICE","30.00-","1,050.64",["CONTOH KEDAI RUNCIT"]),
      ("18/10/26","FUND TRANSFER","200.00+","1,250.64",["CONTOH A/P CONTOH"]),
      ("25/10/26","DEBIT ADVICE","0.50-","1,250.14",["AUTODEBIT 00000"])]
y=306
for d,desc,amt,bal,sub in rows:
    b.append(t(60,y,d)); b.append(t(138,y,desc)); b.append(t(500,y,amt,8.5,"normal","end")); b.append(t(612,y,bal,8.5,"normal","end"))
    for s in sub: b.append(t(138,y+12,s))
    y+=40
b.append(L(55,480,620,480,"#111",.8))
b.append(t(138,496,"ENDING BALANCE :",8.5,"bold")); b.append(t(612,496,"1,250.14",8.5,"bold","end"))
page="".join(b)
page+=callout(700,150,640,150,0) if False else ""
page+=callout(728,140,624,141,2) if False else ""
co=[callout(720,150,630-4,158,1,14,17)]  # placeholder replaced below
co=[callout(80,162,114,140,1), callout(678,181,626,181,2), callout(228,60,278,60,3), callout(678,139,626,139,4)]
page+="".join(co)
page+=stamp(337,300,500,86,60,-24)+stamp(337,62,330,52,34,-6)
page+=stamp(337,150,330,52,34,-4) if False else ""
items=[(1,["Account holder name","Must be the student's own name","(not a parent's or a joint name)"]),
       (2,["Account number","Digits must be readable","and match what you entered"]),
       (3,["Bank name","Logo or name of the bank","printed at the top"]),
       (4,["Statement date","A recent month, so the","account is still active"])]
S=1.6
body=f'<defs><clipPath id="c"><rect x="0" y="0" width="700" height="500"/></clipPath></defs><g transform="translate(20,20) scale({S}) translate(0,0)"><g clip-path="url(#c)">{page}</g></g>'+panel(1190,70,380,items,19)
open("../designs/samples_v2/bank_statement.svg","w",encoding="utf-8").write(svg(1600,850,body))
