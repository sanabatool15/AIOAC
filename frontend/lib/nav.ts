import { CreditCard, FolderOpen, Gauge, type LucideIcon } from "lucide-react";

// Sidebar and user-menu links. Every entry is a page that exists; nothing for keys, plans or payment methods.
// The sidebar and the user menu show the same icon for the same page.
export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}
export const NAV_ITEMS: readonly NavItem[] = [
  { label: "Projects", href: "/projects", icon: FolderOpen },
  { label: "Usage", href: "/account/usage", icon: Gauge },
  { label: "Billing history", href: "/account/billing", icon: CreditCard },
];

// The sidebar is a fixed column from this width up (Tailwind `lg`), and a drawer below it.
export const DESKTOP_QUERY = "(min-width: 1024px)";

// A link is "current" on its own page, and on pages below it (/projects/abc is under Projects).
export function isCurrent(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

// The project id when the path is a chat page (/c/<id>), else null. Used to highlight the project in the sidebar.
export function activeProjectId(pathname: string): string | null {
  return pathname.startsWith("/c/") ? pathname.slice(3).split("/")[0] || null : null;
}

// The drawer is open only for the page it was opened on, so moving to another page closes it without an effect.
export function drawerIsOpen(openedAt: string | null, pathname: string): boolean {
  return openedAt !== null && openedAt === pathname;
}
