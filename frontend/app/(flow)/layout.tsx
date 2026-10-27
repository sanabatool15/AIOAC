import { FlowShell } from "@/components/billing/flow-shell";

// Full-screen flows (billing wizard): signed-in only, no sidebar.
export default function FlowLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <FlowShell>{children}</FlowShell>;
}
