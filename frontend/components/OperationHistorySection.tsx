import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { listBatches } from "../services/api.ts";
import type { OperationBatchOut } from "../services/api/types.ts";
import { SpinnerIcon } from "../utils/icons.tsx";

interface Props {
  entityType: string;
  action: string;
  currentBatchId: string;
  onSelectBatch: (batchId: string) => void;
  refreshTrigger?: number;
}

export default function OperationHistorySection({ entityType, action, currentBatchId, onSelectBatch, refreshTrigger = 0 }: Props) {
  const recentBatches = useSignal<OperationBatchOut[]>([]);
  const loading = useSignal(true);

  useEffect(() => {
    (async () => {
      loading.value = true;
      try {
        const { items } = await listBatches({ entity_type: entityType, action, limit: 5 });
        recentBatches.value = items;
      } catch {
        //
      } finally {
        loading.value = false;
      }
    })();
  }, [entityType, action, refreshTrigger]);

  const verbLabel = action === "delete" ? "eliminación" : action === "create" ? "creación" : "visibilidad";

  return (
    <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
      <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-4">
        Operaciones anteriores ({verbLabel})
      </h3>
      {loading.value ? (
        <p class="text-sm text-[var(--text-secondary)]">Cargando historial...</p>
      ) : recentBatches.value.length === 0 ? (
        <p class="text-sm text-[var(--text-secondary)]">No hay operaciones anteriores de {verbLabel}.</p>
      ) : (
        <div class="space-y-2">
          {recentBatches.value.map((b) => {
            const isActive = b.batch_id === currentBatchId;
            const isComplete = b.completed + b.failed >= b.total;
            return (
              <div
                key={b.batch_id}
                onClick={() => {
                  if (!isActive) onSelectBatch(b.batch_id);
                }}
                class={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors border ${
                  isActive
                    ? "border-[var(--accent)] bg-[var(--bg-tertiary)]"
                    : "border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]"
                }`}
              >
                <div class="flex items-center gap-3 min-w-0">
                  <span class="text-xs font-mono text-[var(--text-muted)] shrink-0">{b.batch_id.slice(0, 8)}...</span>
                  <span class="text-xs text-[var(--text-secondary)] truncate">{new Date(b.created_at).toLocaleString()}</span>
                </div>
                <div class="flex items-center gap-2 text-sm shrink-0">
                  {!isComplete && (
                    <span class="flex items-center gap-1 text-yellow-600">
                      <SpinnerIcon class="animate-spin w-3 h-3" />
                    </span>
                  )}
                  <span class="text-[var(--text-muted)]">C:</span>
                  <span class="text-[var(--brand-green)]">{b.completed}</span>
                  <span class="text-[var(--text-muted)]">E:</span>
                  <span class="text-[var(--brand-red)]">{b.failed}</span>
                  <span class="text-[var(--text-muted)]">/</span>
                  <span class="text-[var(--text-primary)]">{b.total}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
      {currentBatchId && (
        <p class="text-xs text-[var(--text-muted)] mt-3">Haz clic en un lote para ver su detalle.</p>
      )}
    </div>
  );
}
