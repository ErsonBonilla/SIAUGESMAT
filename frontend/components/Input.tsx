import type { JSX } from "preact";
import { useSignal } from "@preact/signals";
import { EyeIcon, EyeOffIcon } from "../utils/icons.tsx";

interface InputProps {
  label?: string;
  type?: "text" | "password" | "email";
  placeholder?: string;
  value?: string;
  error?: string;
  disabled?: boolean;
  autocomplete?: string;
  onInput?: (e: JSX.TargetedEvent<HTMLInputElement, Event>) => void;
}

export default function Input(
  {
    label,
    type = "text",
    placeholder,
    value,
    error,
    disabled,
    autocomplete,
    onInput,
  }: InputProps,
) {
  const showPassword = useSignal(false);
  const isPassword = type === "password";
  const actualType = isPassword && showPassword.value ? "text" : type;

  return (
    <div class="flex flex-col gap-1">
      {label && (
        <label class="text-xs font-medium text-[var(--text-primary)]">
          {label}
        </label>
      )}
      <div class="relative w-full">
        <input
          type={actualType}
          class="w-full block bg-[var(--bg-primary)] text-[var(--text-primary)] border-2 border-[var(--border-secondary)] rounded-lg px-3 py-2.5 text-sm leading-5 transition-all duration-200 outline-none focus:border-[var(--accent)] focus:shadow-[0_0_0_3px_rgba(var(--accent-rgb),0.15)] disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-[var(--text-muted)]"
          style={isPassword ? { paddingRight: "2.5rem" } : undefined}
          placeholder={placeholder}
          value={value}
          onInput={onInput}
          disabled={disabled}
          autocomplete={autocomplete}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => (showPassword.value = !showPassword.value)}
            tabIndex={-1}
            class="absolute top-1/2 -translate-y-1/2 right-3 bg-transparent border-0 cursor-pointer p-1 text-[var(--text-primary)] opacity-70 flex items-center justify-center leading-none"
            title={showPassword.value
              ? "Ocultar contraseña"
              : "Mostrar contraseña"}
          >
            {showPassword.value
              ? <EyeOffIcon width={20} height={20} />
              : <EyeIcon width={20} height={20} />}
          </button>
        )}
      </div>
      {error && <span class="text-xs text-[var(--brand-red)]">{error}</span>}
    </div>
  );
}
