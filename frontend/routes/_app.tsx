// routes/_app.tsx
import type { PageProps } from "@fresh/core";
import LimiteError from "../components/LimiteError.tsx";
import ContenedorToast from "../islands/NotificacionIsland.tsx";
import { VARIABLES_TEMA_CLARO, VARIABLES_TEMA_OSCURO } from "../utils/tema.ts";

interface AppState {
  theme?: string;
}

function buildThemeLines(vars: Record<string, string>): string {
  return Object.entries(vars)
    .map(([k, v]) => `r.style.setProperty('${k}','${v}')`)
    .join(";");
}

export default function App({ Component, state }: PageProps<AppState>) {
  const theme = (state as AppState).theme || "dark";

  const darkLines = buildThemeLines(VARIABLES_TEMA_OSCURO);
  const lightLines = buildThemeLines(VARIABLES_TEMA_CLARO);

  const themeScript =
    `(function(){var c=document.cookie.match(/theme=([^;]+)/);var t=c?c[1]:null;if(!t&&typeof localStorage!=='undefined'){t=localStorage.getItem('theme')}var isDark=t!=='light';var r=document.documentElement;if(isDark){${darkLines};r.classList.add('dark');r.classList.remove('light')}else{${lightLines};r.classList.add('light');r.classList.remove('dark')}if(t&&typeof localStorage!=='undefined'){localStorage.setItem('theme',t)}})();`;

  return (
    <html lang="es" class={theme}>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>SIAUGESMAT - Universidad del Tolima</title>
        <meta
          name="description"
          content="Sistema de Integración y Automatización para la Gestión de Matrículas en Moodle"
        />
        <link rel="icon" type="image/x-icon" href="/SIAUGESMAT.ico" />
        <link rel="stylesheet" href="/styles.css" />
        <link rel="stylesheet" href="/main.css" />
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__THEME__="${theme}";`,
          }}
        />
        <script
          dangerouslySetInnerHTML={{
            __html: themeScript,
          }}
        />
      </head>
      <body class="min-h-screen bg-[var(--bg-primary)]">
        <div class="page-enter">
          <LimiteError>
            <Component />
          </LimiteError>
          <ContenedorToast />
        </div>
      </body>
    </html>
  );
}
