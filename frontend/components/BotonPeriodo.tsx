import { ETIQUETAS_MESES } from "../utils/constantes.ts";

interface Props {
  period: "A" | "B";
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
}

export default function BotonPeriodo(
  { period, selected, disabled, onClick }: Props,
) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      class={`flex-1 px-3 py-1.5 rounded-lg border text-sm font-medium transition ${
        selected
          ? "bg-[var(--accent)] text-white border-[var(--accent)]"
          : "bg-[var(--bg-primary)] text-[var(--text-secondary)] border-[var(--border-secondary)] hover:bg-[var(--bg-tertiary)]"
      } disabled:opacity-30 disabled:cursor-not-allowed`}
    >
      <div class="leading-tight">{period}</div>
      <div class="text-[10px] opacity-80 leading-tight">
        {ETIQUETAS_MESES[period]}
      </div>
    </button>
  );
}
