// components/ProgressBar.tsx

import { formatEta } from "../utils/date.ts";

const PHASE_ICONS = ["🔄", "📊", "⚡", "📋"];
const PHASE_LABELS = [
  "Consultar Moodle",
  "Analizar datos",
  "Ejecutar cambios",
  "Generar reportes",
];

interface ProgressBarProps {
  currentPhase: string | null;
  currentStep: number | null;
  progressPct: number;
  status?: string;
  etaSeconds?: number;
}

export default function ProgressBar(
  { currentPhase, currentStep, progressPct, status, etaSeconds }:
    ProgressBarProps,
) {
  const step = currentStep ?? 1;
  const icon = PHASE_ICONS[step - 1] ?? "⏳";
  const phaseLabel = PHASE_LABELS[step - 1] ?? "Procesando";
  const pct = Math.round(progressPct);
  const running = pct < 100;
  const progressColor = `hsl(${pct * 1.2}, 85%, 42%)`;

  return (
    <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-2xl p-6 mb-6">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <span
            class={`text-2xl ${running ? "animate-spin" : ""}`}
          >
            {icon}
          </span>
          <div>
            <p class="text-sm font-semibold text-[var(--text-primary)]">
              {currentPhase ?? "Procesando…"}
            </p>
            <p class="text-xs text-[var(--text-secondary)]">
              {phaseLabel} · Fase {step} de 4
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-2xl font-bold" style={{ color: progressColor }}>
            {pct}%
          </span>
          {status === "running" && etaSeconds != null && etaSeconds > 0 && (
            <span class="text-xs text-[var(--text-secondary)] whitespace-nowrap">
              {formatEta(etaSeconds)}
            </span>
          )}
        </div>
      </div>
      <div class="w-full h-2.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
        <div
          class="h-full rounded-full progress-bar"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div class="flex justify-between gap-1 mt-2">
        {PHASE_LABELS.map((l, i) => {
          const idx = i + 1;
          const isDone = idx < step;
          const isCurrent = idx === step;
          return (
            <div
              key={l}
              class="h-1 rounded-full transition-all duration-700"
              style={{
                width: "21%",
                backgroundColor: isDone || isCurrent
                  ? progressColor
                  : "var(--bg-tertiary)",
                opacity: isDone ? 1 : isCurrent ? 0.8 : 0.3,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
