// routes/login.tsx
import { redirectIfAuth } from "../utils/auth-guard.ts";
import LoginPageIsland from "../islands/LoginPageIsland.tsx";

export const handler = redirectIfAuth();

export default function LoginPage() {
  return <LoginPageIsland />;
}