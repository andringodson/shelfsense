"""Record the full ShelfSense walkthrough from the LIVE dashboard (server.py + Exasol), paced by the narration.

    python demo.py            # needs: server.py on :8000, vo/l<i>.wav from voice.py
Writes frames/ + capture.json (frame timestamps, events, narration start times).
"""
import asyncio, base64, json, os
import soundfile as sf
from playwright.async_api import async_playwright
from overlay import OVERLAY

URL = "http://localhost:8000/#2026102408"
UNCACHED = "2026093012"  # an hour the server has not computed yet -> shows a live Exasol compute
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "frames"); os.makedirs(OUT, exist_ok=True)

EXTRA_CSS = r"""
(() => { const s = document.createElement("style"); s.textContent = `
#bv-t .sub { display:block; margin-top:26px; font:500 21px/1.5 Inter,sans-serif; color:#9FC9B5; max-width:860px; margin-inline:auto }
#bv-t .chips { display:flex; flex-wrap:wrap; gap:10px; justify-content:center; margin:26px auto 0; max-width:1000px }
#bv-t .chips span { font:500 17px Inter,sans-serif; color:#F3F6F4; background:#16352A; border:1px solid #24503F; padding:8px 14px; border-radius:10px }
#bv-t pre { text-align:left; margin:28px auto 0; padding:22px 26px; border-radius:14px; background:#0F2A21; border:1px solid #24503F;
  font:500 19px/1.55 "Cascadia Code",Consolas,monospace; color:#DDEBE4; max-width:940px; white-space:pre }
#bv-t pre b { color:#F2A541; font-weight:500 } #bv-t pre i { color:#7FB89E; font-style:normal }
#bv-t h2 { font:400 64px/1.1 "Instrument Serif",Georgia,serif; margin:0 }
`; document.head.append(s); })();
"""

SQL = ("<b>SELECT</b> STORE_ID, SKU_NAME, STOCK, RISK_PROB, RECOMMENDATION\n"
       "<b>FROM</b>   SHELFSENSE.V_ACTIONS\n<b>WHERE</b>  RISK_STATUS &lt;&gt; 'OK'\n<b>ORDER BY</b> REVENUE_AT_RISK <b>DESC</b>;\n\n"
       "<i>-- time-travel: every view follows</i>\n<b>UPDATE</b> SHELFSENSE.APP_STATE <b>SET</b> AS_OF = '2026-10-20 18:00:00';")


async def main():
    lines = json.load(open(os.path.join(HERE, "narration.json")))
    durs = [sf.info(os.path.join(HERE, "vo", f"l{i}.wav")).duration for i in range(len(lines))]
    # minimum on-screen time per scene so the action fits even if the line is short
    mins = {"intro": 0, "problem": 0, "overview": 0, "replay": 12, "live": 11, "actions": 0, "lost": 0, "sql": 0, "dark": 7, "outro": 6}
    starts, t = [], 0.6
    for l, d in zip(lines, durs):
        starts.append(t); t += max(d + 0.9, mins[l["id"]])
    END = t + 1.6
    S = {l["id"]: s for l, s in zip(lines, starts)}
    D = {l["id"]: d for l, d in zip(lines, durs)}

    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--force-color-profile=srgb"])
        pg = await b.new_page(viewport={"width": 1440, "height": 810}, device_scale_factor=4 / 3, color_scheme="light")
        await pg.goto(URL); await pg.wait_for_selector("#rows tr[data-key]")
        await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(2500)
        await pg.evaluate(OVERLAY); await pg.evaluate(EXTRA_CSS)
        await pg.evaluate("bv.card(true); document.getElementById('bv-card').style.transition='none'")
        await pg.wait_for_timeout(300); await pg.evaluate("document.getElementById('bv-card').style.transition=''")

        cdp = await pg.context.new_cdp_session(pg)
        frames, events = [], []
        async def ack(sid):
            try: await cdp.send("Page.screencastFrameAck", {"sessionId": sid})
            except Exception: pass
        def on_frame(e):
            frames.append((e["metadata"]["timestamp"], e["data"])); asyncio.ensure_future(ack(e["sessionId"]))
        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1})
        loop = asyncio.get_running_loop(); t0 = loop.time()

        async def at(t): await asyncio.sleep(max(0, t0 + t - loop.time()))
        def ev(name): events.append((round(loop.time() - t0, 3), name))
        async def js(code): return await asyncio.wait_for(pg.evaluate(code), 8)
        async def center(sel):
            return await js(f"(() => {{ const r = ({sel}).getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height/2]; }})()")
        async def move_to(sel, dx=0, dy=0):
            x, y = await center(sel); await js(f"bv.move({x - 4 + dx},{y - 4 + dy})")
        async def click(sel):
            ev("click"); await js(f"bv.click(); ({sel}).click()")

        # intro
        s = S["intro"]; await at(s - 0.45); ev("whoosh")
        await js("""bv.text(`<svg width='76' height='76' viewBox='0 0 32 32' style='display:block;margin:0 auto 24px'><rect width='32' height='32' rx='8' fill='#1F7A55'/><path d='M8 11h16M8 16h16M8 21h10' stroke='#fff' stroke-width='2.5' stroke-linecap='round'/><circle cx='23' cy='21' r='2.5' fill='#F2A541'/></svg><h2>ShelfSense</h2><em>Catch stock-outs before they happen.</em><small>ExaThon India 2026 · Track 02: Customers, Channels &amp; Demand · built on Exasol Personal</small>`)""")
        # problem
        s = S["problem"]; await at(s - 0.3); ev("whoosh")
        await js("""bv.text(`An empty shelf looks exactly like <em>a quiet hour.</em><span class='sub'>Sales record what was sold, not what customers wanted. Forecasts learn the zeros, the next order shrinks, and the shelf empties again.</span>`)""")
        # overview: reveal the live dashboard
        s = S["overview"]; await at(s - 0.6); await js("bv.fade()")
        await at(s - 0.15); ev("reveal"); await js("bv.card(false)")
        await at(s + 0.6); await js("bv.cap('Live · computed by Exasol Personal on this laptop')")
        await at(s + 1.2); await move_to("document.getElementById('mode')")
        await at(s + 4.6); await move_to("document.querySelectorAll('.kpi')[0]", 40)
        await at(s + 6.6); await move_to("document.querySelectorAll('.kpi')[1]", 40)
        await at(s + 9.2); await move_to("document.querySelectorAll('.kpi')[2]", 40)
        # replay
        s = S["replay"]; await at(s); await js("bv.cap('Replay: 1,325 shelves re-scored every hour')")
        await at(s + 0.3); await move_to("document.getElementById('play')")
        await at(s + 1.1); await click("document.getElementById('play')")
        await at(S["live"] - 0.6); await click("document.getElementById('play')")
        # live compute of an uncached hour, then back to a cached one
        s = S["live"]; await at(s); await js("bv.cap('Any hour in six weeks of history, computed live')")
        await at(s + 0.4)
        x = await js(f"(() => {{ const sl = document.getElementById('slider'), r = sl.getBoundingClientRect(); const i = (toDate('{UNCACHED}') - toDate(state.index.lo)) / 3600e3; return [r.left + 9 + (r.width - 18) * i / sl.max, r.top + r.height / 2]; }})()")
        await js(f"bv.move({x[0] - 4},{x[1] - 4})")
        await at(s + 1.3); ev("click"); await js(f"bv.click(); go('{UNCACHED}')")
        await at(s + 2.0); await move_to("document.querySelector('#engine b')", -10)
        await at(s + 6.4); ev("click"); await js("bv.click(); go('2026102410')")
        # action board: Critical filter, a city with a transfer, the shelf detail
        s = S["actions"]; await at(s); await js("bv.cap('What to do: transfer from a nearby store, or expedite')")
        await at(s + 0.2); ev("swoosh"); await js("bv.scrollTo(250, 800)")
        await at(s + 1.3); await move_to("document.querySelector('#seg button[data-s=\"CRITICAL\"]')")
        await at(s + 2.1); await click("document.querySelector('#seg button[data-s=\"CRITICAL\"]')")
        city = await js("(state.data.actions.find(a => a.RISK_STATUS === 'CRITICAL' && (a.RECOMMENDATION || '').startsWith('Transfer')) || {}).CITY || ''")
        await at(s + 3.4); await move_to("document.getElementById('city')")
        await at(s + 4.2); ev("click"); await js(f"bv.click(); const c = document.getElementById('city'); c.value = {json.dumps(city)}; c.dispatchEvent(new Event('change'))")
        row = "[...document.querySelectorAll('#rows tr')].find(r => r.textContent.includes('Transfer') && !r.classList.contains('sel')) || document.querySelectorAll('#rows tr')[1]"
        await at(s + 5.6); await move_to(row, -180)
        await at(s + 6.6); await click(row)
        await at(s + 9.5); await move_to("document.querySelector('#detail .rec')", -60)
        await at(s + 12.0); await move_to("document.querySelector('#chart')", 40)
        # lost revenue + backtest
        s = S["lost"]; await at(s); await js("bv.cap('Revenue already lost, and every call backtested')")
        await at(s + 0.2); ev("swoosh"); await js("bv.move(1300, 700); bv.scrollTo(document.querySelector('.lower').getBoundingClientRect().top + scrollY - 70, 1200)")
        await at(s + 2.0); await move_to("document.querySelector('#lost .row')", -120)
        await at(s + 9.0); await move_to("document.querySelector('#bt .bars .row:last-child')", -40)
        # SQL card
        s = S["sql"]; await at(s - 0.35); ev("whoosh"); await js(f"bv.cap(''); bv.card(true); bv.text(`<h2>All of it is SQL views in Exasol</h2><div class='chips'><span>V_SHAPE · V_RATE: censoring-aware demand</span><span>V_FORECAST: 48 h</span><span>V_RISK: Poisson</span><span>V_ACTIONS: same-city rebalancing</span><span>V_BACKTEST</span></div><pre>{SQL}</pre>`)")
        # dark mode
        s = S["dark"]; await at(s - 0.5); await js("bv.fade()")
        await at(s - 0.1); ev("reveal"); await js("scrollTo(0, 0); document.querySelector('#seg button[data-s=\"\"]').click(); const c = document.getElementById('city'); c.value=''; c.dispatchEvent(new Event('change')); bv.card(false)")
        await at(s + 0.5); await js("bv.cap('Dark mode · hosted at shelfsense-exathon.vercel.app')")
        await at(s + 0.7); await move_to("document.getElementById('theme')")
        await at(s + 1.6); await click("document.getElementById('theme')")
        await at(s + 3.6); await click("document.getElementById('play')")
        await at(S["outro"] - 0.7); await click("document.getElementById('play')")
        # outro
        s = S["outro"]; await at(s - 0.4); ev("whoosh")
        await js("""bv.cap(''); bv.card(true); bv.text(`<svg width='76' height='76' viewBox='0 0 32 32' style='display:block;margin:0 auto 24px'><rect width='32' height='32' rx='8' fill='#1F7A55'/><path d='M8 11h16M8 16h16M8 21h10' stroke='#fff' stroke-width='2.5' stroke-linecap='round'/><circle cx='23' cy='21' r='2.5' fill='#F2A541'/></svg>ShelfSense<br><em>Catch the empty shelf<br>before your customer does.</em><small>shelfsense-exathon.vercel.app · github.com/andringodson/shelfsense</small><small style='margin-top:8px'>Andrin Godson &amp; Karthikeyan · ExaThon India 2026</small>`)""")
        await at(END); ev("end")
        await cdp.send("Page.stopScreencast"); await b.close()

    base = frames[0][0]; meta = []
    for i, (ts, data) in enumerate(frames):
        path = os.path.join(OUT, f"f{i:05d}.jpg")
        with open(path, "wb") as f: f.write(base64.b64decode(data))
        meta.append((ts - base, path))
    narr = [{"at": s, **l} for s, l in zip(starts, lines)]
    json.dump({"frames": meta, "events": events, "end": END, "narration": narr}, open(os.path.join(HERE, "capture.json"), "w"))
    print(len(frames), "frames;", f"{END:.1f}s;", "events:", events)

asyncio.run(main())
