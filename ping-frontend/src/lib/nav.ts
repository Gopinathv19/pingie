import type { IconName } from "@/components/Icon";
import type { Role } from "./types";

export interface NavItem {
  key: string;
  label: string;
  icon: IconName;
  /** Path segment under /bots/[botId]; empty string is the overview. */
  segment: string;
  /** Which of the bot's counts to show as a badge. */
  count?: "conversations" | "sources" | "domains";
  /** Hidden from people below this role. */
  ownerOnly?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const botNav: NavGroup[] = [
  {
    label: "Bot",
    items: [
      { key: "overview", label: "Overview", icon: "overview", segment: "" },
      { key: "conversations", label: "Conversations", icon: "conversations", segment: "conversations", count: "conversations" },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { key: "knowledge", label: "Sources", icon: "knowledge", segment: "knowledge", count: "sources" },
      { key: "test", label: "Test retrieval", icon: "test", segment: "test" },
    ],
  },
  {
    label: "Widget",
    items: [
      { key: "appearance", label: "Appearance", icon: "appearance", segment: "appearance" },
      { key: "install", label: "Install & embed", icon: "install", segment: "install" },
      { key: "domains", label: "Allowed domains", icon: "domains", segment: "domains", count: "domains" },
    ],
  },
  {
    label: "Manage",
    items: [
      { key: "settings", label: "Bot settings", icon: "settings", segment: "settings" },
      { key: "sharing", label: "Sharing", icon: "external", segment: "sharing", ownerOnly: true },
    ],
  },
];

export function visibleNav(role: Role): NavGroup[] {
  return botNav.map((g) => ({ ...g, items: g.items.filter((i) => !i.ownerOnly || role === "owner") }));
}

export function botHref(botId: string, segment = "") {
  return segment ? `/bots/${botId}/${segment}` : `/bots/${botId}`;
}
