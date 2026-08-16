// utils/profile.ts
import { signal } from "@preact/signals";
import type { PerfilUsuario } from "../services/api.ts";

export const profileSignal = signal<PerfilUsuario | null>(null);

let fetchPromise: Promise<void> | null = null;

export function garantizarPerfil(fetcher: () => Promise<PerfilUsuario>) {
  if (profileSignal.value) return;
  if (fetchPromise) return fetchPromise;
  fetchPromise = fetcher().then((p) => {
    profileSignal.value = p;
  }).catch(() => {
    // no-op
  }).finally(() => {
    fetchPromise = null;
  });
  return fetchPromise;
}
