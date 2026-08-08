import { mobileOpenSignal } from "../utils/layout.ts";
import { Bars3Icon, XMarkIcon } from "../utils/icons.tsx";

export default function MobileMenuButton() {
  return (
    <button
      type="button"
      class="bg-transparent border-none text-inherit cursor-pointer p-2 -ml-2 flex items-center"
      onClick={() => (mobileOpenSignal.value = !mobileOpenSignal.value)}
      aria-label={mobileOpenSignal.value ? "Cerrar menú" : "Abrir menú"}
    >
      {mobileOpenSignal.value
        ? <XMarkIcon class="w-6 h-6" />
        : <Bars3Icon class="w-6 h-6" />}
    </button>
  );
}
