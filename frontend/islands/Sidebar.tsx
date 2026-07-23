import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { removeToken, removeTokenCookie } from "../utils/auth.ts";
import { getMyProfile, type UserProfile } from "../services/api.ts";
import { profileSignal, ensureProfile } from "../utils/profile.ts";
import { UploadIcon, ListIcon, ChartBarIcon, TrashIcon, SearchIcon } from "../utils/icons.tsx";
import ThemeToggle from "./ThemeToggle.tsx";

const NAV_SECTIONS = [
  {
    label: "Carga académica",
    items: [
      { href: "/crear/cursos", icon: UploadIcon, label: "Crear Cursos" },
      { href: "/crear/usuarios", icon: UploadIcon, label: "Crear Usuarios" },
      { href: "/crear/categorias", icon: UploadIcon, label: "Crear Categorías" },
    ],
  },
  {
    label: "Mantenimiento",
    items: [
      { href: "/mantenimiento/cursos", icon: TrashIcon, label: "Eliminar Cursos" },
      { href: "/mantenimiento/usuarios", icon: TrashIcon, label: "Eliminar Usuarios" },
      { href: "/mantenimiento/categorias", icon: TrashIcon, label: "Eliminar Categorías" },
    ],
  },
  {
    label: "Operaciones",
    items: [
      { href: "/operaciones/ejecuciones", icon: ListIcon, label: "Ejecuciones" },
      { href: "/operaciones/historico", icon: ChartBarIcon, label: "Histórico" },
    ],
  },
  {
    label: "Consultas",
    items: [
      { href: "/consultas/cursos", icon: SearchIcon, label: "Cursos" },
      { href: "/consultas/usuarios", icon: SearchIcon, label: "Usuarios" },
      { href: "/consultas/categorias", icon: SearchIcon, label: "Categorías" },
    ],
  },
];

const navBase = "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium no-underline text-inherit transition-all duration-150";
const navIdle = "bg-transparent hover:bg-brand-red-100 dark:bg-transparent dark:hover:bg-[var(--bg-tertiary)]";
const navMove = "hover:translate-x-0.5 active:translate-x-0 active:scale-[0.98]";
const navActive = "font-semibold border border-brand-red-200 bg-brand-red-100 dark:bg-[var(--bg-tertiary)] dark:border-[var(--border-secondary)] text-brand-red-900 dark:text-[var(--text-primary)]";

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const currentPath = useSignal("");

  useEffect(() => {
    currentPath.value = globalThis.location?.pathname ?? "";
  }, []);

  useEffect(() => {
    ensureProfile(getMyProfile);
  }, []);

  const displayName = profileSignal.value?.firstname || "Usuario";
  const avatarUrl = profileSignal.value?.profileimageurl || null;
  const initial = displayName.charAt(0).toUpperCase();

  const handleLogout = () => {
    removeToken();
    removeTokenCookie();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  const closeMobile = () => { onClose(); };

  const isActive = (href: string) => currentPath.value === href;

  return (
    <>
      <div
        class={`fixed inset-0 bg-black/40 z-25 md:hidden ${mobileOpen ? "" : "hidden"}`}
        onClick={closeMobile}
      />

      <aside
        class={`w-[220px] h-screen flex flex-col fixed left-0 top-0 z-30 border-r border-[var(--border-secondary)] bg-[var(--navbar-bg)] text-[var(--navbar-text)] ${mobileOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
      >
        <a href="/dashboard" class="flex items-center gap-3 px-5 py-5 font-bold no-underline text-inherit">
          <span class="gradient-text text-xl px-3 py-1 rounded-md bg-[var(--bg-tertiary)]">SIAUGESMAT</span>
        </a>

        <nav class="flex-1 flex flex-col gap-0.5 px-2 py-2 overflow-y-auto">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label}>
              <p class="px-3 pt-3 pb-1 text-[0.6rem] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                {section.label}
              </p>
              {section.items.map(({ href, icon: Icon, label }) => (
                <a
                  key={href}
                  href={href}
                  onClick={closeMobile}
                  class={`${navBase} ${isActive(href) ? navActive : `${navIdle} ${navMove}`}`}
                >
                  <Icon class="w-4 h-4 shrink-0" />
                  <span>{label}</span>
                </a>
              ))}
            </div>
          ))}
        </nav>

        <div class="px-4 py-3 border-t border-[var(--border-secondary)] flex flex-col gap-2">
          <div class="flex items-center gap-2.5">
            {avatarUrl
              ? (
                <img
                  src={avatarUrl}
                  alt={`Foto de ${displayName}`}
                  class="w-8 h-8 rounded-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                    const parent = (e.target as HTMLElement).parentElement;
                    if (parent) {
                      const fb = parent.querySelector(".avatar-fallback") as HTMLElement;
                      if (fb) fb.style.display = "flex";
                    }
                  }}
                />
              )
              : null}
            <div
              class="avatar-fallback w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0"
              style={{
                display: avatarUrl ? "none" : "flex",
                backgroundColor: "var(--navbar-user-bg)",
                color: "var(--navbar-user-text)",
              }}
            >
              {initial}
            </div>
            <span class="text-[0.8125rem] font-medium truncate">{displayName}</span>
            <ThemeToggle />
          </div>
          <button onClick={handleLogout} class="bg-transparent border-none text-inherit cursor-pointer text-xs text-left opacity-60 hover:opacity-100 p-0 font-inherit transition-opacity duration-150">
            Cerrar sesión
          </button>
        </div>
      </aside>
    </>
  );
}
