// components/Paginacion.tsx
interface Props {
  offset: number;
  tamanoPagina: number;
  total: number;
  label: string;
  alCambiarPagina: (offset: number) => void;
}

export default function Paginacion(
  { offset, tamanoPagina, total, label, alCambiarPagina }: Props,
) {
  const totalPages = Math.ceil(total / tamanoPagina);
  const currentPage = Math.floor(offset / tamanoPagina) + 1;

  if (totalPages <= 1) return null;

  return (
    <div class="flex items-center justify-between mt-4 text-sm text-[var(--text-secondary)]">
      <span>Página {currentPage} de {totalPages} ({total} {label})</span>
      <div class="flex gap-2">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => alCambiarPagina(Math.max(0, offset - tamanoPagina))}
          class="px-3 py-1 border border-[var(--border-secondary)] rounded disabled:opacity-40 hover:bg-[var(--bg-tertiary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
        >
          Anterior
        </button>
        <button
          type="button"
          disabled={offset + tamanoPagina >= total}
          onClick={() => alCambiarPagina(offset + tamanoPagina)}
          class="px-3 py-1 border border-[var(--border-secondary)] rounded disabled:opacity-40 hover:bg-[var(--bg-tertiary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}
