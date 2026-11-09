import { ProjectsScreen } from "@/components/shell/projects-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return <ProjectsScreen />;
}
