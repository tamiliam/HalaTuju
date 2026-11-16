import math, random
RED = "#d92d20"
def esc(s): return s.replace("&","&amp;").replace("<","&lt;")
def T(x,y,s,size=12,w="normal",fill="#222",a="start",fam="Arial, Helvetica, sans-serif",tl=None,style="",extra=""):
    t = f' textLength="{tl}" lengthAdjust="spacingAndGlyphs"' if tl else ""
    st = f' font-style="{style}"' if style else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{fill}" text-anchor="{a}" font-family="{fam}"{t}{st} {extra}>{esc(s)}</text>'
def R(x,y,w,h,fill="none",stroke="none",sw=1,rx=0,extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="{rx}" {extra}/>'
def L(x1,y1,x2,y2,stroke="#222",sw=1):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"/>'
def callout(cx,cy,tx,ty,n,r=14,fs=17):
    """circle at (cx,cy), arrow pointing to (tx,ty)"""
    dx,dy=tx-cx,ty-cy; d=math.hypot(dx,dy); ux,uy=dx/d,dy/d
    sx,sy=cx+ux*r,cy+uy*r
    hx,hy=tx-ux*9,ty-uy*9
    px,py=-uy*5,ux*5
    return (f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{RED}" stroke-width="2.5"/>'
      f'<polygon points="{tx:.1f},{ty:.1f} {hx+px:.1f},{hy+py:.1f} {hx-px:.1f},{hy-py:.1f}" fill="{RED}"/>'
      f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{RED}"/>'
      + T(cx,cy+fs*0.35,str(n),fs,"bold","#fff","middle"))
def panel(x,y,w,items,fs=16,title="What we check"):
    out=[T(x,y,title,fs*1.25,"bold",RED)]
    yy=y+fs*2.2
    for n,lines in items:
        out.append(f'<circle cx="{x+fs*0.8}" cy="{yy-fs*0.3}" r="{fs*0.8}" fill="{RED}"/>')
        out.append(T(x+fs*0.8,yy-fs*0.3+fs*0.32,str(n),fs*0.95,"bold","#fff","middle"))
        for i,l in enumerate(lines):
            out.append(T(x+fs*2.2,yy+i*fs*1.35,l,fs,"bold" if i==0 else "normal","#333"))
        yy+=fs*1.35*len(lines)+fs*1.0
    return "".join(out)
def stamp(cx,cy,w,h,fs,rot=-30,op=0.22):
    return (f'<g transform="rotate({rot} {cx} {cy})" opacity="{op}">'
      f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="{h/9}" fill="none" stroke="{RED}" stroke-width="{fs/9}"/>'
      + T(cx,cy+fs*0.35,"SAMPLE / CONTOH",fs,"bold",RED,"middle") + '</g>')
def svg(w,h,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="#f3f4f6"/>{body}</svg>'
def bars(x,y,w,h,seed,fill="#111"):
    rnd=random.Random(seed); out=[]; cx=x
    while cx<x+w-2:
        bw=rnd.choice([1,1,2,3]); 
        if rnd.random()<.55: out.append(f'<rect x="{cx}" y="{y}" width="{bw}" height="{h}" fill="{fill}"/>')
        cx+=bw+rnd.choice([1,2])
    return "".join(out)
