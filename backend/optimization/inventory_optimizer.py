import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class InventoryPolicy:
    sku_id: str
    safety_stock: float
    reorder_point: float
    economic_order_quantity: float
    avg_daily_demand: float
    demand_std: float
    lead_time_days: int
    holding_cost: float
    stockout_cost: float
    ordering_cost: float
    service_level: float
    annual_holding_cost: float
    annual_ordering_cost: float
    total_annual_cost: float


class InventoryOptimizer:
    def __init__(self, service_level=0.95, ordering_cost=20.0):
        self.service_level = service_level
        self.ordering_cost = ordering_cost
        self.z_score = self._get_z_score(service_level)

    @staticmethod
    def _get_z_score(service_level):
        from scipy.stats import norm
        return norm.ppf(service_level)

    def compute_demand_stats(self, sales_df, sku_id):
        sku_sales = sales_df[sales_df["sku_id"] == sku_id].copy()
        daily = sku_sales.groupby("date")["units_sold"].sum().reset_index()
        daily["units_sold"] = daily["units_sold"].fillna(0)
        avg_demand = daily["units_sold"].mean()
        std_demand = daily["units_sold"].std()
        return avg_demand, std_demand

    def calculate_safety_stock(self, demand_std, lead_time_days):
        return self.z_score * demand_std * np.sqrt(lead_time_days)

    def calculate_reorder_point(self, avg_demand, lead_time_days, safety_stock):
        return avg_demand * lead_time_days + safety_stock

    def calculate_eoq(self, annual_demand, ordering_cost, holding_cost):
        if holding_cost <= 0:
            holding_cost = 0.01
        return np.sqrt(2 * annual_demand * ordering_cost / holding_cost)

    def optimize(self, sales_df, product_info_df, sku_id) -> InventoryPolicy:
        product = product_info_df[product_info_df["sku_id"] == sku_id].iloc[0]
        lead_time = int(product["lead_time_days"])
        holding_cost = float(product["holding_cost"])
        stockout_cost = float(product["stockout_cost"])

        avg_demand, std_demand = self.compute_demand_stats(sales_df, sku_id)
        annual_demand = avg_demand * 365

        safety_stock = self.calculate_safety_stock(std_demand, lead_time)
        rop = self.calculate_reorder_point(avg_demand, lead_time, safety_stock)
        eoq = self.calculate_eoq(annual_demand, self.ordering_cost, holding_cost)

        num_orders = annual_demand / eoq if eoq > 0 else 0
        annual_ordering = num_orders * self.ordering_cost
        annual_holding = (eoq / 2 + safety_stock) * holding_cost
        total_cost = annual_ordering + annual_holding

        return InventoryPolicy(
            sku_id=sku_id,
            safety_stock=round(safety_stock, 1),
            reorder_point=round(rop, 1),
            economic_order_quantity=round(eoq, 1),
            avg_daily_demand=round(avg_demand, 2),
            demand_std=round(std_demand, 2),
            lead_time_days=lead_time,
            holding_cost=holding_cost,
            stockout_cost=stockout_cost,
            ordering_cost=self.ordering_cost,
            service_level=self.service_level,
            annual_holding_cost=round(annual_holding, 2),
            annual_ordering_cost=round(annual_ordering, 2),
            total_annual_cost=round(total_cost, 2),
        )

    def optimize_all(self, sales_df, product_info_df) -> Dict[str, InventoryPolicy]:
        policies = {}
        for sku_id in product_info_df["sku_id"].unique():
            try:
                policies[sku_id] = self.optimize(sales_df, product_info_df, sku_id)
            except Exception as e:
                logger.error(f"Optimization failed for {sku_id}: {e}")
        return policies

    def sensitivity_analysis(self, sales_df, product_info_df, sku_id,
                             service_levels=None):
        if service_levels is None:
            service_levels = [0.85, 0.90, 0.95, 0.97, 0.99]
        results = []
        for sl in service_levels:
            orig_sl = self.service_level
            orig_z = self.z_score
            self.service_level = sl
            self.z_score = self._get_z_score(sl)
            policy = self.optimize(sales_df, product_info_df, sku_id)
            results.append({
                "service_level": sl,
                "safety_stock": policy.safety_stock,
                "reorder_point": policy.reorder_point,
                "total_cost": policy.total_annual_cost,
            })
            self.service_level = orig_sl
            self.z_score = orig_z
        return results
