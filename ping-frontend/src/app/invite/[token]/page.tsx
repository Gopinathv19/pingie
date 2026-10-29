import { InviteView } from "./InviteView";

export const metadata = { title: "Invitation" };

export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <InviteView token={token} />;
}
