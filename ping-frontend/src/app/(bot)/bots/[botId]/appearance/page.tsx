import { AppearanceView } from "@/components/widget/AppearanceView";
import { EditGuard } from "@/components/ui/EditGuard";

export const metadata = { title: "Appearance" };

export default function Page() {
  return (
    <EditGuard>
      <AppearanceView />
    </EditGuard>
  );
}
