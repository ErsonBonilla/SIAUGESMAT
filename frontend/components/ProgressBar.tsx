// components/ProgressBar.tsx

const PHASE_ICONS = ["🔄", "📊", "🏗️", "👥", "📋"];
const PHASE_LABELS = ["Consultar Moodle", "Analizar datos", "Estructura", "Gestionar personas", "Generar reportes"];

interface ProgressBarProps {
  currentPhase: string | null;
  currentStep: number | null;
  progressPct: number;
}

export default function ProgressBar({ currentPhase, currentStep, progressPct }: ProgressBarProps) {
  const step = currentStep ?? 1;
  const icon = PHASE_ICONS[step - 1] ?? "⏳";
  const phaseLabel = PHASE_LABELS[step - 1] ?? "Procesando";
  const pct = Math.round(progressPct);
  const running = pct < 100;

  return (
    <div class="bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-2xl p-6 mb-6">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <span class={`text-2xl ${running ? "animate-spin" : ""}`}>{icon}</span>
          <div>
            <p class="text-sm font-semibold text-[var(--text-primary)]">{currentPhase ?? "Procesando…"}</p>
            <p class="text-xs text-[var(--text-secondary)]">{phaseLabel} · Fase {step} de 5</p>
          </div>
        </div>
        <span class="text-2xl font-bold gradient-text">{pct}%</span>
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
              class="h-1 rounded-full"
              style={{
                width: "21%",
                background: isDone || isCurrent
                  ? "linear-gradient(to right, var(--brand-red), var(--brand-green))"
                  : "var(--bg-tertiary)",
                opacity: isDone ? 0.7 : isCurrent ? 1 : 0.3,
              }}
            >
              {isCurrent && <div class="h-full w-full rounded-full phase-active" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
