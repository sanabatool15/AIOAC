import { PayScreen } from "@/components/shell/pay-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Payment" };

export default async function PayPage({ params }: { params: Promise<{ chatId: string }> }) {
  const { chatId } = await params;
  return <PayScreen key={chatId} chatId={chatId} />;
}
