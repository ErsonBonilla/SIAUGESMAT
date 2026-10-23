// utils/perfil.ts
import { signal } from "@preact/signals";
import type { PerfilUsuario } from "../services/api.ts";

export const senalPerfil = signal<PerfilUsuario | null>(null);

let fetchPromise: Promise<void> | null = null;

export function garantizarPerfil(fetcher: () => Promise<PerfilUsuario>) {
  if (senalPerfil.value) return;
  if (fetchPromise) return fetchPromise;
  fetchPromise = fetcher().then((p) => {
    senalPerfil.value = p;
  }).catch(() => {
    // no-op
  }).finally(() => {
    fetchPromise = null;
  });
  return fetchPromise;
}
