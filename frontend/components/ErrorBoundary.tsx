import { Component, type ComponentChildren } from "preact";

interface ErrorBoundaryProps {
  children: ComponentChildren;
  fallback?: ComponentChildren;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { hasError: false, error: null };

  static override getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error) {
    console.error("ErrorBoundary caught:", error);
  }

  override render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div class="flex flex-col items-center justify-center gap-2 p-6 text-center">
          <span class="text-lg">⚠️</span>
          <p class="text-sm font-medium text-[var(--brand-red)]">Algo salió mal</p>
          <p class="text-xs text-[var(--text-secondary)]">{this.state.error?.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
