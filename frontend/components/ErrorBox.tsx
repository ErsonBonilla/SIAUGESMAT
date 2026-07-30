// components/ErrorBox.tsx
import { ExclamationCircleIcon } from "../utils/icons.tsx";

interface Props {
  message: string;
}

export default function ErrorBox({ message }: Props) {
  return (
    <div class="flex items-center gap-1.5 text-xs text-[var(--brand-red)]">
      <ExclamationCircleIcon
        style={{ width: "0.75rem", height: "0.75rem", flexShrink: 0 }}
      />
      <span>{message}</span>
    </div>
  );
}
