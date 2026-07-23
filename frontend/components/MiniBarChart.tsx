// components/MiniBarChart.tsx
export default function MiniBarChart({ data }: { data: { label: string; value: number }[] }) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.value), 1);
  const pad = { top: 8, bottom: 28, left: 0, right: 0 };
  const w = 400;
  const h = 180;
  const chartH = h - pad.top - pad.bottom;
  const cols = data.length;
  const gap = cols > 1 ? 12 : 0;
  const barW = Math.max(12, (w - gap * (cols - 1)) / cols);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} class="w-full block" style={{ maxHeight: `${h}px`, height: "auto" }}>
      {data.map((d, i) => {
        const barH = (d.value / max) * chartH;
        const x = i * (barW + gap);
        const y = pad.top + chartH - barH;
        return (
          <g key={d.label}>
            <rect x={x} y={y} width={barW} height={barH} rx={3} fill="var(--brand-green)" opacity={0.85} />
            <text x={x + barW / 2} y={pad.top + chartH + 16} textAnchor="middle" font-size="9" fill="var(--text-secondary)">
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
