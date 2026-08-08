import { useSignal } from "@preact/signals";
import { login } from "../services/api.ts";
import { setToken } from "../utils/auth.ts";
import {
  BuildingIcon,
  DeviceIcon,
  ExclamationCircleIcon,
} from "../utils/icons.tsx";
import { MODALIDADES } from "../utils/constants.ts";
import Button from "../components/Button.tsx";
import Input from "../components/Input.tsx";

interface LoginFormProps {
  modalidad: string;
  onModalidadChange: (m: string) => void;
}

export default function LoginForm(
  { modalidad, onModalidadChange }: LoginFormProps,
) {
  const username = useSignal("");
  const password = useSignal("");
  const error = useSignal("");
  const loading = useSignal(false);
  const transitioning = useSignal(false);

  const handleSubmit = async (e: Event) => {
    e.preventDefault();
    if (!MODALIDADES.includes(modalidad as typeof MODALIDADES[number])) {
      error.value = "Modalidad no disponible.";
      return;
    }
    if (!username.value.trim() || !password.value.trim()) {
      error.value = "Ingrese su usuario y contraseña.";
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      const data = await login(
        username.value.trim(),
        password.value.trim(),
        modalidad,
      );
      setToken(data.access_token);
      if (typeof window !== "undefined") {
        window.location.href = "/panel";
      }
    } catch (err) {
      let msg = err instanceof Error ? err.message : "";
      if (msg.includes("Failed to fetch")) {
        msg = "Error de conexión. Verifique su red.";
      }
      error.value = msg.includes("Fallo de autenticación")
        ? "Credenciales inválidas"
        : msg || "Error inesperado.";
    } finally {
      loading.value = false;
    }
  };

  const selectModalidad = (m: string) => {
    transitioning.value = true;
    setTimeout(() => {
      onModalidadChange(m);
      transitioning.value = false;
    }, 150);
  };

  const goBack = () => {
    transitioning.value = true;
    setTimeout(() => {
      onModalidadChange("");
      transitioning.value = false;
    }, 150);
  };

  const showPills = modalidad === "" && !transitioning.value;
  const showLogin = modalidad !== "" && !transitioning.value;

  const pillBase =
    "flex items-center gap-2 w-full px-4 py-2.5 rounded-[2rem] border border-[var(--border-secondary)] bg-[var(--bg-primary)] cursor-pointer transition-all duration-200 text-sm";
  const pillHover = "hover:border-[var(--accent)] hover:brightness-95";

  return (
    <form onSubmit={handleSubmit} class="flex flex-col gap-4 w-full">
      {showPills && (
        <div class="login-fadeIn flex flex-col gap-3">
          <button
            type="button"
            onClick={() => selectModalidad("PRESENCIAL")}
            class={`${pillBase} ${pillHover}`}
          >
            <BuildingIcon
              class="w-5 h-5 shrink-0"
              style={{ color: "var(--brand-red)" }}
            />
            <span class="font-semibold text-[var(--text-primary)]">
              PRESENCIAL
            </span>
          </button>

          <button
            type="button"
            onClick={() => selectModalidad("DISTANCIA")}
            class={`${pillBase} ${pillHover}`}
          >
            <DeviceIcon
              class="w-5 h-5 shrink-0"
              style={{ color: "var(--brand-red)" }}
            />
            <span class="font-semibold text-[var(--text-primary)]">
              DISTANCIA
            </span>
          </button>

          <p class="text-center text-xs text-[var(--text-muted)] -mt-2">
            Seleccioná tu modalidad para continuar
          </p>
        </div>
      )}

      {transitioning.value && (
        <div class="flex justify-center py-6">
          <span class="w-6 h-6 rounded-full border-2 border-[var(--border-secondary)] border-t-[var(--accent)] animate-spin" />
        </div>
      )}

      {showLogin && (
        <div class="login-fadeIn flex flex-col gap-4">
          <Input
            label="Usuario"
            type="text"
            placeholder="ej. juan.perez"
            value={username.value}
            disabled={loading.value}
            autocomplete="username"
            onInput={(
              e,
            ) => (username.value = (e.target as HTMLInputElement).value)}
          />

          <Input
            label="Contraseña"
            type="password"
            placeholder="••••••••"
            value={password.value}
            disabled={loading.value}
            autocomplete="current-password"
            onInput={(
              e,
            ) => (password.value = (e.target as HTMLInputElement).value)}
          />

          {error.value && (
            <div class="error-msg error-msg--center">
              <ExclamationCircleIcon />
              <span>{error.value}</span>
            </div>
          )}

          <Button
            variant="gradient"
            type="submit"
            loading={loading.value}
            style={{ width: "100%" }}
          >
            Iniciar sesión
          </Button>

          <Button variant="ghost" type="button" onClick={goBack}>
            ← Cambiar modalidad
          </Button>
        </div>
      )}
    </form>
  );
}
