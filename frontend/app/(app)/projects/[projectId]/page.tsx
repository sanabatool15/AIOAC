import { ProjectScreen } from "@/components/shell/project-screen";

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ProjectScreen projectId={projectId} />;
}
