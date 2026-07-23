import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { toasts, dismissToast } from "../utils/toast.ts";
import { CheckIcon, XMarkIcon } from "../utils/icons.tsx";

export default function ToastContainer() {
  const mounted = useSignal(false);

  useEffect(() => {
    mounted.value = true;
  }, []);

  if (!mounted.value) return null;

  return (
    <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 min-w-[280px]">
      {toasts.value.map((t) => (
        <div
          key={t.id}
          class={`flex items-start gap-2 px-4 py-3 rounded-lg shadow-lg text-sm animate-fadeIn ${
            t.type === "success" ? "bg-[var(--brand-green)] text-white"
              : t.type === "error" ? "bg-[var(--brand-red)] text-white"
              : "bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-secondary)]"
          }`}
        >
          {t.type === "success" && <CheckIcon class="w-4 h-4 shrink-0 mt-0.5" />}
          {t.type === "error" && <XMarkIcon class="w-4 h-4 shrink-0 mt-0.5" />}
          <span class="flex-1 text-xs leading-relaxed">{t.message}</span>
          <button
            type="button"
            onClick={() => dismissToast(t.id)}
            class="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
          >
            <XMarkIcon class="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
