"""Local ShelfSense server: the dashboard in site/, with every replay hour computed live by Exasol.

    python server.py            # http://localhost:8000

/snap/<YYYYMMDDHH>.json is served from site/snap/ when pre-exported (that is all Vercel has),
otherwise computed from Exasol on demand and kept in memory.
"""
import functools
import json
import os
import socket
import threading
import time
from datetime import datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from load import DEFAULT_AS_OF
from shelfsense_db import connect, snapshot

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
CACHE = os.path.join(HERE, "data", "cache")  # computed hours survive restarts; load.py clears it
conn, lock, cache = connect(), threading.Lock(), {}
waiting = 0  # user requests queued for the connection; the warmer yields to them


def key_to_ts(key):
    return datetime.strptime(key, "%Y%m%d%H").strftime("%Y-%m-%d %H:%M:%S")


def live_snapshot(key):
    if key in cache:
        return cache[key]
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        with open(path, "rb") as f:
            cache[key] = f.read()
        return cache[key]
    with lock:  # one connection, and APP_STATE is shared: compute one hour at a time
        if key not in cache:
            t = time.perf_counter()
            d = snapshot(conn, key_to_ts(key))
            d["ms"] = round((time.perf_counter() - t) * 1000)
            cache[key] = json.dumps(d).encode()
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "wb") as f:
                f.write(cache[key])
        return cache[key]


def warm():
    """Pre-compute every hour, nearest to the default first, pausing whenever a user request is waiting."""
    idx = index()
    lo, hi, d0 = (datetime.strptime(idx[k], "%Y%m%d%H") for k in ("lo", "hi", "default"))
    hours = [lo + timedelta(hours=h) for h in range(int((hi - lo).total_seconds() // 3600) + 1)]
    for ts in sorted(hours, key=lambda h: abs(h - d0)):
        while waiting:
            time.sleep(0.05)
        live_snapshot(ts.strftime("%Y%m%d%H"))
    print(f"warm: all {len(hours)} hours cached")


@functools.lru_cache(maxsize=1)
def index():
    with lock:
        lo, hi = conn.execute("SELECT MIN(TS), MAX(TS) FROM SALES_HOURLY").fetchone()
    fmt = lambda t: datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
    first = fmt(lo) + timedelta(days=15)  # the demand model needs two weeks of history
    return {"lo": first.strftime("%Y%m%d%H"), "hi": fmt(hi).strftime("%Y%m%d%H"), "live": True,
            "default": datetime.strptime(DEFAULT_AS_OF, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d%H")}


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/snap/index.json":
            return self.send_json(json.dumps(index()).encode())
        name = path.removeprefix("/snap/").removesuffix(".json")
        if path.startswith("/snap/") and name.isdigit() and len(name) == 10:
            if not os.path.exists(os.path.join(SITE, "snap", name + ".json")):
                global waiting
                waiting += 1
                try:
                    return self.send_json(live_snapshot(name))
                except ValueError:
                    return self.send_error(400, "bad hour")
                finally:
                    waiting -= 1
        return super().do_GET()

    def send_json(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the console quiet
        pass


class DualStackServer(ThreadingHTTPServer):
    # Windows resolves "localhost" to ::1 first; an IPv4-only socket costs ~200 ms per request.
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"ShelfSense on http://localhost:{port}")
    threading.Thread(target=warm, daemon=True).start()
    DualStackServer(("::", port), partial(Handler, directory=SITE)).serve_forever()
