import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import MetricsChart from "./MetricsChart.tsx";
import SemesterComparison from "./SemesterComparison.tsx";
import SemesterMultiPicker from "../components/SemesterMultiPicker.tsx";
import { getHistory, type SemesterMetrics } from "../services/api.ts";
import { darkSignal } from "../utils/theme.ts";
import ErrorBox from "../components/ErrorBox.tsx";
import LoadingSkeleton from "../components/LoadingSkeleton.tsx";

export default function Historico() {
  const view = useSignal<"history" | "comparison">("history");
  const historyData = useSignal<SemesterMetrics[]>([]);
  const loading = useSignal(true);
  const error = useSignal("");
  const selectedSemesters = useSignal<string[]>([]);

  useEffect(() => {
    async function loadHistory() {
      loading.value = true;
      try {
        const data = await getHistory();
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
          ? <LoadingSkeleton variant="chart" />
          : error.value
          ? <ErrorBox message={error.value} />
          : (
            view.value === "history"
              ? (
                <>
                  <div class="mb-4 flex justify-center">
                    <SemesterMultiPicker
                      selected={selectedSemesters.value}
                      onChange={(s) => (selectedSemesters.value = s)}
                      availableSemesters={historyData.value.map((d) =>
                        d.semester
                      )}
                    />
                  </div>
                  <MetricsChart
                    data={historyData.value}
                    selectedSemesters={selectedSemesters.value}
                  />
                </>
              )
              : <SemesterComparison allMetrics={historyData.value} />
          )}
      </div>
    </div>
  );
}
