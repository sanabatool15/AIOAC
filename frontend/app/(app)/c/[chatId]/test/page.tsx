import { TestModelScreen } from "@/components/shell/test-model-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Test your model" };

export default async function TestModelPage({ params }: { params: Promise<{ chatId: string }> }) {
  const { chatId } = await params;
  return <TestModelScreen key={chatId} chatId={chatId} />;
}
