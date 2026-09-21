"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const CHART_COLORS = {
  accent: "var(--accent)",
  success: "var(--success)",
  warning: "var(--warning)",
  danger: "var(--danger)",
  muted: "var(--text-muted)",
};

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-popover">
      {label && <p className="mb-1 font-medium text-fg">{label}</p>}
      {payload.map((entry: any) => (
        <p key={entry.dataKey} className="flex items-center gap-1.5 text-fgMuted">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: entry.color }} />
          {entry.name}: <span className="font-mono font-medium text-fg">{entry.value}</span>
        </p>
      ))}
    </div>
  );
}

export function TrendLineChart({
  data,
  lines,
  xKey,
  height = 220,
}: {
  data: Record<string, string | number>[];
  lines: { key: string; label: string; color?: keyof typeof CHART_COLORS }[];
  xKey: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 11, fill: "var(--text-muted)" }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={false}
        />
        <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} width={32} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--border)" }} />
        {lines.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label}
            stroke={CHART_COLORS[line.color ?? "accent"]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ComparisonBarChart({
  data,
  barKey,
  labelKey,
  color = "accent",
  height = 220,
}: {
  data: Record<string, string | number>[];
  barKey: string;
  labelKey: string;
  color?: keyof typeof CHART_COLORS;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey={labelKey}
          tick={{ fontSize: 11, fill: "var(--text-muted)" }}
          axisLine={false}
          tickLine={false}
          width={100}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--surface-2)" }} />
        <Bar dataKey={barKey} fill={CHART_COLORS[color]} radius={[0, 4, 4, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Sparkline({
  data,
  dataKey,
  color = "accent",
  height = 40,
}: {
  data: Record<string, string | number>[];
  dataKey: string;
  color?: keyof typeof CHART_COLORS;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={CHART_COLORS[color]}
          strokeWidth={1.75}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
