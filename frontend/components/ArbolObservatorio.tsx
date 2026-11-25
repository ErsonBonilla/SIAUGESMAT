import type {
  DepartamentoObservatorio,
  MunicipioCatObservatorio,
  ProgramaObservatorio,
} from "../services/api.ts";
import {
  claveCat,
  filtrarDepartamentosObservatorio,
  pluralizarConteo,
} from "../utils/observatorio.ts";

interface PropsArbolObservatorio {
  departamentos: DepartamentoObservatorio[];
  dptosAbiertos: Set<string>;
  catsAbiertos: Set<string>;
  busqueda: string;
  onToggleDpto: (dptoCode: string) => void;
  onToggleCat: (claveCat: string, dptoCode: string, mpioCode: string) => void;
  onExpandirTodo: () => void;
  onColapsarTodo: () => void;
}

function FilaProgramaArbol({ prog }: { prog: ProgramaObservatorio }) {
  return (
    <div class="flex items-center justify-between px-2.5 py-1.5 rounded text-xs bg-[var(--bg-secondary)]/60 hover:bg-[var(--bg-tertiary)] transition-colors">
      <div class="min-w-0 pr-2">
        <span class="font-medium text-[var(--text-primary)] block truncate">
          {prog.program_name}
        </span>
        <span class="text-[0.6875rem] text-[var(--text-muted)] font-mono">
          Código {prog.program_code} · {pluralizarConteo(
            prog.courses_count,
            "curso activo",
            "cursos activos",
          )}
        </span>
      </div>
      <span class="px-2 py-0.5 rounded-md font-semibold bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-[var(--border-secondary)] shrink-0">
        {pluralizarConteo(prog.students_count, "Estudiante", "Estudiantes")}
      </span>
    </div>
  );
}

function ItemMunicipioArbol({
  mpio,
  dptoCode,
  abierto,
  onToggleCat,
}: {
  mpio: MunicipioCatObservatorio;
  dptoCode: string;
  abierto: boolean;
  onToggleCat: (claveCat: string, dptoCode: string, mpioCode: string) => void;
}) {
  const clave = claveCat(mpio);
  return (
    <div class="py-1">
      <button
        type="button"
        aria-expanded={abierto}
        onClick={() => onToggleCat(clave, dptoCode, mpio.mpio_code)}
        class="w-full flex items-center justify-between px-2.5 py-2 rounded-md text-left hover:bg-[var(--bg-tertiary)] transition-colors cursor-pointer border-none bg-transparent"
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class="text-xs text-[var(--text-secondary)] w-3 inline-block">
            {abierto ? "▾" : "▸"}
          </span>
          <span
            class="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ backgroundColor: "#00A859" }}
          />
          <span class="font-medium text-sm text-[var(--text-primary)] truncate">
            {mpio.display_name}
          </span>
          <span class="text-xs text-[var(--text-muted)] font-mono">
            ({mpio.cat_shortname})
          </span>
        </div>
        <span
          class="px-2.5 py-0.5 rounded-full text-xs font-semibold text-white shrink-0"
          style={{ backgroundColor: "#00A859" }}
        >
          {pluralizarConteo(mpio.programs_count, "Programa", "Programas")}
        </span>
      </button>

      {abierto && (
        <div class="mt-1 ml-6 pl-3 border-l-2 border-[var(--border-secondary)] space-y-1 py-1">
          {mpio.programs.map((prog) => (
            <FilaProgramaArbol key={prog.program_code} prog={prog} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ArbolObservatorio({
  departamentos,
  dptosAbiertos,
  catsAbiertos,
  busqueda,
  onToggleDpto,
  onToggleCat,
  onExpandirTodo,
  onColapsarTodo,
}: PropsArbolObservatorio) {
  const hayFiltro = Boolean(busqueda.trim());
  const departamentosFiltrados = filtrarDepartamentosObservatorio(
    departamentos,
    busqueda,
  );

  if (departamentos.length === 0) {
    return (
      <div class="py-10 text-center text-sm text-[var(--text-secondary)]">
        Aún no hay datos de cursos activos en el Observatorio. Presiona
        "Actualizar" para sincronizar con Moodle.
      </div>
    );
  }

  if (departamentosFiltrados.length === 0) {
    return (
      <div class="py-10 text-center text-sm text-[var(--text-secondary)]">
        No se encontraron departamentos, municipios (CAT) ni programas que
        coincidan con la búsqueda.
      </div>
    );
  }

  return (
    <div class="flex flex-col gap-2">
      <div class="flex items-center justify-between text-xs text-[var(--text-secondary)] px-1 mb-1">
        <span>
          Estructura: <strong>Departamento</strong> →{" "}
          <strong>Municipio (CAT)</strong> → <strong>Programa</strong>
        </span>
        {!hayFiltro && (
          <div class="flex items-center gap-2">
            <button
              type="button"
              onClick={onExpandirTodo}
              class="bg-transparent border-none text-[var(--accent)] hover:underline cursor-pointer text-xs p-0 font-medium"
            >
              Expandir todo
            </button>
            <span>·</span>
            <button
              type="button"
              onClick={onColapsarTodo}
              class="bg-transparent border-none text-[var(--text-secondary)] hover:underline cursor-pointer text-xs p-0"
            >
              Colapsar
            </button>
          </div>
        )}
      </div>

      <div class="space-y-2 max-h-[540px] overflow-y-auto pr-1">
        {departamentosFiltrados.map((dpto) => {
          const abiertoDpto = hayFiltro || dptosAbiertos.has(dpto.dpto_code);
          return (
            <div
              key={dpto.dpto_code}
              class="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] overflow-hidden"
            >
              <button
                type="button"
                aria-expanded={abiertoDpto}
                onClick={() => onToggleDpto(dpto.dpto_code)}
                class="w-full flex items-center justify-between px-3.5 py-2.5 text-left bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors cursor-pointer border-none"
              >
                <div class="flex items-center gap-2.5 min-w-0">
                  <span class="text-xs text-[var(--text-secondary)] w-3 inline-block">
                    {abiertoDpto ? "▾" : "▸"}
                  </span>
                  <span
                    class="w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: "#ED3237" }}
                  />
                  <span class="font-semibold text-sm text-[var(--text-primary)] truncate">
                    {dpto.dpto_name}
                  </span>
                </div>
                <span
                  class="px-2.5 py-0.5 rounded-full text-xs font-semibold text-white shrink-0"
                  style={{ backgroundColor: "#ED3237" }}
                >
                  {pluralizarConteo(dpto.cats_count, "CAT", "CATs")}
                </span>
              </button>

              {abiertoDpto && (
                <div class="divide-y divide-[var(--border-primary)] pl-4 pr-2 py-1.5 bg-[var(--bg-primary)]">
                  {dpto.municipalities.map((mpio) => {
                    const clave = claveCat(mpio);
                    return (
                      <ItemMunicipioArbol
                        key={clave}
                        mpio={mpio}
                        dptoCode={dpto.dpto_code}
                        abierto={hayFiltro || catsAbiertos.has(clave)}
                        onToggleCat={onToggleCat}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
