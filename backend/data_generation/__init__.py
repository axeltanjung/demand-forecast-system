import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import os

np.random.seed(42)

START_DATE = datetime(2021, 1, 1)
END_DATE = datetime(2023, 12, 31)
dates = pd.date_range(START_DATE, END_DATE, freq="D")
NUM_DAYS = len(dates)

SKUS = [f"SKU_{str(i).zfill(3)}" for i in range(1, 21)]
STORES = [f"STORE_{str(i).zfill(2)}" for i in range(1, 6)]
CATEGORIES = ["Electronics", "Apparel", "Grocery", "Home & Garden", "Sports"]

SKU_CONFIG = {}
for i, sku in enumerate(SKUS):
    cat_idx = i % len(CATEGORIES)
    SKU_CONFIG[sku] = {
        "category": CATEGORIES[cat_idx],
        "base_demand": np.random.uniform(20, 120),
        "price": round(np.random.uniform(5, 200), 2),
        "yearly_amp": np.random.uniform(0.1, 0.4),
        "yearly_phase": np.random.uniform(0, 2 * np.pi),
        "weekly_amp": np.random.uniform(0.05, 0.2),
        "trend": np.random.uniform(-0.005, 0.01),
        "noise_std": np.random.uniform(0.05, 0.2),
        "promo_lift": np.random.uniform(1.3, 2.5),
        "lead_time_days": int(np.random.choice([3, 5, 7, 10, 14])),
        "holding_cost": round(np.random.uniform(0.5, 5.0), 2),
        "stockout_cost": round(np.random.uniform(5.0, 50.0), 2),
    }


def generate_external_features(dates):
    records = []
    for d in dates:
        doy = d.timetuple().tm_yday
        seasonality_index = 0.5 + 0.5 * np.sin(2 * np.pi * doy / 365)
        holiday = 1 if d.month == 12 and d.day >= 20 else 0
        holiday = holiday or (d.month == 11 and 22 <= d.day <= 28)
        holiday = holiday or (d.month == 7 and d.day == 4)
        holiday = holiday or (d.month == 1 and d.day == 1)
        economic_index = 100 + 10 * np.sin(2 * np.pi * doy / 365 * 0.5) + np.random.normal(0, 2)
        records.append({
            "date": d.strftime("%Y-%m-%d"),
            "holiday_flag": int(holiday),
            "seasonality_index": round(seasonality_index, 4),
            "economic_index": round(economic_index, 2),
        })
    return pd.DataFrame(records)


def generate_promotion_calendar(dates, skus):
    promos = {}
    for sku in skus:
        sku_promos = np.zeros(len(dates), dtype=int)
        num_promos = np.random.randint(6, 15)
        for _ in range(num_promos):
            start = np.random.randint(0, len(dates) - 14)
            duration = np.random.randint(3, 10)
            sku_promos[start : start + duration] = 1
        for d_idx, d in enumerate(dates):
            if d.month == 11 and 24 <= d.day <= 30:
                sku_promos[d_idx] = 1
            if d.month == 12 and 15 <= d.day <= 25:
                sku_promos[d_idx] = 1
        promos[sku] = sku_promos
    return promos


def generate_sales_data(dates, skus, stores, ext_features, promo_calendar):
    records = []
    ext_df = ext_features.set_index("date")

    for sku in skus:
        cfg = SKU_CONFIG[sku]
        for store in stores:
            store_scale = np.random.uniform(0.7, 1.3)
            for i, d in enumerate(dates):
                doy = d.timetuple().tm_yday
                dow = d.weekday()
                t = i / NUM_DAYS

                base = cfg["base_demand"] * store_scale
                trend = base * cfg["trend"] * i
                yearly = base * cfg["yearly_amp"] * np.sin(2 * np.pi * doy / 365 + cfg["yearly_phase"])
                weekly = base * cfg["weekly_amp"] * np.sin(2 * np.pi * dow / 7)
                noise = np.random.normal(0, base * cfg["noise_std"])

                demand = base + trend + yearly + weekly + noise

                date_str = d.strftime("%Y-%m-%d")
                holiday = ext_df.loc[date_str, "holiday_flag"]
                if holiday:
                    demand *= np.random.uniform(1.3, 1.8)

                promo = promo_calendar[sku][i]
                if promo:
                    demand *= cfg["promo_lift"]

                demand = max(0, int(round(demand)))

                if np.random.random() < 0.02:
                    demand = np.nan

                price = cfg["price"]
                if promo:
                    price = round(price * np.random.uniform(0.7, 0.9), 2)

                records.append({
                    "date": date_str,
                    "sku_id": sku,
                    "store_id": store,
                    "units_sold": demand,
                    "price": price,
                    "promotion_flag": promo,
                })

    return pd.DataFrame(records)


def generate_product_info(skus):
    records = []
    for sku in skus:
        cfg = SKU_CONFIG[sku]
        records.append({
            "sku_id": sku,
            "category": cfg["category"],
            "lead_time_days": cfg["lead_time_days"],
            "holding_cost": cfg["holding_cost"],
            "stockout_cost": cfg["stockout_cost"],
        })
    return pd.DataFrame(records)


def generate_inventory_data(dates, skus, sales_agg):
    records = []
    for sku in skus:
        cfg = SKU_CONFIG[sku]
        sku_sales = sales_agg[sales_agg["sku_id"] == sku].set_index("date")
        stock = int(cfg["base_demand"] * 30)
        rop = int(cfg["base_demand"] * cfg["lead_time_days"] * 1.5)
        eoq = int(np.sqrt(2 * cfg["base_demand"] * 365 * 20 / cfg["holding_cost"]))
        pending_order = 0
        order_arrival = None

        for d in dates:
            date_str = d.strftime("%Y-%m-%d")
            daily_demand = 0
            if date_str in sku_sales.index:
                daily_demand = int(sku_sales.loc[date_str, "units_sold"])

            if order_arrival and d >= order_arrival:
                stock += pending_order
                pending_order = 0
                order_arrival = None

            stock = max(0, stock - daily_demand)

            if stock <= rop and pending_order == 0:
                pending_order = eoq
                order_arrival = d + timedelta(days=cfg["lead_time_days"])

            records.append({
                "date": date_str,
                "sku_id": sku,
                "stock_level": stock,
                "reorder_point": rop,
                "order_quantity": eoq,
            })

    return pd.DataFrame(records)


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(output_dir, exist_ok=True)

    print("Generating external features...")
    ext_features = generate_external_features(dates)
    ext_features.to_csv(os.path.join(output_dir, "external_features.csv"), index=False)

    print("Generating promotion calendar...")
    promo_cal = generate_promotion_calendar(dates, SKUS)

    print("Generating sales data...")
    sales = generate_sales_data(dates, SKUS, STORES, ext_features, promo_cal)
    sales.to_csv(os.path.join(output_dir, "sales_data.csv"), index=False)

    print("Generating product info...")
    products = generate_product_info(SKUS)
    products.to_csv(os.path.join(output_dir, "product_info.csv"), index=False)

    print("Generating inventory data...")
    sales_agg = sales.groupby(["date", "sku_id"])["units_sold"].sum().reset_index()
    inventory = generate_inventory_data(dates, SKUS, sales_agg)
    inventory.to_csv(os.path.join(output_dir, "inventory_data.csv"), index=False)

    print(f"Sales records: {len(sales):,}")
    print(f"Inventory records: {len(inventory):,}")
    print(f"Missing values in sales: {sales['units_sold'].isna().sum():,}")
    print(f"Data saved to {output_dir}")

    config_out = {}
    for sku, cfg in SKU_CONFIG.items():
        config_out[sku] = {k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer,)) else v) for k, v in cfg.items()}
    with open(os.path.join(output_dir, "sku_config.json"), "w") as f:
        json.dump(config_out, f, indent=2)


if __name__ == "__main__":
    main()
