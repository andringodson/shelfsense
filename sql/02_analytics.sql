OPEN SCHEMA SHELFSENSE;

-- Hourly facts up to "now", with hour-of-day / day-of-week (0 = Monday; 2024-01-01 was a Monday).
-- An hour that ended with an empty shelf is CENSORED: sales understate what customers wanted.
CREATE OR REPLACE VIEW V_HOURLY AS
SELECT s.TS, s.STORE_ID, s.SKU_ID, k.CATEGORY, s.UNITS_SOLD, s.STOCK_END,
       HOUR(s.TS) AS HOD,
       MOD(DAYS_BETWEEN(CAST(s.TS AS DATE), DATE '2024-01-01'), 7) AS DOW,
       CASE WHEN s.STOCK_END = 0 THEN 1 ELSE 0 END AS CENSORED
FROM SALES_HOURLY s
JOIN SKUS k ON k.SKU_ID = s.SKU_ID
CROSS JOIN APP_STATE a
WHERE s.TS <= a.AS_OF;

-- Category demand shape by weekday x hour, learned only from uncensored hours, normalised to mean 1.
CREATE OR REPLACE VIEW V_SHAPE AS
WITH c AS (
    SELECT CATEGORY, DOW, HOD, AVG(UNITS_SOLD) AS AVG_UNITS
    FROM V_HOURLY
    WHERE CENSORED = 0
    GROUP BY CATEGORY, DOW, HOD
)
SELECT CATEGORY, DOW, HOD,
       AVG_UNITS / NULLIF(AVG(AVG_UNITS) OVER (PARTITION BY CATEGORY), 0) AS SHAPE
FROM c;

-- Store x SKU demand rate over the last 14 days, in units per unit of shape.
-- Censored hours are excluded, so stock-outs don't drag the forecast down (the classic trap).
CREATE OR REPLACE VIEW V_RATE AS
SELECT h.STORE_ID, h.SKU_ID,
       SUM(h.UNITS_SOLD) / NULLIF(SUM(sh.SHAPE), 0) AS DEMAND_RATE
FROM V_HOURLY h
JOIN V_SHAPE sh ON sh.CATEGORY = h.CATEGORY AND sh.DOW = h.DOW AND sh.HOD = h.HOD
CROSS JOIN APP_STATE a
WHERE h.CENSORED = 0
  AND h.TS > ADD_DAYS(a.AS_OF, -14)
GROUP BY h.STORE_ID, h.SKU_ID;

-- Shelf stock right now.
CREATE OR REPLACE VIEW V_POSITION AS
SELECT s.STORE_ID, s.SKU_ID, s.STOCK_END AS STOCK
FROM SALES_HOURLY s
JOIN APP_STATE a ON s.TS = a.AS_OF;

-- Expected demand for each of the next 48 hours.
CREATE OR REPLACE VIEW V_FORECAST AS
WITH hz AS (
    SELECT z.H, ADD_HOURS(a.AS_OF, z.H) AS TS
    FROM HORIZON z CROSS JOIN APP_STATE a
)
SELECT p.STORE_ID, p.SKU_ID, hz.H, hz.TS,
       r.DEMAND_RATE * sh.SHAPE AS EXP_UNITS
FROM V_POSITION p
CROSS JOIN hz
JOIN SKUS k   ON k.SKU_ID = p.SKU_ID
JOIN V_RATE r ON r.STORE_ID = p.STORE_ID AND r.SKU_ID = p.SKU_ID
JOIN V_SHAPE sh ON sh.CATEGORY = k.CATEGORY
               AND sh.HOD = HOUR(hz.TS)
               AND sh.DOW = MOD(DAYS_BETWEEN(CAST(hz.TS AS DATE), DATE '2024-01-01'), 7);

-- Will this shelf empty before the next truck (06:00 daily)?
-- TRUCK_H = hours until the delivery hour; demand in hours 1..TRUCK_H-1 must come from current stock.
-- Stock-out probability: P(Poisson(mu) > stock), normal approximation with a logistic CDF
-- (Phi(z) ~ 1/(1+exp(-1.702z)), max error ~0.01).
CREATE OR REPLACE VIEW V_RISK AS
WITH t AS (
    SELECT MOD(6 - HOUR(AS_OF) + 23, 24) + 1 AS TRUCK_H FROM APP_STATE
), f AS (
    SELECT f.STORE_ID, f.SKU_ID, f.H, f.EXP_UNITS,
           SUM(f.EXP_UNITS) OVER (PARTITION BY f.STORE_ID, f.SKU_ID ORDER BY f.H) AS CUM_EXP
    FROM V_FORECAST f
), agg AS (
    SELECT p.STORE_ID, p.SKU_ID, p.STOCK, t.TRUCK_H,
           MIN(CASE WHEN f.CUM_EXP >= p.STOCK THEN f.H END) AS OOS_H,
           SUM(CASE WHEN f.H < t.TRUCK_H THEN f.EXP_UNITS ELSE 0 END) AS MU
    FROM V_POSITION p
    JOIN f ON f.STORE_ID = p.STORE_ID AND f.SKU_ID = p.SKU_ID
    CROSS JOIN t
    GROUP BY p.STORE_ID, p.SKU_ID, p.STOCK, t.TRUCK_H
)
SELECT a.STORE_ID, st.CITY, st.AREA, a.SKU_ID, k.SKU_NAME, k.CATEGORY, k.CASE_PACK, k.UNIT_PRICE,
       a.STOCK, a.TRUCK_H,
       CASE WHEN a.STOCK = 0 THEN 0 ELSE a.OOS_H END AS HOURS_TO_OOS,
       a.MU AS DEMAND_TO_TRUCK,
       CASE WHEN a.STOCK = 0 THEN 1
            WHEN a.MU = 0 THEN 0
            ELSE 1 - 1 / (1 + EXP(-1.702 * (a.STOCK + 0.5 - a.MU) / SQRT(a.MU))) END AS RISK_PROB,
       GREATEST(a.MU - a.STOCK, 0) AS EXP_LOST_UNITS,
       GREATEST(a.MU - a.STOCK, 0) * k.UNIT_PRICE AS REVENUE_AT_RISK,
       -- top-up to cover demand until the truck at ~95% service (mu + 1.65 sigma)
       GREATEST(CEIL(a.MU + 1.65 * SQRT(a.MU) - a.STOCK), 0) AS NEED_UNITS,
       -- what this store can give away and still cover itself until the truck
       GREATEST(FLOOR(a.STOCK - a.MU - 1.65 * SQRT(a.MU)), 0) AS SURPLUS_UNITS
FROM agg a
JOIN SKUS k    ON k.SKU_ID = a.SKU_ID
JOIN STORES st ON st.STORE_ID = a.STORE_ID;

-- The action list: every at-risk shelf, with the best same-city store to borrow from,
-- falling back to an expedited case-pack order.
CREATE OR REPLACE VIEW V_ACTIONS AS
WITH r AS (
    SELECT r.*,
           CASE WHEN r.STOCK = 0 THEN 'OUT'
                WHEN r.RISK_PROB >= 0.7 THEN 'CRITICAL'
                WHEN r.RISK_PROB >= 0.4 THEN 'AT RISK'
                ELSE 'OK' END AS RISK_STATUS
    FROM V_RISK r
), donors AS (
    SELECT n.STORE_ID, n.SKU_ID, d.STORE_ID AS DONOR_STORE, d.AREA AS DONOR_AREA, d.SURPLUS_UNITS,
           ROW_NUMBER() OVER (PARTITION BY n.STORE_ID, n.SKU_ID ORDER BY d.SURPLUS_UNITS DESC) AS RN
    FROM r n
    JOIN V_RISK d ON d.SKU_ID = n.SKU_ID AND d.CITY = n.CITY AND d.STORE_ID <> n.STORE_ID
    WHERE n.RISK_STATUS <> 'OK' AND n.NEED_UNITS > 0 AND d.SURPLUS_UNITS >= n.NEED_UNITS
)
SELECT r.*,
       d.DONOR_STORE, d.DONOR_AREA,
       CASE WHEN r.RISK_STATUS = 'OK' THEN NULL
            WHEN d.DONOR_STORE IS NOT NULL
                 THEN 'Transfer ' || CAST(r.NEED_UNITS AS VARCHAR(9)) || ' from ' || d.DONOR_STORE
                      || ' (' || d.DONOR_AREA || ')'
            WHEN r.NEED_UNITS > 0
                 THEN 'Expedite ' || CAST(CEIL(r.NEED_UNITS / r.CASE_PACK) * r.CASE_PACK AS VARCHAR(9))
                      || ' units (' || CAST(CEIL(r.NEED_UNITS / r.CASE_PACK) AS VARCHAR(9)) || ' case)'
            ELSE 'Watch' END AS RECOMMENDATION
FROM r
LEFT JOIN donors d ON d.STORE_ID = r.STORE_ID AND d.SKU_ID = r.SKU_ID AND d.RN = 1;

-- Backtest: what actually happened after AS_OF (the data continues past it when replaying history).
-- A shelf "actually went out" if it hit zero in any hour before the truck.
CREATE OR REPLACE VIEW V_BACKTEST AS
SELECT r.STORE_ID, r.SKU_ID, r.RISK_STATUS, r.RISK_PROB,
       MAX(CASE WHEN s.STOCK_END = 0 THEN 1 ELSE 0 END) AS ACTUAL_OOS
FROM V_ACTIONS r
CROSS JOIN APP_STATE a
JOIN SALES_HOURLY s ON s.STORE_ID = r.STORE_ID AND s.SKU_ID = r.SKU_ID
                   AND s.TS > a.AS_OF AND s.TS < ADD_HOURS(a.AS_OF, r.TRUCK_H)
WHERE r.STOCK > 0
GROUP BY r.STORE_ID, r.SKU_ID, r.RISK_STATUS, r.RISK_PROB;

-- Lost sales already suffered: every censored hour, valued at the demand we expected for it.
CREATE OR REPLACE VIEW V_LOST_SALES AS
SELECT h.TS, h.STORE_ID, h.SKU_ID, h.CATEGORY, h.UNITS_SOLD,
       r.DEMAND_RATE * sh.SHAPE AS EXP_UNITS,
       GREATEST(r.DEMAND_RATE * sh.SHAPE - h.UNITS_SOLD, 0) AS LOST_UNITS,
       GREATEST(r.DEMAND_RATE * sh.SHAPE - h.UNITS_SOLD, 0) * k.UNIT_PRICE AS LOST_REVENUE
FROM V_HOURLY h
JOIN V_RATE r   ON r.STORE_ID = h.STORE_ID AND r.SKU_ID = h.SKU_ID
JOIN V_SHAPE sh ON sh.CATEGORY = h.CATEGORY AND sh.DOW = h.DOW AND sh.HOD = h.HOD
JOIN SKUS k     ON k.SKU_ID = h.SKU_ID
WHERE h.CENSORED = 1;
