import { ChatScreen } from "@/components/shell/chat-screen";

export default async function ChatPage({
  params,
}: {
  params: Promise<{ chatId: string }>;
}) {
  const { chatId } = await params;
  return <ChatScreen key={chatId} chatId={chatId} />;
}
