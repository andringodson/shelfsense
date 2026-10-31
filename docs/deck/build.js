// Builds docs/ShelfSense-pitch.pptx:  npm i pptxgenjs@3.12.0 && node docs/deck/build.js docs/ShelfSense-pitch.pptx
const path = require("path");
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.title = "ShelfSense: ExaThon India 2026";
pres.author = "Andrin Godson, Karthikeyan";
pres.theme = { headFontFace: "Cambria", bodyFontFace: "Calibri" };

const DARK = "123B2C", GREEN = "1F7A55", MINT = "E3F4EA", SAFFRON = "E8891C", INK = "1B1D1F", MUTE = "5F6670", WHITE = "FFFFFF";
const OUT = process.argv[2];

pres.defineSlideMaster({
  title: "CONTENT", background: { color: WHITE },
  objects: [{ text: { text: "ShelfSense · ExaThon India 2026 · Track 02", options: { x: 0.5, y: 5.2, w: 6, h: 0.3, fontSize: 10, color: MUTE, fontFace: "Calibri" } } }],
  slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: MUTE, fontFace: "Calibri", align: "right" },
});

const title = (s, t) => s.addText(t, { x: 0.5, y: 0.35, w: 9, h: 0.75, fontFace: "Cambria", fontSize: 30, bold: true, color: DARK, margin: 0, isTextBox: true });
const text = (s, t, o) => s.addText(t, { fontFace: "Calibri", color: INK, fontSize: 15, margin: 0, valign: "top", isTextBox: true, ...o });
const stat = (s, x, y, w, big, label, color = GREEN) => {
  text(s, big, { x, y, w, h: 0.75, fontSize: 40, bold: true, color, fontFace: "Cambria" });
  text(s, label, { x, y: y + 0.78, w, h: 0.6, fontSize: 13, color: MUTE });
};
const card = (s, x, y, w, h, fill = MINT) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.12 });
const dot = (s, x, y, n, fill = GREEN) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color: fill }, line: { color: fill } });
  text(s, String(n), { x, y, w: 0.42, h: 0.42, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle" });
};

// 1. Title
let s = pres.addSlide();
s.background = { color: DARK };
text(s, "ExaThon India 2026 · Track 02: Customers, Channels & Demand", { x: 0.6, y: 0.6, w: 8.8, h: 0.4, fontSize: 14, color: "9FD8B8" });
text(s, "ShelfSense", { x: 0.6, y: 1.35, w: 8.8, h: 1.0, fontSize: 54, bold: true, color: WHITE, fontFace: "Cambria" });
text(s, "Catch stock-outs before they happen.", { x: 0.6, y: 2.4, w: 8.8, h: 0.6, fontSize: 24, color: SAFFRON, italic: true, fontFace: "Cambria" });
text(s, "Stock-out early warning for quick-commerce dark stores, computed entirely in SQL inside Exasol Personal.", { x: 0.6, y: 3.15, w: 7.5, h: 0.7, fontSize: 16, color: "D6E9DE" });
text(s, "Andrin Godson · Karthikeyan", { x: 0.6, y: 4.55, w: 5, h: 0.35, fontSize: 14, color: WHITE, bold: true });
text(s, "shelfsense-exathon.vercel.app · github.com/andringodson/shelfsense", { x: 0.6, y: 4.9, w: 8, h: 0.35, fontSize: 12, color: "9FD8B8" });
s.addNotes("ShelfSense predicts which shelves in which dark stores will run empty before the next truck, and tells the ops team what to do about each one.");

// 2. Problem
s = pres.addSlide({ masterName: "CONTENT" });
title(s, "An empty shelf is a lost customer");
text(s, [
  { text: "The customer doesn't wait. They open another app.", options: { bullet: true, breakLine: true } },
  { text: "Store managers find out from complaints or a weekly report, hours too late.", options: { bullet: true, breakLine: true } },
  { text: "Sales data can't show it: an empty shelf at 7 PM looks exactly like a quiet hour.", options: { bullet: true } },
], { x: 0.5, y: 1.35, w: 4.6, h: 2.6, fontSize: 16, paraSpaceAfter: 10 });
card(s, 5.5, 1.3, 4.0, 3.5);
stat(s, 5.8, 1.5, 3.5, "5.7%", "of all demand goes unserved because the shelf was empty", SAFFRON);
stat(s, 5.8, 3.05, 3.5, "₹15 lakh", "revenue lost in 14 days across 25 stores (simulated network)");
s.addNotes("Who has it: dark-store managers and city ops at quick-commerce chains. Why it matters: every miss is revenue plus a customer trained to use a competitor.");

// 3. The trap
s = pres.addSlide({ masterName: "CONTENT" });
title(s, "Stock-outs hide, then breed more stock-outs");
const loop = [
  ["Shelf runs empty", "Sales record 0, not the 12 customers who wanted it."],
  ["Forecast learns \"low demand\"", "Models trained on sales copy the stock-out zeros."],
  ["Next order is smaller", "So the shelf empties earlier, and the loop tightens."],
];
loop.forEach(([h, b], i) => {
  const x = 0.5 + i * 3.1;
  card(s, x, 1.45, 2.8, 2.5);
  dot(s, x + 0.25, 1.7, i + 1, i === 2 ? SAFFRON : GREEN);
  text(s, h, { x: x + 0.25, y: 2.3, w: 2.35, h: 0.7, fontSize: 17, bold: true, color: DARK, fontFace: "Cambria" });
  text(s, b, { x: x + 0.25, y: 3.0, w: 2.35, h: 0.85, fontSize: 14 });
  if (i < 2) text(s, "→", { x: x + 2.8, y: 2.4, w: 0.3, h: 0.5, fontSize: 22, bold: true, color: SAFFRON, align: "center" });
});
text(s, "ShelfSense breaks the loop: it learns demand only from hours when the shelf was NOT empty.", { x: 0.5, y: 4.25, w: 9, h: 0.5, fontSize: 16, bold: true, color: GREEN });

// 4. Solution
s = pres.addSlide({ masterName: "CONTENT" });
title(s, "Will this shelf empty before the truck?");
s.addImage({ path: path.join(__dirname, "..", "dashboard.png"), x: 0.5, y: 1.25, w: 5.47, h: 3.8, altText: "ShelfSense dashboard action board" });
[["Action board", "Risk of running empty before the 06:00 truck, revenue at stake, and the fix: transfer or expedite."],
 ["Lost sales", "Demand hidden behind every empty-shelf hour, valued in ₹."],
 ["Backtest replay", "Rewind to any hour, then score the calls against what really happened."]].forEach(([h, b], i) => {
  dot(s, 6.3, 1.3 + i * 1.25, i + 1);
  text(s, h, { x: 6.85, y: 1.3 + i * 1.25, w: 2.7, h: 0.35, fontSize: 16, bold: true, color: DARK });
  text(s, b, { x: 6.85, y: 1.65 + i * 1.25, w: 2.7, h: 0.8, fontSize: 13 });
});

// 5. Exasol
s = pres.addSlide({ masterName: "CONTENT" });
title(s, "All the intelligence lives in Exasol as SQL views");
const steps = [["V_SHAPE · V_RATE", "Censoring-aware demand"], ["V_FORECAST", "48-hour forecast"], ["V_RISK", "Poisson risk, hours to empty"], ["V_ACTIONS", "Same-city rebalancing"], ["V_BACKTEST", "Scored against the future"]];
steps.forEach(([v, d], i) => {
  const x = 0.5 + i * 1.86;
  card(s, x, 1.4, 1.66, 1.5, i % 2 ? MINT : "CDEBD8");
  text(s, v, { x: x + 0.12, y: 1.55, w: 1.45, h: 0.55, fontSize: 12, bold: true, color: DARK, fontFace: "Calibri" });
  text(s, d, { x: x + 0.12, y: 2.1, w: 1.45, h: 0.7, fontSize: 13 });
});
stat(s, 0.5, 3.25, 2.8, "1.3 M", "hourly rows bulk-loaded in 2.5 s");
stat(s, 3.6, 3.25, 2.8, "1.2 s", "to score every shelf at any hour: 3 queries, on a laptop");
stat(s, 6.7, 3.25, 2.8, "20 ms", "to replay any hour once cached: the timeline scrubs live", SAFFRON);
s.addNotes("Window functions for running demand, ROW_NUMBER self-join for donor stores, a single APP_STATE row lets every view time-travel. Analysts can query V_ACTIONS from any SQL client.");

// 6. Results
s = pres.addSlide({ masterName: "CONTENT" });
title(s, "The calls hold up against what really happened");
stat(s, 0.5, 1.35, 2.0, "72%", "of alerts were right (precision)");
stat(s, 2.6, 1.35, 2.0, "57%", "of real stock-outs caught in advance");
stat(s, 0.5, 2.95, 4.1, "96%", "of shelves rated 85–100% risk really ran out. At 0–10% risk, only 4% did.", SAFFRON);
s.addChart(pres.charts.BAR, [{ name: "Actually ran out", labels: ["0–10%", "10–25%", "25–40%", "40–55%", "55–70%", "70–85%", "85–100%"], values: [0.04, 0.22, 0.37, 0.47, 0.64, 0.87, 0.96] }], {
  x: 4.9, y: 1.2, w: 4.6, h: 3.8, barDir: "col", chartColors: [GREEN],
  showTitle: true, title: "Predicted risk vs actual stock-out rate", titleFontSize: 13, titleColor: INK, titleFontFace: "Calibri",
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0%", dataLabelFontSize: 11, dataLabelColor: INK, dataLabelFontFace: "Calibri",
  valAxisHidden: true, valAxisMaxVal: 1.1, valGridLine: { style: "none" }, catGridLine: { style: "none" },
  catAxisLabelColor: MUTE, catAxisLabelFontSize: 10, catAxisLabelFontFace: "Calibri", showLegend: false,
});
s.addNotes("Replay at Saturday 24 Oct 08:00: 218 shelves really went empty before the next truck. Lost-sales estimate is within 28% of simulator ground truth, deliberately conservative.");

// 7. Impact
s = pres.addSlide({ masterName: "CONTENT" });
title(s, "From alert to action in one screen");
card(s, 0.5, 1.35, 4.35, 3.4);
text(s, "Saturday, 08:00 · 25 stores", { x: 0.8, y: 1.55, w: 3.8, h: 0.4, fontSize: 14, color: MUTE });
stat(s, 0.8, 2.0, 3.8, "173 shelves", "will empty before tomorrow's truck");
stat(s, 0.8, 3.35, 3.8, "₹1.19 lakh", "at risk today, before anyone notices", SAFFRON);
text(s, "What the ops team gets", { x: 5.2, y: 1.4, w: 4.3, h: 0.4, fontSize: 18, bold: true, color: DARK, fontFace: "Cambria" });
text(s, [
  { text: "57 shortfalls fixed by a same-city transfer: \"Transfer 23 from DS07 (T Nagar)\"", options: { bullet: true, breakLine: true } },
  { text: "The rest get a case-pack-rounded expedite order", options: { bullet: true, breakLine: true } },
  { text: "Ranked by ₹ at risk, so the first call is the most valuable one", options: { bullet: true, breakLine: true } },
  { text: "Planners see true demand, so the next order stops shrinking", options: { bullet: true } },
], { x: 5.2, y: 1.95, w: 4.3, h: 2.8, fontSize: 15, paraSpaceAfter: 8 });

// 8. Close
s = pres.addSlide();
s.background = { color: DARK };
text(s, "Real-world next steps", { x: 0.6, y: 0.5, w: 8.8, h: 0.7, fontSize: 32, bold: true, color: WHITE, fontFace: "Cambria" });
[["Plug in real feeds", "POS and WMS exports load with the same IMPORT path. The schema is 4 tables."],
 ["Smarter fixes", "Dark-store distance, rider capacity, and shelf life for perishables."],
 ["Push, not pull", "Alerts to store managers on WhatsApp or Slack the moment risk crosses 70%."]].forEach(([h, b], i) => {
  const x = 0.6 + i * 3.0;
  dot(s, x, 1.5, i + 1, SAFFRON);
  text(s, h, { x, y: 2.05, w: 2.7, h: 0.4, fontSize: 17, bold: true, color: WHITE });
  text(s, b, { x, y: 2.5, w: 2.7, h: 1.0, fontSize: 14, color: "D6E9DE" });
});
text(s, "Live: shelfsense-exathon.vercel.app\nCode: github.com/andringodson/shelfsense (MIT)", { x: 0.6, y: 3.95, w: 6.5, h: 0.7, fontSize: 15, color: "9FD8B8" });
text(s, "Andrin Godson: data model, Exasol SQL, dashboard\nKarthikeyan: testing, reproducibility, demo review", { x: 0.6, y: 4.65, w: 8.8, h: 0.6, fontSize: 12, color: WHITE });

pres.writeFile({ fileName: OUT }).then(f => console.log("wrote", f));
