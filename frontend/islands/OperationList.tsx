// islands/OperationList.tsx
import { useSignal, useComputed } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { listBatches, getBatchReportUrl, type OperationBatchOut } from "../services/api.ts";
import { STATUS_COLORS, STATUS_LABELS } from "../utils/constants.ts";
import ErrorBox from "../components/ErrorBox.tsx";
import Pagination from "../components/Pagination.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";

const PAGE_SIZE = 20;

const ENTITY_LABELS: Record<string, string> = {
  courses: "Cursos",
  categories: "Categorías",
  users: "Usuarios",
};

const ACTION_LABELS: Record<string, string> = {
  create: "Creación",
  delete: "Eliminación",
};

function statusFromBatch(b: OperationBatchOut): string {
  if (b.completed_at) return "completed";
  if ((b.completed || 0) + (b.failed || 0) > 0) return "running";
  return "pending";
}

interface Props {
  defaultEntity?: string;
  defaultAction?: string;
}

export default function OperationList({ defaultEntity, defaultAction }: Props) {
  const items = useSignal<OperationBatchOut[]>([]);
  const total = useSignal(0);
  const loading = useSignal(true);
  const error = useSignal("");

  const isLocked = !!(defaultEntity && defaultAction);

  const filterEntity = useSignal(defaultEntity || "");
  const filterAction = useSignal(defaultAction || "");
  const filterModalidad = useSignal("");
  const offset = useSignal(0);

  async function load() {
    loading.value = true;
    error.value = "";
    try {
      const result = await listBatches({
        entity_type: filterEntity.value || undefined,
        action: filterAction.value || undefined,
        modalidad: filterModalidad.value || undefined,
        limit: PAGE_SIZE,
        offset: offset.value,
      });
      items.value = result.items;
      total.value = result.total;
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Error al cargar lotes";
    } finally {
      loading.value = false;
    }
  }

  useEffect(() => { load(); }, []);

  const totalPages = useComputed(() => Math.ceil(total.value / PAGE_SIZE));
  const currentPage = useComputed(() => Math.floor(offset.value / PAGE_SIZE) + 1);

  function applyFilters() { offset.value = 0; load(); }

  const hasFilters = useComputed(() =>
    filterEntity.value || filterAction.value || filterModalidad.value
  );

  return (
    <div>
      <div class="flex flex-wrap gap-4 mb-8 items-end">
        {!isLocked && (
          <>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Entidad</label>
          <select
            value={filterEntity.value}
            onChange={(e) => filterEntity.value = (e.target as HTMLSelectElement).value}
            class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)]"
          >
            <option value="">Todas</option>
            <option value="courses">Cursos</option>
            <option value="categories">Categorías</option>
            <option value="users">Usuarios</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Acción</label>
          <select
            value={filterAction.value}
            onChange={(e) => filterAction.value = (e.target as HTMLSelectElement).value}
            class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)]"
          >
            <option value="">Todas</option>
            <option value="create">Creación</option>
            <option value="delete">Eliminación</option>
          </select>
        </div>
          </>
        )}
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Modalidad</label>
          <select
            value={filterModalidad.value}
            onChange={(e) => filterModalidad.value = (e.target as HTMLSelectElement).value}
            class="border border-[var(--border-secondary)] rounded px-3 py-1.5 text-sm bg-[var(--bg-primary)] text-[var(--text-primary)]"
          >
            <option value="">Todas</option>
            <option value="DISTANCIA">Distancia</option>
          </select>
        </div>
        <button
          onClick={applyFilters}
          class="px-4 py-1.5 bg-gradient-to-r from-[var(--brand-red)] to-[var(--brand-green)] text-white rounded text-sm hover:brightness-110"
        >
          Filtrar
        </button>
        {hasFilters.value && (
          <button
            onClick={() => {
              if (!isLocked) { filterEntity.value = ""; filterAction.value = ""; }
              filterModalidad.value = "";
              applyFilters();
            }}
            class="px-4 py-1.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded text-sm hover:bg-[var(--border-secondary)]"
          >
            Limpiar
          </button>
        )}
      </div>

      {loading.value ? (
        <LoadingSkeleton />
      ) : error.value ? (
        <ErrorBox message={error.value} />
      ) : items.value.length === 0 ? (
        <div class="text-center py-12 text-[var(--text-secondary)]">
          <p class="text-lg mb-2">No se encontraron lotes</p>
          <p class="text-sm">Pruebe con otros filtros o cree una operación desde el panel.</p>
        </div>
      ) : (
        <>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--border-primary)]">
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Lote</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Entidad</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Acción</th>
                  <th class="text-center py-3 px-2 font-medium text-[var(--text-secondary)]">Total</th>
                  <th class="text-center py-3 px-2 font-medium text-[var(--text-secondary)]">Completado</th>
                  <th class="text-center py-3 px-2 font-medium text-[var(--text-secondary)]">Fallido</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Modalidad</th>
                  <th class="text-left py-3 px-2 font-medium text-[var(--text-secondary)]">Estado</th>
                  <th class="text-right py-3 px-2 font-medium text-[var(--text-secondary)]">Acción</th>
                </tr>
              </thead>
              <tbody>
                {items.value.map((b) => (
                  <tr class="border-b border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]">
                    <td class="py-3 px-2 font-mono text-xs text-[var(--text-secondary)]">{b.batch_id.slice(0, 12)}</td>
                    <td class="py-3 px-2">{ENTITY_LABELS[b.entity_type] || b.entity_type}</td>
                    <td class="py-3 px-2">{ACTION_LABELS[b.action] || b.action}</td>
                    <td class="py-3 px-2 text-center">{b.total}</td>
                    <td class="py-3 px-2 text-center text-[var(--brand-green)]">{b.completed || 0}</td>
                    <td class="py-3 px-2 text-center text-[var(--brand-red)]">{b.failed || 0}</td>
                    <td class="py-3 px-2">
                      <span class="inline-flex items-center px-1.5 py-0.5 status-blue rounded text-xs font-medium">
                        {b.modalidad}
                      </span>
                    </td>
                    <td class="py-3 px-2">
                      <span class={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[statusFromBatch(b)]}`}>
                        {STATUS_LABELS[statusFromBatch(b)]}
                      </span>
                    </td>
                    <td class="py-3 px-2 text-right whitespace-nowrap">
                      <a href={getBatchReportUrl(b.batch_id)} class="gradient-text hover:brightness-110 text-sm font-medium">CSV</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            offset={offset.value}
            pageSize={PAGE_SIZE}
            total={total.value}
            label="lotes"
            onPageChange={(o) => { offset.value = o; load(); }}
          />
        </>
      )}
    </div>
  );
}
