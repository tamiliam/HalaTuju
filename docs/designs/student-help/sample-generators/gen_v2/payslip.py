from common import *
M="'Courier New', Courier, monospace"
fs=11.6
def m(x,y,s,a="start",w="normal"): return T(x,y,s,fs,w,"#111",a,M)
b=[]
b.append(R(0,0,903,1202,"#fff","#ccc",1))
# header
b.append(m(82,186,"SYARIKAT CONTOH SDN BHD",w="bold"))
b.append(m(82,198,"NAME   : NAMA CONTOH BIN CONTOH"))
b.append(m(82,210,"DEPT   : OPERASI"))
b.append(m(518,186,"PAY PERIOD  : END-OCT-2026"))
b.append(m(518,198,"STAFF#      : 000001"))
b.append(m(518,210,"I/C#        : 000000-00-0000"))
# column heads
b.append(m(115,241,"--- EARNINGS ---")); b.append(m(316,241,"--- RM ---"))
b.append(m(425,241,"--- DEDUCTIONS ---")); b.append(m(638,241,"--- RM ---"))
b.append(L(292,230,292,420)); b.append(L(392,230,392,568)); b.append(L(617,230,617,420))
rows=[("BASIC PAY","1,800.00"),("FIXED ALLOWANCE","200.00")]
for i,(a,v) in enumerate(rows):
    y=258+i*12.4; b.append(m(82,y,a)); b.append(m(386,y,v,"end")) if False else b.append(m(285,y,v,"end"))
ded=[("EMPLOYEE EPF (KWSP)","220.00"),("EMPLOYEE SOCSO (PERKESO)","10.00"),("EMPLOYEE EIS","4.00"),("INCOME TAX PCB","0.00")]
for i,(a,v) in enumerate(ded):
    y=258+i*12.4; b.append(m(400,y,a)); b.append(m(710,y,v,"end"))
b.append(m(247,416,"TOTAL :")); b.append(m(385,416,"2,000.00","end"))
b.append(m(555,416,"TOTAL :")); b.append(m(710,416,"234.00","end"))
b.append(L(78,427,710,427))
b.append(m(82,438,"ANNL LEAVE TAKEN : 0.00    BALANCE :  0.00"))
b.append(m(82,450,"SICK LEAVE TAKEN : 0.00    BALANCE :  0.00"))
b.append(m(532,438,"NETT PAY :")); b.append(m(710,438,"1,766.00","end"))
b.append(L(617,442,710,442)); b.append(L(617,445,710,445))
b.append(m(400,461,"EPF#      : 00000000")); b.append(m(576,461,"TAX# : SG 00000000 00"))
b.append(m(400,473,"SOCSO/EIS#: 000000000")); b.append(m(576,473,"BANK# : 1234567890123"))
# ytd bar
b.append(L(78,494,165,494)); b.append(m(167,497,"CURRENT-MONTH")); b.append(L(258,494,390,494))
b.append(L(397,494,516,494)); b.append(m(520,497,"YEAR-TO-DATE")); b.append(L(608,494,710,494))
b.append(m(165,509,"E.P.F.  SOCSO    EIS    TAX")); b.append(m(484,509,"E.P.F.  SOCSO    EIS    TAX"))
def cols(x0,vals): 
    return "".join(m(x0+i*58,0,"") for i in range(0))
def line(y,lab,a,b2,xlab,xs,vals):
    out=[m(xlab,y,lab)]
    for x,v in zip(xs,vals):
        if v: out.append(m(x,y,v,"end"))
    return "".join(out)
cx=[222,266,306,380]; yx=[525,569,609,712]
b.append(line(522,"EMP'EE:",0,0,82,[225,267,307,381],["220.00","10.00","4.00","0.00"]))
b.append(line(534,"EMP'ER:",0,0,82,[225,267,307,381],["260.00","35.00","4.00",""]))
b.append(line(546,"TOTAL :",0,0,82,[225,267,307,381],["480.00","45.00","8.00","0.00"]))
b.append(line(522,"EMP'EE:",0,0,400,[541,596,637,710],["2,200.00","100.00","40.00","0.00"]))
b.append(line(534,"EMP'ER:",0,0,400,[541,596,637,710],["2,600.00","350.00","40.00",""]))
b.append(line(546,"TOTAL :",0,0,400,[541,596,637,710],["4,800.00","450.00","80.00","0.00"]))
b.append(L(392,560,392,568))
page="".join(b)
# callouts on page (right margin x~790)
co=[callout(790,198,722,198,1),   # name/ic/period header
    callout(352,320,398,284,2),
    callout(790,416,716,416,3),
    callout(790,438,716,438,4)]
page+= "".join(co)
page+=stamp(450,380,640,110,78,-24)+stamp(300,200,380,70,44,-8,0.22)
items=[(1,["Name, IC and pay period","Must match the student's parent","and be a recent month"]),
       (2,["EPF / SOCSO / EIS / PCB","Statutory deduction lines","show a real employee"]),
       (3,["Total deductions","Earnings and deductions"," must add up"]),
       (4,["NETT PAY","The take-home amount","used for the income check"])]
body=f'<defs><clipPath id="c"><rect x="0" y="130" width="903" height="500"/></clipPath></defs><g transform="translate(20,20) scale(1.25) translate(0,-130)"><g clip-path="url(#c)">{page}</g></g>'+panel(1190,70,380,items,19)
open("../designs/samples_v2/payslip.svg","w",encoding="utf-8").write(svg(1600,665,body))
