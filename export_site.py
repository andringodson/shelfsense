"""Pre-compute replay hours into site/snap/ so the static Vercel site can scrub them instantly.

    python export_site.py [first_day] [last_day]     # default: 2026-10-22 .. 2026-10-25, every hour
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

from load import DEFAULT_AS_OF
from shelfsense_db import connect, snapshot

first = datetime.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2026-10-22")
last = datetime.fromisoformat(sys.argv[2] if len(sys.argv) > 2 else "2026-10-25") + timedelta(hours=23)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", "snap")
os.makedirs(out, exist_ok=True)

conn, ts, n, total = connect(), first, 0, time.perf_counter()
while ts <= last:
    t = time.perf_counter()
    d = snapshot(conn, ts.strftime("%Y-%m-%d %H:%M:%S"))
    d["ms"] = round((time.perf_counter() - t) * 1000)
    with open(os.path.join(out, ts.strftime("%Y%m%d%H") + ".json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    ts, n = ts + timedelta(hours=1), n + 1
with open(os.path.join(out, "index.json"), "w") as f:
    json.dump({"lo": first.strftime("%Y%m%d%H"), "hi": last.strftime("%Y%m%d%H"), "live": False,
               "default": datetime.fromisoformat(DEFAULT_AS_OF).strftime("%Y%m%d%H")}, f)
print(f"{n} hours -> site/snap/ in {time.perf_counter() - total:.0f} s")
