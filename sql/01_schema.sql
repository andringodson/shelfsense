CREATE SCHEMA IF NOT EXISTS SHELFSENSE;
OPEN SCHEMA SHELFSENSE;

CREATE OR REPLACE TABLE STORES (
    STORE_ID VARCHAR(8) PRIMARY KEY,
    CITY     VARCHAR(40),
    AREA     VARCHAR(40)
);

CREATE OR REPLACE TABLE SKUS (
    SKU_ID          VARCHAR(8) PRIMARY KEY,
    SKU_NAME        VARCHAR(60),
    CATEGORY        VARCHAR(30),
    SHELF_LIFE_DAYS DECIMAL(5),
    CASE_PACK       DECIMAL(5),
    UNIT_PRICE      DECIMAL(10,2)
);

-- One row per store x SKU x hour: what was sold and what was left on the shelf at the end of the hour.
-- Demand is never recorded - only sales, which are capped by stock. That is the blind spot.
CREATE OR REPLACE TABLE SALES_HOURLY (
    TS         TIMESTAMP,
    STORE_ID   VARCHAR(8),
    SKU_ID     VARCHAR(8),
    UNITS_SOLD DECIMAL(9),
    STOCK_END  DECIMAL(9)
);

CREATE OR REPLACE TABLE RECEIPTS (
    TS       TIMESTAMP,
    STORE_ID VARCHAR(8),
    SKU_ID   VARCHAR(8),
    QTY      DECIMAL(9)
);

-- Simulation ground truth: the demand behind every censored hour. Used ONLY to validate estimates.
CREATE OR REPLACE TABLE TRUTH_DEMAND (
    TS       TIMESTAMP,
    STORE_ID VARCHAR(8),
    SKU_ID   VARCHAR(8),
    DEMAND   DECIMAL(9)
);

-- Forecast horizon, hours 1..48 ahead.
CREATE OR REPLACE TABLE HORIZON (H DECIMAL(3));

-- The "now" every view is evaluated at. Move it to replay any moment in history.
CREATE OR REPLACE TABLE APP_STATE (AS_OF TIMESTAMP);
