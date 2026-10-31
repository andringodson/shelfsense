"""Connection helper shared by the loader and the app.

Defaults match `exasol install local`; override with EXA_DSN / EXA_USER / EXA_PASSWORD
(see `exasol info` for your deployment's values).
"""
import os

import pyexasol


def connect(schema="SHELFSENSE"):
    return pyexasol.connect(
        dsn=os.environ.get("EXA_DSN", "localhost:8563"),
        user=os.environ.get("EXA_USER", "sys"),
        password=os.environ.get("EXA_PASSWORD", "exasol"),
        schema=schema,
        # shortcut: local deployments use a self-signed cert; set EXA_VERIFY_CERT=1 for real servers
        websocket_sslopt=None if os.environ.get("EXA_VERIFY_CERT") == "1" else {"cert_reqs": 0},
        compression=True,
    )


ACTION_COLS = ["RISK_STATUS", "STORE_ID", "AREA", "CITY", "SKU_ID", "SKU_NAME", "CATEGORY", "STOCK",
               "DEMAND_TO_TRUCK", "HOURS_TO_OOS", "RISK_PROB", "REVENUE_AT_RISK", "RECOMMENDATION"]
CAL_EDGES = [0, .1, .25, .4, .55, .7, .85, 1.0001]


def rows(conn, sql, params=None):
    # execute()+fetch over the websocket: ~1 s faster per query than export_to_pandas' HTTP tunnel
    st = conn.execute(sql, params)
    cols = st.column_names()
    return [dict(zip(cols, r)) for r in st]


def snapshot(conn, as_of):
    """Everything the dashboard shows for one moment, as a JSON-ready dict. Three queries."""
    # APP_STATE is the single "now" all views read; single-user Exasol Personal, so a plain UPDATE is fine.
    conn.execute("UPDATE APP_STATE SET AS_OF = {ts}", {"ts": as_of})
    actions = rows(conn, "SELECT " + ", ".join(ACTION_COLS) + ", TRUCK_H FROM V_ACTIONS")
    # Projected shelf stock until the truck, next to what really happened (when replaying history).
    traj = rows(conn, """
        SELECT f.STORE_ID, f.SKU_ID, f.H,
               GREATEST(p.STOCK - SUM(f.EXP_UNITS) OVER (PARTITION BY f.STORE_ID, f.SKU_ID ORDER BY f.H), 0) AS PROJ,
               s.STOCK_END AS ACTUAL
        FROM V_FORECAST f
        JOIN V_POSITION p ON p.STORE_ID = f.STORE_ID AND p.SKU_ID = f.SKU_ID
        LEFT JOIN SALES_HOURLY s ON s.STORE_ID = f.STORE_ID AND s.SKU_ID = f.SKU_ID AND s.TS = f.TS
        WHERE f.H < MOD(6 - HOUR({ts}) + 23, 24) + 1
        ORDER BY f.STORE_ID, f.SKU_ID, f.H""", {"ts": as_of})
    # Lost sales by day x category, with the simulator's hidden ground truth alongside (validation only).
    lost = rows(conn, """
        SELECT TO_CHAR(l.TS, 'YYYY-MM-DD') AS SALES_DAY, l.CATEGORY, SUM(l.LOST_REVENUE) AS LOST_REVENUE,
               SUM(l.LOST_UNITS) AS EST_UNITS, CAST(SUM(t.DEMAND - l.UNITS_SOLD) AS DECIMAL(18, 0)) AS TRUE_UNITS
        FROM V_LOST_SALES l
        LEFT JOIN TRUTH_DEMAND t ON t.TS = l.TS AND t.STORE_ID = l.STORE_ID AND t.SKU_ID = l.SKU_ID
        WHERE l.TS > ADD_DAYS({ts}, -14)
        GROUP BY TO_CHAR(l.TS, 'YYYY-MM-DD'), l.CATEGORY""", {"ts": as_of})

    series = {}
    for r in traj:
        series.setdefault((r["STORE_ID"], r["SKU_ID"]), []).append(r)
    order = {"OUT": 0, "CRITICAL": 1, "AT RISK": 2}
    risky = sorted((a for a in actions if a["RISK_STATUS"] != "OK"),
                   key=lambda a: (order[a["RISK_STATUS"]], -a["REVENUE_AT_RISK"]))
    for a in risky:
        s = series.get((a["STORE_ID"], a["SKU_ID"]), [])
        a["PROJ"] = [round(r["PROJ"], 1) for r in s]
        a["ACTUAL"] = [r["ACTUAL"] for r in s]  # None beyond the end of the data

    # Backtest from the same trajectories: did a shelf that had stock really hit zero before the truck?
    bt = []
    for a in actions:
        actual = [r["ACTUAL"] for r in series.get((a["STORE_ID"], a["SKU_ID"]), [])]
        if a["STOCK"] > 0 and actual and None not in actual:
            bt.append((a["RISK_STATUS"] in ("CRITICAL", "AT RISK"), 0 in actual, a["RISK_PROB"]))
    hit = sum(o for _, o, _ in bt)
    flagged = sum(f for f, _, _ in bt)
    tp = sum(f and o for f, o, _ in bt)
    cal = []
    for lo, hi in zip(CAL_EDGES, CAL_EDGES[1:]):
        b = [o for _, o, p in bt if lo <= p < hi]
        if b:
            cal.append({"lo": lo, "hi": min(hi, 1), "n": len(b), "rate": sum(b) / len(b)})

    by_cat, by_day = {}, {}
    for r in lost:
        by_cat[r["CATEGORY"]] = by_cat.get(r["CATEGORY"], 0) + r["LOST_REVENUE"]
        by_day[r["SALES_DAY"]] = by_day.get(r["SALES_DAY"], 0) + r["LOST_REVENUE"]
    return {
        "as_of": as_of[:16],
        "truck_h": actions[0]["TRUCK_H"] if actions else 0,
        "shelves": len(actions),
        "kpi": {"out": sum(a["RISK_STATUS"] == "OUT" for a in actions),
                "at_risk": sum(a["RISK_STATUS"] in ("CRITICAL", "AT RISK") for a in actions),
                "revenue_at_risk": round(sum(a["REVENUE_AT_RISK"] for a in risky)),
                "lost_14d": round(sum(by_cat.values())),
                "transfers": sum((a["RECOMMENDATION"] or "").startswith("Transfer") for a in risky)},
        "actions": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in a.items() if k != "TRUCK_H"}
                    for a in risky],
        "lost_by_category": {k: round(v) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
        "lost_by_day": {k: round(by_day[k]) for k in sorted(by_day)},
        "validation": {"estimated": round(sum(r["EST_UNITS"] for r in lost)),
                       "actual": sum(r["TRUE_UNITS"] or 0 for r in lost)},
        "backtest": None if not bt else {"actual": hit, "flagged": flagged,
                                         "recall": tp / max(hit, 1), "precision": tp / max(flagged, 1),
                                         "calibration": cal},
    }


def run_sql_file(conn, path):
    # Statements are separated by ';' at end of line; our SQL files contain no ';' inside strings.
    with open(path, encoding="utf-8") as f:
        sql = "\n".join(line for line in f.read().splitlines() if not line.strip().startswith("--"))
    for stmt in (s.strip() for s in sql.split(";")):
        if stmt:
            conn.execute(stmt)
