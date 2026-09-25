"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
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

const DONUT_PALETTE = [
  "var(--accent)",
  "var(--success)",
  "var(--warning)",
  "var(--danger)",
  "var(--text-muted)",
  "var(--text-subtle)",
];

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

export function DonutChart({
  data,
  dataKey,
  nameKey,
  height = 200,
}: {
  data: Record<string, string | number>[];
  dataKey: string;
  nameKey: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey={dataKey}
          nameKey={nameKey}
          innerRadius="62%"
          outerRadius="95%"
          paddingAngle={data.length > 1 ? 3 : 0}
          strokeWidth={0}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={DONUT_PALETTE[i % DONUT_PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function DonutLegend({
  data,
  dataKey,
  nameKey,
}: {
  data: Record<string, string | number>[];
  dataKey: string;
  nameKey: string;
}) {
  const total = data.reduce((sum, d) => sum + Number(d[dataKey] ?? 0), 0);
  return (
    <div className="flex flex-col gap-2">
      {data.map((d, i) => {
        const value = Number(d[dataKey] ?? 0);
        const pct = total > 0 ? Math.round((value / total) * 100) : 0;
        return (
          <div key={String(d[nameKey])} className="flex items-center justify-between gap-2 text-sm">
            <span className="flex min-w-0 items-center gap-2 text-fg">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: DONUT_PALETTE[i % DONUT_PALETTE.length] }}
              />
              <span className="truncate">{d[nameKey]}</span>
            </span>
            <span className="shrink-0 font-mono tabular-nums text-fgMuted">
              {value} <span className="text-fgSubtle">· {pct}%</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function RadialGauge({
  value,
  label,
  color = "accent",
  size = 108,
}: {
  /** 0–100 */
  value: number;
  label?: string;
  color?: keyof typeof CHART_COLORS;
  size?: number;
}) {
  const data = [{ value: Math.min(Math.max(value, 0), 100) }];
  return (
    <div className="relative flex flex-col items-center justify-center" style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          innerRadius="72%"
          outerRadius="100%"
          data={data}
          startAngle={90}
          endAngle={-270}
          barSize={8}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar background={{ fill: "var(--surface-2)" }} dataKey="value" cornerRadius={8} fill={CHART_COLORS[color]} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-lg font-semibold text-fg">{Math.round(value)}%</span>
        {label && <span className="text-[11px] text-fgSubtle">{label}</span>}
      </div>
    </div>
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
