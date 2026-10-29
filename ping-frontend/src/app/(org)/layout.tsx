import { OrgShell } from "@/components/shell/BotShell";

export default function OrgLayout({ children }: { children: React.ReactNode }) {
  return <OrgShell>{children}</OrgShell>;
}
