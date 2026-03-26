"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { SkuSelector, Card, LoadingSpinner, KPICard } from "@/components/ui";
import {
  Sliders, DollarSign, AlertTriangle, TrendingUp,
  BarChart3, ShieldCheck, Package, Download,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, AreaChart, Area, BarChart, Bar,
  ComposedChart,
} from "recharts";

export default function SimulationPage() {
  const [skus, setSkus] = useState<any[]>([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [promoIntensity, setPromoIntensity] = useState(0.3);
  const [leadTime, setLeadTime] = useState<number | null>(null);
  const [demandVar, setDemandVar] = useState(1.0);
  const [serviceLevel, setServiceLevel] = useState(0.95);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [scenarios, setScenarios] = useState<any[]>([]);

  useEffect(() => {
    api.getSkus().then((data) => {
      setSkus(data.skus);
      if (data.skus.length > 0) setSelectedSku(data.skus[0].sku_id);
    });
  }, []);

  const runSimulation = useCallback(async () => {
    if (!selectedSku) return;
    setLoading(true);
    try {
      const data = await api.simulate({
        sku_id: selectedSku,
        promo_intensity: promoIntensity,
        lead_time_override: leadTime,
        demand_variability: demandVar,
        service_level: serviceLevel,
      });
      setResult(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, [selectedSku, promoIntensity, leadTime, demandVar, serviceLevel]);

  const addScenario = () => {
    if (!result) return;
    setScenarios((prev) => [
      ...prev,
      {
        name: `Promo=${promoIntensity}, Var=${demandVar}, SL=${(serviceLevel * 100).toFixed(0)}%`,
        ...result,
      },
    ]);
  };

  const downloadReport = () => {
    if (!result) return;
    const report = {
      sku_id: selectedSku,
      parameters: { promoIntensity, leadTime, demandVar, serviceLevel },
      results: {
        total_cost: result.total_cost,
        service_level: result.service_level,
        stockout_probability: result.stockout_probability,
        fill_rate: result.fill_rate,
      },
      policy: result.inventory_policy,
      scenarios: scenarios,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `simulation_report_${selectedSku}.json`;
    a.click();
  };

  const r = result;
  const daily = r?.daily_results || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Simulation Engine</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Explore what-if scenarios and business impact
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SkuSelector skus={skus} selected={selectedSku} onChange={setSelectedSku} />
          <button
            onClick={runSimulation}
            disabled={loading}
            className="px-6 py-2 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-all disabled:opacity-50"
          >
            {loading ? "Simulating..." : "Run Simulation"}
          </button>
        </div>
      </div>

      <Card>
        <h3 className="font-semibold mb-6 flex items-center gap-2">
          <Sliders className="w-5 h-5 text-primary-500" />
          Scenario Parameters
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          <div>
            <label className="text-sm font-medium block mb-2">
              Promotion Intensity: <span className="text-primary-500">{promoIntensity.toFixed(1)}</span>
            </label>
            <input
              type="range" min="0" max="2" step="0.1"
              value={promoIntensity}
              onChange={(e) => setPromoIntensity(parseFloat(e.target.value))}
              className="slider-track w-full"
            />
            <div className="flex justify-between text-xs text-[var(--text-secondary)] mt-1">
              <span>None</span><span>Heavy</span>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium block mb-2">
              Lead Time Override: <span className="text-primary-500">{leadTime || "Default"}</span>
            </label>
            <input
              type="range" min="1" max="30" step="1"
              value={leadTime || 7}
              onChange={(e) => setLeadTime(parseInt(e.target.value))}
              className="slider-track w-full"
            />
            <div className="flex justify-between text-xs text-[var(--text-secondary)] mt-1">
              <span>1 day</span><span>30 days</span>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium block mb-2">
              Demand Variability: <span className="text-primary-500">{demandVar.toFixed(1)}x</span>
            </label>
            <input
              type="range" min="0.1" max="3" step="0.1"
              value={demandVar}
              onChange={(e) => setDemandVar(parseFloat(e.target.value))}
              className="slider-track w-full"
            />
            <div className="flex justify-between text-xs text-[var(--text-secondary)] mt-1">
              <span>Low</span><span>High</span>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium block mb-2">
              Service Level: <span className="text-primary-500">{(serviceLevel * 100).toFixed(0)}%</span>
            </label>
            <input
              type="range" min="0.8" max="0.99" step="0.01"
              value={serviceLevel}
              onChange={(e) => setServiceLevel(parseFloat(e.target.value))}
              className="slider-track w-full"
            />
            <div className="flex justify-between text-xs text-[var(--text-secondary)] mt-1">
              <span>80%</span><span>99%</span>
            </div>
          </div>
        </div>
      </Card>

      {loading && <LoadingSpinner />}

      {r && !loading && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <KPICard title="Total Cost" value={`$${r.total_cost.toLocaleString()}`} icon={DollarSign} color="primary" />
            <KPICard title="Holding Cost" value={`$${r.holding_cost.toLocaleString()}`} icon={Package} color="green" />
            <KPICard title="Stockout Cost" value={`$${r.stockout_cost.toLocaleString()}`} icon={AlertTriangle} color="red" />
            <KPICard title="Service Level" value={`${(r.service_level * 100).toFixed(1)}%`} icon={ShieldCheck} color="green" />
            <KPICard title="Stockout Risk" value={`${(r.stockout_probability * 100).toFixed(1)}%`} icon={AlertTriangle} color="amber" />
            <KPICard title="Fill Rate" value={`${(r.fill_rate * 100).toFixed(1)}%`} icon={TrendingUp} color="purple" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h3 className="font-semibold mb-4">Stock Level & Demand (90 days)</h3>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="day" stroke="var(--text-secondary)" />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                  <Legend />
                  <Area type="monotone" dataKey="stock" fill="#3b82f620" stroke="#3b82f6" strokeWidth={2} name="Stock" />
                  <Line type="monotone" dataKey="demand" stroke="#f59e0b" strokeWidth={1.5} dot={false} name="Demand" />
                  <Bar dataKey="lost" fill="#ef4444" opacity={0.7} name="Lost Sales" />
                </ComposedChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <h3 className="font-semibold mb-4">Cost Breakdown</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={[
                    { name: "Holding", cost: r.holding_cost, color: "#3b82f6" },
                    { name: "Stockout", cost: r.stockout_cost, color: "#ef4444" },
                    { name: "Ordering", cost: r.ordering_cost, color: "#f59e0b" },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--text-secondary)" />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                  <Bar dataKey="cost" radius={[8, 8, 0, 0]}>
                    {[
                      { name: "Holding", cost: r.holding_cost, fill: "#3b82f6" },
                      { name: "Stockout", cost: r.stockout_cost, fill: "#ef4444" },
                      { name: "Ordering", cost: r.ordering_cost, fill: "#f59e0b" },
                    ].map((entry, idx) => (
                      <rect key={idx} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <div className="flex gap-3">
            <button
              onClick={addScenario}
              className="px-4 py-2 rounded-xl bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 transition-all"
            >
              Save Scenario for Comparison
            </button>
            <button
              onClick={downloadReport}
              className="px-4 py-2 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-sm font-medium hover:bg-primary-500/5 transition-all flex items-center gap-2"
            >
              <Download className="w-4 h-4" /> Download Report
            </button>
          </div>

          {scenarios.length > 1 && (
            <Card>
              <h3 className="font-semibold mb-4">Scenario Comparison</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)]">
                      <th className="text-left py-3 px-4">Scenario</th>
                      <th className="text-right py-3 px-4">Total Cost</th>
                      <th className="text-right py-3 px-4">Service Level</th>
                      <th className="text-right py-3 px-4">Stockout Risk</th>
                      <th className="text-right py-3 px-4">Fill Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarios.map((s, i) => (
                      <tr key={i} className="border-b border-[var(--border)] last:border-0">
                        <td className="py-3 px-4 font-medium">{s.name}</td>
                        <td className="text-right py-3 px-4">${s.total_cost?.toLocaleString()}</td>
                        <td className="text-right py-3 px-4">{((s.service_level || 0) * 100).toFixed(1)}%</td>
                        <td className="text-right py-3 px-4">{((s.stockout_probability || 0) * 100).toFixed(1)}%</td>
                        <td className="text-right py-3 px-4">{((s.fill_rate || 0) * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
