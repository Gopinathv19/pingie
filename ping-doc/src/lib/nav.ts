export interface NavItem {
  title: string;
  href: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
  internal?: boolean;
}

/** Guide pages map to content/<slug>.md; "/" is content/index.md. */
export const NAV: NavSection[] = [
  {
    title: "Getting started",
    items: [
      { title: "Introduction", href: "/" },
      { title: "Quickstart", href: "/getting-started/quickstart" },
      { title: "Core concepts", href: "/getting-started/concepts" },
    ],
  },
  {
    title: "Guides",
    items: [
      { title: "Knowledge sources", href: "/guides/knowledge" },
      { title: "Install the widget", href: "/guides/widget" },
      { title: "Widget JavaScript API", href: "/guides/javascript-api" },
      { title: "Conversations & leads", href: "/guides/conversations" },
      { title: "Live chat & handoff", href: "/guides/live-chat" },
      { title: "Teams & sharing", href: "/guides/sharing" },
      { title: "Plans & limits", href: "/guides/plans" },
    ],
  },
  {
    title: "How Pingie works",
    items: [
      { title: "Architecture", href: "/how-it-works/architecture" },
      { title: "Answer pipeline", href: "/how-it-works/answer-pipeline" },
      { title: "Security & privacy", href: "/how-it-works/security" },
    ],
  },
  {
    title: "API",
    items: [
      { title: "API overview", href: "/api/overview" },
      { title: "Build a custom chat UI", href: "/api/custom-widget" },
      { title: "API reference", href: "/api-reference" },
    ],
  },
  {
    title: "Internal",
    internal: true,
    items: [
      { title: "Local development", href: "/internal/local-setup" },
      { title: "Configuration", href: "/internal/configuration" },
      { title: "Admin console", href: "/internal/admin-console" },
      { title: "Deployment", href: "/internal/deployment" },
    ],
  },
];

export const FLAT_NAV: NavItem[] = NAV.flatMap((s) => s.items);

export function neighbours(href: string): { prev?: NavItem; next?: NavItem } {
  const i = FLAT_NAV.findIndex((n) => n.href === href);
  if (i < 0) return {};
  return { prev: FLAT_NAV[i - 1], next: FLAT_NAV[i + 1] };
}
