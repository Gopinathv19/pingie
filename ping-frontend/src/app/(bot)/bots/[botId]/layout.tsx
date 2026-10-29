import { BotShell } from "@/components/shell/BotShell";

export default async function BotLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ botId: string }>;
}) {
  const { botId } = await params;
  return <BotShell botId={botId}>{children}</BotShell>;
}
