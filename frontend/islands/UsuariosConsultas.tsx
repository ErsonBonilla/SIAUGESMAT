import { useSignal } from "@preact/signals";
import TablaConsultaIsland from "./TablaConsultaIsland.tsx";
import ConsultaDocentesSinAcceso from "./ConsultaDocentesSinAcceso.tsx";
import ConsultaCorreosDuplicados from "./ConsultaCorreosDuplicados.tsx";
import { ENTITY_CONSULT_CONFIGS } from "../utils/entity-configs.ts";

type Mode = "normal" | "inactive" | "duplicates";

export default function UsuariosConsultas() {
  const mode = useSignal<Mode>("normal");
  const usersConfig = ENTITY_CONSULT_CONFIGS.users;

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
          Docentes sin acceso
        </button>
        <button
          type="button"
          onClick={() => mode.value = "duplicates"}
          class={`px-4 py-1.5 rounded-md text-sm font-medium transition ${
            mode.value === "duplicates"
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Correos duplicados
        </button>
      </div>

      {mode.value === "normal"
        ? <TablaConsultaIsland entity="users" {...usersConfig} />
        : mode.value === "inactive"
        ? <ConsultaDocentesSinAcceso />
        : <ConsultaCorreosDuplicados />}
    </div>
  );
}
