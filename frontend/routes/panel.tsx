// routes/panel.tsx
import { requireAuth } from "../utils/auth-guard.ts";
import PanelIsland from "../islands/PanelIsland.tsx";

export const handler = requireAuth();

export default function DashboardPage() {
  return <PanelIsland />;
}
