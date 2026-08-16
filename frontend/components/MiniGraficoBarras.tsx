// components/MiniBarChart.tsx
interface MiniBarChartProps {
  data: { label: string; value: number }[];
  width?: number;
  height?: number;
  color?: string;
}

export default function MiniBarChart(
  { data, width = 400, height = 180, color = "var(--brand-green)" }:
    MiniBarChartProps,
) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.value), 1);
  const pad = { top: 8, bottom: 28, left: 0, right: 0 };
  const chartH = height - pad.top - pad.bottom;
  const cols = data.length;
  const gap = cols > 1 ? 12 : 0;
  const barW = Math.max(12, (width - gap * (cols - 1)) / cols);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      class="w-full block"
      style={{ maxHeight: `${height}px`, height: "auto" }}
    >
      {data.map((d, i) => {
        const barH = (d.value / max) * chartH;
        const x = i * (barW + gap);
        const y = pad.top + chartH - barH;
        return (
          <g key={d.label}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={barH}
              rx={3}
              fill={color}
              opacity={0.85}
            />
            <text
              x={x + barW / 2}
              y={pad.top + chartH + 16}
              textAnchor="middle"
              font-size="9"
              fill="var(--text-secondary)"
            >
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
