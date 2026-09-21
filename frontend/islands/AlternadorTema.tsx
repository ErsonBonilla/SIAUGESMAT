// islands/AlternadorTema.tsx
import {
  aplicarVariablesTema,
  senalTemaOscuro,
  VARIABLES_TEMA_CLARO,
  VARIABLES_TEMA_OSCURO,
} from "../utils/tema.ts";

export default function AlternadorTema() {
  const handleClick = (e: MouseEvent) => {
    e.stopPropagation();
    const newDark = !senalTemaOscuro.value;
    const root = document.documentElement;
    const vars = newDark ? VARIABLES_TEMA_OSCURO : VARIABLES_TEMA_CLARO;
    aplicarVariablesTema(root, vars);
    root.classList.toggle("dark", newDark);
    root.classList.toggle("light", !newDark);
    localStorage.setItem("theme", newDark ? "dark" : "light");
    const expires = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000)
      .toUTCString();
    document.cookie = `theme=${
      newDark ? "dark" : "light"
    }; expires=${expires}; path=/; SameSite=Lax`;
    senalTemaOscuro.value = newDark;
    (window as unknown as { __THEME__: string }).__THEME__ = newDark
      ? "dark"
      : "light";
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      class="bg-transparent border-none cursor-pointer p-0 flex items-center leading-none"
      title={senalTemaOscuro.value
        ? "Cambiar a modo claro"
        : "Cambiar a modo oscuro"}
    >
      <div
        class={`w-8 h-[18px] rounded-full relative transition-colors duration-200 ease-in-out ${
          senalTemaOscuro.value
            ? "bg-[var(--accent)]"
            : "bg-[var(--text-muted)]"
        }`}
      >
        <div
          class={`w-3.5 h-3.5 rounded-full bg-white absolute top-0.5 left-0.5 shadow-md ${
            senalTemaOscuro.value ? "translate-x-3.5" : "translate-x-0"
          }`}
        />
      </div>
    </button>
  );
}
