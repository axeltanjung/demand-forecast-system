"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { SkuSelector, Card, LoadingSpinner, KPICard } from "@/components/ui";
import { Package, Shield, RefreshCw, DollarSign, TrendingUp, AlertTriangle } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Legend, RadarChart,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";

export default function OptimizationPage() {
  const [skus, setSkus] = useState<any[]>([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [serviceLevel, setServiceLevel] = useState(0.95);
  const [policy, setPolicy] = useState<any>(null);
  const [sensitivity, setSensitivity] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSkus().then((data) => {
      setSkus(data.skus);
      if (data.skus.length > 0) setSelectedSku(data.skus[0].sku_id);
    });
  }, []);

  useEffect(() => {
    if (!selectedSku) return;
    setLoading(true);
    api.optimize(selectedSku, serviceLevel).then((data) => {
      setPolicy(data.policy);
      setSensitivity(data.sensitivity);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [selectedSku, serviceLevel]);

  const p = policy;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Inventory Optimization</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Optimal reorder points, safety stock & EOQ</p>
        </div>
        <div className="flex items-center gap-3">
          <SkuSelector skus={skus} selected={selectedSku} onChange={setSelectedSku} />
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--text-secondary)]">Service Level:</label>
            <input
              type="range"
              min="0.8"
              max="0.99"
              step="0.01"
              value={serviceLevel}
              onChange={(e) => setServiceLevel(parseFloat(e.target.value))}
              className="slider-track w-32"
            />
            <span className="text-sm font-medium w-12">{(serviceLevel * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : p ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <KPICard title="Safety Stock" value={Math.round(p.safety_stock)} icon={Shield} color="primary" />
            <KPICard title="Reorder Point" value={Math.round(p.reorder_point)} icon={AlertTriangle} color="amber" />
            <KPICard title="EOQ" value={Math.round(p.economic_order_quantity)} icon={Package} color="green" />
            <KPICard title="Avg Daily Demand" value={p.avg_daily_demand} icon={TrendingUp} color="purple" />
            <KPICard title="Annual Holding Cost" value={`$${p.annual_holding_cost.toLocaleString()}`} icon={DollarSign} color="red" />
            <KPICard title="Total Annual Cost" value={`$${p.total_annual_cost.toLocaleString()}`} icon={DollarSign} color="primary" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h3 className="font-semibold mb-4">Policy Parameters</h3>
              <div className="space-y-4">
                {[
                  { label: "Lead Time", value: `${p.lead_time_days} days`, desc: "Supplier delivery time" },
                  { label: "Holding Cost", value: `$${p.holding_cost}/unit/year`, desc: "Cost to store inventory" },
                  { label: "Stockout Cost", value: `$${p.stockout_cost}/unit`, desc: "Lost sale penalty" },
                  { label: "Ordering Cost", value: `$${p.ordering_cost}/order`, desc: "Fixed cost per order" },
                  { label: "Demand Variability", value: `σ = ${p.demand_std}`, desc: "Daily demand std dev" },
                  { label: "Service Level", value: `${(p.service_level * 100).toFixed(1)}%`, desc: "Target fill rate" },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0">
                    <div>
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-xs text-[var(--text-secondary)]">{item.desc}</p>
                    </div>
                    <span className="text-sm font-bold">{item.value}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <h3 className="font-semibold mb-4">Service Level Sensitivity</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={sensitivity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="service_level"
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                    stroke="var(--text-secondary)"
                  />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }}
                    labelFormatter={(v: number) => `Service Level: ${(v * 100).toFixed(0)}%`}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="safety_stock" stroke="#3b82f6" strokeWidth={2} name="Safety Stock" />
                  <Line type="monotone" dataKey="total_cost" stroke="#ef4444" strokeWidth={2} name="Total Cost ($)" />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card>
            <h3 className="font-semibold mb-4">Cost Breakdown</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart
                data={[
                  { name: "Holding", cost: p.annual_holding_cost },
                  { name: "Ordering", cost: p.annual_ordering_cost },
                  { name: "Total", cost: p.total_annual_cost },
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="name" stroke="var(--text-secondary)" />
                <YAxis stroke="var(--text-secondary)" />
                <Tooltip contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                <Bar dataKey="cost" fill="#3b82f6" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </>
      ) : null}
    </div>
  );
}
