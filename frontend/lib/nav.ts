// Sidebar and user-menu links. Every entry is a page that exists; nothing for keys, plans or payment methods.
export interface NavItem {
  label: string;
  href: string;
}
export const NAV_ITEMS: readonly NavItem[] = [
  { label: "Projects", href: "/projects" },
  { label: "Usage", href: "/account/usage" },
  { label: "Billing history", href: "/account/billing" },
];

// A link is "current" on its own page, and on pages below it (/projects/abc is under Projects).
export function isCurrent(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
