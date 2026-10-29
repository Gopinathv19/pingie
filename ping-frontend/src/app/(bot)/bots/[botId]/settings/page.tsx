import { SettingsView } from "@/components/settings/SettingsView";
import { EditGuard } from "@/components/ui/EditGuard";

export const metadata = { title: "Bot settings" };

export default function Page() {
  return (
    <EditGuard>
      <SettingsView />
    </EditGuard>
  );
}
