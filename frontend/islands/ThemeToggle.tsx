// islands/ThemeToggle.tsx
import {
  applyThemeVars,
  DARK_THEME_VARS,
  darkSignal,
  LIGHT_THEME_VARS,
} from "../utils/theme.ts";

export default function ThemeToggle() {
  const handleClick = (e: MouseEvent) => {
    e.stopPropagation();
    const newDark = !darkSignal.value;
    const root = document.documentElement;
    const vars = newDark ? DARK_THEME_VARS : LIGHT_THEME_VARS;
    applyThemeVars(root, vars);
    root.classList.toggle("dark", newDark);
    root.classList.toggle("light", !newDark);
    localStorage.setItem("theme", newDark ? "dark" : "light");
    const expires = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000)
      .toUTCString();
    document.cookie = `theme=${
      newDark ? "dark" : "light"
    }; expires=${expires}; path=/; SameSite=Lax`;
    darkSignal.value = newDark;
    (window as unknown as { __THEME__: string }).__THEME__ = newDark
      ? "dark"
      : "light";
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      class="bg-transparent border-none cursor-pointer p-0 flex items-center leading-none"
      title={darkSignal.value
        ? "Cambiar a modo claro"
        : "Cambiar a modo oscuro"}
    >
      <div
        class={`w-8 h-[18px] rounded-full relative transition-colors duration-200 ease-in-out ${
          darkSignal.value ? "bg-[var(--accent)]" : "bg-[var(--text-muted)]"
        }`}
      >
        <div
          class={`w-3.5 h-3.5 rounded-full bg-white absolute top-0.5 left-0.5 shadow-md ${
            darkSignal.value ? "translate-x-3.5" : "translate-x-0"
          }`}
        />
      </div>
    </button>
  );
}
