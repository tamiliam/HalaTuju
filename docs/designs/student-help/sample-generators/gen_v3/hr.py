import sys
sys.path.insert(0,"C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/gen_v2")
from common import T,R,L,callout,RED,esc
OUT="C:/Users/tamil/AppData/Local/Temp/claude/eb28b8543bf7d74a/c815fc87-653e-43e3-acd1-b9174408e9c2/scratchpad/designs/samples_v2/"
SANS="Arial, Helvetica, sans-serif"; GEO="'Times New Roman', Times, serif"; TIM="'Times New Roman', Times, serif"
def tx(x,y,parts,size=12,fam=SANS,a="start",fill="#111",extra=""):
    """parts: list of (text, weight, style)"""
    s="".join(f'<tspan font-weight="{w}" font-style="{st}">{esc(t)}</tspan>' for t,w,st in parts)
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{a}" font-family="{fam}" xml:space="preserve" {extra}>{s}</text>'
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
    for n,(cy,ty,tx_) in enumerate(calls,1):
        b+=callout(826,cy+20,tx_+20,ty+20,n)
    b+=panelbox(items)+"</svg>"
    open(OUT+name+".svg","w",encoding="utf-8").write(b)

def crest(x,y,w,mono=False):
    """Jata Negara in a 100x120 box scaled to width w"""
    s=w/100
    Y="#f2c200" if not mono else "none"; RD="#c8102e" if not mono else "none"; BK="#111"; WH="#fff"
    TG="#e8a317" if not mono else "#fff"
    k=f'stroke="{BK}" stroke-width="{1.2 if mono else 0.8}"'
    g=[f'<g transform="translate({x} {y}) scale({s})">']
    # crescent + 14-point star
    g.append(f'<path d="M40 14 A12 12 0 1 1 56 24 A9.5 9.5 0 1 0 40 14 Z" fill="{Y}" {k}/>')
    import math
    pts=[]
    for i in range(28):
        r=9 if i%2==0 else 4; a=math.radians(i*360/28-90); pts.append(f"{58+r*math.cos(a)*0.0+50+ r*math.cos(a)-50+ 0:.1f},{14+r*math.sin(a):.1f}")
    pts=[]
    for i in range(28):
        r=8 if i%2==0 else 4; a=math.radians(i*360/28-90); pts.append(f"{54+r*math.cos(a):.1f},{20+r*math.sin(a):.1f}")
    g.append(f'<polygon points="{" ".join(pts)}" fill="{Y}" {k}/>')
    # tigers (left, mirrored right)
    tig=(f'<path d="M33 92 C22 88 14 76 17 62 C19 52 12 46 17 36 C22 30 27 34 28 40 L32 48 L36 56 L35 90 Z" fill="{TG}" {k}/>'
         f'<path d="M17 36 C14 30 20 26 25 30" fill="none" {k}/><path d="M19 58 L27 60 M18 68 L27 70 M20 78 L29 78 M22 48 L29 52" {k} fill="none"/>'
         f'<path d="M30 56 L36 62 L33 70" fill="none" {k}/>')
    g.append(tig); g.append(f'<g transform="translate(100 0) scale(-1 1)">{tig}</g>')
    # shield
    g.append(f'<path d="M33 36 H67 V70 Q67 86 50 94 Q33 86 33 70 Z" fill="{WH}" {k}/>')
    g.append(f'<path d="M33 36 H67 V46 H33 Z" fill="{RD}" {k}/>')
    for i in range(5): g.append(f'<rect x="{35+i*6.4:.1f}" y="38" width="3" height="6" fill="{WH if not mono else BK}"/>')
    g.append(f'<path d="M33 46 H67 V62 H33 Z" fill="{Y}" {k}/><path d="M50 46 V62" {k}/><path d="M33 54 H67" {k}/>')
    g.append(f'<path d="M33 62 H67 V70 Q67 86 50 94 Q33 86 33 70 Z" fill="{BK if not mono else WH}" {k}/>')
    g.append(f'<circle cx="50" cy="75" r="6" fill="{RD}" {k}/><path d="M44 75 H56 M50 69 V81" stroke="{WH if not mono else BK}" stroke-width="0.8"/>')
    # ribbon
    g.append(f'<path d="M8 100 Q50 108 92 100 L90 112 Q50 120 10 112 Z" fill="{Y}" {k}/>')
    g.append(f'<text x="50" y="112" font-size="5.2" font-weight="bold" text-anchor="middle" fill="{BK}" font-family="{SANS}" letter-spacing=".3">BERSEKUTU BERTAMBAH MUTU</text>')
    g.append('</g>')
    return "".join(g)
