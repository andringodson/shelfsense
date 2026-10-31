"""ShelfSense dashboard. Every number is computed live by Exasol from the SHELFSENSE views.

    streamlit run app/app.py
"""
import os
import sys
import time
from datetime import datetime, time as dtime

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shelfsense_db import connect, snapshot  # noqa: E402

st.set_page_config(page_title="ShelfSense", page_icon="🛒", layout="wide")


@st.cache_resource
def conn():
    return connect()


def q(sql, params=None):
    return conn().export_to_pandas(sql, params)


@st.cache_data
def bounds():
    return q("SELECT MIN(TS) AS LO, MAX(TS) AS HI FROM SALES_HOURLY").iloc[0]


@st.cache_data
def load(as_of):
    t = time.perf_counter()
    result = snapshot(conn(), as_of)
    return *result, (time.perf_counter() - t) * 1000


def inr(x):
    return f"₹{x:,.0f}"


lo, hi = bounds()
lo, hi = pd.Timestamp(lo), pd.Timestamp(hi)

with st.sidebar:
    st.title("🛒 ShelfSense")
    st.caption("Stock-out early warning for quick-commerce dark stores, computed in Exasol.")
    day = st.date_input("Replay as of", datetime(2026, 10, 24).date(),
                        min_value=(lo + pd.Timedelta(days=15)).date(), max_value=hi.date())
    hour = st.slider("Hour", 0, 23, 8)
    as_of = datetime.combine(day, dtime(hour)).strftime("%Y-%m-%d %H:%M:%S")
    st.caption("Pick any past moment: ShelfSense only sees data up to it, "
               "then the Backtest tab checks its calls against what really happened.")

actions, lost, check, backtest, ms = load(as_of)
risky = actions[actions.RISK_STATUS != "OK"]
truck_h = int(actions.TRUCK_H.iloc[0]) if len(actions) else 0

st.subheader(f"As of {as_of[:16]} · next truck in {truck_h} h (06:00)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Shelves empty now", int((actions.RISK_STATUS == "OUT").sum()))
c2.metric("Will empty before truck", int(actions.RISK_STATUS.isin(["CRITICAL", "AT RISK"]).sum()))
c3.metric("Revenue at risk before truck", inr(risky.REVENUE_AT_RISK.sum()))
c4.metric("Lost revenue, last 14 days", inr(lost.LOST_REVENUE.sum()))
st.caption(f"{len(actions):,} shelves scored over 1.3M hourly rows · Exasol query time {ms:,.0f} ms")

t1, t2, t3, t4 = st.tabs(["🚨 Action board", "📉 Lost sales", "🎯 Backtest", "🔍 Shelf drill-down"])

with t1:
    f1, f2, f3 = st.columns(3)
    cities = f1.multiselect("City", sorted(actions.CITY.unique()))
    cats = f2.multiselect("Category", sorted(actions.CATEGORY.unique()))
    statuses = f3.multiselect("Status", ["OUT", "CRITICAL", "AT RISK"], ["OUT", "CRITICAL", "AT RISK"])
    view = risky[risky.RISK_STATUS.isin(statuses)]
    if cities:
        view = view[view.CITY.isin(cities)]
    if cats:
        view = view[view.CATEGORY.isin(cats)]
    order = {"OUT": 0, "CRITICAL": 1, "AT RISK": 2}
    view = view.assign(_o=view.RISK_STATUS.map(order)).sort_values(["_o", "REVENUE_AT_RISK"], ascending=[True, False])
    st.dataframe(
        view[["RISK_STATUS", "STORE_ID", "AREA", "CITY", "SKU_NAME", "CATEGORY", "STOCK", "DEMAND_TO_TRUCK",
              "HOURS_TO_OOS", "RISK_PROB", "REVENUE_AT_RISK", "RECOMMENDATION"]],
        hide_index=True, use_container_width=True,
        column_config={
            "RISK_STATUS": "Status", "STORE_ID": "Store", "AREA": "Area", "CITY": "City", "SKU_NAME": "Product",
            "CATEGORY": "Category", "STOCK": "On shelf",
            "DEMAND_TO_TRUCK": st.column_config.NumberColumn("Demand until truck", format="%.1f"),
            "HOURS_TO_OOS": st.column_config.NumberColumn("Empty in (h)", format="%d"),
            "RISK_PROB": st.column_config.ProgressColumn("Stock-out risk", min_value=0, max_value=1, format="percent"),
            "REVENUE_AT_RISK": st.column_config.NumberColumn("₹ at risk", format="₹%.0f"),
            "RECOMMENDATION": "Do this now",
        })
    transfers = view.RECOMMENDATION.fillna("").str.startswith("Transfer").sum()
    st.caption(f"{transfers} shortfalls can be fixed by moving stock between stores in the same city; "
               "the rest need an expedited order.")

with t2:
    st.markdown("**Sales data never shows a stock-out**: an empty shelf just looks like a slow hour. "
                "ShelfSense estimates the demand behind every empty-shelf hour.")
    a, b = st.columns(2)
    a.bar_chart(lost.pivot_table(index="SALES_DAY", columns="CATEGORY", values="LOST_REVENUE", aggfunc="sum").fillna(0),
                y_label="Lost revenue (₹)")
    b.bar_chart(lost.groupby("CATEGORY").LOST_REVENUE.sum().sort_values(), horizontal=True, x_label="₹ lost, 14 days")
    est, act = check.ESTIMATED.sum(), check.ACTUAL.sum()
    st.markdown(f"**Validation against simulator ground truth:** estimated {est:,.0f} lost units vs "
                f"{act:,.0f} actual ({(est - act) / act:+.1%}).")
    st.dataframe(check, hide_index=True, use_container_width=True,
                 column_config={"ESTIMATED": st.column_config.NumberColumn(format="%.0f"),
                                "ACTUAL": st.column_config.NumberColumn(format="%.0f")})

with t3:
    if backtest.empty:
        st.info("No future data after this moment. Pick an earlier time to backtest.")
    else:
        flagged = backtest.RISK_STATUS.isin(["CRITICAL", "AT RISK"])
        hit = backtest.ACTUAL_OOS == 1
        tp, fp, fn = int((flagged & hit).sum()), int((flagged & ~hit).sum()), int((~flagged & hit).sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("Stock-outs that really happened", int(hit.sum()))
        m2.metric("Caught in advance (recall)", f"{tp / max(tp + fn, 1):.0%}")
        m3.metric("Alerts that were right (precision)", f"{tp / max(tp + fp, 1):.0%}")
        bins = pd.cut(backtest.RISK_PROB, [0, .1, .25, .4, .55, .7, .85, 1.0001], right=False)
        cal = backtest.groupby(bins, observed=True).ACTUAL_OOS.agg(["mean", "count"]).reset_index()
        cal["RISK_PROB"] = cal.RISK_PROB.astype(str)
        st.markdown("**Calibration**: of shelves given risk X, how many actually ran out?")
        st.dataframe(cal.rename(columns={"RISK_PROB": "Predicted risk", "mean": "Actually ran out", "count": "Shelves"}),
                     hide_index=True, use_container_width=True,
                     column_config={"Actually ran out": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")})

with t4:
    a, b = st.columns(2)
    store = a.selectbox("Store", sorted(actions.STORE_ID.unique()),
                        index=0, format_func=lambda s: f"{s} · {actions[actions.STORE_ID == s].AREA.iloc[0]}")
    skus = actions[actions.STORE_ID == store].sort_values("RISK_PROB", ascending=False)
    sku = b.selectbox("Product (riskiest first)", skus.SKU_ID, format_func=lambda k: skus[skus.SKU_ID == k].SKU_NAME.iloc[0])
    hist = q("""SELECT TS, UNITS_SOLD, STOCK_END FROM SALES_HOURLY
                WHERE STORE_ID = {s} AND SKU_ID = {k} AND TS > ADD_DAYS({ts}, -3) AND TS <= ADD_HOURS({ts}, 48)
                ORDER BY TS""", {"s": store, "k": sku, "ts": as_of})
    fc = q("SELECT TS, EXP_UNITS FROM V_FORECAST WHERE STORE_ID = {s} AND SKU_ID = {k} ORDER BY TS", {"s": store, "k": sku})
    df = hist.set_index("TS").join(fc.set_index("TS"), how="outer")
    df.columns = ["Sold", "On shelf (end of hour)", "Forecast demand"]
    st.line_chart(df)
    st.caption("Lines after the replay moment show what really happened, for comparison with the forecast.")
