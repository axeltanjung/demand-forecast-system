"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { KPICard, SkuSelector, Card, LoadingSpinner } from "@/components/ui";
import { BarChart3, Package, TrendingUp, AlertTriangle, Clock, DollarSign } from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Area, AreaChart,
} from "recharts";

export default function DashboardPage() {
  const [skus, setSkus] = useState<any[]>([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSkus().then((data) => {
      setSkus(data.skus);
      if (data.skus.length > 0) setSelectedSku(data.skus[0].sku_id);
    });
  }, []);

  useEffect(() => {
    if (!selectedSku) return;
    setLoading(true);
    api.getDashboard(selectedSku).then((data) => {
      setDashboard(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [selectedSku]);

  if (!dashboard && loading) return <LoadingSpinner />;

  const kpis = dashboard?.kpis;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Real-time demand & inventory overview</p>
        </div>
        <SkuSelector skus={skus} selected={selectedSku} onChange={setSelectedSku} />
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <KPICard title="Avg Daily Demand" value={kpis?.avg_daily_demand || 0} icon={BarChart3} color="primary" />
            <KPICard title="Demand Std Dev" value={kpis?.demand_std || 0} icon={TrendingUp} color="amber" />
            <KPICard title="Recent 30d Avg" value={kpis?.recent_30d_demand || 0} icon={TrendingUp} color="green" />
            <KPICard title="Current Stock" value={kpis?.current_stock || 0} icon={Package} color="purple" />
            <KPICard title="Reorder Point" value={kpis?.reorder_point || 0} icon={AlertTriangle} color="red" />
            <KPICard title="Lead Time (days)" value={kpis?.lead_time || 0} icon={Clock} color="primary" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h3 className="font-semibold mb-4">Weekly Demand Trend</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={dashboard?.weekly_demand || []}>
                  <defs>
                    <linearGradient id="demandGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="var(--text-secondary)" />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }}
                  />
                  <Area type="monotone" dataKey="units_sold" stroke="#3b82f6" fill="url(#demandGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <h3 className="font-semibold mb-4">Monthly Demand</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={dashboard?.monthly_demand || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke="var(--text-secondary)" />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }}
                  />
                  <Bar dataKey="units_sold" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
