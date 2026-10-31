"""Create the SHELFSENSE schema in Exasol, bulk-load data/*.csv and build the analytics views.

    python generate_data.py && python load.py
"""
import os
import sys
import time

from shelfsense_db import connect, run_sql_file

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DEFAULT_AS_OF = "2026-10-24 08:00:00"  # Saturday breakfast rush; data continues after it, so the backtest works

TABLES = [("stores.csv", "STORES"), ("skus.csv", "SKUS"), ("sales_hourly.csv", "SALES_HOURLY"),
          ("receipts.csv", "RECEIPTS"), ("truth_demand.csv", "TRUTH_DEMAND")]


def main():
    missing = [f for f, _ in TABLES if not os.path.exists(os.path.join(DATA, f))]
    if missing:
        sys.exit(f"Missing {missing} - run `python generate_data.py` first.")
    conn = connect(schema="")
    run_sql_file(conn, os.path.join(HERE, "sql", "01_schema.sql"))
    conn.execute("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
    for fname, table in TABLES:
        t = time.time()
        conn.import_from_file(os.path.join(DATA, fname), ("SHELFSENSE", table), import_params={"row_separator": "CRLF"})
        n = conn.execute(f"SELECT COUNT(*) FROM SHELFSENSE.{table}").fetchval()
        print(f"{table:<14} {n:>10,} rows  {time.time() - t:5.1f}s")
    conn.execute("INSERT INTO SHELFSENSE.HORIZON SELECT LEVEL FROM DUAL CONNECT BY LEVEL <= 48")
    conn.execute("INSERT INTO SHELFSENSE.APP_STATE VALUES ({ts})", {"ts": DEFAULT_AS_OF})
    run_sql_file(conn, os.path.join(HERE, "sql", "02_analytics.sql"))
    print("Views built. Try: SELECT * FROM SHELFSENSE.V_ACTIONS WHERE RISK_STATUS <> 'OK' "
          "ORDER BY REVENUE_AT_RISK DESC;")


if __name__ == "__main__":
    main()
