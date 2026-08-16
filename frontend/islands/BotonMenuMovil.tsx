import { mobileOpenSignal } from "../utils/disposicion.ts";
import { IconoBarras, IconoX } from "../utils/iconos.tsx";

export default function BotonMenuMovil() {
  return (
    <button
      type="button"
      class="bg-transparent border-none text-inherit cursor-pointer p-2 -ml-2 flex items-center"
      onClick={() => (mobileOpenSignal.value = !mobileOpenSignal.value)}
      aria-label={mobileOpenSignal.value ? "Cerrar menú" : "Abrir menú"}
    >
      {mobileOpenSignal.value
        ? <IconoX class="w-6 h-6" />
        : <IconoBarras class="w-6 h-6" />}
    </button>
  );
}
