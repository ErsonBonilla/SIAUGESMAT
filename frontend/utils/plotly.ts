// utils/plotly.ts
// Carga perezosa de Plotly.js desde CDN. Llamar loadPlotly() antes de newPlot().

declare global {
  interface Window {
    Plotly: {
      newPlot(
        el: HTMLElement,
        traces: unknown[],
        layout: Record<string, unknown>,
        config?: Record<string, unknown>,
      ): void;
      purge(el: HTMLElement): void;
    };
  }
}

let plotlyLoaded = false;
let plotlyLoading: Promise<void> | null = null;

export function loadPlotly(): Promise<void> {
  if (plotlyLoaded) return Promise.resolve();
  if (plotlyLoading) return plotlyLoading;
  plotlyLoading = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdn.plot.ly/plotly-3.0.1.min.js";
    script.onload = () => {
      plotlyLoaded = true;
      resolve();
    };
    script.onerror = () => {
      plotlyLoading = null;
      reject(new Error("No se pudo cargar Plotly.js"));
    };
    document.head.appendChild(script);
  });
  return plotlyLoading;
}
