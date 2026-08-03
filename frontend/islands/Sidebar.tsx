import { useSignal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import type { JSX } from "preact";
import { logout } from "../services/api.ts";
import { removeToken } from "../utils/auth.ts";
import { getMyProfile } from "../services/api.ts";
import { ensureProfile, profileSignal } from "../utils/profile.ts";
import { mobileOpenSignal } from "../utils/layout.ts";
import {
  BookOpenIcon,
  CogIcon,
  FolderIcon,
  UserGroupIcon,
} from "../utils/icons.tsx";
import ThemeToggle from "./ThemeToggle.tsx";

const NAV_ITEMS = [
  {
    href: "/usuarios",
    icon: UserGroupIcon,
    label: "Usuarios",
    match: "/usuarios",
  },
  { href: "/cursos", icon: BookOpenIcon, label: "Cursos", match: "/cursos" },
  {
    href: "/categorias",
    icon: FolderIcon,
    label: "Categorías",
    match: "/categorias",
  },
  {
    href: "/operaciones",
    icon: CogIcon,
    label: "Operaciones",
    match: "/operaciones",
  },
];

const navBase =
  "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium no-underline text-inherit transition-all duration-150";
const navIdle =
  "bg-transparent hover:bg-brand-red-100 dark:bg-transparent dark:hover:bg-[var(--bg-tertiary)]";
const navActive =
  "font-semibold border border-brand-red-200 bg-brand-red-100 dark:bg-[var(--bg-tertiary)] dark:border-[var(--border-secondary)] text-brand-red-900 dark:text-[var(--text-primary)]";

export default function Sidebar() {
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
    logout();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  const closeMobile = () => {
    mobileOpenSignal.value = false;
  };

  const isActive = (match: string) => currentPath.value.startsWith(match);

  return (
    <>
      <div
        class={`fixed inset-0 bg-black/40 z-25 md:hidden ${
          mobileOpenSignal.value ? "" : "hidden"
        }`}
        onClick={closeMobile}
      />

      <aside
        class={`w-[220px] h-screen flex flex-col fixed left-0 top-0 z-30 border-r border-[var(--border-secondary)] bg-[var(--navbar-bg)] text-[var(--navbar-text)] ${
          mobileOpenSignal.value ? "translate-x-0" : "-translate-x-full"
        } md:translate-x-0`}
      >
        <a
          href="/dashboard"
          class="flex items-center gap-3 px-5 py-5 font-bold no-underline text-inherit border-b border-[var(--border-secondary)]"
        >
          <span class="gradient-text text-xl px-3 py-1 rounded-md bg-[var(--bg-tertiary)]">
            SIAUGESMAT
          </span>
        </a>

        <nav class="flex-1 flex flex-col gap-1 px-3 py-3">
          {NAV_ITEMS.map(({ href, icon: Icon, label, match }) => (
            <a
              key={href}
              href={href}
              onClick={closeMobile}
              class={`${navBase} ${isActive(match) ? navActive : navIdle}`}
            >
              <Icon class="w-5 h-5 shrink-0" />
              <span>{label}</span>
            </a>
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
                  onError={(e: JSX.TargetedEvent<HTMLImageElement, Event>) => {
                    (e.target as HTMLImageElement).style.display = "none";
                    const parent = (e.target as HTMLElement).parentElement;
                    if (parent) {
                      const fb = parent.querySelector(
                        ".avatar-fallback",
                      ) as HTMLElement;
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
            <span class="text-[0.8125rem] font-medium truncate">
              {displayName}
            </span>
            <ThemeToggle />
          </div>
          <button
            type="button"
            onClick={handleLogout}
            class="bg-transparent border-none text-inherit cursor-pointer text-xs text-left opacity-60 hover:opacity-100 p-0 font-inherit transition-opacity duration-150"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
    </>
  );
}
