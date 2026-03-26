const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API Error");
  }
  return res.json();
}

export const api = {
  getSkus: () => fetchApi<any>("/skus"),
  getDashboard: (skuId: string) => fetchApi<any>(`/dashboard/${skuId}`),
  forecast: (skuId: string, modelType: string = "arima", steps: number = 12) =>
    fetchApi<any>("/forecast", {
      method: "POST",
      body: JSON.stringify({ sku_id: skuId, model_type: modelType, steps }),
    }),
  forecastCompare: (skuId: string) =>
    fetchApi<any>("/forecast/compare", {
      method: "POST",
      body: JSON.stringify({ sku_id: skuId }),
    }),
  optimize: (skuId: string, serviceLevel: number = 0.95) =>
    fetchApi<any>("/optimize", {
      method: "POST",
      body: JSON.stringify({ sku_id: skuId, service_level: serviceLevel }),
    }),
  optimizeAll: () => fetchApi<any>("/optimize/all"),
  simulate: (params: any) =>
    fetchApi<any>("/simulate", {
      method: "POST",
      body: JSON.stringify(params),
    }),
  simulateCompare: (skuId: string, scenarios: any[]) =>
    fetchApi<any>("/simulate/compare", {
      method: "POST",
      body: JSON.stringify({ sku_id: skuId, scenarios }),
    }),
  featureImportance: (skuId: string) => fetchApi<any>(`/feature-importance/${skuId}`),
};
