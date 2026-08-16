// components/CajaError.tsx
import { IconoCirculoExclamacion } from "../utils/iconos.tsx";

interface Props {
  message: string;
}

export default function CajaError({ message }: Props) {
  return (
    <div class="flex items-center gap-1.5 text-xs text-[var(--brand-red)]">
      <IconoCirculoExclamacion
        style={{ width: "0.75rem", height: "0.75rem", flexShrink: 0 }}
      />
      <span>{message}</span>
    </div>
  );
}
