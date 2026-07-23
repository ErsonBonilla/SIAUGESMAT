// islands/LoginPageIsland.tsx
import { useComputed, useSignal } from "@preact/signals";
import LoginForm from "./LoginForm.tsx";
import ThemeToggle from "./ThemeToggle.tsx";
import { darkSignal } from "../utils/theme.ts";

export default function LoginPageIsland() {
  const outerBg = useComputed(() => darkSignal.value ? "#111827" : "#F3F4F6");
  const circleWhiteBg = useComputed(() => darkSignal.value ? "#F9FAFB" : "#FFFFFF");
  const modalidad = useSignal("");

  const footerText = () => {
    switch (modalidad.value) {
      case "PRESENCIAL":
        return "Tu Aula Media";
      case "DISTANCIA":
        return "Tu Aula Virtual";
      default:
        return "Tu Aula";
    }
  };

  return (
    <div
      class="min-h-screen flex items-center justify-center px-4 relative"
      style={{
        backgroundColor: outerBg.value,
      }}
    >
      <div class="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div class="w-full max-w-md bg-[var(--bg-primary)] rounded-2xl shadow-lg border border-[var(--border-primary)] p-8">
        <div class="text-center">
          <h1 class="text-3xl font-bold gradient-text" style={{ letterSpacing: "-0.02em" }}>
            SIAUGESMAT
          </h1>
          <p class="text-xs mt-3 text-[var(--text-secondary)]" style={{ lineHeight: 1.4, maxWidth: "20rem", margin: "0.75rem auto 0" }}>
            Sistema de Automatización para la Gestión de Matrículas
          </p>
          <p class="text-[0.65rem] italic opacity-60 mt-0.5 text-[var(--text-secondary)]">
            Cursos Semestrales
          </p>
          <div class="w-12 h-px bg-[var(--border-secondary)] mx-auto my-4" />
          <p class="text-xs font-semibold text-[var(--brand-red)]">
            Universidad del Tolima
          </p>
          <div class="mt-4 flex justify-center gap-2.5">
            <span class="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "var(--brand-red)" }} />
            <span class="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "var(--brand-green)" }} />
            <span
              class="inline-block w-2.5 h-2.5 rounded-full border"
              style={{ backgroundColor: circleWhiteBg.value, borderColor: "var(--border-secondary)" }}
            />
          </div>
        </div>

        <div class="mt-6">
          <LoginForm modalidad={modalidad.value} onModalidadChange={(m) => (modalidad.value = m)} />

          <p class="text-xs mt-6 text-center text-[var(--text-secondary)]">
            Acceda con sus credenciales de{" "}
            <span class="font-medium" style={{ color: "var(--brand-red)" }}>
              {footerText()}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
