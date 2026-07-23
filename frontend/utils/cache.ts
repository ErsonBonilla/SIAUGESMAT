import { signal } from "@preact/signals";
import type { UserProfile, LatestExecution } from "../services/api.ts";

const CACHE_TTL = 30_000;

interface CacheEntry<T> {
  data: T | null;
  timestamp: number;
}

function createCache<T>(storageKey?: string, ttlMs = CACHE_TTL) {
  let initial: CacheEntry<T> = { data: null, timestamp: 0 };
  if (storageKey && typeof localStorage !== "undefined") {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as CacheEntry<T>;
        if (Date.now() - parsed.timestamp < ttlMs) {
          initial = parsed;
        }
      }
    } catch { /* ignore */ }
  }

  const entry = signal<CacheEntry<T>>(initial);

  return {
    signal: entry,
    get: () => entry.value.data,
    hasData: () => entry.value.data !== null,
    set: (data: T) => {
      const newEntry: CacheEntry<T> = { data, timestamp: Date.now() };
      entry.value = newEntry;
      if (storageKey && typeof localStorage !== "undefined") {
        try { localStorage.setItem(storageKey, JSON.stringify(newEntry)); } catch { /* ignore */ }
      }
    },
    isValid: () => Date.now() - entry.value.timestamp < ttlMs,
  };
}

export const profileCache = createCache<UserProfile>("profile_cache", 300_000);
export const latestExecutionCache = createCache<LatestExecution>();
