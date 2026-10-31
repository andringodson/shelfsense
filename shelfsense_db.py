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


def snapshot(conn, as_of):
    """Everything the dashboard shows for one moment: (actions, lost, check, backtest) DataFrames."""
    # APP_STATE is the single "now" all views read; single-user Exasol Personal, so a plain UPDATE is fine.
    conn.execute("UPDATE APP_STATE SET AS_OF = {ts}", {"ts": as_of})
    q = conn.export_to_pandas
    actions = q("SELECT * FROM V_ACTIONS")
    lost = q("""SELECT CAST(TS AS DATE) AS SALES_DAY, CATEGORY, SUM(LOST_UNITS) AS LOST_UNITS,
                       SUM(LOST_REVENUE) AS LOST_REVENUE
                FROM V_LOST_SALES WHERE TS > ADD_DAYS({ts}, -14)
                GROUP BY CAST(TS AS DATE), CATEGORY""", {"ts": as_of})
    # Validation against the simulator's hidden ground truth (unknowable in real life).
    check = q("""SELECT l.CATEGORY, SUM(l.LOST_UNITS) AS ESTIMATED, SUM(t.DEMAND - l.UNITS_SOLD) AS ACTUAL
                 FROM V_LOST_SALES l
                 LEFT JOIN TRUTH_DEMAND t ON t.TS = l.TS AND t.STORE_ID = l.STORE_ID AND t.SKU_ID = l.SKU_ID
                 WHERE l.TS > ADD_DAYS({ts}, -14)
                 GROUP BY l.CATEGORY ORDER BY l.CATEGORY""", {"ts": as_of})
    backtest = q("SELECT * FROM V_BACKTEST")
    return actions, lost, check, backtest


def run_sql_file(conn, path):
    # Statements are separated by ';' at end of line; our SQL files contain no ';' inside strings.
    with open(path, encoding="utf-8") as f:
        sql = "\n".join(line for line in f.read().splitlines() if not line.strip().startswith("--"))
    for stmt in (s.strip() for s in sql.split(";")):
        if stmt:
            conn.execute(stmt)
