import os
import logging
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from dataclasses import asdict

from models.arima_model import ARIMAForecaster
from models.lstm_model import LSTMForecaster
from optimization.inventory_optimizer import InventoryOptimizer
from simulation.simulation_engine import SimulationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Demand Forecasting & Inventory Optimization API",
    version="1.0.0",
    description="SKU-level demand prediction with inventory optimization and simulation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

sales_df = None
product_df = None
inventory_df = None
external_df = None
arima_forecaster = None
lstm_forecaster = None
optimizer = None
sim_engine = None


def load_data():
    global sales_df, product_df, inventory_df, external_df
    logger.info("Loading datasets...")
    sales_df = pd.read_csv(os.path.join(DATA_DIR, "sales_data.csv"))
    product_df = pd.read_csv(os.path.join(DATA_DIR, "product_info.csv"))
    inventory_df = pd.read_csv(os.path.join(DATA_DIR, "inventory_data.csv"))
    external_df = pd.read_csv(os.path.join(DATA_DIR, "external_features.csv"))
    logger.info(f"Loaded {len(sales_df):,} sales records, {len(product_df)} SKUs")


def init_models():
    global arima_forecaster, lstm_forecaster, optimizer, sim_engine
    arima_forecaster = ARIMAForecaster(order=(2, 1, 2))
    lstm_forecaster = LSTMForecaster(lookback=24, forecast_horizon=12, epochs=30)
    optimizer = InventoryOptimizer(service_level=0.95, ordering_cost=20.0)
    sim_engine = SimulationEngine(num_days=365, num_simulations=50)


@app.on_event("startup")
async def startup():
    if not os.path.exists(os.path.join(DATA_DIR, "sales_data.csv")):
        logger.info("No data found, generating dataset...")
        from data_generation.generate_dataset import main as gen_main
        gen_main()
    load_data()
    init_models()


class ForecastRequest(BaseModel):
    sku_id: str
    model_type: str = Field(default="arima", description="arima or lstm")
    steps: int = Field(default=12, ge=1, le=52)


class OptimizeRequest(BaseModel):
    sku_id: str
    service_level: float = Field(default=0.95, ge=0.5, le=0.999)
    ordering_cost: float = Field(default=20.0, ge=0)


class SimulateRequest(BaseModel):
    sku_id: str
    promo_intensity: float = Field(default=0.0, ge=0, le=2.0)
    lead_time_override: Optional[int] = Field(default=None, ge=1, le=60)
    demand_variability: float = Field(default=1.0, ge=0.1, le=3.0)
    service_level: float = Field(default=0.95, ge=0.5, le=0.999)


class ScenarioCompareRequest(BaseModel):
    sku_id: str
    scenarios: List[Dict]


@app.get("/health")
async def health():
    return {"status": "healthy", "skus": len(product_df) if product_df is not None else 0}


@app.get("/skus")
async def list_skus():
    if product_df is None:
        raise HTTPException(500, "Data not loaded")
    skus = product_df.to_dict("records")
    return {"skus": skus}


@app.get("/dashboard/{sku_id}")
async def dashboard(sku_id: str):
    if sales_df is None:
        raise HTTPException(500, "Data not loaded")
    if sku_id not in sales_df["sku_id"].values:
        raise HTTPException(404, f"SKU {sku_id} not found")

    sku_sales = sales_df[sales_df["sku_id"] == sku_id].copy()
    daily = sku_sales.groupby("date").agg({"units_sold": "sum", "price": "mean"}).reset_index()
    daily["units_sold"] = daily["units_sold"].fillna(0)

    sku_inv = inventory_df[inventory_df["sku_id"] == sku_id].copy()
    latest_inv = sku_inv.iloc[-1] if len(sku_inv) > 0 else None

    product = product_df[product_df["sku_id"] == sku_id].iloc[0]

    avg_demand = daily["units_sold"].mean()
    std_demand = daily["units_sold"].std()

    recent_30 = daily.tail(30)
    recent_demand = recent_30["units_sold"].mean()

    monthly = sku_sales.copy()
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
    monthly_agg = monthly.groupby("month")["units_sold"].sum().reset_index()

    weekly = sku_sales.copy()
    weekly["date"] = pd.to_datetime(weekly["date"])
    weekly_agg = weekly.set_index("date").resample("W")["units_sold"].sum().reset_index()
    weekly_agg["date"] = weekly_agg["date"].dt.strftime("%Y-%m-%d")

    return {
        "sku_id": sku_id,
        "category": product["category"],
        "kpis": {
            "avg_daily_demand": round(avg_demand, 1),
            "demand_std": round(std_demand, 1),
            "recent_30d_demand": round(recent_demand, 1),
            "current_stock": int(latest_inv["stock_level"]) if latest_inv is not None else 0,
            "reorder_point": int(latest_inv["reorder_point"]) if latest_inv is not None else 0,
            "lead_time": int(product["lead_time_days"]),
        },
        "weekly_demand": weekly_agg.tail(52).to_dict("records"),
        "monthly_demand": monthly_agg.to_dict("records"),
    }


@app.post("/forecast")
async def forecast(req: ForecastRequest):
    if sales_df is None:
        raise HTTPException(500, "Data not loaded")
    if req.sku_id not in sales_df["sku_id"].values:
        raise HTTPException(404, f"SKU {req.sku_id} not found")

    if req.model_type == "arima":
        arima_forecaster.fit(sales_df, req.sku_id)
        preds = arima_forecaster.predict(req.sku_id, steps=req.steps)
        eval_result = arima_forecaster.evaluate(sales_df, req.sku_id, test_weeks=req.steps)
    elif req.model_type == "lstm":
        lstm_forecaster.fit(sales_df, req.sku_id, external_df)
        preds = lstm_forecaster.predict(sales_df, req.sku_id, external_df)
        eval_result = lstm_forecaster.evaluate(sales_df, req.sku_id, external_df)
    else:
        raise HTTPException(400, "model_type must be 'arima' or 'lstm'")

    sku_sales = sales_df[sales_df["sku_id"] == req.sku_id]
    daily = sku_sales.groupby("date")["units_sold"].sum().reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    weekly = daily.set_index("date").resample("W")["units_sold"].sum()

    last_date = weekly.index[-1]
    future_dates = pd.date_range(last_date + pd.Timedelta(weeks=1), periods=len(preds), freq="W")

    historical = weekly.tail(52)

    return {
        "sku_id": req.sku_id,
        "model": req.model_type,
        "forecast": [{"date": d.strftime("%Y-%m-%d"), "demand": round(float(v), 1)} for d, v in zip(future_dates, preds)],
        "historical": [{"date": d.strftime("%Y-%m-%d"), "demand": float(v)} for d, v in zip(historical.index, historical.values)],
        "evaluation": eval_result,
    }


@app.post("/forecast/compare")
async def forecast_compare(req: ForecastRequest):
    if sales_df is None:
        raise HTTPException(500, "Data not loaded")
    if req.sku_id not in sales_df["sku_id"].values:
        raise HTTPException(404, f"SKU {req.sku_id} not found")

    arima_forecaster.fit(sales_df, req.sku_id)
    arima_eval = arima_forecaster.evaluate(sales_df, req.sku_id, test_weeks=req.steps)

    lstm_eval = lstm_forecaster.evaluate(sales_df, req.sku_id, external_df)

    return {
        "sku_id": req.sku_id,
        "arima": arima_eval,
        "lstm": lstm_eval,
    }


@app.post("/optimize")
async def optimize(req: OptimizeRequest):
    if sales_df is None or product_df is None:
        raise HTTPException(500, "Data not loaded")
    if req.sku_id not in product_df["sku_id"].values:
        raise HTTPException(404, f"SKU {req.sku_id} not found")

    opt = InventoryOptimizer(service_level=req.service_level, ordering_cost=req.ordering_cost)
    policy = opt.optimize(sales_df, product_df, req.sku_id)
    sensitivity = opt.sensitivity_analysis(sales_df, product_df, req.sku_id)

    return {
        "policy": asdict(policy),
        "sensitivity": sensitivity,
    }


@app.get("/optimize/all")
async def optimize_all():
    if sales_df is None or product_df is None:
        raise HTTPException(500, "Data not loaded")

    policies = optimizer.optimize_all(sales_df, product_df)
    return {"policies": {k: asdict(v) for k, v in policies.items()}}


@app.post("/simulate")
async def simulate(req: SimulateRequest):
    if sales_df is None or product_df is None:
        raise HTTPException(500, "Data not loaded")
    if req.sku_id not in product_df["sku_id"].values:
        raise HTTPException(404, f"SKU {req.sku_id} not found")

    opt = InventoryOptimizer(service_level=req.service_level)
    policy = opt.optimize(sales_df, product_df, req.sku_id)

    lead_time = req.lead_time_override or policy.lead_time_days

    result = sim_engine.run_monte_carlo(
        avg_demand=policy.avg_daily_demand,
        std_demand=policy.demand_std,
        lead_time=lead_time,
        reorder_point=policy.reorder_point,
        order_quantity=policy.economic_order_quantity,
        safety_stock=policy.safety_stock,
        holding_cost_per_unit=policy.holding_cost,
        stockout_cost_per_unit=policy.stockout_cost,
        ordering_cost=policy.ordering_cost,
        promo_intensity=req.promo_intensity,
        demand_variability=req.demand_variability,
        scenario_name="Custom Scenario",
    )

    result_dict = asdict(result)
    result_dict["daily_results"] = result_dict["daily_results"][:90] if result_dict["daily_results"] else []
    result_dict["inventory_policy"] = asdict(policy)

    return result_dict


@app.post("/simulate/compare")
async def simulate_compare(req: ScenarioCompareRequest):
    if sales_df is None or product_df is None:
        raise HTTPException(500, "Data not loaded")

    opt = InventoryOptimizer(service_level=0.95)
    policy = opt.optimize(sales_df, product_df, req.sku_id)

    base_params = {
        "avg_demand": policy.avg_daily_demand,
        "std_demand": policy.demand_std,
        "lead_time": policy.lead_time_days,
        "reorder_point": policy.reorder_point,
        "order_quantity": policy.economic_order_quantity,
        "safety_stock": policy.safety_stock,
        "holding_cost_per_unit": policy.holding_cost,
        "stockout_cost_per_unit": policy.stockout_cost,
        "ordering_cost": policy.ordering_cost,
    }

    results = sim_engine.compare_scenarios(base_params, req.scenarios)
    for r in results:
        r["daily_results"] = None

    return {"sku_id": req.sku_id, "scenarios": results}


@app.get("/feature-importance/{sku_id}")
async def feature_importance(sku_id: str):
    if sales_df is None:
        raise HTTPException(500, "Data not loaded")

    sku_sales = sales_df[sales_df["sku_id"] == sku_id].copy()
    if len(sku_sales) == 0:
        raise HTTPException(404, f"SKU {sku_id} not found")

    daily = sku_sales.groupby("date").agg({
        "units_sold": "sum",
        "price": "mean",
        "promotion_flag": "max",
    }).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date")
    daily["units_sold"] = daily["units_sold"].fillna(0)

    daily["day_of_week"] = daily["date"].dt.dayofweek
    daily["month"] = daily["date"].dt.month
    daily["lag_7"] = daily["units_sold"].shift(7)
    daily["rolling_mean_7"] = daily["units_sold"].rolling(7).mean()
    daily = daily.dropna()

    ext = external_df.copy()
    ext["date"] = pd.to_datetime(ext["date"])
    daily = daily.merge(ext, on="date", how="left").fillna(0)

    features = ["price", "promotion_flag", "day_of_week", "month",
                 "lag_7", "rolling_mean_7", "holiday_flag",
                 "seasonality_index", "economic_index"]

    X = daily[features].values
    y = daily["units_sold"].values

    from sklearn.ensemble import GradientBoostingRegressor
    model = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
    model.fit(X, y)

    importances = dict(zip(features, [round(float(v), 4) for v in model.feature_importances_]))
    importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

    return {"sku_id": sku_id, "feature_importance": importances}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
