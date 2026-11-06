// Shared top bar for chat screens: left slot (title / breadcrumb) + optional actions.
export function TopBar({
  left,
  actions,
}: {
  left: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-6">
      <div className="flex items-center gap-2.5">{left}</div>
      <div className="flex items-center gap-2">{actions}</div>
    </header>
  );
}
