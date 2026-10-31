"""Freeze one moment of the live Exasol results into site/snapshot.json for the static Vercel page.

    python export_site.py [as_of]      # default: Sat 24 Oct 2026 08:00
"""
import json
import os
import sys
import time

from load import DEFAULT_AS_OF
from shelfsense_db import connect, snapshot

as_of = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AS_OF
t = time.perf_counter()
actions, lost, check, backtest = snapshot(connect(), as_of)
ms = (time.perf_counter() - t) * 1000

order = {"OUT": 0, "CRITICAL": 1, "AT RISK": 2}
risky = actions[actions.RISK_STATUS != "OK"].assign(_o=lambda d: d.RISK_STATUS.map(order))
risky = risky.sort_values(["_o", "REVENUE_AT_RISK"], ascending=[True, False])
flagged = backtest.RISK_STATUS.isin(["CRITICAL", "AT RISK"])
hit = backtest.ACTUAL_OOS == 1
tp = int((flagged & hit).sum())
edges = [0, .1, .25, .4, .55, .7, .85, 1.0001]
cal = [{"bin": f"{lo:.0%}–{min(hi, 1):.0%}", "n": int(m.sum()), "rate": float(backtest.ACTUAL_OOS[m].mean())}
       for lo, hi in zip(edges, edges[1:]) if (m := backtest.RISK_PROB.between(lo, hi, inclusive="left")).any()]

out = {
    "as_of": as_of[:16], "truck_h": int(actions.TRUCK_H.iloc[0]), "ms": round(ms), "shelves": len(actions),
    "kpi": {"out": int((actions.RISK_STATUS == "OUT").sum()),
            "at_risk": int(actions.RISK_STATUS.isin(["CRITICAL", "AT RISK"]).sum()),
            "revenue_at_risk": float(risky.REVENUE_AT_RISK.sum()),
            "lost_14d": float(lost.LOST_REVENUE.sum()),
            "transfers": int(risky.RECOMMENDATION.fillna("").str.startswith("Transfer").sum())},
    "actions": risky[["RISK_STATUS", "STORE_ID", "AREA", "CITY", "SKU_NAME", "CATEGORY", "STOCK",
                      "DEMAND_TO_TRUCK", "HOURS_TO_OOS", "RISK_PROB", "REVENUE_AT_RISK", "RECOMMENDATION"]]
              .round(3).to_dict("records"),
    "lost_by_category": lost.groupby("CATEGORY").LOST_REVENUE.sum().round().sort_values(ascending=False).to_dict(),
    "lost_by_day": lost.groupby(lost.SALES_DAY.astype(str)).LOST_REVENUE.sum().round().to_dict(),
    "validation": {"estimated": float(check.ESTIMATED.sum()), "actual": float(check.ACTUAL.sum())},
    "backtest": {"actual": int(hit.sum()), "recall": tp / max(int(hit.sum()), 1),
                 "precision": tp / max(int(flagged.sum()), 1), "calibration": cal},
}
os.makedirs("site", exist_ok=True)
with open("site/snapshot.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, default=str)
print(f"site/snapshot.json: {len(out['actions'])} actions, {ms:.0f} ms in Exasol")
