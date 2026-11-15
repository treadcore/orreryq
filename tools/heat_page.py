"""telemetry.py chart: QUEUE/plan/telemetry.html, the fleet's heat as one page (see tools/telemetry.py).

Paul, 15 November: "continue applying graphs. more overlays. correlating the harddrives and other
temperatures to the thermal soak. that will be longer, days of data ... keep it by cpu primary, and its
general conservation of watts and tau calculations. expand the row on click, less hover information."

THE PAGE is the fleet's watts over the record (each machine a band: what goes in comes out), then a
row a machine, the CPU first: its temperature against its limit, its watts, and the tau, R and C its
steps gave. A row opens on a click:

  the CPU (and the card) in degrees, each fitted step drawn over it as the curve the fit found;
  the watts, at the wall, at the CPU, at the card, on the same clock;
  THE SOAK: every other thermometer (disks, NVMe, memory, the board, a port) overlaid, each as
  degrees above its own lowest in the record, coloured by what kind of part it is;
  and a table of those parts. A click on a part's line in the table picks its line out of the overlay.

A SOAK FIGURE is not a step fit: a disk never gets a clean step. It is the part's temperature fitted
to the machine's watts passed through one lag, T = a + k * lag(W, tau): the tau that fits best is how
slowly the part follows the machine's heat, k its degrees a watt. It is said only where the fit
explains 60% of the part's movement, and as "longer than the record" where the best tau is the
longest tried. Hours of record give a first figure; days give the disks'.

Pointing at a plot shows the clock and that plot's leading values, one line, and nothing else.
"""
import json
import math
import os
import time

import telemetry
import telemetry_chart
import thermal

POINTS = 600
SERIES_LIGHT = telemetry_chart.SERIES_LIGHT
SERIES_DARK = telemetry_chart.SERIES_DARK
# A kind of part: its name on the page, and its place in the palette (the CPU is 0 and the card 1 everywhere).
KINDS = [("disk", "disks", 2), ("nvme", "NVMe", 3), ("memory", "memory", 4), ("board", "the board", 6), ("port", "10 GbE", 7), ("card", "the card", 1)]


def kind(k):
    if k == "gpu.c":
        return "card"
    if k.startswith(("drivetemp", "disk.")):
        return "disk"
    if k.startswith("nvme"):
        return "nvme"
    if k.startswith("jc42") or "DIMM" in k:
        return "memory"
    if k.startswith("nic."):
        return "port"
    return "board"


def lag_fit(ws, ys, dt):
    """(tau_s, degrees a watt, r2, at_edge) of ys = a + k * lag(ws, tau), or None where nothing is to be said."""
    idx = [i for i in range(len(ys)) if ys[i] is not None]
    wv = [w for w in ws if w is not None]
    if len(idx) < 60 or not wv or max(wv) - min(wv) < 20:
        return None
    yv = [ys[i] for i in idx]
    if max(yv) - min(yv) < 2:
        return None
    span = dt * len(ys)
    taus, tau = [], 30.0
    while tau < span / 2:
        taus.append(tau)
        tau *= 1.3
    if not taus:
        return None
    my = sum(yv) / len(yv)
    syy = sum((y - my) ** 2 for y in yv)
    best = None
    for tau in taus:
        a = 1 - math.exp(-dt / tau)
        lp, cur = [], None
        for w in ws:
            if w is not None:
                cur = w if cur is None else cur + a * (w - cur)
            lp.append(cur)
        xs = [lp[i] for i in idx]
        if any(x is None for x in xs):
            j = next(i for i, x in enumerate(xs) if x is not None)
            xs, yy = xs[j:], yv[j:]
        else:
            yy = yv
        mx, m2 = sum(xs) / len(xs), sum(yy) / len(yy)
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - m2) for x, y in zip(xs, yy))
        s2 = sum((y - m2) ** 2 for y in yy) or syy
        if sxx <= 0 or s2 <= 0:
            continue
        r2 = sxy * sxy / (sxx * s2)
        if best is None or r2 > best[2]:
            best = (tau, sxy / sxx, r2, tau == taus[-1])
    if not best or best[2] < 0.6 or best[1] <= 0:
        return None
    return best


def page(q, args):
    hours = float(args[0]) if args and args[0].replace(".", "").isdigit() else 72.0
    out = next((a for a in args if a.endswith(".html")), os.path.join(q, "plan", "telemetry.html"))
    thermal.model(q)
    doc = telemetry.load(os.path.join(q, "plan", "thermal.json"), {}) or {}
    said = {m["name"]: m for m in doc.get("machines", [])}
    boxes = (telemetry.load(os.path.join(thermal.HERE, "plans", "power.json"), {}) or {}).get("boxes", {})
    now = time.time()
    data = {n: telemetry.series(q, n, hours) for n in sorted(telemetry.machines(q))}
    data = {n: r for n, r in data.items() if len(r) >= 3}
    if not data:
        print("no telemetry yet: `telemetry.py QUEUE pull` brings it")
        return 1
    t0 = min(r[0]["t"] for r in data.values())
    dt = (now - t0) / POINTS
    ts = [round(t0 + dt * (i + 0.5)) for i in range(POINTS)]
    machines = []
    for name, rows in data.items():
        acc = [[] for _ in range(POINTS)]
        for r in rows:
            acc[min(POINTS - 1, max(0, int((r["t"] - t0) / dt)))].append(r)
        keys = set().union(*rows)
        ck = thermal.cpu_keys(keys)

        def col(f, digits=1):
            o = []
            for b in acc:
                v = [x for x in (f(r) for r in b) if x is not None]
                o.append(round(sum(v) / len(v), digits) if v else None)
            return o

        box = boxes.get(name)
        w3 = lambda r, i: (lambda x: x[i] if x else None)(thermal.watts(box, r))
        wall = col(lambda r: w3(r, 2), 0)
        m = said.get(name, {})
        # The parts that are not the CPU: no ACPI zone (a constant), no input with nothing on it
        # (-39, 127), and an NVMe's first and eighth sensors are its Composite again.
        parts = []
        for k in sorted(keys):
            if not telemetry_chart.is_temp(k) or k in ck or k.startswith(("acpitz", "coretemp", "k10temp", "zenpower")):
                continue
            if k.startswith("nvme") and k.endswith((".Sensor_1", ".Sensor_8")):
                continue
            ys = col(lambda r: r[k] if k in r and 5 < r[k] < 120 else None)
            v = [y for y in ys if y is not None]
            if len(v) < 3:
                continue
            f = lag_fit(wall, ys, dt)
            parts.append({"key": k, "kind": kind(k), "y": ys, "lo": min(v), "hi": max(v), "now": v[-1],
                          "tau_s": round(f[0]) if f else None, "c_w": round(f[1], 3) if f else None,
                          "r2": round(f[2], 2) if f else None, "edge": bool(f and f[3])})
        # The CPU's steps: on a CPU read core by core, one step is every core's fit; the median speaks.
        by_at = {}
        for f in m.get("fits", []):
            if f.get("main") and f["channel"] in ck:
                by_at.setdefault(f["at"], []).append(f)
        steps = []
        for at, fs in sorted(by_at.items()):
            fs.sort(key=lambda f: f["tau_s"])
            f = fs[len(fs) // 2]
            st = {k: f.get(k) for k in ("at", "step", "tau_s", "start_c", "end_c", "taus_held", "r_c_w", "c_j_c", "dp_w")}
            # The plot's line is the hottest core: the curve drawn over it is that core's own fit.
            hot = max(fs, key=lambda f: max(f["start_c"], f["end_c"]))
            st["curve"] = [hot["tau_s"], hot["start_c"], hot["end_c"]]
            st["cores"] = len(fs)
            steps.append(st)
        slow = max((p for p in parts if p["tau_s"]), key=lambda p: p["tau_s"], default=None)
        machines.append({
            "name": name, "cpu": col(lambda r: max((r[k] for k in ck if k in r), default=None)),
            "card": col(lambda r: r.get("gpu.c")) if "gpu.c" in keys else None,
            "wall": wall, "cpu_w": col(lambda r: w3(r, 0)), "card_w": col(lambda r: r.get("gpu.w")) if "gpu.w" in keys else None,
            "now": {k: m.get(k) for k in ("cpu_c", "cpu_hot", "gpu_c", "gpu_hot", "wall_w", "cpu_w", "gpu_w", "busy", "watts_from", "air_m3h")},
            "model": m.get("model") or {}, "steps": steps, "parts": parts,
            "slow": {"key": slow["key"], "tau_s": slow["tau_s"], "edge": slow["edge"]} if slow else None})
    page_doc = {"t": ts, "machines": machines, "fleet": {k: doc.get("fleet", {}).get(k) for k in ("heat_w", "btu_h", "air_m3h", "coldest_c", "coldest_from")},
                "kinds": KINDS, "light": SERIES_LIGHT, "dark": SERIES_DARK, "made": time.strftime("%d %B %Y, %H:%M"),
                "span_h": round((now - t0) / 3600, 1)}
    # Orrery's Heat screens read thermal.json: each machine's parts and its CPU's steps go there too,
    # a part's record thinned to a hundred points.
    by = {m["name"]: m for m in machines}
    for m in doc.get("machines", []):
        mine = by.get(m["name"])
        if not mine:
            continue
        thin = lambda y: [y[int(i * len(y) / 100)] for i in range(100)]
        m["parts"] = [dict({k: p[k] for k in ("key", "kind", "lo", "hi", "now", "tau_s", "c_w", "r2", "edge")}, y=thin(p["y"])) for p in mine["parts"]]
        m["steps"] = mine["steps"]
        m["slow"] = mine["slow"]
        m["record"] = {"cpu": thin(mine["cpu"]), "card": thin(mine["card"]) if mine["card"] else [], "wall": thin(mine["wall"]),
                       "cpu_w": thin(mine["cpu_w"]), "card_w": thin(mine["card_w"]) if mine["card_w"] else []}
    doc["record_h"] = round((now - t0) / 3600, 1)
    tj = os.path.join(q, "plan", "thermal.json")
    with open(tj + ".tmp", "w") as f:
        json.dump(doc, f)
    os.replace(tj + ".tmp", tj)
    with open(out, "w") as f:
        f.write(PAGE.replace("__DATA__", json.dumps(page_doc, separators=(",", ":"))))
    print("wrote %s: %d machines, %.1f hours of record" % (out, len(machines), (now - t0) / 3600))
    return 0


PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fleet Heat</title>
<style>
:root{color-scheme:light;--surface:#fcfcfb;--page:#f3f2ee;--text:#0b0b0b;--text2:#52514e;--muted:#8a897f;--grid:#e4e3dc;--grey:#bcbbb2;--warn:#b45309}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--surface:#1a1a19;--page:#111110;--text:#f0efec;--text2:#c3c2b7;--muted:#8a897f;--grid:#30302d;--grey:#55554f;--warn:#f0a35e}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--page:#111110;--text:#f0efec;--text2:#c3c2b7;--muted:#8a897f;--grid:#30302d;--grey:#55554f;--warn:#f0a35e}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--text);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1140px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}p.sub{margin:0 0 18px;color:var(--text2);max-width:78ch}
section{background:var(--surface);border-radius:10px;padding:16px;margin:0 0 16px}
h2{font-size:16px;margin:0 0 8px}
h3{font-size:12px;font-weight:600;margin:14px 0 2px;color:var(--text2);text-transform:uppercase;letter-spacing:.04em;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
h3 .read{font-weight:400;text-transform:none;letter-spacing:0;color:var(--text);font-variant-numeric:tabular-nums;min-height:1.4em}
svg{display:block;width:100%;height:auto;touch-action:pan-y}
text{fill:var(--muted);font-size:11px}
.tiles{display:flex;flex-wrap:wrap;gap:8px 28px;margin:0 0 10px}
.tiles div{min-width:120px}.tiles b{display:block;font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}.tiles span{color:var(--text2);font-size:12px}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin:4px 0 0;color:var(--text2);font-size:12px}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:5px}
.scroll{overflow-x:auto}
.rows{min-width:900px}
.head,.row{display:grid;grid-template-columns:22px 118px 96px 170px 70px 70px 70px 76px 76px 1fr;gap:0 10px;align-items:center;padding:8px 6px;text-align:right;font-variant-numeric:tabular-nums}
.head{color:var(--text2);font-size:12px;border-bottom:1px solid var(--grid)}
.row{width:100%;background:none;border:0;border-bottom:1px solid var(--grid);color:inherit;font:inherit;cursor:pointer}
.row:hover,.row:focus-visible{background:var(--page);outline:none}
.row>*:nth-child(2),.head>*:nth-child(2),.row>*:last-child,.head>*:last-child{text-align:left}
.row .n{font-weight:600}.row .of{color:var(--muted)}.row .chev{color:var(--muted);transition:transform .15s}
.row[aria-expanded="true"] .chev{transform:rotate(90deg)}
.none{color:var(--muted)}
.panel{padding:4px 6px 18px;border-bottom:1px solid var(--grid)}
.panel p{color:var(--text2);margin:6px 0 0;max-width:86ch}
.seg{display:inline-flex;border:1px solid var(--grid);border-radius:6px;overflow:hidden;font-weight:400;text-transform:none;letter-spacing:0}
.seg button{background:none;border:0;color:var(--text2);font:inherit;font-size:12px;padding:2px 9px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--page);color:var(--text);font-weight:600}
table{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px;margin-top:8px;width:100%}
td,th{padding:3px 12px 3px 0;text-align:right;white-space:nowrap}th{color:var(--text2);font-weight:400;font-size:12px}
td:first-child,th:first-child{text-align:left}
tr.pick{cursor:pointer}tr.pick:hover td{background:var(--page)}tr.on td{font-weight:600}
td i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}
</style></head><body><main>
<h1>Fleet heat</h1><p class="sub" id="sub"></p>
<section><h2>What goes in comes out</h2><div class="tiles" id="tiles"></div><div id="fleet"></div></section>
<section><h2>Each machine, by its CPU</h2><div class="scroll"><div class="rows" id="rows"></div></div></section>
</main>
<script>
const D=__DATA__;
const isDark=()=>document.documentElement.dataset.theme?document.documentElement.dataset.theme==="dark":matchMedia("(prefers-color-scheme: dark)").matches;
const NS="http://www.w3.org/2000/svg",el=(n,a,p)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e};
const h=(tag,cls,txt,p)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;p&&p.appendChild(e);return e};
const T=D.t,t0=T[0],t1=T[T.length-1],days=(t1-t0)>36*3600;
const clock=t=>{const d=new Date(t*1000),hm=d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});return days?d.toLocaleDateString([], {weekday:"short"})+" "+hm:hm};
const nm=k=>k==="gpu.c"?"card":k.replace(/^drivetemp_(\d+)\.temp1$/,"disk $1").replace(/^ipmi\./,"").replace(/^disk\./,"disk ").replace(/_(\d+)\./," $1 ").replace(/_/g," ");
const took=s=>s==null?"":s<120?Math.round(s)+" s":s<7200?Math.round(s/60)+" min":(s/3600).toFixed(1)+" h";
const open=new Set(decodeURIComponent(location.hash.slice(1)).split(",").filter(Boolean)),mode={},pick={};
const KIND=Object.fromEntries(D.kinds.map(([k,n,i])=>[k,{name:n,i}]));

// One plot: lines on one scale, a crosshair, and one line of words above it. No floating box.
function plot(host,title,unit,lines,opt={}){
  const pal=isDark()?D.dark:D.light,head=h("h3",null,null,host);h("span",null,title+" ("+unit+")",head);
  if(opt.control)head.appendChild(opt.control);
  const read=h("span","read","",head);
  const W=1080,H=opt.h||200,L=40,R=opt.right||12,TP=8,B=20;
  let lo=Infinity,hi=-Infinity;for(const l of lines)for(const v of l.y)if(v!=null){lo=Math.min(lo,v);hi=Math.max(hi,v)}
  if(opt.stack)T.forEach((_,i)=>{hi=Math.max(hi,lines.reduce((a,l)=>a+(l.y[i]||0),0))});
  if(opt.limit!=null&&hi>opt.limit-12)hi=Math.max(hi,opt.limit);
  if(!isFinite(lo)){lo=0;hi=1}
  const pad=Math.max(1,(hi-lo)*.06);lo=opt.zero?0:Math.floor(lo-pad);hi=Math.ceil(hi+pad);
  const X=t=>L+(t-t0)/(t1-t0||1)*(W-L-R),Y=v=>TP+(hi-v)/(hi-lo||1)*(H-TP-B);
  const svg=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":title},null);host.appendChild(svg);
  const step=[1,2,5,10,20,25,50,100,200,250,500].find(s=>(hi-lo)/s<=5)||1000;
  for(let v=Math.ceil(lo/step)*step;v<=hi;v+=step){el("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v),stroke:"var(--grid)","stroke-width":1},svg);el("text",{x:L-6,y:Y(v)+4,"text-anchor":"end"},svg).textContent=v}
  const span=t1-t0,tk=[300,600,1800,3600,7200,14400,21600,43200].find(s=>span/s<=8)||86400;
  for(let t=Math.ceil(t0/tk)*tk;t<=t1;t+=tk)el("text",{x:X(t),y:H-5,"text-anchor":"middle"},svg).textContent=clock(t);
  if(opt.limit!=null&&opt.limit<=hi){el("line",{x1:L,x2:W-R,y1:Y(opt.limit),y2:Y(opt.limit),stroke:"var(--warn)","stroke-width":1,"stroke-dasharray":"4 4"},svg);
    el("text",{x:W-R-2,y:Y(opt.limit)-4,"text-anchor":"end",style:"fill:var(--warn)"},svg).textContent="the keeper's limit, "+opt.limit}
  const path=y=>{let d="",pen=false;y.forEach((v,i)=>{if(v==null){pen=false;return}d+=(pen?"L":"M")+X(T[i]).toFixed(1)+" "+Y(v).toFixed(1);pen=true});return d};
  if(opt.stack){let base=T.map(()=>0);for(const l of lines){const top=base.map((b,i)=>b+(l.y[i]||0));
      let d="";top.forEach((v,i)=>d+=(i?"L":"M")+X(T[i]).toFixed(1)+" "+Y(v).toFixed(1));for(let i=T.length-1;i>=0;i--)d+="L"+X(T[i]).toFixed(1)+" "+Y(base[i]).toFixed(1);
      el("path",{d:d+"Z",fill:pal[l.c],stroke:"var(--surface)","stroke-width":1,"fill-opacity":.85},svg);base=top}}
  else for(const l of lines)el("path",{d:path(l.y),fill:"none",stroke:l.ink?"var(--text)":l.c==null?"var(--grey)":pal[l.c],"stroke-width":l.w||2,"stroke-linejoin":"round",
      "stroke-opacity":l.o==null?1:l.o,"stroke-dasharray":l.dash||""},svg);
  for(const s of opt.steps||[]){if(s.at<t0||s.at>t1)continue;
    const [ctau,c0,c1]=s.curve;let d="";const end=Math.min(t1,s.at+5*ctau),n=40;for(let i=0;i<=n;i++){const t=s.at+(end-s.at)*i/n;d+=(i?"L":"M")+X(t).toFixed(1)+" "+Y(c1+(c0-c1)*Math.exp(-(t-s.at)/ctau)).toFixed(1)}
    el("path",{d,fill:"none",stroke:"var(--text)","stroke-width":1.5,"stroke-dasharray":"3 3"},svg);
    el("line",{x1:X(s.at),x2:X(s.at),y1:TP,y2:H-B,stroke:"var(--muted)","stroke-width":1,"stroke-dasharray":"2 4"},svg)}
  for(const l of lines)if(l.label&&!opt.stack){let i=l.y.length-1;while(i>=0&&l.y[i]==null)i--;if(i>=0)el("text",{x:X(T[i])+4,y:Y(l.y[i])+4,style:"fill:var(--text2)"},svg).textContent=l.label}
  const cross=el("line",{y1:TP,y2:H-B,stroke:"var(--muted)","stroke-width":1,visibility:"hidden"},svg);
  const hit=el("rect",{x:L,y:TP,width:W-L-R,height:H-TP-B,fill:"transparent"},svg);
  const move=e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W,i=Math.max(0,Math.min(T.length-1,Math.round((x-L)/(W-L-R)*(T.length-1))));
    cross.setAttribute("x1",X(T[i]));cross.setAttribute("x2",X(T[i]));cross.setAttribute("visibility","visible");
    const said=lines.filter(l=>l.say&&l.y[i]!=null).map(l=>l.say+" "+l.y[i]);
    if(opt.stack)said.unshift("all "+Math.round(lines.reduce((a,l)=>a+(l.y[i]||0),0)));
    read.textContent=clock(T[i])+(said.length?" · "+said.join(" · ")+" "+unit:"")};
  hit.addEventListener("pointermove",move);hit.addEventListener("pointerdown",move);
  hit.addEventListener("pointerleave",()=>{cross.setAttribute("visibility","hidden");read.textContent=""});
  return svg}

function legend(host,items){const pal=isDark()?D.dark:D.light,lg=h("div","legend",null,host);
  for(const [c,txt] of items){const s=h("span",null,null,lg),i=h("i",null,null,s);i.style.background=c==="ink"?"var(--text)":pal[c];s.appendChild(document.createTextNode(txt))}}

function fleet(){
  const f=D.fleet,tiles=document.getElementById("tiles");tiles.innerHTML="";
  const tile=(v,w)=>{const d=h("div",null,null,tiles);h("b",null,v,d);h("span",null,w,d)};
  tile((f.heat_w||0).toLocaleString()+" W","heat into the room now");tile((f.btu_h||0).toLocaleString(),"BTU an hour");
  tile((f.air_m3h||0)+" m³/h","air to carry it off at a 10° rise");
  tile(f.coldest_c!=null?f.coldest_c+" °C":"none","the coldest reading ("+(f.coldest_from||"").replace("disk."," disk ")+"): the room is no warmer");
  const host=document.getElementById("fleet");host.innerHTML="";
  const ms=D.machines.filter(m=>m.wall.some(v=>v!=null));
  plot(host,"Watts at the wall, a band a machine","W",ms.map((m,i)=>({y:m.wall,c:i%8,say:null})),{stack:true,zero:true,h:220});
  legend(host,ms.map((m,i)=>[i%8,m.name+(m.now.wall_w!=null?" · "+m.now.wall_w+" W":"")]))}

function spark(m){const W=170,H=26,svg=el("svg",{viewBox:`0 0 ${W} ${H}`,"aria-hidden":"true"}),v=m.cpu.filter(x=>x!=null);if(!v.length)return svg;
  const lo=Math.min(...v)-1,hi=Math.max(...v)+1;let d="",pen=false;
  m.cpu.forEach((y,i)=>{if(y==null){pen=false;return}d+=(pen?"L":"M")+(i/(T.length-1)*W).toFixed(1)+" "+(2+(hi-y)/(hi-lo)*(H-4)).toFixed(1);pen=true});
  el("path",{d,fill:"none",stroke:(isDark()?D.dark:D.light)[0],"stroke-width":1.5},svg);return svg}

function panel(m,host){
  const c=m.model.cpu,g=m.model.gpu,n=m.now;
  h("p",null,(c?"The CPU answers a step with a tau of "+took(c.tau_s)+" and is settled in "+took(c.five_tau_s)+". At "+c.r_c_w+" °C a watt over "+c.zero_c+"° air inside the case it settles at "+c.settles_c+"° on the watts it draws now. Its "+c.c_j_c.toLocaleString()+" J/°C is the metal, or the water, that warms with it."
     :"No held step of this CPU is in the record yet: its lane paused until the job in hand ends and then twenty minutes more makes one.")
     +(g?" The card: tau "+took(g.tau_s)+", "+g.r_c_w+" °C/W, "+g.c_j_c+" J/°C, settles at "+g.settles_c+"°.":""),host);
  const lines=[{y:m.cpu,c:0,say:"CPU",label:"CPU"}];if(m.card)lines.push({y:m.card,c:1,say:"card",label:"card"});
  plot(host,"The CPU"+(m.card?" and the card":"")+(m.steps.length?", each fitted step dashed over it":""),"°C",lines,{limit:n.cpu_hot,steps:m.steps,right:44});
  const wl=[{y:m.wall,c:6,say:"wall",label:"wall"},{y:m.cpu_w,c:0,say:"CPU",label:"CPU"}];if(m.card_w)wl.push({y:m.card_w,c:1,say:"card",label:"card"});
  plot(host,"Watts: "+(n.watts_from||""),"W",wl,{zero:true,h:150,right:44});
  if(m.steps.length){const t=h("table",null,null,host);
    t.innerHTML="<tr><th>the CPU's steps</th><th>tau</th><th>from</th><th>to</th><th>°C/W</th><th>J/°C</th><th>tau held</th></tr>"+m.steps.slice().reverse().map(s=>
      "<tr><td>"+clock(s.at)+", "+s.step+(s.cores>1?" (the median of "+s.cores+" cores)":"")+"</td><td>"+took(s.tau_s)+"</td><td>"+s.start_c+"°</td><td>"+s.end_c+"°</td><td>"+(s.r_c_w??"")+"</td><td>"+(s.c_j_c!=null?s.c_j_c.toLocaleString():"")+"</td><td>"+s.taus_held+(s.taus_held<3?" (a projection)":"")+"</td></tr>").join("")}
  if(!m.parts.length)return;
  // The soak: every other thermometer, by kind.
  const rise=(mode[m.name]||"rise")==="rise",sel=pick[m.name];
  const seg=h("span","seg");for(const [k,w] of [["rise","degrees above its lowest"],["abs","degrees"]]){const b=h("button",null,w,seg);b.setAttribute("aria-pressed",String((mode[m.name]||"rise")===k));b.onclick=()=>{mode[m.name]=k;draw()}}
  const sl=m.parts.map(p=>({y:rise?p.y.map(v=>v==null?null:Math.round((v-p.lo)*10)/10):p.y,c:KIND[p.kind].i,w:p.key===sel?3:1.25,o:sel?(p.key===sel?1:.25):.85,ink:p.key===sel,say:p.key===sel?nm(p.key):null}));
  plot(host,"The soak: "+m.parts.length+" other thermometers","°C",sl,{control:seg,h:240,zero:rise});
  const kinds=D.kinds.filter(([k])=>m.parts.some(p=>p.kind===k));
  legend(host,kinds.map(([k,name,i])=>[i,name+" ("+m.parts.filter(p=>p.kind===k).length+")"]).concat(sel?[["ink",nm(sel)+", picked below"]]:[]));
  const pal=isDark()?D.dark:D.light,t=h("table",null,null,host);
  t.innerHTML="<tr><th>part (click one to pick its line out)</th><th>now</th><th>lowest</th><th>highest</th><th>follows the watts with a lag of</th><th>°C a watt</th><th>fit</th></tr>";
  const order=D.kinds.map(k=>k[0]);
  for(const p of m.parts.slice().sort((a,b)=>order.indexOf(a.kind)-order.indexOf(b.kind)||(b.tau_s||0)-(a.tau_s||0))){
    const tr=h("tr","pick"+(p.key===sel?" on":""),null,t);
    tr.innerHTML="<td><i style='background:"+pal[KIND[p.kind].i]+"'></i>"+nm(p.key)+"</td><td>"+p.now+"°</td><td>"+p.lo+"°</td><td>"+p.hi+"°</td>"+
      (p.tau_s?"<td>"+(p.edge?"longer than the record (over "+took(p.tau_s)+")":took(p.tau_s))+"</td><td>"+p.c_w+"</td><td>"+Math.round(p.r2*100)+"%</td>":"<td class='none'>not yet told</td><td></td><td></td>");
    tr.onclick=()=>{pick[m.name]=p.key===sel?null:p.key;draw()}}
  h("p",null,"A part's lag is its temperature fitted to this machine's watts passed through one lag; it is given where that explains 60% of the part's movement. A disk wants days of record before its figure means much.",host)}

function draw(){
  document.getElementById("sub").textContent=D.span_h+" hours of record, a sample every 5 seconds. Made "+D.made+". A row opens on a click.";
  fleet();
  const rows=document.getElementById("rows");rows.innerHTML="";
  const head=h("div","head",null,rows);for(const w of ["","machine","CPU now","its record","wall W","CPU W","tau","°C/W","J/°C","slowest part found"])h("span",null,w,head);
  for(const m of D.machines){
    const n=m.now,c=m.model.cpu,b=h("button","row",null,rows);b.setAttribute("aria-expanded",String(open.has(m.name)));
    h("span","chev","›",b);h("span","n",m.name,b);
    const cn=h("span",null,null,b);cn.innerHTML=n.cpu_c!=null?Math.round(n.cpu_c)+"° <span class='of'>of "+Math.round(n.cpu_hot)+"</span>":"";
    h("span",null,null,b).appendChild(spark(m));
    h("span",null,n.wall_w??"",b);h("span",null,n.cpu_w!=null?Math.round(n.cpu_w):"",b);
    h("span",c?null:"none",c?took(c.tau_s):"no step",b);h("span",null,c?c.r_c_w:"",b);h("span",null,c?c.c_j_c.toLocaleString():"",b);
    h("span",m.slow?null:"none",m.slow?nm(m.slow.key)+", "+(m.slow.edge?"over ":"")+took(m.slow.tau_s):"not yet told",b);
    b.onclick=()=>{open.has(m.name)?open.delete(m.name):open.add(m.name);history.replaceState(null,"","#"+[...open].join(","));draw()};
    if(open.has(m.name))panel(m,h("div","panel",null,rows))}}
draw();matchMedia("(prefers-color-scheme: dark)").addEventListener("change",draw);
new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
</script></body></html>
'''
