import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    scenario_name: str
    total_cost: float
    holding_cost: float
    stockout_cost: float
    ordering_cost: float
    service_level: float
    stockout_probability: float
    avg_stock_level: float
    num_stockouts: int
    total_units_sold: int
    total_units_lost: int
    fill_rate: float
    daily_results: Optional[List[Dict]] = None


class SimulationEngine:
    def __init__(self, num_days=365, num_simulations=100):
        self.num_days = num_days
        self.num_simulations = num_simulations

    def _generate_demand(self, avg_demand, std_demand, num_days,
                         promo_intensity=0.0, demand_variability=1.0,
                         seasonality_amp=0.2):
        t = np.arange(num_days)
        base = avg_demand * np.ones(num_days)
        seasonal = avg_demand * seasonality_amp * np.sin(2 * np.pi * t / 365)
        weekly = avg_demand * 0.1 * np.sin(2 * np.pi * t / 7)
        noise = np.random.normal(0, std_demand * demand_variability, num_days)

        promo_days = np.zeros(num_days)
        if promo_intensity > 0:
            num_promos = max(1, int(promo_intensity * 12))
            for _ in range(num_promos):
                start = np.random.randint(0, num_days - 7)
                duration = np.random.randint(3, 8)
                promo_days[start:start + duration] = 1

        promo_effect = promo_days * avg_demand * promo_intensity * 0.8
        demand = base + seasonal + weekly + noise + promo_effect
        demand = np.maximum(demand, 0).astype(int)
        return demand, promo_days

    def run_single_simulation(self, avg_demand, std_demand, lead_time,
                              reorder_point, order_quantity, safety_stock,
                              holding_cost_per_unit, stockout_cost_per_unit,
                              ordering_cost, promo_intensity=0.0,
                              demand_variability=1.0):
        demand, promo_days = self._generate_demand(
            avg_demand, std_demand, self.num_days,
            promo_intensity, demand_variability
        )

        stock = reorder_point + order_quantity
        pending_orders = []
        total_holding = 0
        total_stockout = 0
        total_ordering = 0
        stockout_days = 0
        total_sold = 0
        total_lost = 0
        daily = []

        for day in range(self.num_days):
            arrivals = [qty for arr_day, qty in pending_orders if arr_day == day]
            stock += sum(arrivals)
            pending_orders = [(d, q) for d, q in pending_orders if d != day]

            d = demand[day]
            if stock >= d:
                sold = d
                stock -= d
                lost = 0
            else:
                sold = stock
                lost = d - stock
                stock = 0
                stockout_days += 1

            total_sold += sold
            total_lost += lost
            total_holding += stock * holding_cost_per_unit / 365
            total_stockout += lost * stockout_cost_per_unit

            if stock <= reorder_point and not any(True for _ in pending_orders):
                actual_lt = max(1, int(lead_time + np.random.normal(0, lead_time * 0.1)))
                pending_orders.append((day + actual_lt, order_quantity))
                total_ordering += ordering_cost

            daily.append({
                "day": day,
                "demand": int(d),
                "stock": int(stock),
                "sold": int(sold),
                "lost": int(lost),
                "promo": int(promo_days[day]),
            })

        total_cost = total_holding + total_stockout + total_ordering
        service_level = 1 - (stockout_days / self.num_days)
        fill_rate = total_sold / (total_sold + total_lost) if (total_sold + total_lost) > 0 else 1.0

        return {
            "total_cost": total_cost,
            "holding_cost": total_holding,
            "stockout_cost": total_stockout,
            "ordering_cost": total_ordering,
            "service_level": service_level,
            "stockout_days": stockout_days,
            "avg_stock": np.mean([d["stock"] for d in daily]),
            "total_sold": total_sold,
            "total_lost": total_lost,
            "fill_rate": fill_rate,
            "daily": daily,
        }

    def run_monte_carlo(self, avg_demand, std_demand, lead_time,
                        reorder_point, order_quantity, safety_stock,
                        holding_cost_per_unit, stockout_cost_per_unit,
                        ordering_cost, promo_intensity=0.0,
                        demand_variability=1.0, scenario_name="Base"):
        results = []
        for _ in range(self.num_simulations):
            r = self.run_single_simulation(
                avg_demand, std_demand, lead_time,
                reorder_point, order_quantity, safety_stock,
                holding_cost_per_unit, stockout_cost_per_unit,
                ordering_cost, promo_intensity, demand_variability
            )
            results.append(r)

        avg_result = {
            "total_cost": np.mean([r["total_cost"] for r in results]),
            "holding_cost": np.mean([r["holding_cost"] for r in results]),
            "stockout_cost": np.mean([r["stockout_cost"] for r in results]),
            "ordering_cost": np.mean([r["ordering_cost"] for r in results]),
            "service_level": np.mean([r["service_level"] for r in results]),
            "stockout_probability": np.mean([r["stockout_days"] > 0 for r in results]),
            "avg_stock": np.mean([r["avg_stock"] for r in results]),
            "stockout_days": int(np.mean([r["stockout_days"] for r in results])),
            "total_sold": int(np.mean([r["total_sold"] for r in results])),
            "total_lost": int(np.mean([r["total_lost"] for r in results])),
            "fill_rate": np.mean([r["fill_rate"] for r in results]),
        }

        representative = min(results, key=lambda r: abs(r["total_cost"] - avg_result["total_cost"]))

        return SimulationResult(
            scenario_name=scenario_name,
            total_cost=round(avg_result["total_cost"], 2),
            holding_cost=round(avg_result["holding_cost"], 2),
            stockout_cost=round(avg_result["stockout_cost"], 2),
            ordering_cost=round(avg_result["ordering_cost"], 2),
            service_level=round(avg_result["service_level"], 4),
            stockout_probability=round(avg_result["stockout_probability"], 4),
            avg_stock_level=round(avg_result["avg_stock"], 1),
            num_stockouts=avg_result["stockout_days"],
            total_units_sold=avg_result["total_sold"],
            total_units_lost=avg_result["total_lost"],
            fill_rate=round(avg_result["fill_rate"], 4),
            daily_results=representative["daily"],
        )

    def compare_scenarios(self, base_params, scenarios):
        results = []
        base_result = self.run_monte_carlo(**base_params, scenario_name="Base")
        results.append(asdict(base_result))

        for scenario in scenarios:
            params = {**base_params, **scenario.get("overrides", {})}
            name = scenario.get("name", "Scenario")
            sr = self.run_monte_carlo(**params, scenario_name=name)
            results.append(asdict(sr))

        return results
