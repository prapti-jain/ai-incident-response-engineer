"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartPoint } from "@/lib/types";

type Props = {
  data: ChartPoint[];
  lastUpdated: Date | null;
};

const GRID = "#2a2f38";
const AXIS = "#6b7280";
const TOOLTIP_BG = "#1a1f27";
const TOOLTIP_BORDER = "#2a2f38";

function ChartCard({
  title,
  unit,
  children,
}: {
  title: string;
  unit: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-[#2a2f38] bg-[#12161c] p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-medium tracking-wide text-[#c9d1d9]">
          {title}
        </h2>
        <span className="text-xs text-[#6b7280]">{unit}</span>
      </div>
      <div className="h-56">{children}</div>
    </section>
  );
}

export default function MetricsCharts({ data, lastUpdated }: Props) {
  const empty = data.length === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-widest text-[#6b7280]">
          Metrics (last 15 min)
        </h2>
        {lastUpdated && (
          <span className="text-xs text-[#6b7280]">
            updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {empty ? (
        <div className="rounded-lg border border-dashed border-[#2a2f38] bg-[#12161c] px-4 py-12 text-center text-sm text-[#6b7280]">
          No metric samples yet. Click the Fault Injection buttons above to
          generate traffic.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Error rate" unit="%">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: AXIS, fontSize: 10 }}
                  interval="preserveStartEnd"
                  minTickGap={40}
                />
                <YAxis tick={{ fill: AXIS, fontSize: 10 }} width={36} />
                <Tooltip
                  contentStyle={{
                    background: TOOLTIP_BG,
                    border: `1px solid ${TOOLTIP_BORDER}`,
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "#9ca3af" }}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: "#9ca3af" }} />
                <Line
                  type="monotone"
                  dataKey="service_a_error_rate"
                  name="service-a"
                  stroke="#d1d5db"
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="service_b_error_rate"
                  name="service-b"
                  stroke="#6b7280"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Latency" unit="ms">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: AXIS, fontSize: 10 }}
                  interval="preserveStartEnd"
                  minTickGap={40}
                />
                <YAxis tick={{ fill: AXIS, fontSize: 10 }} width={36} />
                <Tooltip
                  contentStyle={{
                    background: TOOLTIP_BG,
                    border: `1px solid ${TOOLTIP_BORDER}`,
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "#9ca3af" }}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: "#9ca3af" }} />
                <Line
                  type="monotone"
                  dataKey="service_a_latency_ms"
                  name="service-a"
                  stroke="#d1d5db"
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="service_b_latency_ms"
                  name="service-b"
                  stroke="#6b7280"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}
    </div>
  );
}
