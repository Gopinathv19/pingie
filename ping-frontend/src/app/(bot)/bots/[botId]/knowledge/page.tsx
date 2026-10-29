import { SourcesView } from "@/components/knowledge/SourcesView";
import { EditGuard } from "@/components/ui/EditGuard";

export const metadata = { title: "Sources" };

export default function Page() {
  return (
    <EditGuard>
      <SourcesView />
    </EditGuard>
  );
}
