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
