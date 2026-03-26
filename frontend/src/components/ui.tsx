"use client";
import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: number;
  color?: string;
}

export function KPICard({ title, value, subtitle, icon: Icon, trend, color = "primary" }: KPICardProps) {
  const colorMap: Record<string, string> = {
    primary: "from-blue-500/10 to-blue-600/5 text-blue-500",
    green: "from-emerald-500/10 to-emerald-600/5 text-emerald-500",
    amber: "from-amber-500/10 to-amber-600/5 text-amber-500",
    red: "from-red-500/10 to-red-600/5 text-red-500",
    purple: "from-purple-500/10 to-purple-600/5 text-purple-500",
  };
  const iconBg = colorMap[color] || colorMap.primary;

  return (
    <div className="kpi-card animate-fade-in">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${iconBg} flex items-center justify-center`}>
          <Icon className="w-5 h-5" />
        </div>
        {trend !== undefined && (
          <span className={`text-xs font-medium px-2 py-1 rounded-full ${trend >= 0 ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"}`}>
            {trend >= 0 ? "+" : ""}{trend.toFixed(1)}%
          </span>
        )}
      </div>
      <p className="text-2xl font-bold">{typeof value === "number" ? value.toLocaleString() : value}</p>
      <p className="text-xs text-[var(--text-secondary)] mt-1">{title}</p>
      {subtitle && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{subtitle}</p>}
    </div>
  );
}

export function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center p-12">
      <div className="w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export function SkuSelector({ skus, selected, onChange }: { skus: any[]; selected: string; onChange: (v: string) => void }) {
  return (
    <select
      value={selected}
      onChange={(e) => onChange(e.target.value)}
      className="px-4 py-2 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary-500/50 transition-all"
    >
      {skus.map((s: any) => (
        <option key={s.sku_id} value={s.sku_id}>
          {s.sku_id} — {s.category}
        </option>
      ))}
    </select>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card animate-slide-up ${className}`}>{children}</div>;
}
