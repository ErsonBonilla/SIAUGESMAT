import { signal } from "@preact/signals-core";

export type TipoToast = "success" | "error" | "info";

export interface ItemToast {
  id: number;
  message: string;
  type: TipoToast;
}

const toasts = signal<ItemToast[]>([]);
let nextId = 1;

export function toast(message: string, type: TipoToast = "info") {
  const id = nextId++;
  toasts.value = [...toasts.value, { id, message, type }];
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }, 4000);
}

export function descartarToast(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
}

export { toasts };
