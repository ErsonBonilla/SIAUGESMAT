import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import GraficoMetricas from "./GraficoMetricasIsland.tsx";
import ComparacionSemestre from "./ComparacionSemestre.tsx";
import SelectorMultiplesSemestres from "../components/SelectorMultiplesSemestres.tsx";
import { type MetricasSemestre, obtenerHistorial } from "../services/api.ts";
import { darkSignal } from "../utils/tema.ts";
import CajaError from "../components/CajaError.tsx";
import EsqueletoCarga from "../components/EsqueletoCarga.tsx";

export default function Historico() {
  const view = useSignal<"history" | "comparison">("history");
  const historyData = useSignal<MetricasSemestre[]>([]);
  const loading = useSignal(true);
  const error = useSignal("");
  const semestresSeleccionados = useSignal<string[]>([]);

  useEffect(() => {
    async function loadHistory() {
      loading.value = true;
      try {
        const data = await obtenerHistorial();
        historyData.value = data;
      } catch (e) {
        error.value = e instanceof Error
          ? e.message
          : "Error al cargar histórico.";
      } finally {
        loading.value = false;
      }
    }
    loadHistory();
  }, []);

  const activeBtn = "bg-[var(--accent)] text-white";
  const inactiveBase = "border text-[var(--text-secondary)]";
  const inactiveLight =
    "bg-[var(--bg-primary)] border-[var(--border-secondary)]";
  const inactiveDark =
    "bg-[var(--bg-tertiary)] border-[var(--border-secondary)] text-[var(--text-secondary)]";

  return (
    <div>
      <div class="flex gap-4 mb-6">
        {(["history", "comparison"] as const).map((v) => (
          <button
            type="button"
            key={v}
            onClick={() => (view.value = v)}
            class={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors duration-200 ${
              view.value === v
                ? activeBtn
                : `${inactiveBase} ${
                  darkSignal.value ? inactiveDark : inactiveLight
                }`
            }`}
          >
            {v === "history" ? "Evolución semestral" : "Comparar semestres"}
          </button>
        ))}
      </div>

      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
        {loading.value
          ? <EsqueletoCarga variant="chart" />
          : error.value
          ? <CajaError message={error.value} />
          : (
            view.value === "history"
              ? (
                <>
                  <div class="mb-4 flex justify-center">
                    <SelectorMultiplesSemestres
                      selected={semestresSeleccionados.value}
                      onChange={(s) => (semestresSeleccionados.value = s)}
                      semestresDisponibles={historyData.value.map((d) =>
                        d.semester
                      )}
                    />
                  </div>
                  <GraficoMetricas
                    data={historyData.value}
                    semestresSeleccionados={semestresSeleccionados.value}
                  />
                </>
              )
              : <ComparacionSemestre allMetrics={historyData.value} />
          )}
      </div>
    </div>
  );
}
