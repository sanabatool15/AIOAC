import { PublicResultScreen } from "@/components/shell/public-result";

// Public, view-only result page. Outside the signed-in layout: no login, no cookies.
export default async function PublicResultPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <PublicResultScreen key={token} token={token} />;
}
