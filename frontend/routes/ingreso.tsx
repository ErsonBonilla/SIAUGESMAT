// routes/ingreso.tsx
import { redirectIfAuth } from "../utils/auth-guard.ts";
import PaginaLoginIsland from "../islands/PaginaLoginIsland.tsx";

export const handler = redirectIfAuth();

export default function LoginPage() {
  return <PaginaLoginIsland />;
}
