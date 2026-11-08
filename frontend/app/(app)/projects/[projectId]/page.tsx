import { ProjectDetail } from "@/components/shell/project-detail";
import { tabFromQuery } from "@/lib/screens";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Project details" };

export default async function ProjectDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { projectId } = await params;
  const { tab } = await searchParams;
  return <ProjectDetail key={projectId} projectId={projectId} initialTab={tabFromQuery(tab)} />;
}
