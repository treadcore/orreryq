#!/usr/bin/env python3
"""teleprompt.py PAGE.html OUT.mp4 [--wpm 180] [--size 1280x720] [--fps 15] [--dark] [--av1] [--bundle DIR]

A lab report's page read aloud without a voice: scrolled at reading speed, each figure held for a look, each
film held and played to its end, as the page's own Read along button does (Paul, 6 November: "scrolls the
webpage with enough reading time, which then it starts the animation when its in view, stops scrolling to
view it, then continues ... add that special something to the process which helps doing this repeatedly
from an HTML to an MP4 ... I want really small or compressable filesizes").

THE SPECIAL SOMETHING, three things:
  ONE TIMELINE. The pace is the page's own: the recorder asks headless Chrome for window.teleprompt.timeline()
    (tools/report/page.html) at the video's size, so the page played in a browser and its video agree. Films'
    lengths come from ffprobe, written on the page as data-duration, so nothing waits on a video to load.
  NO SCREEN RECORDING. The page is photographed once, whole (Chrome, the sticky bar hidden), and FFmpeg
    slides a window down the picture by the timeline: a crop moved by sendcmd, a whole pixel at a time, every
    film laid over its own place for its time. Nothing depends on the machine's speed; the same page and
    options give the same file, every time.
  SMALL BY CONSTRUCTION. A frame is the last one moved by whole pixels, or the same: the encoder finds every
    block of it in the frame before (a motion vector, no residual), and a held frame costs nearly nothing.
    x264 at a long GOP, or AV1 (--av1, SVT-AV1 with its screen-content tools) for less.

--bundle DIR also writes the smallest form of all: the page as WebP tiles, the timeline, the films, and a
player (index.html) that slides and plays them in any browser, a few hundred bytes of script.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HIDE = "<style>.bar,.tele-line{display:none!important} html{scroll-behavior:auto!important}</style>"


def chrome(args, timeout=180):
    return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                           "--force-device-scale-factor=1", "--run-all-compositor-stages-before-draw"] + args,
                          capture_output=True, text=True, timeout=timeout)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 10.0


def prepared(page, dark, extra=""):
    """The page as the recorder sees it: the bar hidden, each film's length on it, the theme chosen."""
    html = open(page).read()
    base = os.path.dirname(os.path.abspath(page))

    def dur(m):
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        d = probe(os.path.join(base, src.group(1))) if src else 10.0
        return tag.replace("<video", '<video data-duration="%.3f"' % d, 1)
    html = re.sub(r"<video\b[^>]*>", dur, html)
    html = html.replace("</head>", HIDE + "</head>", 1) if "</head>" in html else HIDE + html
    if dark:
        html = '<script>document.documentElement.setAttribute("data-theme","dark")</script>' + html
    return html + extra


def write_beside(page, html, tag):
    p = os.path.join(os.path.dirname(os.path.abspath(page)), ".tele-%s-%s" % (tag, os.path.basename(page)))
    open(p, "w").write(html)
    return p


def timeline(page, w, h, wpm, dark):
    dump = ('<script>addEventListener("load",function(){setTimeout(function(){var t=window.teleprompt.timeline({wpm:%d,width:%d,height:%d});'
            'var p=document.createElement("pre");p.id="tele-dump";p.textContent=JSON.stringify(t);document.body.appendChild(p);},300);});</script>') % (wpm, w, h)
    p = write_beside(page, prepared(page, dark, dump), "t")
    try:
        r = chrome(["--window-size=%d,%d" % (w, h), "--virtual-time-budget=6000", "--dump-dom", "file://" + p])
    finally:
        os.remove(p)
    m = re.search(r'<pre id="tele-dump">(.*?)</pre>', r.stdout, re.S)
    if not m:
        raise SystemExit("no timeline from the page (is it built from tools/report/page.html?): %s" % r.stderr[-300:])
    return json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))


def photograph(page, w, total, dark, out, chunk=8000):
    """The whole page as one picture, shot in chunks (a window is kept under Chrome's limits) and stacked."""
    parts = []
    for k in range(math.ceil(total / chunk)):
        hk = min(chunk, total - k * chunk)
        shift = '<style>body{margin-top:-%dpx!important}</style>' % (k * chunk) if k else ""
        p = write_beside(page, prepared(page, dark, shift), "s%d" % k)
        part = out + ".%d.png" % k
        try:
            r = chrome(["--window-size=%d,%d" % (w, hk), "--virtual-time-budget=4000", "--screenshot=" + part, "file://" + p])
        finally:
            os.remove(p)
        if not os.path.exists(part):
            raise SystemExit("chrome took no picture: %s" % r.stderr[-300:])
        parts.append(part)
    subprocess.run(["magick"] + parts + ["-append", out], check=True)
    for q in parts:
        os.remove(q)


def positions(tl, fps):
    """The window's top at every frame: whole pixels, held where the timeline holds."""
    n = int(math.ceil(tl["duration"] * fps)) + fps
    segs, ys, i = tl["segments"], [], 0
    for f in range(n):
        t = f / fps
        while i < len(segs) and t >= segs[i]["t1"]:
            i += 1
        if i >= len(segs):
            y = segs[-1]["y1"] if segs else 0
        else:
            s = segs[i]
            y = s["y0"] + (s["y1"] - s["y0"]) * max(0.0, (t - s["t0"]) / max(1e-6, s["t1"] - s["t0"]))
        ys.append(int(round(min(max(0, y), max(0, tl["page"] - tl["height"])))))
    return ys


def film(page, tl, shot, out, fps, av1):
    w, h = tl["width"], tl["height"]
    ys = positions(tl, fps)
    work = tempfile.mkdtemp(prefix="tele-")
    cmds = os.path.join(work, "scroll.cmd")
    with open(cmds, "w") as f:
        last = None
        for k, y in enumerate(ys):
            if y != last:
                f.write("%.4f crop y %d;\n" % (k / fps, y))
                last = y
    base = os.path.dirname(os.path.abspath(page))
    ins = ["-loop", "1", "-framerate", str(fps), "-i", shot]
    fc = ["[0:v]sendcmd=f=%s,crop=%d:%d:0:%d[s0]" % (cmds.replace(":", "\\:"), w, h, ys[0] if ys else 0)]
    cur, k = "s0", 0
    for s in tl["segments"]:
        if s["kind"] != "film":
            continue
        fl = tl["films"][s["film"]]
        t0 = s["t0"] + 0.3
        ins += ["-itsoffset", "%.3f" % t0, "-i", os.path.join(base, fl["src"])]
        k += 1
        top = fl["y"] - s["y0"]
        fc.append("[%d:v]scale=%d:%d,fps=%d[f%d]" % (k, int(fl["w"]) // 2 * 2, int(fl["h"]) // 2 * 2, fps, k))
        fc.append("[%s][f%d]overlay=%d:%d:eof_action=pass:enable='between(t,%.3f,%.3f)'[s%d]" % (cur, k, int(fl["x"]), int(top), t0, t0 + fl["dur"], k))
        cur = "s%d" % k
    enc = (["-c:v", "libsvtav1", "-crf", "42", "-preset", "6", "-svtav1-params", "scm=1:tune=0", "-g", str(fps * 20)] if av1
           else ["-c:v", "libx264", "-preset", "veryslow", "-crf", "27", "-tune", "animation", "-g", str(fps * 20), "-bf", "4"])
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", "[%s]" % cur,
                        "-t", "%.2f" % (len(ys) / fps), "-r", str(fps), "-pix_fmt", "yuv420p"] + enc + ["-movflags", "+faststart", out],
                       capture_output=True, text=True)
    shutil.rmtree(work, ignore_errors=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg: %s" % r.stderr[-600:])


PLAYER = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<style>html,body{margin:0;background:#111;height:100%%}#v{position:relative;overflow:hidden;margin:0 auto;background:#000}
#p{position:absolute;left:0;top:0;will-change:transform}#p img{display:block}video{position:absolute}
#c{position:fixed;left:0;right:0;bottom:0;display:flex;gap:8px;padding:8px;background:#000a;color:#ddd;font:13px system-ui}
#c input{flex:1}</style>
<div id="v"><div id="p">%(tiles)s</div></div><div id="c"><button id="b">Play</button><input id="r" type="range" min="0" max="1000" value="0"><span id="t"></span></div>
<script>
fetch("timeline.json").then(function(r){return r.json()}).then(function(tl){
var v=document.getElementById("v"),p=document.getElementById("p"),b=document.getElementById("b"),r=document.getElementById("r"),tt=document.getElementById("t");
v.style.width=tl.width+"px";v.style.height=tl.height+"px";
function fit(){var s=Math.min(innerWidth/tl.width,(innerHeight-40)/tl.height,1);v.style.transform="scale("+s+")";v.style.transformOrigin="top center"}fit();addEventListener("resize",fit);
var vids=tl.films.map(function(f){var e=document.createElement("video");e.src=f.src;e.muted=true;e.playsInline=true;e.style.left=f.x+"px";e.style.top=f.y+"px";e.style.width=f.w+"px";e.style.height=f.h+"px";e.style.display="none";p.appendChild(e);return e});
function y(t){for(var i=0;i<tl.segments.length;i++){var s=tl.segments[i];if(t<s.t1)return[s.y0+(s.y1-s.y0)*Math.max(0,(t-s.t0)/(s.t1-s.t0)),s]}var l=tl.segments[tl.segments.length-1];return[l.y1,l]}
var t=0,run=false,last=0,shown=-1;
function draw(){var a=y(t),s=a[1];p.style.transform="translateY("+(-Math.round(Math.min(a[0],tl.page-tl.height)))+"px)";
var want=s.kind==="film"?s.film:-1;if(want!==shown){if(shown>=0){vids[shown].pause();vids[shown].style.display="none"}if(want>=0){var e=vids[want];e.style.display="block";e.currentTime=Math.max(0,t-s.t0-0.3);if(run)e.play()}shown=want}
r.value=Math.round(1000*t/tl.duration);tt.textContent=Math.floor(t/60)+":"+("0"+Math.floor(t%%60)).slice(-2)+" / "+Math.floor(tl.duration/60)+":"+("0"+Math.floor(tl.duration%%60)).slice(-2)}
function loop(now){if(!run)return;t=Math.min(tl.duration,t+(now-last)/1000);last=now;draw();if(t>=tl.duration){run=false;b.textContent="Play";return}requestAnimationFrame(loop)}
b.onclick=function(){run=!run;b.textContent=run?"Pause":"Play";if(run){last=performance.now();if(shown>=0)vids[shown].play();requestAnimationFrame(loop)}else if(shown>=0)vids[shown].pause()};
r.oninput=function(){t=tl.duration*r.value/1000;shown=-2;draw()};draw()});
</script>
"""


def bundle(page, tl, shot, out, tile=4000):
    os.makedirs(out, exist_ok=True)
    tiles = []
    for k in range(math.ceil(tl["page"] / tile)):
        name = "page-%02d.webp" % k
        subprocess.run(["magick", shot, "-crop", "%dx%d+0+%d" % (tl["width"], tile, k * tile), "+repage", "-quality", "80", "-define", "webp:method=6",
                        os.path.join(out, name)], check=True)
        tiles.append('<img src="%s" width="%d" alt="">' % (name, tl["width"]))
    base = os.path.dirname(os.path.abspath(page))
    os.makedirs(os.path.join(out, "films"), exist_ok=True)
    tl = json.loads(json.dumps(tl))
    for f in tl["films"]:
        dst = os.path.join("films", os.path.basename(f["src"]))
        shutil.copy(os.path.join(base, f["src"]), os.path.join(out, dst))
        f["src"] = dst
    json.dump(tl, open(os.path.join(out, "timeline.json"), "w"))
    title = re.search(r"<title>(.*?)</title>", open(page).read(), re.S)
    open(os.path.join(out, "index.html"), "w").write(PLAYER % {"title": (title.group(1) if title else "Read along"), "tiles": "".join(tiles)})


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    page, out = a[0], a[1]
    w, h = (int(x) for x in opt("--size", "1280x720").split("x"))
    fps, wpm, dark, av1 = int(opt("--fps", 15)), int(opt("--wpm", 180)), "--dark" in a, "--av1" in a
    tl = timeline(page, w, h, wpm, dark)
    shot = os.path.splitext(out)[0] + "-page.png"
    photograph(page, w, tl["page"], dark, shot)
    film(page, tl, shot, out, fps, av1)
    if opt("--bundle"):
        bundle(page, tl, shot, opt("--bundle"))
    films = sum(1 for s in tl["segments"] if s["kind"] == "film")
    print("%s: %d:%02d, %d films played, %d KB (the page %d px, %d words a minute)" % (
        out, tl["duration"] // 60, tl["duration"] % 60, films, os.path.getsize(out) // 1024, tl["page"], wpm))
    os.remove(shot)


if __name__ == "__main__":
    main(sys.argv[1:])
