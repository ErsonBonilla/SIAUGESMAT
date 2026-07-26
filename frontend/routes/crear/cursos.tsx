// routes/crear/cursos.tsx
import { requireAuth } from "../../utils/auth-guard.ts";
import UploadIsland from "../../islands/UploadIsland.tsx";

export const handler = requireAuth();

export default function UploadPage() {
  return <UploadIsland />;
}
