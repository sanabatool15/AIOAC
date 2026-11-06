import { ProjectDetail } from "@/components/shell/project-detail";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ProjectDetail key={projectId} projectId={projectId} />;
}
