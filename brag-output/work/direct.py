"""Drive the real ShelfSense dashboard and capture it frame by frame (CDP screencast, timestamped)."""
import asyncio, base64, json, os, sys
from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8777/#2026102408"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
os.makedirs(OUT, exist_ok=True)

OVERLAY = r"""
(() => {
const css = `
#bv-card { position:fixed; inset:0; z-index:100; display:grid; place-items:center; background:#0B1F18;
  transition:opacity 700ms cubic-bezier(.23,1,.32,1), transform 700ms cubic-bezier(.23,1,.32,1) }
#bv-card.gone { opacity:0; transform:scale(1.03); pointer-events:none }
#bv-card .t { font-family:"Instrument Serif",Georgia,serif; color:#F3F6F4; font-size:64px; line-height:1.1; text-align:center; max-width:980px;
  transition:opacity 450ms ease, transform 450ms cubic-bezier(.23,1,.32,1), filter 450ms ease }
#bv-card .t.out { opacity:0; transform:translateY(10px); filter:blur(4px) }
#bv-card .t em { font-style:normal; color:#F2A541 }
#bv-card small { display:block; margin-top:22px; font:500 20px Inter,sans-serif; color:#9FC9B5; letter-spacing:.01em }
#bv-cap { position:fixed; left:40px; bottom:28px; z-index:90; transform:translateY(12px); opacity:0; max-width:820px;
  padding:14px 24px; border-radius:14px; background:rgb(11 20 17 / .9); color:#F3F6F4; font:500 22px/1.35 Inter,sans-serif;
  box-shadow:0 10px 40px rgb(0 0 0 / .25); backdrop-filter:blur(10px); text-align:left;
  transition:opacity 380ms ease, transform 380ms cubic-bezier(.23,1,.32,1) }
#bv-cap.on { opacity:1; transform:none }
#bv-cur { position:fixed; left:0; top:0; z-index:95; width:26px; height:26px; pointer-events:none;
  transform:translate(1500px,700px); transition:transform 750ms cubic-bezier(.77,0,.175,1) }
@keyframes bv-keep { to { opacity:.98 } }
#bv-keep { position:fixed; left:0; top:0; width:2px; height:2px; z-index:1; animation:bv-keep 1s linear infinite alternate }
#bv-cur svg { transition:transform 140ms ease-out; transform-origin:4px 3px }
#bv-cur.down svg { transform:scale(.82) }
.bv-stats { display:flex; justify-content:center; gap:80px; margin-top:8px }
.bv-stats div { text-align:left; opacity:0; transform:translateY(10px); transition:opacity 500ms ease, transform 500ms cubic-bezier(.23,1,.32,1) }
.bv-stats div.in { opacity:1; transform:none }
.bv-stats b { display:block; font-family:"Instrument Serif",Georgia,serif; font-weight:400; font-size:84px; color:#F3F6F4; line-height:1 }
.bv-stats b.acc { color:#F2A541 }
.bv-stats span { font:500 19px Inter,sans-serif; color:#9FC9B5 }
`;
const s = document.createElement("style"); s.textContent = css; document.head.append(s);
document.body.insertAdjacentHTML("beforeend", `
  <div id="bv-card"><div class="t out" id="bv-t"></div></div>
  <div id="bv-cap"></div><div id="bv-keep"></div>
  <div id="bv-cur"><svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 3l15 7.5-6.5 1.8L10 19z" fill="#111614" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg></div>`);
const T = document.getElementById("bv-t");
window.bv = {
  text(html) { T.classList.add("out"); setTimeout(() => { T.innerHTML = html; T.classList.remove("out"); }, html && T.textContent ? 430 : 0); },
  fade() { T.classList.add("out"); },
  card(on) { document.getElementById("bv-card").classList.toggle("gone", !on); },
  cap(t) { const c = document.getElementById("bv-cap"); c.classList.remove("on");
           setTimeout(() => { if (t) { c.textContent = t; c.classList.add("on"); } }, t && c.textContent ? 380 : 0); },
  move(x, y) { document.getElementById("bv-cur").style.transform = `translate(${x}px,${y}px)`; },
  click() { const c = document.getElementById("bv-cur"); c.classList.add("down"); setTimeout(() => c.classList.remove("down"), 160); },
  stats() { setTimeout(() => [...document.querySelectorAll(".bv-stats div")].forEach((d, i) => setTimeout(() => d.classList.add("in"), 160 + i * 260)), 460); },
  scrollTo(y, dur) { const y0 = scrollY, t0 = performance.now();
    const f = now => { const p = Math.min((now - t0) / dur, 1), e = p < .5 ? 4*p*p*p : 1 - Math.pow(-2*p + 2, 3) / 2;
      scrollTo(0, y0 + (y - y0) * e); if (p < 1) requestAnimationFrame(f); }; requestAnimationFrame(f); },
};
})();
"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--force-color-profile=srgb"])
        pg = await b.new_page(viewport={"width": 1440, "height": 810}, device_scale_factor=4 / 3, color_scheme="light")
        await pg.goto(URL)
        await pg.wait_for_selector("#rows tr[data-key]")
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(5000)  # let the static site preload every hour
        await pg.evaluate(OVERLAY)
        await pg.evaluate("""bv.card(true); document.getElementById('bv-card').style.transition='none'""")
        await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('bv-card').style.transition=''")

        cdp = await pg.context.new_cdp_session(pg)
        frames, events = [], []

        async def ack(sid):
            try: await cdp.send("Page.screencastFrameAck", {"sessionId": sid})
            except Exception: pass

        def on_frame(e):
            frames.append((e["metadata"]["timestamp"], e["data"]))
            asyncio.ensure_future(ack(e["sessionId"]))
        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1})
        loop = asyncio.get_running_loop()
        t0 = loop.time()

        async def at(t):
            await asyncio.sleep(max(0, t0 + t - loop.time()))
        def ev(name): events.append((round(loop.time() - t0, 3), name))
        async def js(code): await asyncio.wait_for(pg.evaluate(code), 5)  # fail loudly instead of hanging the take
        async def center(sel_js):
            r = await pg.evaluate(f"(() => {{ const r = ({sel_js}).getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height/2]; }})()")
            return r

        # 1 hook
        await at(0.15); ev("whoosh"); await js("bv.text('An empty shelf looks exactly like <em>a quiet hour.</em>')")
        # 2 reveal
        await at(3.2); ev("whoosh"); await js("bv.text('ShelfSense sees it coming.<small>Stock-out early warning for 10-minute grocery · built on Exasol Personal</small>')")
        await at(5.55); await js("bv.fade()")
        await at(6.0); ev("reveal"); await js("bv.card(false)")
        # 3 replay
        await at(6.7); await js("bv.cap('Every shelf, every hour: will it run empty before the 06:00 truck?')")
        x, y = await center("document.getElementById('play')")
        await at(7.0); await js(f"bv.move({x - 4},{y - 4})")
        await at(8.0); ev("click"); await js("bv.click(); document.getElementById('play').click()")
        await at(11.2); await js("bv.cap('Press Replay: Exasol re-scores 1,325 shelves each hour and the board re-ranks live.')")
        await at(15.0); ev("click"); await js("bv.click(); document.getElementById('play').click()")
        # 4 shelf
        await at(15.3); await js("bv.cap('Click a shelf: projected stock, drawn against what really happened.'); bv.scrollTo(250, 700)")
        seg = "document.querySelector('#seg button[data-s=\"CRITICAL\"]')"
        await at(16.0); x, y = await center(seg); await js(f"bv.move({x - 4},{y - 4})")
        await at(16.8); ev("click"); await js(f"bv.click(); ({seg}).click()")
        row = "[...document.querySelectorAll('#rows tr')].filter(r => !r.classList.contains('sel'))[1]"
        await at(17.3); x, y = await center(row); await js(f"bv.move({x - 160},{y - 4})")
        await at(18.1); ev("click"); await js(f"bv.click(); ({row}).click()")
        # 5 backtest
        await at(21.0); await js("bv.cap('Every call is backtested against what happened next.')"); await js("bv.move(1500, 760)")
        await at(21.3); ev("swoosh"); await js("bv.scrollTo(document.querySelector('.lower').getBoundingClientRect().top + scrollY - 90, 1300)")
        # 6 speed
        await at(26.5); ev("whoosh"); await js("bv.cap(''); bv.card(true); bv.text(`<div class='bv-stats'><div><b>1.3 M</b><span>hourly rows in Exasol</span></div><div><b>1.2 s</b><span>to score every shelf</span></div><div><b class='acc'>20 ms</b><span>to replay any hour</span></div></div>`)")
        await at(26.8); await js("bv.stats()")
        # 7 outro
        await at(30.6); ev("whoosh"); await js("""bv.text(`<svg width='72' height='72' viewBox='0 0 32 32' style='display:block;margin:0 auto 22px'><rect width='32' height='32' rx='8' fill='#1F7A55'/><path d='M8 11h16M8 16h16M8 21h10' stroke='#fff' stroke-width='2.5' stroke-linecap='round'/><circle cx='23' cy='21' r='2.5' fill='#F2A541'/></svg>ShelfSense<br><em>Catch stock-outs before they happen.</em><small>shelfsense-exathon.vercel.app · ExaThon India 2026 · Track 02</small>`)""")
        await at(35.2); ev("end")
        await cdp.send("Page.stopScreencast")
        await b.close()

    base = frames[0][0]
    meta = []
    for i, (ts, data) in enumerate(frames):
        path = os.path.join(OUT, f"f{i:05d}.jpg")
        with open(path, "wb") as f: f.write(base64.b64decode(data))
        meta.append((ts - base, path))
    json.dump({"frames": meta, "events": events, "screencast_offset": base - 0}, open(os.path.join(OUT, "..", "capture.json"), "w"))
    print(len(frames), "frames;", "events:", events)

asyncio.run(main())
