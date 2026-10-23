// islands/EjecucionesTabs.tsx
import { useSignal } from "@preact/signals";
import ListaEjecucionesIsland from "./ListaEjecucionesIsland.tsx";
import ListaOperacionesIsland from "./ListaOperacionesIsland.tsx";
import {
  type ClavePestana,
  PESTANAS_OPERACIONES,
} from "../utils/pestanas-operaciones.ts";

const ACTIVE = "bg-[var(--accent)] text-white";
const INACTIVE =
  "border bg-[var(--bg-primary)] border-[var(--border-secondary)] " +
  "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]";

function initialTab(): ClavePestana {
  if (typeof window !== "undefined") {
    const fromUrl = new URLSearchParams(window.location.search).get("tab");
    const match = PESTANAS_OPERACIONES.find((t) => t.key === fromUrl);
    if (match) return match.key as ClavePestana;
  }
  return PESTANAS_OPERACIONES[0].key;
}

export default function EjecucionesTabs() {
  const tab = useSignal<ClavePestana>(initialTab());
  const current = PESTANAS_OPERACIONES.find((t) => t.key === tab.value)!;

  return (
    <>
      <div class="flex flex-wrap gap-2 mb-6">
        {PESTANAS_OPERACIONES.map((t) => (
          <button
            type="button"
            key={t.key}
            onClick={() => tab.value = t.key}
            class={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
              tab.value === t.key ? ACTIVE : INACTIVE
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div class="bg-[var(--bg-primary)] rounded-xl shadow-sm border border-[var(--border-primary)] p-6">
        {current.component === "etl"
          ? <ListaEjecucionesIsland key={current.key} />
          : (
            <ListaOperacionesIsland
              key={current.key}
              entidadPredeterminada={current.entity!}
              accionPredeterminada={current.action!}
            />
          )}
      </div>
    </>
  );
}
