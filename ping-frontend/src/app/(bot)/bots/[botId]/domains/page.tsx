import { DomainsView } from "@/components/widget/DomainsView";
import { EditGuard } from "@/components/ui/EditGuard";

export const metadata = { title: "Allowed domains" };

export default function Page() {
  return (
    <EditGuard>
      <DomainsView />
    </EditGuard>
  );
}
