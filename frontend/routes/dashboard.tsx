// routes/dashboard.tsx
import { requireAuth } from "../utils/auth-guard.ts";
import DashboardIsland from "../islands/DashboardIsland.tsx";

export const handler = requireAuth();

export default function DashboardPage() {
  return <DashboardIsland />;
}