// components/Pagination.tsx
interface Props {
  offset: number;
  pageSize: number;
  total: number;
  label: string;
  onPageChange: (offset: number) => void;
}

export default function Pagination(
  { offset, pageSize, total, label, onPageChange }: Props,
) {
  const totalPages = Math.ceil(total / pageSize);
  const currentPage = Math.floor(offset / pageSize) + 1;

  if (totalPages <= 1) return null;

  return (
    <div class="flex items-center justify-between mt-4 text-sm text-[var(--text-secondary)]">
      <span>Página {currentPage} de {totalPages} ({total} {label})</span>
      <div class="flex gap-2">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => onPageChange(Math.max(0, offset - pageSize))}
          class="px-3 py-1 border border-[var(--border-secondary)] rounded disabled:opacity-40 hover:bg-[var(--bg-tertiary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
        >
          Anterior
        </button>
        <button
          type="button"
          disabled={offset + pageSize >= total}
          onClick={() => onPageChange(offset + pageSize)}
          class="px-3 py-1 border border-[var(--border-secondary)] rounded disabled:opacity-40 hover:bg-[var(--bg-tertiary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}
