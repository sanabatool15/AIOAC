import { ProjectDetail } from "@/components/shell/project-detail";
import { tabFromQuery } from "@/lib/screens";

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
