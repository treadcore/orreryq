"""telemetry.py's charts and fits (see tools/telemetry.py).

THE CHART is one page, a block a machine, three plots a block on one clock: every temperature
(degrees C, one axis), the work done (the CPUs' use and the card's use, percent), and the watts
(the card's, and the CPU's where RAPL is read). Never two scales on one plot. The eight channels that
moved most are drawn in colour; the rest are grey lines behind them, named on hover.

THE FIT is the first-order step response, T(t) = T_end + (T_start - T_end) * exp(-(t - t0) / tau):
a channel after its driver (the CPUs' use for a CPU or board channel, the card's watts for the card)
stepped and then held. tau is found by search, T_end and T_start by least squares at each tau. A
second, slower exponential is added where it cuts the error by more than half: a CPU's own silicon
answers in seconds and its cooler, or its loop, in minutes, and one tau cannot be both. A fit is only
as good as its window: the report says how many tau the hold lasted, and a hold under three tau gives
a T_end that is a projection, not a measurement.
"""
import html
import json
import math
import os
import time

import telemetry

SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"]


def is_temp(k):
    return k == "gpu.c" or (("." in k) and not k.startswith(("w.", "gpu.")) and not any(x in k for x in (".fan", ".pwm", ".power"))
                            ) or k.startswith(("nic.", "disk.")) or (k.startswith("ipmi.") and "RPM" not in k and "FAN" not in k.upper())


def thin(rows, n=700):
    """At most n rows, each the mean of its bucket: a day at 5 seconds is 17,280."""
    if len(rows) <= n:
        return rows
    size = len(rows) / n
    out = []
    for i in range(n):
        b = rows[int(i * size):int((i + 1) * size)]
        keys = set().union(*b)
        out.append({k: sum(r[k] for r in b if k in r) / max(1, sum(1 for r in b if k in r)) for k in keys})
    return out


def chart(q, args):
    hours = float(args[0]) if args and args[0].replace(".", "").isdigit() else 6.0
    out = next((a for a in args if a.endswith(".html")), os.path.join(q, "plan", "telemetry.html"))
    blocks = []
    for name in sorted(telemetry.machines(q)):
        rows = telemetry.series(q, name, hours)
        if len(rows) < 3:
            continue
        rows = thin(rows)
        keys = sorted(set().union(*rows) - {"t"})
        temps = [k for k in keys if is_temp(k)]
        swing = {k: (lambda v: max(v) - min(v))([r[k] for r in rows if k in r]) for k in temps}
        # Colour goes to the channels that say most: the CPU and the card first, then by how far each moved.
        lead = [k for k in temps if k == "gpu.c" or "Package" in k or "Tctl" in k]
        ranked = lead + sorted((k for k in temps if k not in lead), key=lambda k: -swing[k])
        blocks.append({
            "name": name, "t": [round(r["t"]) for r in rows],
            "plots": [
                {"title": "Temperatures", "unit": "°C", "colour": ranked[:8], "grey": ranked[8:],
                 "series": {k: [round(r[k], 1) if k in r else None for r in rows] for k in temps}},
                {"title": "Work", "unit": "%", "colour": [k for k in ("busy", "gpu.use") if k in keys], "grey": [], "fixed": [0, 100],
                 "series": {k: [round(r[k] * (100 if k == "busy" else 1), 1) if k in r else None for r in rows] for k in ("busy", "gpu.use") if k in keys}},
                {"title": "Watts", "unit": "W", "colour": [k for k in keys if k.startswith("w.") or k == "gpu.w"][:8], "grey": [],
                 "series": {k: [round(r[k], 1) if k in r else None for r in rows] for k in keys if k.startswith("w.") or k == "gpu.w"}},
            ]})
    names = {"busy": "CPUs in use", "gpu.use": "card in use", "gpu.c": "card", "gpu.w": "card"}
    page = PAGE.replace("__DATA__", json.dumps({"blocks": blocks, "names": names, "light": SERIES_LIGHT, "dark": SERIES_DARK,
                                                 "made": time.strftime("%d %B %Y, %H:%M"), "hours": hours}))
    with open(out, "w") as f:
        f.write(page)
    print("wrote %s: %d machines, the last %g hours" % (out, len(blocks), hours))
    return 0


PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fleet Temperatures</title>
<style>
:root{color-scheme:light;--surface:#fcfcfb;--page:#f3f2ee;--text:#0b0b0b;--text2:#52514e;--muted:#8a897f;--grid:#e4e3dc;--grey:#bcbbb2}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--surface:#1a1a19;--page:#111110;--text:#f0efec;--text2:#c3c2b7;--muted:#8a897f;--grid:#30302d;--grey:#55554f}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--page:#111110;--text:#f0efec;--text2:#c3c2b7;--muted:#8a897f;--grid:#30302d;--grey:#55554f}
body{margin:0;background:var(--page);color:var(--text);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}p.sub{margin:0 0 20px;color:var(--text2)}
section{background:var(--surface);border-radius:10px;padding:16px 16px 8px;margin:0 0 18px}
h2{font-size:17px;margin:0 0 2px}h3{font-size:12px;font-weight:600;margin:12px 0 2px;color:var(--text2);text-transform:uppercase;letter-spacing:.04em}
svg{display:block;width:100%;height:auto;touch-action:pan-y}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin:4px 0 0;color:var(--text2);font-size:12px}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:5px}
.tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--text);border:1px solid var(--grid);border-radius:8px;padding:8px 10px;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.18);max-width:300px;display:none;z-index:5}
.tip b{display:block;margin-bottom:3px}.tip span{display:flex;justify-content:space-between;gap:14px}.tip i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
text{fill:var(--muted);font-size:11px}
details{margin:6px 0 10px;color:var(--text2);font-size:12px}table{border-collapse:collapse;font-variant-numeric:tabular-nums}td,th{padding:2px 10px 2px 0;text-align:right}td:first-child,th:first-child{text-align:left}
</style></head><body><main>
<h1>Fleet temperatures</h1><p class="sub" id="sub"></p><div id="root"></div></main><div class="tip" id="tip"></div>
<script>
const D=__DATA__;
const dark=()=>document.documentElement.dataset.theme?document.documentElement.dataset.theme==="dark":matchMedia("(prefers-color-scheme: dark)").matches;
const NS="http://www.w3.org/2000/svg",el=(n,a,p)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e};
const nm=k=>D.names[k]||k.replace(/_(\d+)\./," $1 ").replace(/_/g," ");
const clock=t=>new Date(t*1000).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
const tip=document.getElementById("tip");
document.getElementById("sub").textContent="Every channel each machine reports, every 5 seconds, over the last "+D.hours+" hours. Made "+D.made+".";
function draw(){
  const root=document.getElementById("root");root.innerHTML="";const pal=dark()?D.dark:D.light;
  for(const b of D.blocks){
    const sec=document.createElement("section");root.appendChild(sec);
    sec.innerHTML="<h2>"+b.name+"</h2>";
    const t0=b.t[0],t1=b.t[b.t.length-1];
    for(const p of b.plots){
      const keys=[...p.grey,...p.colour];if(!keys.length)continue;
      const h3=document.createElement("h3");h3.textContent=p.title+" ("+p.unit+")";sec.appendChild(h3);
      const W=1060,H=p.title==="Temperatures"?250:120,L=38,R=10,T=8,B=20;
      let lo=Infinity,hi=-Infinity;for(const k of keys)for(const v of p.series[k])if(v!=null){lo=Math.min(lo,v);hi=Math.max(hi,v)}
      if(p.fixed){lo=p.fixed[0];hi=p.fixed[1]}else{const pad=Math.max(1,(hi-lo)*.06);lo=Math.floor(lo-pad);hi=Math.ceil(hi+pad);if(p.unit==="W")lo=Math.min(lo,0)}
      const X=t=>L+(t-t0)/(t1-t0||1)*(W-L-R),Y=v=>T+(hi-v)/(hi-lo||1)*(H-T-B);
      const svg=el("svg",{viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":b.name+" "+p.title});sec.appendChild(svg);
      const step=[1,2,5,10,20,25,50].find(s=>(hi-lo)/s<=5)||100;
      for(let v=Math.ceil(lo/step)*step;v<=hi;v+=step){el("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v),stroke:"var(--grid)","stroke-width":1},svg);el("text",{x:L-6,y:Y(v)+4,"text-anchor":"end"},svg).textContent=v}
      const span=t1-t0,ts=[300,600,1800,3600,7200,14400].find(s=>span/s<=8)||28800;
      for(let t=Math.ceil(t0/ts)*ts;t<=t1;t+=ts)el("text",{x:X(t),y:H-5,"text-anchor":"middle"},svg).textContent=clock(t);
      const path=k=>{let d="",pen=false;p.series[k].forEach((v,i)=>{if(v==null){pen=false;return}d+=(pen?"L":"M")+X(b.t[i]).toFixed(1)+" "+Y(v).toFixed(1);pen=true});return d};
      for(const k of p.grey)el("path",{d:path(k),fill:"none",stroke:"var(--grey)","stroke-width":1},svg);
      p.colour.forEach((k,i)=>el("path",{d:path(k),fill:"none",stroke:pal[i],"stroke-width":2,"stroke-linejoin":"round"},svg));
      const cross=el("line",{y1:T,y2:H-B,stroke:"var(--muted)","stroke-width":1,visibility:"hidden"},svg);
      const hit=el("rect",{x:L,y:T,width:W-L-R,height:H-T-B,fill:"transparent"},svg);
      const move=e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W,t=t0+(x-L)/(W-L-R)*(t1-t0);
        let i=0,best=1e18;b.t.forEach((v,j)=>{const d=Math.abs(v-t);if(d<best){best=d;i=j}});
        cross.setAttribute("x1",X(b.t[i]));cross.setAttribute("x2",X(b.t[i]));cross.setAttribute("visibility","visible");
        const rows=[...p.colour.map((k,j)=>[k,pal[j]]),...p.grey.map(k=>[k,"var(--grey)"])].filter(([k])=>p.series[k][i]!=null).sort((a,c)=>p.series[c[0]][i]-p.series[a[0]][i]);
        tip.innerHTML="<b>"+b.name+", "+new Date(b.t[i]*1000).toLocaleTimeString()+"</b>"+rows.map(([k,c])=>"<span><span><i style='background:"+c+"'></i>"+nm(k)+"</span><span>"+p.series[k][i]+" "+p.unit+"</span></span>").join("");
        tip.style.display="block";tip.style.left=Math.min(innerWidth-310,e.clientX+14)+"px";tip.style.top=Math.max(8,e.clientY-20)+"px"};
      hit.addEventListener("pointermove",move);hit.addEventListener("pointerdown",move);hit.addEventListener("pointerleave",()=>{tip.style.display="none";cross.setAttribute("visibility","hidden")});
      const lg=document.createElement("div");lg.className="legend";sec.appendChild(lg);
      p.colour.forEach((k,i)=>{const last=[...p.series[k]].reverse().find(v=>v!=null);lg.innerHTML+="<span><i style='background:"+pal[i]+"'></i>"+nm(k)+(last!=null?" · "+last+" "+p.unit:"")+"</span>"});
      if(p.grey.length)lg.innerHTML+="<span><i style='background:var(--grey)'></i>"+p.grey.length+" more, named on hover</span>";
    }
    const tp=b.plots[0],det=document.createElement("details");det.innerHTML="<summary>The temperatures as a table</summary><table><tr><th>channel</th><th>lowest</th><th>highest</th><th>now</th></tr>"+
      [...tp.colour,...tp.grey].map(k=>{const v=tp.series[k].filter(x=>x!=null);return "<tr><td>"+nm(k)+"</td><td>"+Math.min(...v)+"</td><td>"+Math.max(...v)+"</td><td>"+v[v.length-1]+"</td></tr>"}).join("")+"</table>";
    sec.appendChild(det);
  }
}
draw();matchMedia("(prefers-color-scheme: dark)").addEventListener("change",draw);
new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
</script></body></html>
'''


# ---- the fit -------------------------------------------------------------------------

def mean(v):
    return sum(v) / len(v)


def steps(rows, key, jump, hold_s=240, look_s=45):
    """Where `key` stepped by at least `jump` and then held: (index, before, after, end index). Before
    and after are means over look_s each side; the hold ends where the driver leaves the new level by
    half a jump, or the data ends."""
    out, i, n = [], 0, len(rows)
    t = [r["t"] for r in rows]
    v = [r.get(key) for r in rows]
    while i < n:
        a = [v[j] for j in range(i, -1, -1) if t[i] - t[j] <= look_s and v[j] is not None]
        b = [v[j] for j in range(i + 1, n) if t[j] - t[i] <= look_s and v[j] is not None]
        if len(a) >= 3 and len(b) >= 3 and abs(mean(b) - mean(a)) >= jump:
            # The step's own middle: where the change between the two sides is greatest nearby.
            before, after = mean(a), mean(b)
            end = i + 1
            while end < n and (v[end] is None or abs(v[end] - after) < jump / 2 or
                               abs(mean([x for x in v[end:end + 6] if x is not None] or [after]) - after) < jump / 2):
                end += 1
            if t[min(end, n - 1)] - t[i] >= hold_s:
                out.append((i, before, after, min(end, n - 1)))
            i = max(end, i + 1)
        else:
            i += 1
    return out


def fit_one(ts, ys, taus):
    """Least squares of y = a + b * exp(-t / tau) at each tau: (rms, tau, a, b)."""
    best = None
    n = len(ts)
    for tau in taus:
        e = [math.exp(-x / tau) for x in ts]
        se, see, sy, sey = sum(e), sum(x * x for x in e), sum(ys), sum(x * y for x, y in zip(e, ys))
        den = n * see - se * se
        if abs(den) < 1e-12:
            continue
        b = (n * sey - se * sy) / den
        a = (sy - b * se) / n
        rms = math.sqrt(sum((a + b * x - y) ** 2 for x, y in zip(e, ys)) / n)
        if best is None or rms < best[0]:
            best = (rms, tau, a, b)
    return best


def fit_two(ts, ys, taus):
    """y = a + b * exp(-t / fast) + c * exp(-t / slow), fast < slow: (rms, fast, slow, a, b, c)."""
    best = None
    n = len(ts)
    es = {tau: [math.exp(-x / tau) for x in ts] for tau in taus}
    for i, f in enumerate(taus):
        for s in taus[i + 1:]:
            if s < 3 * f:
                continue
            e1, e2 = es[f], es[s]
            # Normal equations, three unknowns.
            m = [[n, sum(e1), sum(e2)], [sum(e1), sum(x * x for x in e1), sum(x * y for x, y in zip(e1, e2))],
                 [sum(e2), sum(x * y for x, y in zip(e1, e2)), sum(x * x for x in e2)]]
            r = [sum(ys), sum(x * y for x, y in zip(e1, ys)), sum(x * y for x, y in zip(e2, ys))]
            sol = solve3(m, r)
            if sol is None:
                continue
            a, b, c = sol
            if b * c < 0:  # both parts must move the same way: a step, not a wiggle
                continue
            rms = math.sqrt(sum((a + b * x + c * z - y) ** 2 for x, z, y in zip(e1, e2, ys)) / n)
            if best is None or rms < best[0]:
                best = (rms, f, s, a, b, c)
    return best


def solve3(m, r):
    m = [row[:] + [x] for row, x in zip(m, r)]
    for i in range(3):
        p = max(range(i, 3), key=lambda k: abs(m[k][i]))
        if abs(m[p][i]) < 1e-12:
            return None
        m[i], m[p] = m[p], m[i]
        for k in range(3):
            if k != i:
                f = m[k][i] / m[i][i]
                m[k] = [x - f * y for x, y in zip(m[k], m[i])]
    return [m[i][3] / m[i][i] for i in range(3)]


def fits(q, name, hours):
    """Every step of this machine in the window, each channel that answered it."""
    rows = telemetry.series(q, name, hours)
    if len(rows) < 60:
        return []
    keys = set().union(*rows)
    taus = [2 * 1.18 ** i for i in range(48)]  # 2 s to 80 min, for the two-part search
    fine = [2 * 1.05 ** i for i in range(150)]  # the same span in steps of 5%, for the one
    out = []
    for driver, jump, unit, follow in (("busy", 0.4, "of the CPUs", lambda k: is_temp(k) and k != "gpu.c"),
                                       ("gpu.w", 40.0, "W at the card", lambda k: k == "gpu.c")):
        if driver not in keys:
            continue
        for i, before, after, end in steps(rows, driver, jump):
            seg = rows[i:end + 1]
            hold = seg[-1]["t"] - seg[0]["t"]
            for k in sorted(x for x in keys if follow(x)):
                pts = [(r["t"] - seg[0]["t"], r[k]) for r in seg if k in r]
                if len(pts) < 30 or max(p[1] for p in pts) - min(p[1] for p in pts) < 3:
                    continue
                ts, ys = [p[0] for p in pts], [p[1] for p in pts]
                one = fit_one(ts, ys, [t for t in fine if t <= hold])
                # A fit that leaves a quarter of the channel's own swing unexplained is not a step response.
                # Nor is one whose best tau is the longest tried: the channel was still on its way, and
                # the hold says nothing of where it ends.
                if one is None or one[0] > 0.25 * (max(ys) - min(ys)) or one[1] >= 0.9 * hold:
                    continue
                rec = {"machine": name, "channel": k, "driver": driver, "unit": unit, "at": seg[0]["t"], "from": round(before, 2),
                       "to": round(after, 2), "hold_s": round(hold), "start_c": round(ys[0], 1), "last_c": round(mean(ys[-6:]), 1),
                       "tau_s": round(one[1], 1), "end_c": round(one[2], 1), "rms_c": round(one[0], 2), "taus_held": round(hold / one[1], 1)}
                two = fit_two(ts, ys, [t for t in taus if t <= hold])
                if two and two[0] < 0.5 * one[0]:
                    rec.update(fast_s=round(two[1], 1), slow_s=round(two[2], 1), fast_c=round(two[4], 1), slow_c=round(two[5], 1),
                               end2_c=round(two[3], 1), rms2_c=round(two[0], 2), taus_held=round(hold / two[2], 1))
                out.append(rec)
    return out


def fit(q, args):
    names = [a for a in args if not a.replace(".", "").isdigit()] or sorted(telemetry.machines(q))
    hours = next((float(a) for a in args if a.replace(".", "").isdigit()), 6.0)
    every = []
    for name in names:
        every += fits(q, name, hours)
    doc = os.path.join(q, "plan", "telemetry-fits.json")
    with open(doc, "w") as f:
        json.dump({"t": time.time(), "hours": hours, "fits": every}, f, indent=1)
    if not every:
        print("no step held four minutes in the last %g hours: pause a machine, let it settle, resume it" % hours)
        return 0
    print("%-13s %-26s %-22s %6s  %-18s %7s %7s %6s  %s" % ("machine", "channel", "step", "held", "tau", "from C", "ends C", "rms", "taus held"))
    for r in every:
        step = "%s %g -> %g" % ("CPUs" if r["driver"] == "busy" else "card W", r["from"], r["to"])
        tau = "%.0f s + %.0f s" % (r["fast_s"], r["slow_s"]) if "slow_s" in r else "%.0f s" % r["tau_s"]
        print("%-13s %-26s %-22s %5ds  %-18s %7.1f %7.1f %6.2f  %s%s" % (
            r["machine"], r["channel"], step, r["hold_s"], tau, r["start_c"], r.get("end2_c", r["end_c"]), r.get("rms2_c", r["rms_c"]),
            r["taus_held"], "" if r["taus_held"] >= 3 else "  (under 3: the end is a projection)"))
    print("kept: %s" % doc)
    return 0
