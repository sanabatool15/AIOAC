import { ChatScreen } from "@/components/shell/chat-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Chat" };

export default async function ChatPage({
  params,
}: {
  params: Promise<{ chatId: string }>;
}) {
  const { chatId } = await params;
  return <ChatScreen key={chatId} chatId={chatId} />;
}
