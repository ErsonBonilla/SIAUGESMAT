import type { DepartamentoObservatorio } from "../services/api.ts";
import {
  pluralizarConteo,
  type ResumenMunicipioMapa,
} from "../utils/observatorio.ts";

export interface GeometriaDepartamento {
  code: string;
  name: string;
  d: string;
  cx: number;
  cy: number;
}

export interface GeometriaMunicipio {
  code: string;
  dpto_code: string;
  name: string;
  d: string;
  cx: number;
  cy: number;
}

export interface DatosMapaColombia {
  viewBox: string;
  insetBox: {
    x: number;
    y: number;
    width: number;
    height: number;
    label: string;
  };
  departments: GeometriaDepartamento[];
  municipalities: Record<string, GeometriaMunicipio>;
}

interface PropsMapaColombia {
  mapa: DatosMapaColombia;
  departamentosPorCodigo: Map<string, DepartamentoObservatorio>;
  resumenMunicipiosMapa: ResumenMunicipioMapa[];
  dptoSeleccionado: string | null;
  mpioSeleccionado: string | null;
  tooltipTexto: string;
  onHoverTexto: (texto: string) => void;
  onSeleccionarDpto: (dptoCode: string) => void;
  onSeleccionarMpio: (dptoCode: string, mpioCode: string) => void;
}

function etiquetaDepartamento(
  nombre: string,
  info: DepartamentoObservatorio | undefined,
): string {
  if (!info) return `${nombre}: Sin presencia IDEAD`;
  return `${nombre}: ${pluralizarConteo(info.cats_count, "CAT", "CATs")} · ${
    pluralizarConteo(info.students_count, "estudiante", "estudiantes")
  }`;
}

function activarConTeclado(e: KeyboardEvent, accion: () => void) {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    accion();
  }
}

function PathDepartamento({
  dpto,
  info,
  seleccionado,
  onHoverTexto,
  onSeleccionarDpto,
}: {
  dpto: GeometriaDepartamento;
  info: DepartamentoObservatorio | undefined;
  seleccionado: boolean;
  onHoverTexto: (texto: string) => void;
  onSeleccionarDpto: (dptoCode: string) => void;
}) {
  const activo = Boolean(info);
  const fill = activo ? "#ED3237" : "#FFFFFF";
  const stroke = seleccionado ? "#FACC15" : activo ? "#FFFFFF" : "#CBD5E1";
  const strokeWidth = seleccionado ? "2.4" : activo ? "1.2" : "0.9";
  const etiqueta = etiquetaDepartamento(dpto.name, info);

  return (
    <path
      d={dpto.d}
      fill={fill}
      fillOpacity={activo ? (seleccionado ? "1" : "0.9") : "1"}
      stroke={stroke}
      strokeWidth={strokeWidth}
      tabIndex={activo ? 0 : undefined}
      role={activo ? "button" : undefined}
      aria-label={etiqueta}
      class={activo
        ? "cursor-pointer transition-opacity duration-150 hover:opacity-100 focus:outline-none"
        : "transition-opacity duration-150"}
      onMouseEnter={() => onHoverTexto(etiqueta)}
      onMouseLeave={() => onHoverTexto("")}
      onClick={() => {
        if (activo) onSeleccionarDpto(dpto.code);
      }}
      onKeyDown={(e) => {
        if (activo) activarConTeclado(e, () => onSeleccionarDpto(dpto.code));
      }}
    >
      <title>{etiqueta}</title>
    </path>
  );
}

export default function MapaColombiaSvg({
  mapa,
  departamentosPorCodigo,
  resumenMunicipiosMapa,
  dptoSeleccionado,
  mpioSeleccionado,
  tooltipTexto,
  onHoverTexto,
  onSeleccionarDpto,
  onSeleccionarMpio,
}: PropsMapaColombia) {
  const municipiosConGeometria = resumenMunicipiosMapa
    .map((item) => ({ item, geom: mapa.municipalities[item.mpioCode] }))
    .filter((
      x,
    ): x is { item: ResumenMunicipioMapa; geom: GeometriaMunicipio } =>
      Boolean(x.geom)
    );

  return (
    <div class="relative flex flex-col items-center justify-between h-full">
      <div class="w-full flex items-center justify-between mb-2 px-1">
        <span class="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          Presencia Territorial IDEAD
        </span>
        <span class="text-xs font-medium text-[var(--text-secondary)] min-h-[1.25rem]">
          {tooltipTexto ||
            "Pasa el cursor o haz clic sobre un departamento o CAT"}
        </span>
      </div>

      <div class="w-full flex-1 flex items-center justify-center bg-slate-100/80 dark:bg-slate-900/60 rounded-xl border border-[var(--border-primary)] p-2 overflow-hidden">
        <svg
          viewBox={mapa.viewBox}
          class="w-full h-auto max-h-[640px] select-none"
          role="group"
          aria-label="Mapa del Observatorio IDEAD Colombia"
        >
          <rect
            x={mapa.insetBox.x}
            y={mapa.insetBox.y}
            width={mapa.insetBox.width}
            height={mapa.insetBox.height}
            rx="8"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="1.2"
            strokeDasharray="4 3"
          />
          <text
            x={mapa.insetBox.x + 6}
            y={mapa.insetBox.y + 14}
            fill="#64748B"
            fontSize="9.5"
            fontWeight="600"
          >
            {mapa.insetBox.label}
          </text>

          <g>
            {mapa.departments.map((dpto) => (
              <PathDepartamento
                key={dpto.code}
                dpto={dpto}
                info={departamentosPorCodigo.get(dpto.code)}
                seleccionado={dptoSeleccionado === dpto.code}
                onHoverTexto={onHoverTexto}
                onSeleccionarDpto={onSeleccionarDpto}
              />
            ))}
          </g>

          <g>
            {municipiosConGeometria.map(({ item, geom }) => {
              const sel = mpioSeleccionado === item.mpioCode;
              return (
                <path
                  key={`poly-${item.mpioCode}`}
                  d={geom.d}
                  fill="#00A859"
                  stroke={sel ? "#FACC15" : "#FFFFFF"}
                  strokeWidth={sel ? "2.0" : "0.9"}
                  class="cursor-pointer transition-transform duration-150"
                  onMouseEnter={() => onHoverTexto(item.etiquetaTooltip)}
                  onMouseLeave={() => onHoverTexto("")}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeleccionarMpio(item.dptoCode, item.mpioCode);
                  }}
                >
                  <title>{item.etiquetaTooltip}</title>
                </path>
              );
            })}
          </g>

          <g>
            {municipiosConGeometria.map(({ item, geom }) => {
              const sel = mpioSeleccionado === item.mpioCode;
              return (
                <g
                  key={`pin-${item.mpioCode}`}
                  class="cursor-pointer focus:outline-none"
                  tabIndex={0}
                  role="button"
                  aria-label={item.etiquetaTooltip}
                  onMouseEnter={() => onHoverTexto(item.etiquetaTooltip)}
                  onMouseLeave={() => onHoverTexto("")}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeleccionarMpio(item.dptoCode, item.mpioCode);
                  }}
                  onKeyDown={(e) => {
                    e.stopPropagation();
                    activarConTeclado(
                      e,
                      () => onSeleccionarMpio(item.dptoCode, item.mpioCode),
                    );
                  }}
                >
                  <circle
                    cx={geom.cx}
                    cy={geom.cy}
                    r={sel ? "7.5" : "5.2"}
                    fill="#00A859"
                    stroke={sel ? "#FACC15" : "#FFFFFF"}
                    strokeWidth="2.0"
                  />
                  <title>{item.etiquetaTooltip}</title>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      <div class="w-full flex flex-wrap items-center justify-center gap-5 mt-3 pt-2 text-xs text-[var(--text-secondary)]">
        <div class="flex items-center gap-2">
          <span
            class="inline-block w-3.5 h-3.5 rounded-sm border border-[var(--border-secondary)]"
            style={{ backgroundColor: "#FFFFFF" }}
          />
          <span>Departamento sin presencia</span>
        </div>
        <div class="flex items-center gap-2">
          <span
            class="inline-block w-3.5 h-3.5 rounded-sm"
            style={{ backgroundColor: "#ED3237" }}
          />
          <span>Departamento con presencia IDEAD</span>
        </div>
        <div class="flex items-center gap-2">
          <span
            class="inline-block w-3.5 h-3.5 rounded-full border border-white shadow-sm"
            style={{ backgroundColor: "#00A859" }}
          />
          <span>Ciudad / Municipio sede CAT</span>
        </div>
      </div>
    </div>
  );
}
