import { useSignal } from "@preact/signals";
import QueryTable from "./QueryTable.tsx";
import InactiveTeachersQuery from "./InactiveTeachersQuery.tsx";
import { ENTITY_CONSULT_CONFIGS } from "../utils/entity-configs.ts";

type Mode = "normal" | "inactive";

export default function UsuariosConsultas() {
  const mode = useSignal<Mode>("normal");
  const usersConfig = ENTITY_CONSULT_CONFIGS.users;

  return (
    <div class="max-w-6xl mx-auto">
      <div class="flex gap-1 mb-6 bg-[var(--bg-tertiary)] rounded-lg p-1 w-fit">
        <button
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
          onClick={() => mode.value = "inactive"}
          class={`px-4 py-1.5 rounded-md text-sm font-medium transition ${
            mode.value === "inactive"
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Docentes sin acceso
        </button>
      </div>

      {mode.value === "normal"
        ? <QueryTable entity="users" {...usersConfig} />
        : <InactiveTeachersQuery />}
    </div>
  );
}
