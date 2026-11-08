// Shared top bar for screens: left slot (breadcrumb / context) + optional actions.
// The page title is the screen's own single <h1>; put plain text or a <p> in `left`, not a heading.
export function TopBar({
  left,
  actions,
}: {
  left: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-2.5">{left}</div>
      <div className="flex items-center gap-2">{actions}</div>
    </header>
  );
}
