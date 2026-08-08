import { useSignal } from "@preact/signals";
import TablaConsultaIsland from "./TablaConsultaIsland.tsx";
import ConsultaCursosSinUso from "./ConsultaCursosSinUso.tsx";
import { ENTITY_CONSULT_CONFIGS } from "../utils/entity-configs.ts";

type Mode = "normal" | "inactive";

export default function CursosConsultas() {
  const mode = useSignal<Mode>("normal");
  const coursesConfig = ENTITY_CONSULT_CONFIGS.courses;

  return (
    <div class="max-w-6xl mx-auto">
      <div class="flex gap-1 mb-6 bg-[var(--bg-tertiary)] rounded-lg p-1 w-fit">
        <button
          type="button"
          onClick={() => mode.value = "normal"}
          class={`px-4 py-1.5 rounded-md text-sm font-medium transition ${
            mode.value === "normal"
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Consulta normal
        </button>
        <button
          type="button"
          onClick={() => mode.value = "inactive"}
          class={`px-4 py-1.5 rounded-md text-sm font-medium transition ${
            mode.value === "inactive"
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Cursos sin uso
        </button>
      </div>

      {mode.value === "normal"
        ? <TablaConsultaIsland entity="courses" {...coursesConfig} />
        : <ConsultaCursosSinUso />}
    </div>
  );
}
