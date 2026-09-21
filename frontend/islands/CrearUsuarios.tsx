import { useSignal } from "@preact/signals";
import SubirCsv from "./CsvUploader.tsx";
import BotonEjecucion from "../components/BotonEjecucion.tsx";

type RolUsuario = "student" | "editingteacher" | "all";

const ROLE_CONFIG = {
  student: {
    endpoint: "users/create-csv?default_role=student",
    label: "Estudiantes",
    desc: "Crear estudiantes",
    help: "para crear estudiantes en Moodle (rol student).",
  },
  editingteacher: {
    endpoint: "users/create-csv?default_role=editingteacher",
    label: "Profesores",
    desc: "Crear profesores",
    help: "para crear profesores en Moodle (rol editingteacher).",
  },
  all: {
    endpoint: "users/create-csv",
    label: "General",
    desc: "Crear usuarios",
    help:
      "para crear usuarios en Moodle. El CSV debe incluir la columna 'role1' (student, editingteacher, teacher, manager o su ID: 1,3,4,5) y opcionalmente 'forcepasswordchange' (1/0).",
  },
};

export default function CrearUsuarios() {
  const role = useSignal<RolUsuario>("student");

  const config = ROLE_CONFIG[role.value];

  return (
    <div>
      <div class="flex flex-col sm:flex-row gap-2 mb-4">
        {(Object.keys(ROLE_CONFIG) as RolUsuario[]).map((r) => (
          <label
            key={r}
            class={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition text-sm font-medium ${
              role.value === r
                ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                : "bg-[var(--bg-primary)] text-[var(--text-primary)] border-[var(--border-secondary)] hover:bg-[var(--bg-tertiary)]"
            }`}
          >
            <input
              type="radio"
              name="userRole"
              value={r}
              checked={role.value === r}
              onChange={() => (role.value = r)}
              class="hidden"
            />
            <span>{ROLE_CONFIG[r].label}</span>
          </label>
        ))}
      </div>

      <SubirCsv
        description={`Subí un archivo CSV con las columnas 'username', 'firstname', 'lastname' y 'email' ${config.help}`}
        uploadEndpoint={config.endpoint}
        etiquetaSingular="usuario"
        etiquetaPlural="usuarios"
        action="create"
        help={[
          {
            title: "Archivo CSV requerido",
            body: [
              "Columnas obligatorias: username, firstname, lastname y email.",
              ...(role.value === "all"
                ? [
                  "Rol (opcional): role1 con 'student', 'editingteacher', 'teacher', 'manager' o su ID (1,3,4,5).",
                  "Opcional: forcepasswordchange (1/0).",
                ]
                : role.value === "editingteacher"
                ? ["Los usuarios se crean con rol editingteacher."]
                : ["Los usuarios se crean con rol student."]),
            ],
          },
        ]}
      />
      <BotonEjecucion tab="crear_usuarios" />
    </div>
  );
}
