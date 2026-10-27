import { PublicResultScreen } from "@/components/shell/public-result";

export default async function PublicResultPage({
  params,
}: {
  params: Promise<{ shareId: string }>;
}) {
  const { shareId } = await params;
  return <PublicResultScreen shareId={shareId} />;
}
