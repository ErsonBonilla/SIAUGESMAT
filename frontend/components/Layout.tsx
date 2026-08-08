// components/Layout.tsx
import { ComponentChildren } from "preact";
import BarraLateral from "../islands/BarraLateral.tsx";
import BotonMenuMovil from "../islands/BotonMenuMovil.tsx";
import { profileSignal } from "../utils/profile.ts";

interface LayoutProps {
  children: ComponentChildren;
  title?: string;
}

export default function Layout({ children, title }: LayoutProps) {
  return (
    <div class="flex min-h-screen w-full text-[var(--text-primary)]">
      <BarraLateral />

      {/* Top bar �?" solo visible en mobile */}
      <div class="md:hidden h-14 flex items-center px-4 sticky top-0 z-20 border-b border-[var(--border-secondary)] bg-[var(--navbar-bg)] text-[var(--navbar-text)]">
        <BotonMenuMovil />
        <span class="text-base font-bold ml-2">SIAUGESMAT</span>
        <div class="ml-auto flex items-center gap-2">
          {profileSignal.value?.profileimageurl
            ? (
              <img
                src={profileSignal.value.profileimageurl}
                alt=""
                class="w-8 h-8 rounded-full object-cover"
              />
            )
            : (
              <div
                class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0"
                style={{
                  backgroundColor: "var(--navbar-user-bg)",
                  color: "var(--navbar-user-text)",
                }}
              >
                {profileSignal.value?.firstname?.charAt(0).toUpperCase() || "U"}
              </div>
            )}
        </div>
      </div>

      <div class="flex-1 ml-0 md:ml-[220px] min-w-0 flex flex-col">
        <main class="flex-1 w-full max-w-5xl mx-auto px-4 md:px-8 py-6 md:py-10">
          {title && <h1 class="text-2xl font-bold mb-6">{title}</h1>}
          {children}
        </main>
      </div>
    </div>
  );
}
