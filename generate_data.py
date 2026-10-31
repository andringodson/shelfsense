"""Synthetic quick-commerce data: dark stores, SKUs, hourly sales, stock and deliveries.

All data is synthetic (seeded numpy). True demand is simulated, but only *sales*
(demand capped by stock) are exported - exactly the blind spot real retailers have.
True demand is written separately to data/truth_demand.csv so the lost-sales
estimate can be validated.

    python generate_data.py [--stores 25] [--skus 80] [--days 42] [--out data]
"""
import argparse
import csv
import os
from datetime import datetime, timedelta

import numpy as np

START = datetime(2026, 9, 14)  # a Monday
CITIES = [("Bengaluru", ["Koramangala", "Indiranagar", "HSR Layout", "Whitefield", "Jayanagar"]),
          ("Chennai", ["Adyar", "T Nagar", "Velachery", "Anna Nagar", "OMR"]),
          ("Mumbai", ["Andheri", "Bandra", "Powai", "Thane", "Chembur"]),
          ("Delhi NCR", ["Saket", "Dwarka", "Gurugram 29", "Noida 18", "Rohini"]),
          ("Hyderabad", ["Gachibowli", "Madhapur", "Kondapur", "Banjara Hills", "Kukatpally"])]
CATEGORIES = {  # category: (products, price range INR, shelf life days, case pack)
    "Dairy": (["Toned Milk 500ml", "Curd 400g", "Paneer 200g", "Butter 100g", "Cheese Slices", "Buttermilk 200ml"], (25, 110), 3, 12),
    "Bakery": (["White Bread", "Brown Bread", "Pav 6pc", "Rusk 300g", "Burger Buns"], (30, 70), 4, 10),
    "Fruits & Veg": (["Banana 1 dozen", "Onion 1kg", "Tomato 1kg", "Potato 1kg", "Coriander", "Apple 4pc", "Green Chilli 100g", "Lemon 4pc"], (15, 160), 5, 10),
    "Snacks": (["Potato Chips", "Namkeen 200g", "Biscuits Cream", "Cookies", "Instant Noodles", "Popcorn"], (10, 60), 120, 24),
    "Beverages": (["Cola 750ml", "Mango Drink 1L", "Soda 600ml", "Cold Coffee", "Energy Drink", "Coconut Water"], (20, 125), 180, 24),
    "Staples": (["Atta 5kg", "Basmati Rice 1kg", "Toor Dal 1kg", "Sugar 1kg", "Salt 1kg", "Sunflower Oil 1L"], (25, 280), 365, 6),
    "Personal Care": (["Toothpaste", "Bath Soap", "Shampoo Sachet", "Handwash", "Sanitary Pads"], (20, 150), 730, 12),
    "Household": (["Dishwash Bar", "Detergent 1kg", "Garbage Bags", "Floor Cleaner", "Tissue Roll"], (30, 240), 730, 12),
    "Baby Care": (["Diapers M", "Baby Wipes", "Baby Food"], (150, 450), 365, 6),
    "Ice Cream": (["Vanilla Tub", "Choco Bar", "Kulfi"], (20, 250), 180, 12),
}
# Quick-commerce hour-of-day shape: breakfast and late-evening peaks, dead 2-5am.
HOD = np.array([.25, .15, .08, .05, .05, .10, .45, .95, 1.4, 1.3, 1.0, .95,
                1.05, 1.0, .85, .80, .90, 1.15, 1.45, 1.70, 1.75, 1.45, 1.00, .55])
DOW = np.array([.92, .90, .93, .97, 1.05, 1.18, 1.15])  # Mon..Sun


def build_catalog(rng, n_skus):
    skus = []
    for cat, (names, (lo, hi), life, pack) in CATEGORIES.items():
        for name in names:
            skus.append((cat, name, life, pack, round(float(rng.uniform(lo, hi)), 2)))
    rng.shuffle(skus)
    skus = skus[:n_skus]
    return [(f"SKU{i + 1:03d}", *s) for i, s in enumerate(skus)]


def simulate(n_stores=25, n_skus=80, days=42, seed=7):
    rng = np.random.default_rng(seed)
    stores = [(f"DS{i + 1:02d}", city, area) for i, (city, area) in
              enumerate((c, a) for c, areas in CITIES for a in areas)][:n_stores]
    skus = build_catalog(rng, n_skus)
    S, K, H = len(stores), len(skus), days * 24

    # Demand rate (units/hour at shape=1) per store x sku: popularity x store size.
    popularity = rng.lognormal(mean=-0.6, sigma=0.8, size=K)
    store_size = rng.uniform(0.6, 1.6, size=S)
    base = np.outer(store_size, popularity)
    trend = 1 + rng.normal(0.0, 0.004, size=(S, K))  # slow per-day drift (some items heating up)

    # Replenishment policy: one delivery per day at 06:00, order-up-to a par level the planner set
    # from a stale average. Some store x sku pairs are badly under-provisioned -> chronic stock-outs.
    daily_mean = base * HOD.sum()
    par = daily_mean * rng.uniform(0.85, 1.8, size=(S, K))
    on_hand = np.ceil(par).astype(np.int64)
    packs = np.array([s[4] for s in skus])

    sales = np.zeros((H, S, K), dtype=np.int32)
    demand = np.zeros((H, S, K), dtype=np.int32)
    stock_end = np.zeros((H, S, K), dtype=np.int32)
    receipts = []
    supplier_fail = rng.random(size=(days, K)) < 0.04  # supplier misses a day for a SKU (all stores)
    promo_days = rng.random(size=(days, S, K)) < 0.015  # local promo / viral spike

    for h in range(H):
        d, hod = divmod(h, 24)
        if hod == 6:
            gap = np.maximum(par - on_hand, 0)
            qty = (np.ceil(gap / packs) * packs).astype(np.int64)
            qty[:, supplier_fail[d]] = 0
            qty[rng.random(size=(S, K)) < 0.01] = 0  # truck missed the store
            on_hand += qty
            for s, k in zip(*np.nonzero(qty)):
                receipts.append((h, s, k, int(qty[s, k])))
        lam = base * HOD[hod] * DOW[(START.weekday() + d) % 7] * trend ** d
        lam = np.where(promo_days[d], lam * 3.0, lam)
        dem = rng.poisson(lam)
        sold = np.minimum(dem, on_hand)
        on_hand -= sold
        demand[h], sales[h], stock_end[h] = dem, sold, on_hand
    return stores, skus, sales, demand, stock_end, receipts


def write(out, stores, skus, sales, demand, stock_end, receipts):
    os.makedirs(out, exist_ok=True)
    ts = [(START + timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S") for h in range(sales.shape[0])]
    with open(os.path.join(out, "stores.csv"), "w", newline="") as f:
        csv.writer(f).writerows(stores)
    with open(os.path.join(out, "skus.csv"), "w", newline="") as f:
        csv.writer(f).writerows((sid, name, cat, life, pack, price) for sid, cat, name, life, pack, price in skus)
    with open(os.path.join(out, "receipts.csv"), "w", newline="") as f:
        csv.writer(f).writerows((ts[h], stores[s][0], skus[k][0], q) for h, s, k, q in receipts)
    # One row per store x sku x hour: units sold and stock on hand at the end of the hour.
    with open(os.path.join(out, "sales_hourly.csv"), "w", newline="") as f, \
            open(os.path.join(out, "truth_demand.csv"), "w", newline="") as t:
        w, wt = csv.writer(f), csv.writer(t)
        for h in range(sales.shape[0]):
            for s in range(sales.shape[1]):
                sid = stores[s][0]
                w.writerows((ts[h], sid, skus[k][0], int(sales[h, s, k]), int(stock_end[h, s, k]))
                            for k in range(sales.shape[2]))
                wt.writerows((ts[h], sid, skus[k][0], int(demand[h, s, k]))
                             for k in range(sales.shape[2]) if demand[h, s, k] != sales[h, s, k])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--stores", type=int, default=25)
    p.add_argument("--skus", type=int, default=80)
    p.add_argument("--days", type=int, default=42)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default="data")
    a = p.parse_args()
    result = simulate(a.stores, a.skus, a.days, a.seed)
    write(a.out, *result)
    sales, demand = result[2], result[3]
    print(f"rows={sales.size:,} units_sold={int(sales.sum()):,} "
          f"lost_units={int((demand - sales).sum()):,} receipts={len(result[5]):,} -> {a.out}/")
