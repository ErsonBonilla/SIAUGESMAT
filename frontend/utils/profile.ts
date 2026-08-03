// utils/profile.ts
import { signal } from "@preact/signals";
import type { UserProfile } from "../services/api.ts";

export const profileSignal = signal<UserProfile | null>(null);

let fetchPromise: Promise<void> | null = null;

export function ensureProfile(fetcher: () => Promise<UserProfile>) {
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
