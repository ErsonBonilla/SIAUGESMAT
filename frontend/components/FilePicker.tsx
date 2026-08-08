import { useRef } from "preact/hooks";
import type { Signal } from "@preact/signals";
import { XMarkIcon } from "../utils/icons.tsx";

interface FilePickerProps {
  id: string;
  label: string;
  accept: string;
  file: Signal<File | null>;
  onChange: (e: Event) => void;
  onClear?: () => void;
  disabled?: boolean;
}

export default function FilePicker(
  { id, label, accept, file, onChange, onClear, disabled }: FilePickerProps,
) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: Event) => {
    onChange(e);
    (e.currentTarget as HTMLInputElement).value = "";
  };

  const clear = () => {
    file.value = null;
    if (inputRef.current) inputRef.current.value = "";
    onClear?.();
  };

  const hasFile = file.value !== null;

  return (
    <div>
      <label
        for={id}
        class="block text-sm font-medium text-[var(--text-secondary)] mb-2"
      >
        {label}
      </label>
      <div class="flex items-center gap-3">
        <input
          ref={inputRef}
          id={id}
          type="file"
          accept={accept}
          onChange={handleChange}
          disabled={disabled || hasFile}
          class="block w-full text-sm text-[var(--text-muted)] file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-[var(--file-btn-bg)] file:text-[var(--file-btn-text)] hover:file:bg-[var(--file-btn-hover)] transition disabled:opacity-40 disabled:cursor-not-allowed"
        />
        {hasFile && (
          <button
            type="button"
            onClick={clear}
            title="Quitar archivo seleccionado"
            aria-label="Quitar archivo seleccionado"
            class="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-full border border-[var(--border-secondary)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--brand-red)] hover:text-white hover:border-[var(--brand-red)] transition cursor-pointer"
          >
            <XMarkIcon class="w-4 h-4" />
          </button>
        )}
      </div>
      {hasFile && (
        <p class="mt-2 text-xs text-[var(--text-secondary)]">
          Archivo seleccionado:{" "}
          <span class="font-medium text-[var(--text-primary)]">
            {file.value!.name}
          </span>
        </p>
      )}
    </div>
  );
}
