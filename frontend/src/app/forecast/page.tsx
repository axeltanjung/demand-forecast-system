"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { SkuSelector, Card, LoadingSpinner, KPICard } from "@/components/ui";
import { TrendingUp, BarChart3, Activity } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, BarChart, Bar,
} from "recharts";

export default function ForecastPage() {
  const [skus, setSkus] = useState<any[]>([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [modelType, setModelType] = useState("arima");
  const [forecastData, setForecastData] = useState<any>(null);
  const [importance, setImportance] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSkus().then((data) => {
      setSkus(data.skus);
      if (data.skus.length > 0) setSelectedSku(data.skus[0].sku_id);
    });
  }, []);

  const runForecast = async () => {
    if (!selectedSku) return;
    setLoading(true);
    try {
      const [fc, fi] = await Promise.all([
        api.forecast(selectedSku, modelType),
        api.featureImportance(selectedSku),
      ]);
      setForecastData(fc);
      setImportance(fi);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const chartData = () => {
    if (!forecastData) return [];
    const hist = (forecastData.historical || []).map((d: any) => ({
      date: d.date,
      actual: d.demand,
      forecast: null,
    }));
    const fc = (forecastData.forecast || []).map((d: any) => ({
      date: d.date,
      actual: null,
      forecast: d.demand,
    }));
    return [...hist, ...fc];
  };

  const evalData = forecastData?.evaluation;
  const comparisonData = evalData
    ? evalData.dates?.map((d: string, i: number) => ({
        date: d,
        actual: evalData.actuals?.[i],
        predicted: evalData.predictions?.[i],
      }))
    : [];

  const importanceData = importance
    ? Object.entries(importance.feature_importance || {}).map(([k, v]) => ({
        feature: k,
        importance: v,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Demand Forecast</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Multi-SKU forecasting with model comparison</p>
        </div>
        <div className="flex items-center gap-3">
          <SkuSelector skus={skus} selected={selectedSku} onChange={setSelectedSku} />
          <select
            value={modelType}
            onChange={(e) => setModelType(e.target.value)}
            className="px-4 py-2 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          >
            <option value="arima">ARIMA</option>
            <option value="lstm">LSTM</option>
          </select>
          <button
            onClick={runForecast}
            disabled={loading}
            className="px-6 py-2 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-all disabled:opacity-50"
          >
            {loading ? "Running..." : "Run Forecast"}
          </button>
        </div>
      </div>

      {loading && <LoadingSpinner />}

      {forecastData && !loading && (
        <>
          {evalData && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <KPICard title="Model" value={evalData.model} icon={Activity} color="primary" />
              <KPICard title="MAE" value={evalData.mae} icon={BarChart3} color="amber" />
              <KPICard title="RMSE" value={evalData.rmse} icon={TrendingUp} color="red" />
            </div>
          )}

          <Card>
            <h3 className="font-semibold mb-4">Historical & Forecast</h3>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={chartData()}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="var(--text-secondary)" />
                <YAxis stroke="var(--text-secondary)" />
                <Tooltip contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                <Legend />
                <Line type="monotone" dataKey="actual" stroke="#3b82f6" strokeWidth={2} dot={false} name="Actual" />
                <Line type="monotone" dataKey="forecast" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Forecast" />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {comparisonData.length > 0 && (
              <Card>
                <h3 className="font-semibold mb-4">Actual vs Predicted (Test Set)</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={comparisonData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="var(--text-secondary)" />
                    <YAxis stroke="var(--text-secondary)" />
                    <Tooltip contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                    <Legend />
                    <Line type="monotone" dataKey="actual" stroke="#3b82f6" strokeWidth={2} name="Actual" />
                    <Line type="monotone" dataKey="predicted" stroke="#10b981" strokeWidth={2} name="Predicted" />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            )}

            {importanceData.length > 0 && (
              <Card>
                <h3 className="font-semibold mb-4">Feature Importance</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={importanceData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" stroke="var(--text-secondary)" />
                    <YAxis dataKey="feature" type="category" tick={{ fontSize: 11 }} width={120} stroke="var(--text-secondary)" />
                    <Tooltip contentStyle={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                    <Bar dataKey="importance" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}
